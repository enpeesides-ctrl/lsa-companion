"""
The only safe way to set a business's webhook_url — setting the column
directly via SQL would flood the new webhook with the entire historical
backlog (confirmed happens: exported all 177 of Vertex's leads in one
test run). This script sets the URL AND marks existing leads as already
exported in the same step, so only genuinely new leads trigger it going
forward.

Run: python3 set_webhook_url.py <business_name> <webhook_url>
"""

import sys
from pathlib import Path

from dotenv import dotenv_values
from supabase import create_client

HERE = Path(__file__).resolve().parent
ENV = dotenv_values(HERE / ".env")


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 set_webhook_url.py <business_name> <webhook_url>")
        sys.exit(1)

    business_name, webhook_url = sys.argv[1], sys.argv[2]
    supabase = create_client(ENV["SUPABASE_URL"], ENV["SUPABASE_SERVICE_ROLE_KEY"])

    business = (
        supabase.table("businesses").select("id").eq("name", business_name).single().execute()
    ).data

    # Mark all existing leads as already-exported BEFORE setting the URL,
    # so the backlog never gets sent.
    supabase.table("leads").update({"webhook_sent": True}).eq("business_id", business["id"]).execute()
    supabase.table("businesses").update({"webhook_url": webhook_url}).eq("id", business["id"]).execute()

    print(f"Webhook set for {business_name}. Existing leads marked as already-exported — "
          f"only new leads from this point forward will be sent.")


if __name__ == "__main__":
    main()
