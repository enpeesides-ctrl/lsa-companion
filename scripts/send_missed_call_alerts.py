"""
Missed-call alerts: emails a business about phone leads where
call_duration_millis = 0 (confirmed unanswered — see BUILD_PLAN.md for
the verification history behind this signal, including two earlier
wrong signals before finding the right one).

Separate from send_alerts.py (new-lead alerts) — tracked via its own
missed_call_alert_sent column, since a lead could be alerted as "new"
and, separately, flagged as "missed" once call data syncs in.

Setup: same .env as send_alerts.py (needs RESEND_API_KEY).
Run: python3 send_missed_call_alerts.py (intended to run right after
sync_leads.py, once call_duration_millis has synced).
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
        f"<tr><td>{l['contact_phone'] or '-'}</td><td>{l['google_created_at'] or '-'}</td></tr>"
        for l in leads
    )
    return f"""
    <h2>{len(leads)} missed call(s) for {business_name}</h2>
    <p>These calls did not connect (confirmed via call duration, not a proxy) —
    worth a callback.</p>
    <table border="1" cellpadding="6" style="border-collapse:collapse">
      <tr><th>Phone</th><th>Created</th></tr>
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

        missed = (
            supabase.table("leads")
            .select("id, contact_phone, google_created_at")
            .eq("business_id", business["id"])
            .eq("lead_type", "PHONE_CALL")
            .eq("call_duration_millis", 0)
            .eq("missed_call_alert_sent", False)
            .execute()
        ).data

        print(f"{business['name']}: {len(missed)} missed call(s) to alert on")
        if not missed:
            continue

        html = build_email_html(business["name"], missed)
        try:
            send_email(business["alert_email"], f"{len(missed)} missed call(s)", html)
            lead_ids = [l["id"] for l in missed]
            supabase.table("leads").update({"missed_call_alert_sent": True}).in_("id", lead_ids).execute()
            print(f"  emailed {business['alert_email']}")
        except requests.RequestException as ex:
            print(f"  FAILED to send: {ex}")


if __name__ == "__main__":
    main()
