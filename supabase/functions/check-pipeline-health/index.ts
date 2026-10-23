// Monitors the one signal that would have caught the real ~2-month
// silent outage (2026-08 to 2026-10): sync-business silently failing
// on every run while cron.job_run_details kept reporting "succeeded"
// the entire time, because that table only proves the dispatcher SQL
// ran, never that the actual HTTP call to Google succeeded.
//
// Deliberately scoped to sync-business's health specifically, not all
// seven scheduled functions individually — every other function
// depends on the exact same Google refresh token, so this single
// check would have caught the actual incident. A function-specific
// failure unrelated to the shared token (e.g. a bad webhook_url) is a
// real, accepted gap in this first version, not an oversight.
//
// Relies on sync-business explicitly setting leads.synced_at on every
// upsert (fixed in the same change that added this function) — without
// that fix, synced_at could stay stale on an existing lead even during
// a genuinely healthy sync with nothing new to pull in, making it an
// unreliable signal.

import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'
import { sendEmail } from '../_shared/resend.ts'

const STALE_AFTER_MINUTES = 15 // 3x the 5-minute sync cadence

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

Deno.serve(async (_req) => {
  try {
    const supabase = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!,
    )
    const operatorEmail = Deno.env.get('OPERATOR_ALERT_EMAIL')!

    const { data: activeBusinesses } = await supabase
      .from('businesses')
      .select('id')
      .eq('status', 'active')

    if (!activeBusinesses || !activeBusinesses.length) {
      return jsonResponse({ skipped: true, reason: 'no active businesses to monitor' })
    }

    const { data: mostRecent } = await supabase
      .from('leads')
      .select('synced_at')
      .in('business_id', activeBusinesses.map((b) => b.id))
      .order('synced_at', { ascending: false })
      .limit(1)
      .single()

    const lastSyncedAt = mostRecent?.synced_at ? new Date(mostRecent.synced_at) : null
    const minutesSinceSync = lastSyncedAt ? (Date.now() - lastSyncedAt.getTime()) / 60000 : Infinity
    const isHealthy = minutesSinceSync <= STALE_AFTER_MINUTES

    const { data: previousCheck } = await supabase
      .from('pipeline_health_status')
      .select('is_healthy')
      .order('checked_at', { ascending: false })
      .limit(1)
      .maybeSingle()

    const wasHealthyBefore = previousCheck ? previousCheck.is_healthy : true // assume healthy if no prior record, so the very first check doesn't alert on nothing

    await supabase.from('pipeline_health_status').insert({
      is_healthy: isHealthy,
      detail: lastSyncedAt
        ? `last synced_at was ${minutesSinceSync.toFixed(0)} minutes ago`
        : 'no synced leads found at all',
    })

    if (!isHealthy && wasHealthyBefore) {
      await sendEmail(
        operatorEmail,
        'LSA Companion: sync pipeline looks stuck',
        `<h2>Sync pipeline may be down</h2>
         <p>No lead has synced in the last ${minutesSinceSync.toFixed(0)} minutes (expected within ${STALE_AFTER_MINUTES}).</p>
         <p>This usually means the Google refresh token has expired or another auth failure is happening silently — check <code>net._http_response</code> for the real error, same as the 2026-10 incident.</p>`,
      )
      return jsonResponse({ healthy: false, alerted: true, minutesSinceSync })
    }

    if (isHealthy && !wasHealthyBefore) {
      await sendEmail(
        operatorEmail,
        'LSA Companion: sync pipeline recovered',
        `<h2>Sync pipeline is healthy again</h2>
         <p>Most recent lead synced ${minutesSinceSync.toFixed(0)} minutes ago.</p>`,
      )
      return jsonResponse({ healthy: true, recoveredAlertSent: true, minutesSinceSync })
    }

    return jsonResponse({ healthy: isHealthy, minutesSinceSync })
  } catch (err) {
    return jsonResponse({ error: String(err) }, 500)
  }
})
