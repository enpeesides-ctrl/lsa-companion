-- Enforces the retention commitment PRIVACY_POLICY.md makes in section
-- 6: end-customer lead data is deleted 90 days after a business
-- disconnects. That section was written before this existed and said
-- so explicitly — this closes the gap between stated policy and
-- actual behavior.
--
-- Scope is deliberately narrow: only `leads` (which cascades to
-- `conversation_messages` via its existing FK — confirmed, not
-- assumed) gets purged. That's the table holding real end-customer PII
-- (contact_phone, message text). daily_cost/verification_artifacts
-- describe the business's own account, not their customers, and aren't
-- covered by this specific policy commitment — not swept here to avoid
-- promising more (or less) than section 6 actually says.
--
-- The business row itself is NOT deleted — only its customers' lead
-- data. A disconnected business can still see its own account/history
-- if it ever reconnects; it just won't have its old customer data back.

create table data_retention_purges (
  id uuid primary key default gen_random_uuid(),
  business_id uuid not null,
  business_name text not null,
  leads_deleted integer not null,
  purged_at timestamptz not null default now()
);

-- No FK to businesses(id) on purpose — this is an audit trail and
-- should survive independently of whatever later happens to the
-- business row it describes.

create or replace function purge_disconnected_business_data()
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  biz record;
  deleted_count integer;
begin
  for biz in
    select id, name from businesses
    where status = 'disconnected'
      and disconnected_at is not null
      and disconnected_at < now() - interval '90 days'
  loop
    delete from leads where business_id = biz.id;
    get diagnostics deleted_count = row_count;

    if deleted_count > 0 then
      insert into data_retention_purges (business_id, business_name, leads_deleted)
      values (biz.id, biz.name, deleted_count);
    end if;
  end loop;
end;
$$;

revoke all on function purge_disconnected_business_data() from public, anon, authenticated;

-- Pure SQL operation, no external API call — runs directly via
-- pg_cron, no need for the dispatch_edge_function/net.http_post/Vault
-- pattern the other scheduled jobs use, since there's no HTTP round
-- trip involved. Daily is plenty of granularity for a 90-day window.
select cron.schedule(
  'lsa-purge-disconnected-data',
  '0 3 * * *',
  $$select purge_disconnected_business_data();$$
);
