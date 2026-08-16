// Shared Google Ads API helper for all Edge Functions in this project.
//
// [UNVERIFIED, same honesty note as send-reply's AppendLeadConversation
// call]: the GoogleAdsService.Search REST shape below has NOT been
// tested against the live endpoint yet — it follows Google's documented
// REST convention (POST /v{version}/customers/{id}/googleAds:search),
// but every GAQL query in this project so far went through the Python
// client library, never raw REST. Treat the first real call as the
// actual test of this shape, same discipline as send-reply.

const API_VERSION = "v25"; // matches the version used throughout the Python scripts

export async function getAccessToken(
  refreshToken: string,
  clientId: string,
  clientSecret: string,
): Promise<string> {
  const response = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      client_id: clientId,
      client_secret: clientSecret,
      refresh_token: refreshToken,
      grant_type: "refresh_token",
    }),
  });
  const data = await response.json();
  if (!data.access_token) {
    throw new Error(`Failed to refresh Google access token: ${JSON.stringify(data)}`);
  }
  return data.access_token;
}

export interface GaqlSearchParams {
  customerId: string;
  query: string;
  accessToken: string;
  developerToken: string;
  loginCustomerId: string;
}

// Returns the raw array of result rows (each row is the JSON-shaped
// equivalent of what the Python client's `row.local_services_lead` etc.
// gave us — REST responses use camelCase field names, not snake_case).
export async function gaqlSearch({
  customerId,
  query,
  accessToken,
  developerToken,
  loginCustomerId,
}: GaqlSearchParams): Promise<any[]> {
  const results: any[] = [];
  let pageToken: string | undefined = undefined;

  do {
    const response = await fetch(
      `https://googleads.googleapis.com/${API_VERSION}/customers/${customerId}/googleAds:search`,
      {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${accessToken}`,
          "developer-token": developerToken,
          "login-customer-id": loginCustomerId,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ query, pageToken }),
      },
    );

    const data = await response.json();
    if (!response.ok) {
      throw new Error(`GAQL search failed: ${JSON.stringify(data)}`);
    }

    results.push(...(data.results || []));
    pageToken = data.nextPageToken;
  } while (pageToken);

  return results;
}
