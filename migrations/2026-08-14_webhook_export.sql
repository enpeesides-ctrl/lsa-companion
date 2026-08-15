-- Generic webhook export: each business can configure their own
-- receiving URL (e.g. a Zapier "Webhooks by Zapier" trigger), and we
-- POST new leads to it — no bespoke CRM integration needed for v1.

alter table businesses
  add column webhook_url text;

alter table leads
  add column webhook_sent boolean not null default false;
