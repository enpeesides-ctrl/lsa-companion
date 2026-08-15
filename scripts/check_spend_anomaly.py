"""
Spend-pace anomaly alerts: compares today's spend against a rolling
14-day baseline, and emails if it's more than 2x higher or less than
half (including a drop to £0, which often means ads stopped running
entirely — e.g. a payment failure — not just a quiet day).

Before flagging, cross-checks account_budget's spending limit against
what we saw last time — if the budget itself changed, that explains a
spend change and we stay quiet, rather than crying wolf over a change
you made on purpose. Best-effort: approved_spending_limit_micros can be
null/unset (confirmed true for Vertex when we checked earlier), in which
case this cross-check is simply skipped, not guaranteed.

Reuses the same Resend email pattern as send_alerts.py.

Setup: same .env as sync_leads.py / send_alerts.py.
Run: python3 check_spend_anomaly.py (intended to run after sync_leads.py)
"""

import json
from pathlib import Path

import requests
from dotenv import dotenv_values
from google.ads.googleads.client import GoogleAdsClient
from supabase import create_client

HERE = Path(__file__).resolve().parent
CLIENT_SECRETS_FILE = HERE / "client_secret.json"
ENV = dotenv_values(HERE / ".env")

DEVELOPER_TOKEN = ENV["DEVELOPER_TOKEN"]
MANAGER_CUSTOMER_ID = ENV["MANAGER_CUSTOMER_ID"].replace("-", "")
RESEND_API_KEY = ENV["RESEND_API_KEY"]

HIGH_RATIO = 2.0
LOW_RATIO = 0.5
BASELINE_DAYS = 14


def send_email(to_email, subject, html):
    response = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
        json={"from": "LSA Companion <onboarding@resend.dev>", "to": [to_email], "subject": subject, "html": html},
    )
    response.raise_for_status()
    return response.json()


def get_google_ads_client(refresh_token):
    with open(CLIENT_SECRETS_FILE) as f:
        client_info = json.load(f)["installed"]
    config = {
        "developer_token": DEVELOPER_TOKEN,
        "client_id": client_info["client_id"],
        "client_secret": client_info["client_secret"],
        "refresh_token": refresh_token,
        "login_customer_id": MANAGER_CUSTOMER_ID,
        "use_proto_plus": True,
    }
    return GoogleAdsClient.load_from_dict(config)


def get_current_budget_limit(ga_service, customer_id):
    query = "SELECT account_budget.approved_spending_limit_micros FROM account_budget"
    rows = list(ga_service.search(customer_id=customer_id, query=query))
    if not rows:
        return None
    limit = rows[0].account_budget.approved_spending_limit_micros
    return limit or None  # 0/unset both treated as "not configured"


def main():
    supabase = create_client(ENV["SUPABASE_URL"], ENV["SUPABASE_SERVICE_ROLE_KEY"])

    businesses = (
        supabase.table("businesses")
        .select("id, name, google_ads_customer_id, alert_email, last_known_budget_micros")
        .eq("status", "active")
        .execute()
    ).data

    for business in businesses:
        if not business["alert_email"]:
            print(f"{business['name']}: no alert email configured, skipping")
            continue

        business_id = business["id"]
        customer_id = business["google_ads_customer_id"].replace("-", "")

        cost_rows = (
            supabase.table("daily_cost")
            .select("date, cost_micros")
            .eq("business_id", business_id)
            .order("date", desc=True)
            .limit(BASELINE_DAYS + 1)
            .execute()
        ).data

        if len(cost_rows) < BASELINE_DAYS + 1:
            print(f"{business['name']}: not enough history yet ({len(cost_rows)} days), skipping")
            continue

        today_row, baseline_rows = cost_rows[0], cost_rows[1:]
        today_spend = today_row["cost_micros"]
        baseline = sum(r["cost_micros"] for r in baseline_rows) / len(baseline_rows)

        if baseline == 0:
            print(f"{business['name']}: baseline is £0, can't compute a ratio, skipping")
            continue

        ratio = today_spend / baseline
        is_anomaly = ratio > HIGH_RATIO or ratio < LOW_RATIO
        print(f"{business['name']}: today=£{today_spend/1e6:.2f} baseline=£{baseline/1e6:.2f} ratio={ratio:.2f} anomaly={is_anomaly}")

        if not is_anomaly:
            continue

        # Cross-check: did the budget itself change? If so, this is expected.
        token_result = supabase.rpc("get_refresh_token", {"p_business_id": business_id}).execute()
        refresh_token = token_result.data
        current_budget = None
        if refresh_token:
            ga_client = get_google_ads_client(refresh_token)
            ga_service = ga_client.get_service("GoogleAdsService")
            current_budget = get_current_budget_limit(ga_service, customer_id)

        previous_budget = business["last_known_budget_micros"]
        if current_budget is not None:
            supabase.table("businesses").update({"last_known_budget_micros": current_budget}).eq("id", business_id).execute()
            if previous_budget is not None and current_budget != previous_budget:
                print(f"  budget changed ({previous_budget} -> {current_budget}) — expected, not alerting")
                continue

        # Don't re-alert for a date we've already flagged.
        already_alerted = (
            supabase.table("spend_anomaly_alerts")
            .select("id")
            .eq("business_id", business_id)
            .eq("date", today_row["date"])
            .execute()
        ).data
        if already_alerted:
            print("  already alerted for this date, skipping")
            continue

        direction = "unusually HIGH" if ratio > HIGH_RATIO else "unusually LOW"
        html = f"""
        <h2>Spend looks {direction} for {business['name']}</h2>
        <p>Today ({today_row['date']}): <strong>£{today_spend/1e6:.2f}</strong></p>
        <p>Normal (last {BASELINE_DAYS}-day average): £{baseline/1e6:.2f}</p>
        <p>That's {ratio:.1f}x the usual pace.</p>
        {"<p><strong>A sudden drop to near-£0 often means ads have stopped running entirely (e.g. a payment issue) — worth checking your account status directly.</strong></p>" if ratio < LOW_RATIO else ""}
        """
        send_email(business["alert_email"], f"Spend {direction.lower()} for {business['name']}", html)
        supabase.table("spend_anomaly_alerts").insert({
            "business_id": business_id,
            "date": today_row["date"],
            "spend_micros": today_spend,
            "baseline_micros": int(baseline),
        }).execute()
        print(f"  ALERT SENT to {business['alert_email']}")


if __name__ == "__main__":
    main()
