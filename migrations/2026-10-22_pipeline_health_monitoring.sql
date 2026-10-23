-- Real monitoring, added after a ~2-month silent outage went
-- undetected because cron.job_run_details reported "succeeded" the
-- entire time (see BUILD_PLAN.md's 2026-10-22 incident entry — that
-- table only proves the dispatcher SQL ran, never that the actual
-- call to Google succeeded). check-pipeline-health checks the one
-- signal that would have caught it: whether leads.synced_at is
-- actually advancing.

create table pipeline_health_status (
  id uuid primary key default gen_random_uuid(),
  is_healthy boolean not null,
  detail text,
  checked_at timestamptz not null default now()
);

-- check-pipeline-health isn't per-business (it checks across all
-- active businesses itself), so it doesn't use dispatch_edge_function's
-- per-business loop — this is the same Vault-credential pattern without
-- that loop.
create or replace function dispatch_platform_function(p_function_name text)
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
    raise exception 'cron_service_role_key not found in Vault';
  end if;

  perform net.http_post(
    url := v_base_url || p_function_name,
    headers := jsonb_build_object(
      'Authorization', 'Bearer ' || v_key,
      'apikey', v_key,
      'Content-Type', 'application/json'
    ),
    body := '{}'::jsonb,
    timeout_milliseconds := 15000
  );
end;
$$;

revoke all on function dispatch_platform_function(text) from public, anon, authenticated;

-- Every 30 minutes, offset 3 minutes after sync-business so it's
-- checking against freshly-attempted data, not stale data from before
-- that cycle's sync even ran.
select cron.schedule(
  'lsa-check-pipeline-health',
  '3,33 * * * *',
  $$select dispatch_platform_function('check-pipeline-health');$$
);
