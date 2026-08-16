// Shared Resend email helper — same pattern as the Python scripts'
// send_email(), reused by send-alerts, check-spend-anomaly, and
// check-verification-expiry.

export async function sendEmail(toEmail: string, subject: string, html: string) {
  const response = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${Deno.env.get('RESEND_API_KEY')}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      from: 'LSA Companion <onboarding@resend.dev>',
      to: [toEmail],
      subject,
      html,
    }),
  })
  if (!response.ok) {
    throw new Error(`Resend send failed: ${await response.text()}`)
  }
  return response.json()
}
