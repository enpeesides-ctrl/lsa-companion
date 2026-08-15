-- Phase 1 data layer: businesses (tenants), credentials (Vault-backed),
-- leads, daily cost, and multi-user membership — with RLS designed in
-- from the start, not retrofitted.

-- ============================================================
-- businesses: one row per connected LSA account (tenant)
-- ============================================================
create table businesses (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  google_ads_customer_id text not null unique,
  status text not null default 'active' check (status in ('active', 'disconnected')),
  connected_at timestamptz not null default now(),
  disconnected_at timestamptz,
  created_at timestamptz not null default now()
);

alter table businesses enable row level security;

-- ============================================================
-- business_members: which auth.users can access which business.
-- Self-select policy included deliberately — a policy elsewhere that
-- checks membership via a subquery against this table will silently
-- return zero rows (not an error, just wrongly-empty access) unless
-- users can select their own row here. Same gotcha Vertex's build hit
-- with lsa_agents; applying the lesson from the start this time.
-- ============================================================
create table business_members (
  business_id uuid not null references businesses(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null default 'owner',
  created_at timestamptz not null default now(),
  primary key (business_id, user_id)
);

alter table business_members enable row level security;

create policy "users can see their own membership rows"
  on business_members for select
  using (user_id = auth.uid());

-- ============================================================
-- business_credentials: OAuth refresh token, Vault-backed.
-- Deliberately NO policies granting user-level access — RLS is enabled
-- with zero policies, meaning nobody using the anon/authenticated key
-- can read this table at all, only the service role (used by our
-- backend sync job) can, since service role bypasses RLS entirely.
-- The actual token lives in vault.secrets (encrypted), referenced here
-- by id — never stored in a plain column.
-- ============================================================
create table business_credentials (
  business_id uuid primary key references businesses(id) on delete cascade,
  refresh_token_secret_id uuid not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table business_credentials enable row level security;
-- No policies added on purpose — see comment above.

-- ============================================================
-- leads: synced from local_services_lead, plus our own added fields
-- ============================================================
create table leads (
  id uuid primary key default gen_random_uuid(),
  business_id uuid not null references businesses(id) on delete cascade,
  google_lead_id bigint not null,
  lead_type text not null,
  lead_status text not null,
  lead_charged boolean not null default false,
  credit_state text not null default 'UNSPECIFIED',
  lead_feedback_submitted boolean not null default false,
  contact_phone text,
  locale text,
  google_created_at timestamptz,
  synced_at timestamptz not null default now(),

  -- Fields Google doesn't track — this tool's own added value
  responded boolean not null default false,
  notes text,
  follow_up_sent boolean not null default false,

  created_at timestamptz not null default now(),
  unique (business_id, google_lead_id)
);

alter table leads enable row level security;

create policy "members can access their business's leads"
  on leads for all
  using (
    exists (
      select 1 from business_members
      where business_members.business_id = leads.business_id
      and business_members.user_id = auth.uid()
    )
  );

-- ============================================================
-- daily_cost: aggregate spend per business per day, from
-- customer + metrics.cost_micros — used for the cost-per-lead estimate
-- ============================================================
create table daily_cost (
  id uuid primary key default gen_random_uuid(),
  business_id uuid not null references businesses(id) on delete cascade,
  date date not null,
  cost_micros bigint not null,
  synced_at timestamptz not null default now(),
  unique (business_id, date)
);

alter table daily_cost enable row level security;

create policy "members can access their business's cost data"
  on daily_cost for all
  using (
    exists (
      select 1 from business_members
      where business_members.business_id = daily_cost.business_id
      and business_members.user_id = auth.uid()
    )
  );

-- ============================================================
-- businesses policy: added last, references business_members which
-- now exists and has its self-select policy in place
-- ============================================================
create policy "members can access their own business"
  on businesses for all
  using (
    exists (
      select 1 from business_members
      where business_members.business_id = businesses.id
      and business_members.user_id = auth.uid()
    )
  );
