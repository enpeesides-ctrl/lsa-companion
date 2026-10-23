-- Tightens the sync cadence from 30 minutes to 5, per explicit user
-- request after learning the original 30-minute figure was an
-- arbitrary early choice, not a real Google API constraint — the
-- actual operation-count math leaves enormous headroom at this scale
-- (144 ops/day at 30 min vs. 864 ops/day at 5 min, against a 2,880/day
-- cap on the current Explorer tier for a single business). Revisit
-- this math again before onboarding a second real business, since the
-- cost multiplies per business, not just per sync.
--
-- cron.schedule() with an existing job name replaces that job's
-- schedule in place (confirmed via Supabase's own quickstart pattern,
-- used throughout this project already) — these are updates, not new
-- jobs.

select cron.schedule(
  'lsa-sync-business',
  '*/5 * * * *',
  $$select dispatch_edge_function('sync-business');$$
);

-- Tightened to match sync, not left at the old 30-minute offsets —
-- the whole point of a faster sync is faster action on what it finds;
-- leaving these at their old cadence would mean fresh data sitting
-- unacted-on for up to 30 minutes regardless of how fast sync itself
-- runs. 2-minute offset after each sync window.
select cron.schedule(
  'lsa-auto-reply',
  '2-57/5 * * * *',
  $$select dispatch_edge_function('auto-reply');$$
);

select cron.schedule(
  'lsa-send-alerts',
  '2-57/5 * * * *',
  $$select dispatch_edge_function('send-alerts');$$
);

-- check-spend-anomaly, check-verification-expiry, webhook-export, and
-- send-followups are deliberately left on their original cadence —
-- none of them are response-time-sensitive the way a new lead's first
-- reply is, same reasoning as when they were first scheduled.

-- check-pipeline-health's staleness threshold was also tightened in
-- the same change (90 -> 15 minutes, still 3x the sync cadence) — its
-- own check frequency needs to be at least as tight as what it's
-- trying to catch, or a real outage could sit undetected for up to the
-- old 30-minute check interval before the first check even notices.
select cron.schedule(
  'lsa-check-pipeline-health',
  '*/10 * * * *',
  $$select dispatch_platform_function('check-pipeline-health');$$
);
