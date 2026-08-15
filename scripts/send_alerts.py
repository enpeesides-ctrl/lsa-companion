"""
Real-time-ish alerts: emails a business when genuinely new leads have
come in since the last run. Only fires for leads not previously alerted
on (alert_sent = false) — meant to run right after sync_leads.py.

Uses Resend's plain HTTP API directly (no new SDK dependency needed).
Sends from Resend's shared testing domain (onboarding@resend.dev), which
works without domain verification as long as you're sending to your own
verified Resend account email — fine for now, would need a verified
sending domain before this could email businesses beyond Vertex.

IMPORTANT: only ever set alert_email via set_alert_email.py, never
directly via SQL — see that script's docstring for why.

Setup: add RESEND_API_KEY to scripts/.env (see .env.example).
Run: python3 send_alerts.py
"""

from pathlib import Path

import requests
from dotenv import dotenv_values
from supabase import create_client

HERE = Path(__file__).resolve().parent
ENV = dotenv_values(HERE / ".env")

RESEND_API_KEY = ENV["RESEND_API_KEY"]


def send_email(to_email, subject, html):
    response = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
        json={
            "from": "LSA Companion <onboarding@resend.dev>",
            "to": [to_email],
            "subject": subject,
            "html": html,
        },
    )
    response.raise_for_status()
    return response.json()


def build_email_html(business_name, leads):
    rows = "".join(
        f"<tr><td>{l['lead_type']}</td><td>{l['lead_status']}</td>"
        f"<td>{l['contact_phone'] or '-'}</td><td>{l['google_created_at'] or '-'}</td></tr>"
        for l in leads
    )
    return f"""
    <h2>{len(leads)} new lead(s) for {business_name}</h2>
    <table border="1" cellpadding="6" style="border-collapse:collapse">
      <tr><th>Type</th><th>Status</th><th>Phone</th><th>Created</th></tr>
      {rows}
    </table>
    """


def main():
    supabase = create_client(ENV["SUPABASE_URL"], ENV["SUPABASE_SERVICE_ROLE_KEY"])

    businesses = (
        supabase.table("businesses")
        .select("id, name, alert_email")
        .eq("status", "active")
        .execute()
    ).data

    for business in businesses:
        if not business["alert_email"]:
            print(f"{business['name']}: no alert email configured, skipping")
            continue

        pending = (
            supabase.table("leads")
            .select("id, lead_type, lead_status, contact_phone, google_created_at")
            .eq("business_id", business["id"])
            .eq("alert_sent", False)
            .execute()
        ).data

        print(f"{business['name']}: {len(pending)} new lead(s) to alert on")
        if not pending:
            continue

        html = build_email_html(business["name"], pending)
        try:
            send_email(business["alert_email"], f"{len(pending)} new lead(s)", html)
            lead_ids = [l["id"] for l in pending]
            supabase.table("leads").update({"alert_sent": True}).in_("id", lead_ids).execute()
            print(f"  emailed {business['alert_email']}")
        except requests.RequestException as ex:
            print(f"  FAILED to send: {ex}")


if __name__ == "__main__":
    main()
