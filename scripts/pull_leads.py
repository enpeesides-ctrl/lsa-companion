"""
Phase 0, step 4-5 (rebuilt 2026-08-14): pull Vertex's real lead data via
the CURRENT, non-deprecated path — the general Google Ads API's
`local_services_lead` resource, queried via GoogleAdsService.Search (GAQL).

The earlier version of this script used the "Local Services API"
(localservices.googleapis.com) documented in Google's own PDF guide — that
product is deprecated and its detailedLeadReports endpoint reliably
returns an empty {} even against accounts with real data (confirmed both
against Vertex's real account and independently by other developers on
Google's forums). This version uses the officially recommended
replacement instead.

Read-only by design — selects fields, never writes/disputes anything.

Setup: same .env as before (DEVELOPER_TOKEN, REFRESH_TOKEN,
MANAGER_CUSTOMER_ID, VERTEX_CUSTOMER_ID) plus client_secret.json.

Install:
  pip3 install google-ads python-dotenv

Run:
  python3 pull_leads.py

Note on the GAQL query below: the exact set of selectable fields on
local_services_lead hasn't been independently confirmed field-by-field
against live docs — this starts with a conservative, minimal field list.
If the API rejects a field name, the error message will name the invalid
field directly; narrow or adjust the SELECT list from there rather than
guessing further.
"""

import json
from pathlib import Path

from dotenv import dotenv_values
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

HERE = Path(__file__).resolve().parent
CLIENT_SECRETS_FILE = HERE / "client_secret.json"
ENV = dotenv_values(HERE / ".env")

DEVELOPER_TOKEN = ENV["DEVELOPER_TOKEN"]
REFRESH_TOKEN = ENV["REFRESH_TOKEN"]
MANAGER_CUSTOMER_ID = ENV["MANAGER_CUSTOMER_ID"].replace("-", "")
VERTEX_CUSTOMER_ID = ENV["VERTEX_CUSTOMER_ID"].replace("-", "")

GAQL_QUERY = """
    SELECT
        local_services_lead.id,
        local_services_lead.lead_type,
        local_services_lead.lead_status,
        local_services_lead.creation_date_time,
        local_services_lead.lead_charged,
        local_services_lead.contact_details,
        local_services_lead.locale
    FROM local_services_lead
"""
# Confirmed working via live trial against Vertex's real account, 2026-08-14.
# Ruled out as invalid: lead_currency, lead_price, dispute_status,
# lead_category (don't exist on this resource).
# Ruled out as SELECT-incompatible (exist but filter/other-use only):
# credit_details, note.
# IMPORTANT GAP: lead_charged is boolean only — this resource does not
# appear to carry the actual dollar amount charged per lead. Cost data
# likely lives on a separate Google Ads cost/metrics resource, not here.
# Needed before the audit tool's ROI math can be calculated for real.


def build_client():
    with open(CLIENT_SECRETS_FILE) as f:
        client_info = json.load(f)["installed"]

    config = {
        "developer_token": DEVELOPER_TOKEN,
        "client_id": client_info["client_id"],
        "client_secret": client_info["client_secret"],
        "refresh_token": REFRESH_TOKEN,
        "login_customer_id": MANAGER_CUSTOMER_ID,
        "use_proto_plus": True,
    }
    return GoogleAdsClient.load_from_dict(config)


def main():
    client = build_client()
    ga_service = client.get_service("GoogleAdsService")

    print(f"Querying local_services_lead for customer {VERTEX_CUSTOMER_ID}...")

    try:
        response = ga_service.search(
            customer_id=VERTEX_CUSTOMER_ID, query=GAQL_QUERY
        )
        rows = list(response)
        print(f"\n--- {len(rows)} leads returned ---")
        for row in rows[:5]:
            print(row.local_services_lead)
        if len(rows) > 5:
            print(f"... and {len(rows) - 5} more")

    except GoogleAdsException as ex:
        print(f"\nRequest failed with status {ex.error.code().name}")
        for error in ex.failure.errors:
            print(f"  Error: {error.message}")
            if error.location:
                for field in error.location.field_path_elements:
                    print(f"    field: {field.field_name}")


if __name__ == "__main__":
    main()
