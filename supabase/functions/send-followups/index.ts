// Port of send_followups.py — nudges a lead that got the initial
// auto-reply but still hasn't had a genuine human response, sent
// automatically on schedule rather than whenever someone remembers to
// run this by hand (same reasoning as auto-reply's port).

import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'
import { getAccessToken } from '../_shared/google-ads.ts'

const FOLLOWUP_DELAY_HOURS = 24
const FOLLOWUP_MAX_AGE_HOURS = 24 * 7 // don't nudge on leads older than a week

const FOLLOWUP_TEMPLATE =
  "Hi again — just checking in on your enquiry. Let us know if you'd still like a quote and we'll get straight back to you."

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

async function sendConversation(
  customerId: string,
  leadResourceName: string,
  text: string,
  accessToken: string,
): Promise<{ ok: boolean; detail: unknown }> {
  const response = await fetch(
    `https://googleads.googleapis.com/v25/customers/${customerId}/localServices:appendLeadConversation`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'developer-token': Deno.env.get('GOOGLE_DEVELOPER_TOKEN')!,
        'login-customer-id': Deno.env.get('MANAGER_CUSTOMER_ID')!,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        conversations: [{ localServicesLead: leadResourceName, text }],
      }),
    },
  )
  const detail = await response.json()
  // See auto-reply/index.ts for why this checks partialFailureError,
  // not just response.ok — Google returns HTTP 200 even on a genuine
  // per-item failure.
  const partialFailure = (detail as any)?.responses?.[0]?.partialFailureError
  return { ok: response.ok && !partialFailure, detail }
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
      .select('id, name, google_ads_customer_id, status')
      .eq('id', business_id)
      .single()
    if (!business) return jsonResponse({ error: 'business not found' }, 404)
    if (business.status !== 'active') return jsonResponse({ skipped: true, reason: 'not active' })

    const now = Date.now()
    const oldestEligible = new Date(now - FOLLOWUP_MAX_AGE_HOURS * 3600_000).toISOString()
    const newestEligible = new Date(now - FOLLOWUP_DELAY_HOURS * 3600_000).toISOString()

    const { data: candidates } = await supabase
      .from('leads')
      .select('id, google_lead_id')
      .eq('business_id', business_id)
      .eq('lead_type', 'MESSAGE')
      .eq('responded', false)
      .eq('auto_reply_sent', true)
      .eq('follow_up_sent', false)
      .gte('google_created_at', oldestEligible)
      .lte('google_created_at', newestEligible)

    if (!candidates || !candidates.length) return jsonResponse({ followedUpWith: 0 })

    const { data: refreshToken } = await supabase.rpc('get_refresh_token', { p_business_id: business_id })
    if (!refreshToken) return jsonResponse({ error: 'no refresh token configured' }, 500)

    const accessToken = await getAccessToken(
      refreshToken,
      Deno.env.get('GOOGLE_CLIENT_ID')!,
      Deno.env.get('GOOGLE_CLIENT_SECRET')!,
    )
    const customerId = business.google_ads_customer_id.replace(/-/g, '')

    let followedUpWith = 0
    const failures: { lead_id: number; error: unknown }[] = []

    for (const lead of candidates) {
      const leadResourceName = `customers/${customerId}/localServicesLeads/${lead.google_lead_id}`
      const result = await sendConversation(customerId, leadResourceName, FOLLOWUP_TEMPLATE, accessToken)
      if (result.ok) {
        await supabase.from('leads').update({ follow_up_sent: true }).eq('id', lead.id)
        followedUpWith++
      } else {
        failures.push({ lead_id: lead.google_lead_id, error: result.detail })
      }
    }

    return jsonResponse({ followedUpWith, failed: failures.length, failures })
  } catch (err) {
    return jsonResponse({ error: String(err) }, 500)
  }
})
