"""
Compliance/verification expiry alerts: syncs local_services_verification_artifact
(insurance, license — the two types with real expiration dates; business
registration and background check don't carry one, confirmed via the
field sweep) and emails at 60/30/7 days before expiry.

Real stakes: if insurance or a license lapses, Google can suspend the
LSA account entirely — confirmed real data for Vertex when we found this:
insurance expires 2027-03-13, £5,000,000 coverage.

Each (artifact, threshold) only ever alerts once — tracked in
verification_expiry_alerts — so re-running this doesn't re-send the same
warning every time.

Setup: same .env as sync_leads.py / send_alerts.py.
Run: python3 check_verification_expiry.py
"""

import json
from datetime import date
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

THRESHOLDS_DAYS = [60, 30, 7]

QUERY = """
    SELECT
        local_services_verification_artifact.id,
        local_services_verification_artifact.artifact_type,
        local_services_verification_artifact.status,
        local_services_verification_artifact.insurance_verification_artifact.expiration_date_time,
        local_services_verification_artifact.insurance_verification_artifact.amount_micros,
        local_services_verification_artifact.license_verification_artifact.expiration_date_time
    FROM local_services_verification_artifact
"""


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


def sync_artifacts(supabase, ga_service, business_id, customer_id):
    rows = list(ga_service.search(customer_id=customer_id, query=QUERY))
    synced = []
    for row in rows:
        a = row.local_services_verification_artifact
        artifact_type = a.artifact_type.name

        expiration = None
        coverage = None
        if artifact_type == "INSURANCE":
            expiration = a.insurance_verification_artifact.expiration_date_time or None
            coverage = a.insurance_verification_artifact.amount_micros or None
        elif artifact_type == "LICENSE":
            expiration = a.license_verification_artifact.expiration_date_time or None

        record = {
            "business_id": business_id,
            "google_artifact_id": a.id,
            "artifact_type": artifact_type,
            "status": a.status.name,
            "expiration_date": expiration.split(" ")[0] if expiration else None,
            "coverage_amount_micros": coverage,
        }
        synced.append(record)
        supabase.table("verification_artifacts").upsert(record, on_conflict="business_id,google_artifact_id").execute()
    return synced


def check_expiry_alerts(supabase, business, artifacts):
    today = date.today()
    for artifact in artifacts:
        if not artifact["expiration_date"]:
            continue

        expiry = date.fromisoformat(artifact["expiration_date"])
        days_remaining = (expiry - today).days

        for threshold in THRESHOLDS_DAYS:
            if days_remaining > threshold:
                continue

            already_sent = (
                supabase.table("verification_expiry_alerts")
                .select("id")
                .eq("business_id", business["id"])
                .eq("google_artifact_id", artifact["google_artifact_id"])
                .eq("threshold_days", threshold)
                .execute()
            ).data
            if already_sent:
                continue

            html = f"""
            <h2>{artifact['artifact_type'].title()} expiring soon for {business['name']}</h2>
            <p>Expires: <strong>{artifact['expiration_date']}</strong> ({days_remaining} days from now)</p>
            <p><strong>If this lapses, Google can suspend your Local Services Ads account entirely.</strong>
            Renew it before the expiry date to avoid losing your leads.</p>
            """
            send_email(business["alert_email"], f"{artifact['artifact_type'].title()} expires in {days_remaining} days", html)
            supabase.table("verification_expiry_alerts").insert({
                "business_id": business["id"],
                "google_artifact_id": artifact["google_artifact_id"],
                "threshold_days": threshold,
            }).execute()
            print(f"  ALERT SENT: {artifact['artifact_type']} expires in {days_remaining} days (threshold {threshold})")
            break  # only the tightest crossed-and-unsent threshold per run


def main():
    supabase = create_client(ENV["SUPABASE_URL"], ENV["SUPABASE_SERVICE_ROLE_KEY"])

    businesses = (
        supabase.table("businesses")
        .select("id, name, google_ads_customer_id, alert_email")
        .eq("status", "active")
        .execute()
    ).data

    for business in businesses:
        customer_id = business["google_ads_customer_id"].replace("-", "")
        print(f"{business['name']}:")

        token_result = supabase.rpc("get_refresh_token", {"p_business_id": business["id"]}).execute()
        refresh_token = token_result.data
        if not refresh_token:
            print("  no refresh token found, skipping")
            continue

        ga_client = get_google_ads_client(refresh_token)
        ga_service = ga_client.get_service("GoogleAdsService")

        artifacts = sync_artifacts(supabase, ga_service, business["id"], customer_id)
        print(f"  synced {len(artifacts)} verification artifact(s)")

        if not business["alert_email"]:
            print("  no alert email configured, skipping expiry check")
            continue

        check_expiry_alerts(supabase, business, artifacts)


if __name__ == "__main__":
    main()
