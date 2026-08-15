"""
Generic webhook export (Tier 1, Phase 3): POSTs new leads to a
business-configured URL (e.g. a Zapier "Webhooks by Zapier" trigger),
so a business can route leads into whatever CRM/tool they already use
without us building a bespoke integration per platform.

Only fires for leads not previously exported (webhook_sent = false),
same pattern as auto_reply_sent — tracked per lead, not re-sent on
every run.

No new external account needed — the business supplies their own
receiving URL. Nothing sends unless a business has actually set
webhook_url on their row (defaults to null, meaning opted out).

Setup: same .env as sync_leads.py.
Run: python3 webhook_export.py
"""

from pathlib import Path

import requests
from dotenv import dotenv_values
from supabase import create_client

HERE = Path(__file__).resolve().parent
ENV = dotenv_values(HERE / ".env")


def build_payload(business, lead):
    return {
        "business_name": business["name"],
        "lead_id": lead["google_lead_id"],
        "lead_type": lead["lead_type"],
        "lead_status": lead["lead_status"],
        "lead_charged": lead["lead_charged"],
        "contact_phone": lead["contact_phone"],
        "created_at": lead["google_created_at"],
    }


def main():
    supabase = create_client(ENV["SUPABASE_URL"], ENV["SUPABASE_SERVICE_ROLE_KEY"])

    businesses = (
        supabase.table("businesses")
        .select("id, name, webhook_url")
        .eq("status", "active")
        .execute()
    ).data

    for business in businesses:
        if not business["webhook_url"]:
            print(f"{business['name']}: no webhook configured, skipping")
            continue

        pending = (
            supabase.table("leads")
            .select("id, google_lead_id, lead_type, lead_status, lead_charged, contact_phone, google_created_at")
            .eq("business_id", business["id"])
            .eq("webhook_sent", False)
            .execute()
        ).data

        print(f"{business['name']}: {len(pending)} lead(s) to export")

        for lead in pending:
            payload = build_payload(business, lead)
            try:
                response = requests.post(business["webhook_url"], json=payload, timeout=10)
                response.raise_for_status()
                supabase.table("leads").update({"webhook_sent": True}).eq("id", lead["id"]).execute()
                print(f"  exported lead {lead['google_lead_id']}")
            except requests.RequestException as ex:
                print(f"  FAILED lead {lead['google_lead_id']}: {ex}")


if __name__ == "__main__":
    main()
