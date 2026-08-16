// Port of webhook_export.py — POSTs new leads to a business-configured
// URL (e.g. a Zapier "Webhooks by Zapier" trigger), so a business can
// route leads into whatever CRM/tool they already use without us
// building a bespoke integration per platform.
//
// Only fires for leads not previously exported (webhook_sent = false).
// Nothing sends unless a business has actually set webhook_url on
// their row (defaults to null, meaning opted out).
//
// One invocation per business, same as the other ported functions.

import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function buildPayload(business: any, lead: any) {
  return {
    business_name: business.name,
    lead_id: lead.google_lead_id,
    lead_type: lead.lead_type,
    lead_status: lead.lead_status,
    lead_charged: lead.lead_charged,
    contact_phone: lead.contact_phone,
    created_at: lead.google_created_at,
  }
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
      .select('id, name, webhook_url, status')
      .eq('id', business_id)
      .single()
    if (!business) return jsonResponse({ error: 'business not found' }, 404)
    if (business.status !== 'active') return jsonResponse({ skipped: true, reason: 'not active' })
    if (!business.webhook_url) return jsonResponse({ skipped: true, reason: 'no webhook configured' })

    const { data: pending } = await supabase
      .from('leads')
      .select('id, google_lead_id, lead_type, lead_status, lead_charged, contact_phone, google_created_at')
      .eq('business_id', business_id)
      .eq('webhook_sent', false)

    if (!pending || !pending.length) return jsonResponse({ exported: 0, failed: 0 })

    let exported = 0
    const failures: { lead_id: number; error: string }[] = []

    for (const lead of pending) {
      try {
        const response = await fetch(business.webhook_url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(buildPayload(business, lead)),
        })
        if (!response.ok) throw new Error(`HTTP ${response.status}: ${await response.text()}`)
        await supabase.from('leads').update({ webhook_sent: true }).eq('id', lead.id)
        exported++
      } catch (err) {
        failures.push({ lead_id: lead.google_lead_id, error: String(err) })
      }
    }

    return jsonResponse({ exported, failed: failures.length, failures })
  } catch (err) {
    return jsonResponse({ error: String(err) }, 500)
  }
})
