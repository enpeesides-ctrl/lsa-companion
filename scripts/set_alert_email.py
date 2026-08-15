"""
The only sanctioned way to set a business's alert_email — mirrors
set_webhook_url.py exactly, for the same reason: setting the column
directly via SQL would flood the first alert run with the entire
historical backlog (confirmed happened with webhooks; applying the
lesson proactively here instead of rediscovering it a third time).

Run: python3 set_alert_email.py <business_name> <alert_email>
"""

import sys
from pathlib import Path

from dotenv import dotenv_values
from supabase import create_client

HERE = Path(__file__).resolve().parent
ENV = dotenv_values(HERE / ".env")


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 set_alert_email.py <business_name> <alert_email>")
        sys.exit(1)

    business_name, alert_email = sys.argv[1], sys.argv[2]
    supabase = create_client(ENV["SUPABASE_URL"], ENV["SUPABASE_SERVICE_ROLE_KEY"])

    business = (
        supabase.table("businesses").select("id").eq("name", business_name).single().execute()
    ).data

    supabase.table("leads").update({"alert_sent": True}).eq("business_id", business["id"]).execute()
    supabase.table("businesses").update({"alert_email": alert_email}).eq("id", business["id"]).execute()

    print(f"Alert email set for {business_name}. Existing leads marked as already-alerted — "
          f"only new leads from this point forward will trigger an email.")


if __name__ == "__main__":
    main()
