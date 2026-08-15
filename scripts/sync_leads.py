"""
Phase 1 sync job: pulls leads + daily cost for every active business from
the Google Ads API and writes them into Supabase.

Preserves our own added fields (responded, notes, follow_up_sent) across
re-syncs — only Google-sourced fields get overwritten on upsert.

Setup: extend scripts/.env with SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY
(see .env.example) plus the existing DEVELOPER_TOKEN / MANAGER_CUSTOMER_ID.

Install:
  pip3 install supabase google-ads python-dotenv

Run:
  python3 sync_leads.py

Intended to run on a schedule (every 30 min, per Phase 1's capacity math)
once deployed — this is the local/manual version for now.
"""

import json
from datetime import date, timedelta
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

LEAD_QUERY = """
    SELECT
        local_services_lead.id,
        local_services_lead.lead_type,
        local_services_lead.lead_status,
        local_services_lead.lead_charged,
        local_services_lead.lead_feedback_submitted,
        local_services_lead.contact_details,
        local_services_lead.locale,
        local_services_lead.creation_date_time,
        local_services_lead.credit_details.credit_state,
        local_services_lead.category_id,
        local_services_lead.service_id
    FROM local_services_lead
"""


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


def sync_leads(supabase, ga_service, business_id, customer_id):
    response = ga_service.search(customer_id=customer_id, query=LEAD_QUERY)
    rows = []
    for row in response:
        lead = row.local_services_lead
        rows.append({
            "business_id": business_id,
            "google_lead_id": lead.id,
            "lead_type": lead.lead_type.name,
            "lead_status": lead.lead_status.name,
            "lead_charged": lead.lead_charged,
            "lead_feedback_submitted": lead.lead_feedback_submitted,
            "contact_phone": lead.contact_details.phone_number or None,
            "locale": lead.locale or None,
            "google_created_at": lead.creation_date_time.split(".")[0] or None,
            "credit_state": lead.credit_details.credit_state.name,
            "category_id": lead.category_id or None,
            "service_id": lead.service_id or None,
            # deliberately NOT included: responded, notes, follow_up_sent
            # — those are ours, preserved across syncs by omission here.
        })

    if rows:
        supabase.table("leads").upsert(
            rows, on_conflict="business_id,google_lead_id"
        ).execute()
    print(f"  synced {len(rows)} leads")


def sync_conversations(supabase, ga_service, business_id, customer_id):
    # Pulls from local_services_lead_conversation (a different resource
    # from local_services_lead, found via GoogleAdsFieldService metadata
    # sweep) — covers three things in one pass:
    #   - call_duration_millis: available immediately (not subject to the
    #     72-hour charge-review delay lead_charged has), 0 cleanly
    #     indicates an unanswered call.
    #   - message_details.text: the actual message content.
    #   - id/participant_type/event_date_time: added 2026-08-15 for the
    #     mobile redesign's chat-bubble view, which needs to know which
    #     side each message is from (CONSUMER vs business) — message_text
    #     alone (one concatenated blob) can't support that.
    query = """
        SELECT
            local_services_lead_conversation.id,
            local_services_lead_conversation.lead,
            local_services_lead_conversation.conversation_channel,
            local_services_lead_conversation.participant_type,
            local_services_lead_conversation.event_date_time,
            local_services_lead_conversation.phone_call_details.call_duration_millis,
            local_services_lead_conversation.message_details.text
        FROM local_services_lead_conversation
    """
    response = ga_service.search(customer_id=customer_id, query=query)

    # google_lead_id -> our internal leads.id, needed for conversation_messages' FK
    lead_rows = (
        supabase.table("leads")
        .select("id, google_lead_id")
        .eq("business_id", business_id)
        .execute()
    ).data
    internal_id_by_google_id = {row["google_lead_id"]: row["id"] for row in lead_rows}

    # A lead can have multiple conversation events (repeat call attempts,
    # multiple messages). Take the max call duration seen (if ANY attempt
    # connected, it's not missed overall) and concatenate message text for
    # the leads-table quick-preview column (kept for the existing list view).
    max_duration_by_lead = {}
    messages_by_lead = {}
    message_rows = []
    for row in response:
        conv = row.local_services_lead_conversation
        google_lead_id = int(conv.lead.split("/")[-1])

        duration = conv.phone_call_details.call_duration_millis
        if duration:
            max_duration_by_lead[google_lead_id] = max(duration, max_duration_by_lead.get(google_lead_id, 0))

        text = conv.message_details.text
        if text:
            messages_by_lead.setdefault(google_lead_id, []).append(text)

        internal_lead_id = internal_id_by_google_id.get(google_lead_id)
        if internal_lead_id:
            message_rows.append({
                "business_id": business_id,
                "lead_id": internal_lead_id,
                "google_conversation_id": conv.id,
                "participant_type": conv.participant_type.name,
                "channel": conv.conversation_channel.name,
                "text": text or None,
                "event_date_time": conv.event_date_time.split(".")[0] if conv.event_date_time else None,
            })

    lead_ids = set(max_duration_by_lead) | set(messages_by_lead)
    updated = 0
    for google_lead_id in lead_ids:
        update = {}
        if google_lead_id in max_duration_by_lead:
            update["call_duration_millis"] = max_duration_by_lead[google_lead_id]
        if google_lead_id in messages_by_lead:
            update["message_text"] = "\n---\n".join(messages_by_lead[google_lead_id])

        result = (
            supabase.table("leads")
            .update(update)
            .eq("business_id", business_id)
            .eq("google_lead_id", google_lead_id)
            .execute()
        )
        if result.data:
            updated += 1

    if message_rows:
        supabase.table("conversation_messages").upsert(
            message_rows, on_conflict="business_id,google_conversation_id"
        ).execute()

    print(f"  synced conversation data for {updated} lead(s), {len(message_rows)} individual message(s)")


def sync_daily_cost(supabase, ga_service, business_id, customer_id):
    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    query = f"""
        SELECT metrics.cost_micros, segments.date
        FROM customer
        WHERE segments.date BETWEEN "{start_date}" AND "{end_date}"
    """
    response = ga_service.search(customer_id=customer_id, query=query)
    rows = [
        {
            "business_id": business_id,
            "date": row.segments.date,
            "cost_micros": row.metrics.cost_micros,
        }
        for row in response
    ]
    if rows:
        supabase.table("daily_cost").upsert(
            rows, on_conflict="business_id,date"
        ).execute()
    print(f"  synced {len(rows)} days of cost data")


def main():
    supabase = create_client(ENV["SUPABASE_URL"], ENV["SUPABASE_SERVICE_ROLE_KEY"])

    businesses = (
        supabase.table("businesses")
        .select("id, name, google_ads_customer_id")
        .eq("status", "active")
        .execute()
    ).data

    print(f"Syncing {len(businesses)} active business(es)...")

    for business in businesses:
        business_id = business["id"]
        customer_id = business["google_ads_customer_id"].replace("-", "")
        print(f"\n{business['name']} ({customer_id}):")

        token_result = supabase.rpc(
            "get_refresh_token", {"p_business_id": business_id}
        ).execute()
        refresh_token = token_result.data
        if not refresh_token:
            print("  no refresh token found, skipping")
            continue

        ga_client = get_google_ads_client(refresh_token)
        ga_service = ga_client.get_service("GoogleAdsService")

        try:
            sync_leads(supabase, ga_service, business_id, customer_id)
            sync_conversations(supabase, ga_service, business_id, customer_id)
            sync_daily_cost(supabase, ga_service, business_id, customer_id)
        except GoogleAdsException as ex:
            print("  ERROR:", ex.failure.errors[0].message)


if __name__ == "__main__":
    main()
