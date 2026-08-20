-- Schedules the two functions deliberately left out of the original
-- cron_scheduling migration: auto-reply and send-followups. Flipping
-- their DRY_RUN flag off wasn't enough on its own to achieve the
-- original point of auto-reply (response speed) — without a real
-- trigger, nothing fires until someone remembers to run the script by
-- hand, which defeats the purpose. This closes that gap.
--
-- auto-reply is scheduled 2 minutes after each sync-business window
-- (:02/:32) — as close to sync as reasonably possible, since the
-- freshest a lead can be known to us is right after a sync completes.
-- This does mean up to ~32 minutes of latency worst-case (a lead that
-- arrives right as a sync window starts waits for the next one) — a
-- real characteristic of polling a 30-minute-cadence API, not
-- something this schedule can improve on further without sync-business
-- itself running more often.
--
-- send-followups doesn't carry the same urgency (it's a 24h+ nudge,
-- not a first-response), so it runs on a lighter, offset cadence.

select cron.schedule(
  'lsa-auto-reply',
  '2,32 * * * *',
  $$select dispatch_edge_function('auto-reply');$$
);

select cron.schedule(
  'lsa-send-followups',
  '20,50 * * * *',
  $$select dispatch_edge_function('send-followups');$$
);
