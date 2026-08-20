// Sends a real reply to a customer via Google's AppendLeadConversation
// API. This is the piece that closes the original gap — without this,
// the dashboard could only show messages, never send them, meaning you
// still had to go back to Google's own site to actually reply.
//
// Deliberately does NOT write the sent message into conversation_messages
// itself — that table's rows carry Google's own conversation id
// (google_conversation_id), which this function doesn't have yet (Google
// assigns it after the fact). Writing a fake placeholder id here risked
// a real data-integrity problem: a collision or duplicate once the next
// regular sync pulls the real record. Instead, the frontend shows the
// sent message immediately in memory (optimistic UI), and the real,
// permanent row appears on the next sync — same pattern as everything
// else in this project always deferring to the sync job as the single
// source of truth for Google-sourced data.
//
// Secrets needed (set via `supabase secrets set`, NOT in this file):
//   GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_DEVELOPER_TOKEN,
//   MANAGER_CUSTOMER_ID
// SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are auto-injected by Supabase.

import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, 'Content-Type': 'application/json' },
  })
}

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response('ok', { headers: corsHeaders })

  try {
    const { lead_id, message } = await req.json()
    if (!lead_id || !message || !message.trim()) {
      return jsonResponse({ error: 'lead_id and a non-empty message are required' }, 400)
    }

    const SUPABASE_URL = Deno.env.get('SUPABASE_URL')!
    const SERVICE_ROLE_KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
    const ANON_KEY = Deno.env.get('SUPABASE_ANON_KEY')!

    // Verify the caller is a real logged-in user (their JWT is forwarded
    // automatically by supabase-js's functions.invoke()).
    const authHeader = req.headers.get('Authorization') ?? ''
    const userClient = createClient(SUPABASE_URL, ANON_KEY, {
      global: { headers: { Authorization: authHeader } },
    })
    const { data: { user }, error: authError } = await userClient.auth.getUser()
    if (authError || !user) return jsonResponse({ error: 'unauthorized' }, 401)

    // Service-role client for the privileged lookups below (Vault access,
    // cross-checking membership) — never exposed to the browser.
    const adminClient = createClient(SUPABASE_URL, SERVICE_ROLE_KEY)

    const { data: lead } = await adminClient
      .from('leads')
      .select('id, business_id, google_lead_id, lead_type')
      .eq('id', lead_id)
      .single()
    if (!lead) return jsonResponse({ error: 'lead not found' }, 404)

    // Explicit authorization check — don't rely on the caller only being
    // able to construct valid lead_ids for their own business.
    const { data: membership } = await adminClient
      .from('business_members')
      .select('business_id')
      .eq('business_id', lead.business_id)
      .eq('user_id', user.id)
      .single()
    if (!membership) return jsonResponse({ error: 'not authorized for this lead' }, 403)

    const { data: business } = await adminClient
      .from('businesses')
      .select('google_ads_customer_id')
      .eq('id', lead.business_id)
      .single()
    if (!business) return jsonResponse({ error: 'business not found' }, 404)

    const { data: refreshToken } = await adminClient.rpc('get_refresh_token', {
      p_business_id: lead.business_id,
    })
    if (!refreshToken) return jsonResponse({ error: 'no refresh token configured for this business' }, 500)

    // Exchange the long-lived refresh token for a short-lived access token.
    const tokenResponse = await fetch('https://oauth2.googleapis.com/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        client_id: Deno.env.get('GOOGLE_CLIENT_ID')!,
        client_secret: Deno.env.get('GOOGLE_CLIENT_SECRET')!,
        refresh_token: refreshToken,
        grant_type: 'refresh_token',
      }),
    })
    const tokenData = await tokenResponse.json()
    if (!tokenData.access_token) {
      return jsonResponse({ error: 'failed to refresh Google access token', detail: tokenData }, 500)
    }

    const customerId = business.google_ads_customer_id.replace(/-/g, '')
    const leadResourceName = `customers/${customerId}/localServicesLeads/${lead.google_lead_id}`

    // [UNVERIFIED beyond this point]: this exact REST shape (URL, header
    // names, camelCase body fields) is inferred from the confirmed Python
    // client library structure (AppendLeadConversationRequest{customer_id,
    // conversations}, Conversation{local_services_lead, text}) — it has
    // NOT been tested against the live REST endpoint directly, unlike
    // everything else built this session via the Python library. Treat
    // the very first real send as the actual test of this shape, not a
    // guaranteed-working call — check the response carefully.
    const appendResponse = await fetch(
      `https://googleads.googleapis.com/v25/customers/${customerId}/localServices:appendLeadConversation`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${tokenData.access_token}`,
          'developer-token': Deno.env.get('GOOGLE_DEVELOPER_TOKEN')!,
          'login-customer-id': Deno.env.get('MANAGER_CUSTOMER_ID')!,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          conversations: [{ localServicesLead: leadResourceName, text: message }],
        }),
      }
    )

    const appendData = await appendResponse.json()
    // Google's REST API returns HTTP 200 even when the append itself
    // failed — the real result is per-item inside responses[].
    // partialFailureError. Confirmed directly against a deliberately
    // invalid lead ID during the auto-reply port: got a clean 200 with
    // an INTERNAL_ERROR buried in the body. Checking appendResponse.ok
    // alone would have silently marked a failed send as successful.
    const partialFailure = appendData?.responses?.[0]?.partialFailureError
    if (!appendResponse.ok || partialFailure) {
      return jsonResponse({ error: 'Google API call failed', detail: appendData }, 502)
    }

    // Mark responded — this is our own field, no Google-id collision risk.
    await adminClient.from('leads').update({ responded: true }).eq('id', lead.id)

    return jsonResponse({ success: true, googleResponse: appendData })
  } catch (err) {
    return jsonResponse({ error: String(err) }, 500)
  }
})
