-- Spend-pace anomaly alerts: track what we last alerted on (avoid
-- re-alerting the same day) and the last known budget limit (to tell
-- an intentional budget change apart from a real anomaly).
--
-- Note: approved_spending_limit_micros may be null/unset (confirmed
-- true for Vertex's account when we checked account_budget earlier) —
-- the budget cross-check is best-effort, not guaranteed to catch every
-- intentional change if this field isn't populated.

alter table businesses
  add column last_known_budget_micros bigint;

create table spend_anomaly_alerts (
  id uuid primary key default gen_random_uuid(),
  business_id uuid not null references businesses(id) on delete cascade,
  date date not null,
  spend_micros bigint not null,
  baseline_micros bigint not null,
  created_at timestamptz not null default now(),
  unique (business_id, date)
);

alter table spend_anomaly_alerts enable row level security;

create policy "members can access their business's anomaly alerts"
  on spend_anomaly_alerts for all
  using (
    exists (
      select 1 from business_members
      where business_members.business_id = spend_anomaly_alerts.business_id
      and business_members.user_id = auth.uid()
    )
  );
