-- Missed-call flagging: call_duration_millis synced from
-- local_services_lead_conversation (0 = confirmed unanswered, verified
-- against real Vertex data). Separate alert-tracking column from the
-- general new-lead alerts, so missed-call alerts can be reasoned about
-- independently.

alter table leads
  add column call_duration_millis bigint,
  add column missed_call_alert_sent boolean not null default false;
