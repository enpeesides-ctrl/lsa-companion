"""
One-time OAuth consent-flow script for LSA Companion.

What this does:
  1. Opens your browser to Google's consent screen using the OAuth Client
     ID/Secret from your Google Cloud project.
  2. You sign in and click "Allow" once.
  3. Prints a REFRESH TOKEN — a long-lived credential we reuse for every
     future API call, so this interactive step only needs to happen once
     (unless the token is later revoked).

Before running:
  1. In Google Cloud Console (the project from Step 2), go to
     APIs & Services -> Credentials -> your OAuth client ID -> Download JSON.
  2. Save that file as `client_secret.json` in this same `scripts/` folder.
     (Do not commit this file or the printed refresh token anywhere —
     both are real credentials.)
  3. Install the one dependency this needs:
       pip install google-auth-oauthlib

Run it with:
    python3 get_refresh_token.py
"""

from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

# Confirmed directly from Google's own Local Services API developer guide.
SCOPES = ["https://www.googleapis.com/auth/adwords"]

# Resolved relative to this script's own location, not the current working
# directory, so it works no matter where you run `python3 ...` from.
CLIENT_SECRETS_FILE = Path(__file__).resolve().parent / "client_secret.json"


def main():
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
    # Spins up a local server but does NOT auto-open a browser — printing the
    # URL instead lets you paste it into an already-logged-in Chrome tab,
    # rather than a fresh/unauthenticated browser context that was
    # triggering repeated sign-in + security checks.
    credentials = flow.run_local_server(port=0, open_browser=False)

    print("\n--- Success ---")
    print("Access token (short-lived, expires soon):")
    print(credentials.token)
    print("\nRefresh token (long-lived — save this securely, this is the one that matters):")
    print(credentials.refresh_token)
    print(
        "\nSave the refresh token somewhere safe (not committed to git). "
        "We'll use it plus your developer token + Manager Account ID to "
        "make the real API call once Basic access is approved."
    )


if __name__ == "__main__":
    main()
