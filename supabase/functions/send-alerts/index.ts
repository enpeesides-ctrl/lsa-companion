// Port of send_alerts.py — emails a business about genuinely new leads
// (alert_sent = false), same non-resend tracking pattern as everything
// else in this project.

import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'
import { sendEmail } from '../_shared/resend.ts'

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function buildHtml(businessName: string, leads: any[]) {
  const rows = leads
    .map(
      (l) =>
        `<tr><td>${l.lead_type}</td><td>${l.lead_status}</td><td>${l.contact_phone || '-'}</td><td>${l.google_created_at || '-'}</td></tr>`,
    )
    .join('')
  return `
    <h2>${leads.length} new lead(s) for ${businessName}</h2>
    <table border="1" cellpadding="6" style="border-collapse:collapse">
      <tr><th>Type</th><th>Status</th><th>Phone</th><th>Created</th></tr>
      ${rows}
    </table>
  `
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
      .select('id, name, alert_email')
      .eq('id', business_id)
      .single()
    if (!business) return jsonResponse({ error: 'business not found' }, 404)
    if (!business.alert_email) return jsonResponse({ skipped: true, reason: 'no alert email configured' })

    const { data: pending } = await supabase
      .from('leads')
      .select('id, lead_type, lead_status, contact_phone, google_created_at')
      .eq('business_id', business_id)
      .eq('alert_sent', false)

    if (!pending || !pending.length) return jsonResponse({ alertsSent: 0 })

    await sendEmail(business.alert_email, `${pending.length} new lead(s)`, buildHtml(business.name, pending))

    const leadIds = pending.map((l: any) => l.id)
    await supabase.from('leads').update({ alert_sent: true }).in('id', leadIds)

    return jsonResponse({ alertsSent: pending.length })
  } catch (err) {
    return jsonResponse({ error: String(err) }, 500)
  }
})
