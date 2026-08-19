-- Supabase Cron replacement for the local launchd job
-- (com.lsacompanion.sync, StartInterval=1800 i.e. every 30 minutes).
--
-- pg_cron jobs run inside Postgres and can't call an Edge Function
-- directly — they need pg_net to fire the HTTP request, and they need
-- a credential to authenticate that request the same way our own test
-- calls did (Authorization: Bearer <service_role key>). That key must
-- never be hardcoded in a migration file that ends up in git, so it's
-- read from Vault at call time instead — same pattern already used by
-- get_refresh_token() for Google refresh tokens.
--
-- ONE-TIME MANUAL STEP REQUIRED BEFORE THIS MIGRATION, run separately
-- in the Supabase SQL Editor (never commit this to git):
--
--   select vault.create_secret(
--     '<paste your service_role key here>',
--     'cron_service_role_key',
--     'Used by pg_cron jobs to authenticate calls to Edge Functions'
--   );
--
-- Get the key from Project Settings > API in the Supabase dashboard,
-- or from scripts/.env locally (SUPABASE_SERVICE_ROLE_KEY). Run that
-- line by itself first, confirm it succeeds, then run this file.

create extension if not exists pg_cron with schema extensions;
create extension if not exists pg_net with schema extensions;

-- Fires one independent HTTP request per active business, per Edge
-- Function — the same "one invocation per business" isolation the
-- functions themselves were built around, so one business's failure
-- can't block or slow down the others.
create or replace function dispatch_edge_function(p_function_name text)
returns void
language plpgsql
security definer
set search_path = public, vault, extensions
as $$
declare
  v_key text;
  v_base_url text := 'https://clzzqqwgluazefftvphw.supabase.co/functions/v1/';
begin
  select decrypted_secret into v_key
  from vault.decrypted_secrets
  where name = 'cron_service_role_key';

  if v_key is null then
    raise exception 'cron_service_role_key not found in Vault — run the one-time Vault setup step first (see comment at top of this file)';
  end if;

  perform net.http_post(
    url := v_base_url || p_function_name,
    headers := jsonb_build_object(
      'Authorization', 'Bearer ' || v_key,
      'apikey', v_key,
      'Content-Type', 'application/json'
    ),
    body := jsonb_build_object('business_id', b.id),
    timeout_milliseconds := 30000
  )
  from businesses b
  where b.status = 'active';
end;
$$;

revoke all on function dispatch_edge_function(text) from public, anon, authenticated;

-- sync-business runs first, every 30 minutes, matching the original
-- launchd cadence — leads/conversations/cost need to be fresh before
-- anything downstream reads them.
select cron.schedule(
  'lsa-sync-business',
  '*/30 * * * *',
  $$select dispatch_edge_function('sync-business');$$
);

-- The rest run 5-15 minutes after each sync window, giving sync-business
-- time to finish (it's a real Google Ads API round trip, not instant)
-- before send-alerts and check-spend-anomaly read data it just wrote.
-- check-verification-expiry doesn't depend on sync-business (it does
-- its own live Google Ads query), but keeping it on the same 30-minute
-- cadence matches what run_all_syncs.sh already did in production.
select cron.schedule(
  'lsa-send-alerts',
  '5,35 * * * *',
  $$select dispatch_edge_function('send-alerts');$$
);

select cron.schedule(
  'lsa-check-spend-anomaly',
  '5,35 * * * *',
  $$select dispatch_edge_function('check-spend-anomaly');$$
);

select cron.schedule(
  'lsa-check-verification-expiry',
  '10,40 * * * *',
  $$select dispatch_edge_function('check-verification-expiry');$$
);

select cron.schedule(
  'lsa-webhook-export',
  '15,45 * * * *',
  $$select dispatch_edge_function('webhook-export');$$
);
