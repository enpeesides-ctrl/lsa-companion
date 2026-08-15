-- Run this yourself in the Supabase SQL Editor, filling in your own
-- refresh token where marked — do not share the token value in chat,
-- only the resulting UUIDs (which are safe, opaque references).

-- Step 1: store the refresh token in Vault (encrypted).
-- Replace 'PASTE_YOUR_REFRESH_TOKEN_HERE' with the real value you saved
-- earlier, then run just this SELECT and copy the UUID it returns.
select vault.create_secret(
  'PASTE_YOUR_REFRESH_TOKEN_HERE',
  'vertex_refresh_token',
  'OAuth refresh token for Vertex Property Care LSA connection'
);

-- Step 2: create the business row.
-- google_ads_customer_id is the one we already confirmed: 8861731566
insert into businesses (name, google_ads_customer_id)
values ('Vertex Property Care', '8861731566')
returning id;

-- Step 3: link the credential.
-- Replace the two placeholders below with the UUIDs returned by Step 1
-- and Step 2 above.
insert into business_credentials (business_id, refresh_token_secret_id)
values ('1a067a0b-805a-4148-8045-f8ccd54b14ff', 'f60eb9e5-8572-4e50-8b28-dc96f1772822');
