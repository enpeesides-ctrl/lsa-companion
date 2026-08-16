"""
Option 1: fixed-template auto-acknowledgment for new message leads.

Deliberately structured for a future AI upgrade — generate_reply() is
the only thing that would need to change; the trigger/send/tracking
logic stays the same either way (see conversation history for why).

SAFETY: defaults to DRY_RUN = True. In dry-run, nothing is sent — it
only prints what WOULD be sent. Flip DRY_RUN to False only when you've
reviewed the output and are ready for a real message to actually reach
a real customer.

Request structure confirmed directly from the installed google-ads
library's own type definitions (not guessed, not from docs — WebFetch
couldn't render Google's JS-based docs pages, so this was verified by
introspecting AppendLeadConversationRequest/Conversation directly):
  AppendLeadConversationRequest: customer_id, conversations (list)
  Conversation: local_services_lead (resource name), text (message)

Setup: same .env as sync_leads.py.
Install: pip3 install google-ads supabase python-dotenv (already done)
Run: python3 auto_reply.py
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
# and deliberately decide to let real messages send.
# ============================================================
DRY_RUN = True

# Added after dry-run testing surfaced a real bug: with no recency filter,
# this matched 18 leads spanning March-August 2026 — sending "we just got
# your message" to a 5-month-old lead would look broken. Only reply to
# genuinely recent leads.
MAX_LEAD_AGE_HOURS = 24

TEMPLATE = (
    "Thanks for reaching out! We've received your message and "
    "will get back to you shortly."
)

AFTER_HOURS_TEMPLATE = (
    "Thanks for reaching out! We're currently closed — we've received "
    "your message and will get back to you when we reopen."
)


def is_after_hours(business):
    # Uses this machine's local time — correct for Vertex (single,
    # UK-based business, and this Mac already runs UK time), but a real
    # limitation worth knowing: this would need a stored per-business
    # timezone before it could serve businesses elsewhere correctly.
    hour = datetime.now().hour
    return not (business["business_hours_start"] <= hour < business["business_hours_end"])


def generate_reply(lead, business):
    # Template selection only for now. A future AI upgrade only changes
    # what happens inside this function — the after-hours check itself
    # stays valid either way.
    if is_after_hours(business):
        return AFTER_HOURS_TEMPLATE
    return TEMPLATE


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


def send_reply(ga_client, customer_id, lead_resource_name, text):
    if DRY_RUN:
        print(f"    [DRY RUN] would send to {lead_resource_name}:")
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
        print(f"    SENT to {lead_resource_name}")
        return True
    except GoogleAdsException as ex:
        print(f"    ERROR sending to {lead_resource_name}: {ex.failure.errors[0].message}")
        return False


def main():
    print(f"Running in {'DRY RUN' if DRY_RUN else 'LIVE SEND'} mode.\n")

    supabase = create_client(ENV["SUPABASE_URL"], ENV["SUPABASE_SERVICE_ROLE_KEY"])

    businesses = (
        supabase.table("businesses")
        .select("id, name, google_ads_customer_id, business_hours_start, business_hours_end")
        .eq("status", "active")
        .execute()
    ).data

    for business in businesses:
        business_id = business["id"]
        customer_id = business["google_ads_customer_id"].replace("-", "")
        print(f"{business['name']} ({customer_id}):")

        # New, unreplied, and genuinely recent message leads only.
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=MAX_LEAD_AGE_HOURS)).isoformat()
        candidates = (
            supabase.table("leads")
            .select("id, google_lead_id, lead_type, lead_status, auto_reply_sent, google_created_at")
            .eq("business_id", business_id)
            .eq("lead_type", "MESSAGE")
            .eq("lead_status", "NEW")
            .eq("auto_reply_sent", False)
            .gte("google_created_at", cutoff)
            .execute()
        ).data

        print(f"  {len(candidates)} new message lead(s) to auto-reply to")
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
            text = generate_reply(lead, business)
            print(f"  lead {lead['google_lead_id']}:")
            success = send_reply(ga_client, customer_id, lead_resource_name, text)

            if success and not DRY_RUN:
                supabase.table("leads").update({
                    "auto_reply_sent": True,
                    "auto_reply_sent_at": "now()",
                }).eq("id", lead["id"]).execute()


if __name__ == "__main__":
    main()
