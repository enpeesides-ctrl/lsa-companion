// Port of check_verification_expiry.py — syncs local_services_verification_artifact
// (insurance, license — the two types with real expiration dates) and
// emails at 60/30/7 days before expiry. Real stakes: if insurance or a
// license lapses, Google can suspend the LSA account entirely.
//
// Each (artifact, threshold) only ever alerts once — tracked in
// verification_expiry_alerts — so re-running this doesn't re-send the
// same warning every time.
//
// One invocation per business, same as sync-business. Syncs artifacts
// even if no alert_email is set (alert_email only gates the email step).

import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'
import { getAccessToken, gaqlSearch } from '../_shared/google-ads.ts'
import { sendEmail } from '../_shared/resend.ts'

const THRESHOLDS_DAYS = [60, 30, 7]

const QUERY = `
  SELECT
    local_services_verification_artifact.id,
    local_services_verification_artifact.artifact_type,
    local_services_verification_artifact.status,
    local_services_verification_artifact.insurance_verification_artifact.expiration_date_time,
    local_services_verification_artifact.insurance_verification_artifact.amount_micros,
    local_services_verification_artifact.license_verification_artifact.expiration_date_time
  FROM local_services_verification_artifact
`

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

async function syncArtifacts(supabase: any, opts: any, accessToken: string, businessId: string) {
  const rows = await gaqlSearch({ ...opts, accessToken, query: QUERY })
  const synced = []

  for (const row of rows) {
    const a = row.localServicesVerificationArtifact
    const artifactType = a.artifactType

    let expiration: string | null = null
    let coverage: number | null = null
    if (artifactType === 'INSURANCE') {
      expiration = a.insuranceVerificationArtifact?.expirationDateTime || null
      coverage = a.insuranceVerificationArtifact?.amountMicros
        ? parseInt(a.insuranceVerificationArtifact.amountMicros)
        : null
    } else if (artifactType === 'LICENSE') {
      expiration = a.licenseVerificationArtifact?.expirationDateTime || null
    }

    const record = {
      business_id: businessId,
      google_artifact_id: parseInt(a.id),
      artifact_type: artifactType,
      status: a.status,
      expiration_date: expiration ? expiration.split(' ')[0] : null,
      coverage_amount_micros: coverage,
    }
    synced.push(record)

    const { error } = await supabase
      .from('verification_artifacts')
      .upsert(record, { onConflict: 'business_id,google_artifact_id' })
    if (error) throw new Error(`verification_artifacts upsert failed: ${JSON.stringify(error)}`)
  }

  return synced
}

async function checkExpiryAlerts(supabase: any, business: any, artifacts: any[]) {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const alertsSent = []

  for (const artifact of artifacts) {
    if (!artifact.expiration_date) continue

    const expiry = new Date(artifact.expiration_date + 'T00:00:00')
    const daysRemaining = Math.round((expiry.getTime() - today.getTime()) / 86400000)

    for (const threshold of THRESHOLDS_DAYS) {
      if (daysRemaining > threshold) continue

      const { data: alreadySent } = await supabase
        .from('verification_expiry_alerts')
        .select('id')
        .eq('business_id', business.id)
        .eq('google_artifact_id', artifact.google_artifact_id)
        .eq('threshold_days', threshold)
      if (alreadySent && alreadySent.length) continue

      const typeLabel = artifact.artifact_type.charAt(0) + artifact.artifact_type.slice(1).toLowerCase()
      const html = `
        <h2>${typeLabel} expiring soon for ${business.name}</h2>
        <p>Expires: <strong>${artifact.expiration_date}</strong> (${daysRemaining} days from now)</p>
        <p><strong>If this lapses, Google can suspend your Local Services Ads account entirely.</strong>
        Renew it before the expiry date to avoid losing your leads.</p>
      `
      await sendEmail(business.alert_email, `${typeLabel} expires in ${daysRemaining} days`, html)
      await supabase.from('verification_expiry_alerts').insert({
        business_id: business.id,
        google_artifact_id: artifact.google_artifact_id,
        threshold_days: threshold,
      })
      alertsSent.push({ artifact_type: artifact.artifact_type, days_remaining: daysRemaining, threshold })
      break // only the tightest crossed-and-unsent threshold per run
    }
  }

  return alertsSent
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
      .select('id, name, google_ads_customer_id, alert_email, status')
      .eq('id', business_id)
      .single()
    if (!business) return jsonResponse({ error: 'business not found' }, 404)
    if (business.status !== 'active') return jsonResponse({ skipped: true, reason: 'not active' })

    const { data: refreshToken } = await supabase.rpc('get_refresh_token', { p_business_id: business_id })
    if (!refreshToken) return jsonResponse({ error: 'no refresh token configured' }, 500)

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

    const artifacts = await syncArtifacts(supabase, opts, accessToken, business_id)

    if (!business.alert_email) {
      return jsonResponse({ artifactsSynced: artifacts.length, skipped: true, reason: 'no alert email configured' })
    }

    const alertsSent = await checkExpiryAlerts(supabase, business, artifacts)

    return jsonResponse({ artifactsSynced: artifacts.length, alertsSent })
  } catch (err) {
    return jsonResponse({ error: String(err) }, 500)
  }
})
