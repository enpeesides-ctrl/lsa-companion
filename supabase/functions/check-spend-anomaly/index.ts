// Port of check_spend_anomaly.py — compares today's spend against a
// rolling 14-day baseline and alerts if it's more than 2x higher or
// less than half (including a drop to near-£0, which often means ads
// stopped running entirely, e.g. a payment failure).
//
// Cross-checks account_budget's spending limit before alerting — if
// the budget itself changed, that explains the spend change and we
// stay quiet rather than crying wolf over a change made on purpose.
// Best-effort: approved_spending_limit_micros can be null/unset, in
// which case this cross-check is simply skipped.
//
// One invocation per business, same as sync-business and send-alerts.
// Intended to run after sync-business has refreshed daily_cost.

import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'
import { getAccessToken, gaqlSearch } from '../_shared/google-ads.ts'
import { sendEmail } from '../_shared/resend.ts'

const HIGH_RATIO = 2.0
const LOW_RATIO = 0.5
const BASELINE_DAYS = 14

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

async function getCurrentBudgetLimit(opts: any, accessToken: string): Promise<number | null> {
  const query = 'SELECT account_budget.approved_spending_limit_micros FROM account_budget'
  const rows = await gaqlSearch({ ...opts, accessToken, query })
  if (!rows.length) return null
  const limit = rows[0].accountBudget?.approvedSpendingLimitMicros
  return limit ? parseInt(limit) : null
}

Deno.serve(async (req) => {
  try {
    const { business_id } = await req.json()
    if (!business_id) return jsonResponse({ error: 'business_id is required' }, 400)

    const supabase = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!,
    )

    const { data: business } = await supabase
      .from('businesses')
      .select('id, name, google_ads_customer_id, alert_email, last_known_budget_micros, status')
      .eq('id', business_id)
      .single()
    if (!business) return jsonResponse({ error: 'business not found' }, 404)
    if (business.status !== 'active') return jsonResponse({ skipped: true, reason: 'not active' })
    if (!business.alert_email) return jsonResponse({ skipped: true, reason: 'no alert email configured' })

    const { data: costRows } = await supabase
      .from('daily_cost')
      .select('date, cost_micros')
      .eq('business_id', business_id)
      .order('date', { ascending: false })
      .limit(BASELINE_DAYS + 1)

    if (!costRows || costRows.length < BASELINE_DAYS + 1) {
      return jsonResponse({ skipped: true, reason: `not enough history yet (${costRows?.length || 0} days)` })
    }

    const [todayRow, ...baselineRows] = costRows
    const todaySpend = todayRow.cost_micros
    const baseline = baselineRows.reduce((sum, r) => sum + r.cost_micros, 0) / baselineRows.length

    if (baseline === 0) return jsonResponse({ skipped: true, reason: 'baseline is £0, cannot compute a ratio' })

    const ratio = todaySpend / baseline
    const isAnomaly = ratio > HIGH_RATIO || ratio < LOW_RATIO
    if (!isAnomaly) return jsonResponse({ anomaly: false, ratio })

    // Cross-check: did the budget itself change? If so, this is expected.
    const { data: refreshToken } = await supabase.rpc('get_refresh_token', { p_business_id: business_id })
    let currentBudget: number | null = null
    if (refreshToken) {
      const accessToken = await getAccessToken(
        refreshToken,
        Deno.env.get('GOOGLE_CLIENT_ID')!,
        Deno.env.get('GOOGLE_CLIENT_SECRET')!,
      )
      const opts = {
        customerId: business.google_ads_customer_id.replace(/-/g, ''),
        developerToken: Deno.env.get('GOOGLE_DEVELOPER_TOKEN')!,
        loginCustomerId: Deno.env.get('MANAGER_CUSTOMER_ID')!,
      }
      currentBudget = await getCurrentBudgetLimit(opts, accessToken)
    }

    const previousBudget = business.last_known_budget_micros
    if (currentBudget !== null) {
      await supabase.from('businesses').update({ last_known_budget_micros: currentBudget }).eq('id', business_id)
      if (previousBudget !== null && currentBudget !== previousBudget) {
        return jsonResponse({ anomaly: true, alerted: false, reason: 'budget changed, expected' })
      }
    }

    // Don't re-alert for a date we've already flagged.
    const { data: alreadyAlerted } = await supabase
      .from('spend_anomaly_alerts')
      .select('id')
      .eq('business_id', business_id)
      .eq('date', todayRow.date)
    if (alreadyAlerted && alreadyAlerted.length) {
      return jsonResponse({ anomaly: true, alerted: false, reason: 'already alerted for this date' })
    }

    const direction = ratio > HIGH_RATIO ? 'unusually HIGH' : 'unusually LOW'
    const html = `
      <h2>Spend looks ${direction} for ${business.name}</h2>
      <p>Today (${todayRow.date}): <strong>£${(todaySpend / 1e6).toFixed(2)}</strong></p>
      <p>Normal (last ${BASELINE_DAYS}-day average): £${(baseline / 1e6).toFixed(2)}</p>
      <p>That's ${ratio.toFixed(1)}x the usual pace.</p>
      ${ratio < LOW_RATIO ? '<p><strong>A sudden drop to near-£0 often means ads have stopped running entirely (e.g. a payment issue) — worth checking your account status directly.</strong></p>' : ''}
    `
    await sendEmail(business.alert_email, `Spend ${direction.toLowerCase()} for ${business.name}`, html)
    await supabase.from('spend_anomaly_alerts').insert({
      business_id,
      date: todayRow.date,
      spend_micros: todaySpend,
      baseline_micros: Math.round(baseline),
    })

    return jsonResponse({ anomaly: true, alerted: true, ratio, direction })
  } catch (err) {
    return jsonResponse({ error: String(err) }, 500)
  }
})
