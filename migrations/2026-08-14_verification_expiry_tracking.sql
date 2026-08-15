-- Compliance/verification expiry alerts: insurance and license lapsing
-- can get an LSA account suspended entirely — confirmed real data for
-- Vertex earlier (insurance expires 2027-03-13, £5M coverage). Alerts
-- fire at 60/30/7 days out, tracked per (artifact, threshold) so each
-- checkpoint only ever sends once, not re-sent every sync.

create table verification_artifacts (
  id uuid primary key default gen_random_uuid(),
  business_id uuid not null references businesses(id) on delete cascade,
  google_artifact_id bigint not null,
  artifact_type text not null,
  status text not null,
  expiration_date date,
  coverage_amount_micros bigint,
  synced_at timestamptz not null default now(),
  unique (business_id, google_artifact_id)
);

alter table verification_artifacts enable row level security;

create policy "members can access their business's verification artifacts"
  on verification_artifacts for all
  using (
    exists (
      select 1 from business_members
      where business_members.business_id = verification_artifacts.business_id
      and business_members.user_id = auth.uid()
    )
  );

create table verification_expiry_alerts (
  id uuid primary key default gen_random_uuid(),
  business_id uuid not null references businesses(id) on delete cascade,
  google_artifact_id bigint not null,
  threshold_days int not null,
  sent_at timestamptz not null default now(),
  unique (business_id, google_artifact_id, threshold_days)
);

alter table verification_expiry_alerts enable row level security;

create policy "members can access their business's verification alerts"
  on verification_expiry_alerts for all
  using (
    exists (
      select 1 from business_members
      where business_members.business_id = verification_expiry_alerts.business_id
      and business_members.user_id = auth.uid()
    )
  );
