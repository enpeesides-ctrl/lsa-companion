-- Vault's decrypted_secrets view isn't reachable through the normal
-- Supabase API. This function wraps the lookup, runs with definer
-- rights (so it can read vault internally), and is locked to
-- service_role only — the sync job authenticates with the service role
-- key, regular users/anon/authenticated can never call this even if
-- they knew the function name.

create or replace function get_refresh_token(p_business_id uuid)
returns text
language sql
security definer
set search_path = public, vault
as $$
  select decrypted_secret
  from vault.decrypted_secrets
  join business_credentials
    on business_credentials.refresh_token_secret_id = vault.decrypted_secrets.id
  where business_credentials.business_id = p_business_id;
$$;

revoke all on function get_refresh_token(uuid) from public, anon, authenticated;
grant execute on function get_refresh_token(uuid) to service_role;
