-- Schedules missed-call-handler: closes both the original
-- send_missed_call_alerts.py gap (never ported to the cloud) and the
-- new real-time customer-text idea, on the same cadence as
-- auto-reply/send-alerts since a missed call is just as time-sensitive
-- as an unanswered message — a hot lead who got no answer may well
-- call a competitor next.

select cron.schedule(
  'lsa-missed-call-handler',
  '2-57/5 * * * *',
  $$select dispatch_edge_function('missed-call-handler');$$
);
