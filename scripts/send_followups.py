"""
Follow-up sequences: nudges a customer who still hasn't heard a real
response, some time after the initial auto-acknowledgment.

Uses the `follow_up_sent` column — present in the schema since Phase 1,
never actually wired up until now.

SAFETY: same DRY_RUN pattern as auto_reply.py. Leave True until you've
reviewed the dry-run output and deliberately decide to let real
follow-ups send.

Targets leads that:
  - already got the initial auto-reply (auto_reply_sent = true)
  - still haven't been genuinely responded to (responded = false)
  - haven't already had a follow-up sent (follow_up_sent = false)
  - are older than FOLLOWUP_DELAY_HOURS (enough time to actually
    warrant a nudge) but younger than FOLLOWUP_MAX_AGE_HOURS (an old,
    likely-dead lead getting a "just checking in" message this late
    would look as broken as the original recency bug this project
    already hit once with auto_reply.py — same lesson, applied here
    proactively instead of rediscovering it).

Setup: same .env as auto_reply.py.
Run: python3 send_followups.py
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import dotenv_values
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from supabase import create_client

HERE = Path(__file__).resolve().parent
CLIENT_SECRETS_FILE = HERE / "client_secret.json"
ENV = dotenv_values(HERE / ".env")

DEVELOPER_TOKEN = ENV["DEVELOPER_TOKEN"]
MANAGER_CUSTOMER_ID = ENV["MANAGER_CUSTOMER_ID"].replace("-", "")

# ============================================================
# SAFETY: leave this True until you've reviewed dry-run output
# and deliberately decide to let real follow-ups send.
# ============================================================
DRY_RUN = False

FOLLOWUP_DELAY_HOURS = 24
FOLLOWUP_MAX_AGE_HOURS = 24 * 7  # don't nudge on leads older than a week

FOLLOWUP_TEMPLATE = (
    "Hi again — just checking in on your enquiry. Let us know if you'd "
    "still like a quote and we'll get straight back to you."
)


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


def send_followup(ga_client, customer_id, lead_resource_name, text):
    if DRY_RUN:
        print(f"    [DRY RUN] would send follow-up to {lead_resource_name}:")
        print(f"    [DRY RUN] \"{text}\"")
        return True

    lead_service = ga_client.get_service("LocalServicesLeadService")
    conversation = ga_client.get_type("Conversation")
    conversation.local_services_lead = lead_resource_name
    conversation.text = text

    request = ga_client.get_type("AppendLeadConversationRequest")
    request.customer_id = customer_id
    request.conversations = [conversation]

    try:
        lead_service.append_lead_conversation(request=request)
        print(f"    SENT follow-up to {lead_resource_name}")
        return True
    except GoogleAdsException as ex:
        print(f"    ERROR sending to {lead_resource_name}: {ex.failure.errors[0].message}")
        return False


def main():
    print(f"Running in {'DRY RUN' if DRY_RUN else 'LIVE SEND'} mode.\n")

    supabase = create_client(ENV["SUPABASE_URL"], ENV["SUPABASE_SERVICE_ROLE_KEY"])

    businesses = (
        supabase.table("businesses")
        .select("id, name, google_ads_customer_id")
        .eq("status", "active")
        .execute()
    ).data

    for business in businesses:
        business_id = business["id"]
        customer_id = business["google_ads_customer_id"].replace("-", "")
        print(f"{business['name']} ({customer_id}):")

        now = datetime.now(timezone.utc)
        oldest_eligible = (now - timedelta(hours=FOLLOWUP_MAX_AGE_HOURS)).isoformat()
        newest_eligible = (now - timedelta(hours=FOLLOWUP_DELAY_HOURS)).isoformat()

        candidates = (
            supabase.table("leads")
            .select("id, google_lead_id, google_created_at")
            .eq("business_id", business_id)
            .eq("lead_type", "MESSAGE")
            .eq("responded", False)
            .eq("auto_reply_sent", True)
            .eq("follow_up_sent", False)
            .gte("google_created_at", oldest_eligible)
            .lte("google_created_at", newest_eligible)
            .execute()
        ).data

        print(f"  {len(candidates)} lead(s) due a follow-up")
        if not candidates:
            continue

        token_result = supabase.rpc(
            "get_refresh_token", {"p_business_id": business_id}
        ).execute()
        refresh_token = token_result.data
        if not refresh_token:
            print("  no refresh token found, skipping")
            continue

        ga_client = get_google_ads_client(refresh_token)

        for lead in candidates:
            lead_resource_name = f"customers/{customer_id}/localServicesLeads/{lead['google_lead_id']}"
            print(f"  lead {lead['google_lead_id']} (created {lead['google_created_at']}):")
            success = send_followup(ga_client, customer_id, lead_resource_name, FOLLOWUP_TEMPLATE)

            if success and not DRY_RUN:
                supabase.table("leads").update({
                    "follow_up_sent": True,
                }).eq("id", lead["id"]).execute()


if __name__ == "__main__":
    main()
