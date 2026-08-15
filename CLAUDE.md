# Project instructions — LSA Companion

Standalone tool, completely separate codebase/database from
`~/businesses/vertex-property-care/` — do not assume shared schema,
shared conventions, or shared Supabase project with that codebase.
Vertex is a test user of this product, not its foundation.

Global grounding rule (verify checkable claims with a real tool before
stating them as fact) still applies — see `~/.claude/CLAUDE.md`.

## Standing scope reminders

- Multi-tenant from the start (any LSA user), not single-business.
- Messages are the primary lead type handled day to day; calls only need a
  missed-call follow-up mechanism, not live-call handling.
- CRM integration is optional/future, not core v1.
- v1 = audit tool + inbox/UX layer, built together (not sequenced).

## Open risk to resolve early

Google Ads API access approval for pulling *other businesses'*
`local_services_lead` data (multi-tenant access) is unverified — confirm
this before committing to an architecture that assumes it's straightforward.
