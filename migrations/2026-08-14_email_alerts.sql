-- Email alerts: notify a business when genuinely new leads come in.
-- alert_sent follows the same non-resend tracking pattern as
-- auto_reply_sent / webhook_sent.

alter table businesses
  add column alert_email text;

alter table leads
  add column alert_sent boolean not null default false;
