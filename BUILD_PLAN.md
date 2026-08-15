# Build Plan — LSA Companion

Phased plan based on everything confirmed during research (see history in
this file's companion `README.md` for product scope). Order matters here —
each phase proves the thing the next phase depends on, rather than building
UI on top of an unproven connection.

## Phase -1 — Confirm we're actually allowed to build this (do this FIRST)

**Added on review — this was missing entirely, and it should gate everything
else.** All prior research covered *how* to connect technically; none of it
covered whether our specific use case (multi-tenant lead tool, potentially
auto-submitting feedback on a business's behalf) is compliant with Google's
own policy. If it isn't, nothing below matters.

1. Read Google's **"Access Levels and Permissible Use"** policy in full
   (found during earlier research, never actually opened) —
   https://developers.google.com/google-ads/api/docs/api-policy/access-levels
2. Read the **"Required Minimum Functionality" (RMF)** requirements
   referenced alongside it — confirm what functionality bar a third-party
   tool must meet to get/keep API access.
3. Confirm specifically whether automated submission of Lead Feedback
   Survey responses on a business's behalf is permitted, or whether that
   needs to stay a human-in-the-loop action (business reviews our
   evidence, submits it themselves).

**Correction, 2026-08-14**: the "Local Services API" (`localservices.googleapis.com`,
documented in Google's PDF developer guide) is **deprecated** — its
`detailedLeadReports` endpoint reliably returns an empty `{}` response even
against accounts with real, matching lead data (confirmed both by our own
real test against Vertex's account and independently by other developers
on Google's forums). **The correct, current path is the general Google Ads
API's `local_services_lead` resource**, queried via `GoogleAdsService.Search`
(GAQL) using the official `google-ads` Python client library — this is what
Google itself now recommends instead. `pull_leads.py` needs rebuilding
against this before Phase 0 can actually complete.

**Findings, 2026-08-12:**
- Reporting (read-only lead/account data) fits cleanly under Google's
  "Reporting" permissible-use category — low risk.
- RMF (functionality-completeness rules) only applies to **Standard**
  Access, not Basic — not a blocker for MVP, revisit at Phase 4 if/when
  applying for Standard access.
- **Unresolved**: `ProvideLeadFeedback()` (automated dispute/feedback
  submission) doesn't clearly fall under any of the three defined
  permissible-use categories. Treat automated submission as **not
  confirmed compliant** — v1 default is the human-in-the-loop version
  (we generate evidence, business submits it themselves), not automation.
- **Unresolved**: could not find Local Services API-specific terms
  separate from the general Google Ads API policy — [UNVERIFIED] whether
  additional restrictions apply. Google's "API Compliance team" contact
  channel (referenced in RMF docs) is likely the real way to close this
  out, not more searching.

**Exit criteria**: a clear yes/no on whether this product, as scoped, is
compliant — before creating any account or writing any code. **Not yet
fully met** — reporting is clear, automated feedback submission is not.

## Phase 0 — Prove the connection works (before writing product code)

Nothing else is worth building until this is proven end-to-end with real
data, since the whole product depends on it.

1. Create our Google Ads Manager Account (free, ~5 min, business email,
   "Manage my clients' accounts" option). [Medium confidence]: sourced from
   WebSearch summaries of Google's help docs, not confirmed by reading the
   primary source directly — re-verify against Google's own page when
   actually doing this step, don't just trust this plan's summary of it.
2. Set up a Google Cloud project and generate a Google Ads API developer
   token (the Cloud project is a real prerequisite step the original plan
   skipped over). **Correction, 2026-08-14**: new developer tokens default
   to **Explorer Access**, which already permits read-only calls against
   real production accounts (2,880 operations/day, no planning/billing
   features — irrelevant to us) — this is sufficient for Phase 0's real
   API call. Basic access (15,000 ops/day) is only needed later, once
   syncing many customers exceeds Explorer's cap — apply for it in
   parallel, but it does not block this step.
3. Link Vertex's existing LSA account to our new Manager Account (real
   linking flow: get Vertex's 10-digit Customer ID → send link request →
   Vertex accepts).
4. Make **one real, READ-ONLY API call** against Vertex's linked account —
   pull a Detailed Lead Report for a short date range and confirm real
   lead data comes back correctly shaped. **Do not test any write/feedback
   capability against Vertex's live account at this stage** — Vertex
   depends on this account for real leads; any write action needs a
   read-only-first, sandbox-or-explicit-confirmation-second discipline,
   the same caution already established (and hard-won) in Vertex's own
   project conventions.
5. Pull enough of Vertex's real historical lead data here to sanity-check
   the core business pitch: how many of their charged leads actually look
   invalid, and roughly how much money is at stake? **This determines
   whether Phase 2's audit tool is worth building as scoped, before a
   single day of UI work goes into it** — do this before Phase 1, not
   after.
6. [Open question, resolve here] Test whether `disputeStatus` read access
   and any write/feedback-submission capability (`ProvideLeadFeedback`)
   both work from the same setup, or if the write path needs separate
   Google Ads API access beyond the Local Services reporting API.

**Exit criteria**: real lead data from Vertex's live account, visible
somewhere we control (even just a terminal printout), AND a real number
for "how much money is actually at stake" — not before.

**Status, 2026-08-14: first half done.** Real call succeeded against
Vertex's live account via `GoogleAdsService.Search` on `local_services_lead`
— 177 leads returned (full history, no date filter applied yet), fields
confirmed working: id, lead_type, lead_status, creation_date_time,
lead_charged. **Update, 2026-08-14**: confirmed working field set via direct live trial
(id, lead_type, lead_status, creation_date_time, lead_charged,
contact_details, locale). **Real gap found, not yet solved**: `lead_charged`
is boolean only — `local_services_lead` does not appear to carry the actual
dollar amount charged per lead. Cost data likely lives on a separate
Google Ads cost/metrics resource, cross-referenced by date/campaign rather
than attached to each lead directly — needs its own research thread before
the audit tool's ROI number can be calculated for real. `dispute_status` (bare field name) does not exist, but the real
dispute/credit field does — **`local_services_lead.credit_details.credit_state`**,
confirmed working with real data (all 10 sampled charged leads currently
show `UNSPECIFIED`, i.e. no credit decision applied yet — verified via
explicit field access, not just trusting the print repr, since default
enum/bool values get silently omitted from proto-plus's default string
output).

**Confirmed structural finding, 2026-08-14**: per-lead cost genuinely does
not exist on `local_services_lead` — tried 4 candidate field names, all
either don't exist or (`metrics.cost_micros`) are explicitly incompatible
with this resource per Google's own error message. Cost lives at a
different resource level (campaign/customer), not joinable to individual
leads in one query. **Product implication**: the audit tool cannot show
"this lead cost you £X" precisely — the realistic version is an estimate
(average cost-per-lead for the period, applied to a count of
flagged/declined-charged leads), not an exact per-lead figure. This is a
real scope change worth being upfront about, not a technical footnote.

**Confirmed working GAQL field set for `local_services_lead`** (saved in
`pull_leads.py`): id, lead_type, lead_status, creation_date_time,
lead_charged, contact_details (nested: phone_number), locale,
credit_details.credit_state.

**The cost piece, resolved 2026-08-14**: per-lead cost genuinely isn't
available (confirmed above), but **aggregate cost is** — confirmed working
against Vertex's real account: `billing_setup` (status: APPROVED, real
payments account attached) plus a `customer`-level query with
`metrics.cost_micros` segmented by `segments.date` (16 days of real spend
data over the last 30 days, £76.00 total). This closes the ROI-estimate
approach: correlate per-lead counts/status (from `local_services_lead`)
against daily aggregate cost (from `customer`/`metrics.cost_micros`) over
the same date range to compute an average cost-per-lead, applied to
flagged/declined-charged leads as an estimate — not exact per-lead
figures, but a real, defensible number rather than a guess.

**Phase 0 is now effectively complete**: real connection proven, full
confirmed field set for leads, dispute status, and cost, all tested live
against Vertex's actual account. Remaining before Phase 1: write the
actual cost-per-lead correlation calculation and run it once for real,
to get Vertex's actual ROI number (not just confirm the fields exist).

## Phase 1 — Data layer — **DONE, 2026-08-14**

Schema built (businesses, business_members, business_credentials with
Vault-backed tokens, leads, daily_cost), all RLS policies in place, Vertex
seeded as the first real business, and `sync_leads.py` run successfully:
177 leads + 16 days of cost data written into real tables, verified
directly — correct typing, correct business_id linkage, our own added
fields (responded/notes/follow_up_sent) correctly defaulted and preserved
across the sync rather than overwritten.

- New database, fully separate from Vertex's CRM/Portal Supabase projects
  (per standing project instruction — no shared schema).
- **Added on review — multi-tenant isolation must be designed here, not
  assumed.** "Separate from Vertex" only covers isolation between this
  product and Vertex; it says nothing about isolation *between different
  LSA Companion customers* once there's more than one tenant. Every table
  needs an explicit tenant/business identifier and real row-level security
  from the start — apply the exact lesson already paid for once in
  Vertex's own build (RLS must be explicitly enabled per table, and any
  policy that checks membership via a lookup table needs a self-select
  policy on that lookup table or it silently grants full access instead of
  restricting it).
- **Added on review — data privacy/compliance is a schema-time decision,
  not a later add-on.** This product holds real consumer PII (names,
  phone numbers, call data) belonging to other businesses' customers,
  across multiple tenants, at least one UK-based (GDPR applies). Before
  building the schema: decide retention period, who can access stored PII
  and how, and draft a basic privacy policy / data processing terms for
  customers. Not fully resolvable in this plan — flagging as a required
  decision before Phase 1 is considered done, not after launch.
- A synced-leads table, mapped from the API's Detailed Lead Report fields
  (leadId, leadType, chargeStatus, disputeStatus, messageLead/phoneLead
  details, etc.) **plus our own added fields Google doesn't track**:
  responded/needs-reply status, internal notes, follow-up-sent flag for
  missed calls.
- A sync job that pulls new/updated leads periodically per connected
  account (30-minute data staleness on Google's side means near-real-time
  polling, not instant). **Added on review**: before finalizing poll
  frequency, do the actual capacity math — (number of businesses) ×
  (report types per sync) × (syncs per day) against the Basic tier's
  15,000 operations/day cap. The original plan asserted this was "fine"
  without ever running the numbers.

## Phase 2 — Core v1 features (audit tool + inbox/UX, built together)

**Audit tool — revised 2026-08-14 based on real validated findings:**
- Surface `lead_status` / `credit_details.credit_state` /
  `lead_feedback_submitted` per lead (all confirmed working fields).
- Flag charged + declined-by-business + uncredited leads for review, same
  logic already validated against Vertex's real history.
- Dashboard total: real, defensible estimate ("£X tied up in flagged
  leads" — average cost-per-lead × flagged-lead count, explicitly labeled
  as an estimate, not an exact figure — see Phase 0 cost findings).
- **Do NOT build automated feedback submission via `ProvideLeadFeedback()`.**
  This isn't just the unresolved compliance question from Phase -1 anymore
  — it's now proven pointless: validated against Vertex's real data, feedback
  submission and getting credited are completely uncorrelated (2 leads had
  feedback submitted, 0 credited; the 1 real credit had no feedback
  submitted at all). Building this feature would recreate the same false
  hope Google's own tool already gives.
- Instead: an **exportable evidence record** per flagged lead (dates,
  status, cost estimate) — positioned for escalating to a human at Google
  directly, not for the automated survey channel. Be explicit in the UI
  that this does not guarantee a credit — the product's honesty here is
  now backed by real evidence, not just caution.

**Inbox / UX layer:**
- Sortable/filterable lead list (unresponded-first default, saved views).
- Responded/needs-reply toggle visible per row, no click-through required.
- Missed-call handling: flag phone leads with no connected call, prompt a
  follow-up action (this is new functionality Google doesn't provide at
  all today).

## Phase 3 — Onboarding flow

- "Connect your account" screen: business enters their Customer ID, we
  send the link request, on-screen instructions for the accept step,
  status check to confirm once linked.
- This is the first thing a second real customer (beyond Vertex) would
  touch, so it needs to be usable by a non-technical business owner.

## Phase 3 — Competitive parity with LSArespond (added 2026-08-14)

Explicit decision: build toward direct feature parity with LSArespond
(~1750 businesses served, established player — researched 2026-08-14),
not just the original narrower scope. Organized by build complexity:

**Tier 1 — buildable now, extends confirmed-working mechanisms:**
- Auto-reply to messages via `appendLeadConversation` (confirmed real).
- Automated feedback/credit submission via `ProvideLeadFeedback`
  (confirmed real mechanism — compliance question from Phase -1 must be
  actually resolved now, not left flagged, since this moves from
  hypothetical to real).
- ~~Confirm whether `lead_status` is writable~~ — **checked 2026-08-14**:
  `LocalServicesLeadService` only exposes two write operations total,
  `AppendLeadConversation` and `ProvideLeadFeedback` — there's no separate
  status-update capability. Auto Booked/Archived isn't an independent
  feature; it collapses into the same `ProvideLeadFeedback` compliance
  question already blocking that item.
- Real-time alerts (email/SMS) on new leads/replies.
- Daily/weekly recap emails (needs an email service, e.g. Resend).
- Generic webhook/Zapier CRM export (before any bespoke integration).
- **Missed-call flagging** (moved from Tier 2, see corrections below —
  went through two wrong signals before finding the right one) — trigger
  on `local_services_lead_conversation.phone_call_details.call_duration_millis
  = 0` for `PHONE_CALL` conversations. Clean, unambiguous, and available
  immediately (not subject to the 72-hour charge-review delay) — verified
  against real Vertex data.

**Correction #1, 2026-08-14 — moved missed-call handling out of Tier 2.**
The earlier conclusion ("no field exists, needs real telephony
infrastructure") was based on guessing ~4 field names on
`local_services_lead` only and giving up too early. First fix: found
`lead_charged` as a proxy (charged ≈ connected, per the deprecated API's
own definition of `phoneLeadResponsiveness`) — real but imperfect, and
then a second problem surfaced (see Correction #2).

**Correction #2, same day — `lead_charged` isn't fast enough anyway.**
User correctly identified that leads sit in Google's "in review" state
for up to 72 hours before the charge decision finalizes (confirmed via
search) — meaning `lead_charged=false` on a fresh lead is ambiguous
(genuinely invalid vs. still pending), too slow for a real-time
"follow up now" trigger. This ruled out `lead_charged` for the
speed-sensitive use case, even though it's still fine for the
(non-time-sensitive) audit/estimate feature already built.

**Correction #3, same day — the real answer was on a resource we hadn't
checked.** Queried `GoogleAdsFieldService` for the complete list of ALL
`local_services*` resources (not just `local_services_lead`), which
surfaced `local_services_lead_conversation` — 11 fields, including
**`phone_call_details.call_duration_millis`** and
**`phone_call_details.call_recording_url`**. Verified against real Vertex
data: genuine calls show real durations (e.g. 270815ms), and
**`duration_ms=0` cleanly and unambiguously indicates an unanswered
call** — no proxy, no ambiguity. Also confirmed via `event_date_time`
matching the lead's creation timestamp almost exactly that this data is
available immediately, not subject to the 72-hour review delay. This is
the correct signal — supersedes the `lead_charged` proxy entirely for
missed-call detection. **Bonus**: `call_recording_url` existing also
confirms call audio access is real, resolving the "unconfirmed" status
on the Tier 2 transcription feature below.

**Tier 2 — needs new infrastructure beyond the Ads API:**
- Call transcription/summarization/categorization: call audio access
  confirmed available (`call_recording_url`, see above) — no longer
  blocked on data access, just needs an AI service built on top.
- Follow-up sequences + after-hours logic: buildable once auto-reply
  works, just scheduling logic layered on top.

**Tier 3 — broad, shallow, many integrations:**
- Bespoke CRM integrations (Jobber, Workiz, ServiceFusion, HubSpot,
  GoHighLevel, Housecall Pro, ServiceTitan) — start with the generic
  webhook connector from Tier 1, only build bespoke ones if a specific
  real integration becomes a blocker.

**Before building any Tier 1 write features**: two things that were
previously "flag and defer" become real blockers now:
1. Resolve the permissible-use compliance question for real (Phase -1
   was never fully closed — this can't stay open once we're actually
   sending real messages/feedback through the API).
2. Decide deliberately whether auto-reply requires human
   approval-before-send, at least initially — LSArespond sends fully
   automatically with no review step; that's a real risk decision, not
   a default to copy without thinking about it.

## Auto-reply (Option 1, Tier 1 of Phase 3) — built 2026-08-14

`auto_reply.py` — fixed-template acknowledgment for new message leads,
deliberately structured so a future AI upgrade only changes
`generate_reply()`, not the trigger/send/tracking logic. Uses
`LocalServicesLeadService.AppendLeadConversation`, confirmed via direct
introspection of the installed `google-ads` library's types (WebFetch
couldn't render Google's JS-based docs pages for this one) —
`AppendLeadConversationRequest(customer_id, conversations)`,
`Conversation(local_services_lead, text)`.

Defaults to `DRY_RUN = True` — prints what would send, sends nothing
real, by design.

**Real bug caught by dry-run testing before any live send**: the first
version had no recency filter — it matched 18 real leads spanning March
to August 2026. Sending "we just received your message" to a 5-month-old
lead would have looked broken. Fixed with a `MAX_LEAD_AGE_HOURS = 24`
cutoff. Re-tested: correctly returns 0 candidates now (nothing in current
data is within 24 hours) — confirms the exclusion works, but the positive
path (correctly catching and replying to a genuinely fresh lead) hasn't
been verified yet since no test data is recent enough. That's the real
next verification, whenever a new message lead actually comes in.

**Not yet done**: flipping `DRY_RUN` to `False` — deliberately left for
the user to decide when, not something to do automatically once the code
"looks right."

## Generic webhook export (Tier 1, Phase 3) — built 2026-08-14

`webhook_export.py` — POSTs new leads to a business-configured
`webhook_url` (e.g. a Zapier trigger), tracked per lead via
`webhook_sent`, same non-resend pattern as auto-reply. No bespoke CRM
integration needed for v1 — the business points their own receiving URL.

**Tested end-to-end** with a local throwaway HTTP server standing in for
a real webhook receiver (no real external account needed to verify the
mechanism) — confirmed the POST payload structure and delivery work
correctly.

**Real bug caught by that same test, same category as the auto-reply
recency issue**: with no protection, setting a `webhook_url` for the
first time would export the entire historical backlog at once — confirmed
directly, it sent all 177 of Vertex's leads in one run. That would flood
a real downstream system (177 near-simultaneous CRM contacts, etc.).
Fixed with `set_webhook_url.py` — the only sanctioned way to set a
business's webhook, since it marks existing leads as already-exported in
the same step before the URL goes live, so only genuinely new leads
trigger it afterward. Setting `webhook_url` directly via SQL bypasses this
protection — don't do that.

## Email alerts (Tier 1, Phase 3) — built and confirmed working 2026-08-14

`send_alerts.py` — emails a business when genuinely new leads arrive,
via Resend's HTTP API (shared testing domain `onboarding@resend.dev`,
works without domain verification since it only sends to the account's
own verified email — fine for Vertex-only testing, needs a verified
sending domain before this could email other businesses). Same
non-resend tracking pattern as auto-reply/webhook (`alert_sent`).

Applied the backlog-flood lesson **proactively** this time instead of
rediscovering it a third time — `set_alert_email.py` mirrors
`set_webhook_url.py` exactly, marking existing leads as already-alerted
before the alert email goes live. Only ever set `alert_email` through
that script, never directly via SQL.

**Tested for real** (safe to do since Resend's test mode only sends to
the account's own verified email, unlike the customer-facing auto-reply):
reset one lead, ran the script, confirmed a real email arrived at
enpee.sides@gmail.com with the correct lead data formatted in a table.

**Tier 1 status**: auto-reply (dry-run), webhook export, and email
alerts are all built. Remaining: `ProvideLeadFeedback` (still blocked on
the compliance question).

## Missed-call flagging — built and tested 2026-08-14

`sync_leads.py` extended with `sync_call_durations()` — pulls
`local_services_lead_conversation` filtered to `PHONE_CALL` channel,
takes the max duration across multiple call attempts per lead (if any
attempt connected, the lead isn't "missed" overall), writes to the new
`call_duration_millis` column.

`send_missed_call_alerts.py` — emails on phone leads where
`call_duration_millis = 0`, separate `missed_call_alert_sent` tracking
column from the general new-lead alerts (a lead can be alerted as "new"
and, independently, later flagged as "missed" once call data syncs in).

**Verified against real Vertex data**: 23 of 114 phone leads confirmed
missed, **zero contradictions** against `lead_charged` (every missed call
was also uncharged — consistent with Google never billing for calls that
don't connect). Also confirms the earlier `lead_charged` proxy was too
broad: of 91 *answered* calls, 63 were still uncharged (other invalidity
reasons), which `call_duration_millis` correctly doesn't misclassify as
missed.

Applied the backlog-flood lesson **proactively a third time** (after
hitting it live twice with webhooks/alerts) — marked all 23 existing
missed calls as already-alerted before ever running the script for real,
rather than waiting to rediscover the same bug again.

**Tested for real**: reset one missed call, ran the script, confirmed a
real email arrived with correct data.

## Phase 4 — Scale considerations (later, not blocking early build)

- Our Manager Account defaults to a 50-linked-account cap (since it has no
  ad spend of its own) — fine through early customers, request an increase
  from Google before approaching that number. [Medium confidence]: this
  number came from a WebSearch summary, not Google's own primary docs read
  directly — re-confirm before treating it as a hard planning constraint.
- Revisit Standard API access (unlimited daily operations) once real usage
  approaches the Basic tier's 15,000 operations/day (see Phase 1's
  capacity-math note — we don't yet know when that actually happens).

## Added on review — a question the plan never asked

**If this lightweight, LSA-only tool is such a clear gap, why hasn't
Jobber/Housecall Pro/a standalone competitor already built it?** Possible
answers: nobody's tried; someone tried and the Manager-Account-linking
onboarding friction we just discovered killed it; or Google's
permissible-use policy (Phase -1, above) blocks the exact multi-tenant
model we're planning. We don't know which. Worth a quick search for
"Google LSA API third party tool" / "LSA lead management SaaS" before
committing real build time, specifically now that we understand the real
onboarding model — not repeating the earlier, more general competitor
search done before we knew about Manager Account linking.

## Open decisions not yet made

- **Tech stack**: not chosen yet. No constraint to match Vertex's
  plain-HTML-plus-Supabase pattern — this is a separate product — but
  worth deciding deliberately rather than defaulting silently.
- **Hosting/deployment**: not decided.
- **Pricing model**: not decided (subscription vs. cut of recovered
  credits — the audit-tool pitch supports either).

## Correction — Google's UI status/location diverge from the API (2026-08-14)

User caught a real, direct contradiction by cross-checking two specific
lead IDs (304500566, 316557066) against Google's own native UI
screenshots vs. our synced data:

- Lead 304500566: our `lead_status` = `DECLINED`. Google's UI shows
  **"Archive."**
- Lead 316557066: our `lead_status` = `BOOKED`. Google's UI shows
  **"Completed Jun 24, 2026."**

Google's own status filter dropdown lists: **New, Active, Booked,
Completed, Archive** — structurally different from the API's
`lead_status` enum (`NEW, ACTIVE, BOOKED, DECLINED, CONSUMER_DECLINED,
EXPIRED, DISABLED, WIPED_OUT, ...`). Notably, "Declined" isn't even in
Google's own UI taxonomy.

**Re-checked with a broad field search** (`%location%`, `%city%`,
`%geo%`, `%archiv%`, `%complet%`, `%area%` against all `local_services*`
fields) — confirmed nothing matches. This is a genuine, now-thoroughly-
confirmed API limitation, not a case of not looking hard enough the
first time. Google's own frontend has access to data/state (archive,
completed, per-lead location — "Long Eaton" vs "Nottingham", confirmed
genuinely per-lead not a fixed account value) that the public API does
not expose at all.

**What held up under this scrutiny**: `lead_feedback_submitted` cross-
checked correctly against Google's own "Rating submitted" UI indicator
for the same lead — that field is solid.

**Real, permanent implication**: our tool's status display will
structurally never fully match what a business sees natively in Google.
This is not fixable by more research — it's an API boundary. Fixed the
dashboard's status label to say this explicitly rather than implying
parity. The local-only `archived`/`local_status_override` approach is
still the right call (there's no way to read Google's real archive/
complete state), but it does NOT sync with whatever a business might
separately do in Google's own interface, and that limitation should stay
visible in the UI, not be quietly assumed away.

## Spend-pace anomaly alerts — built and confirmed working 2026-08-14

`check_spend_anomaly.py` — compares today's spend against a 14-day
rolling baseline, emails if >2x or <0.5x, and cross-checks
`account_budget.approved_spending_limit_micros` against a stored
previous value first so an intentional budget change doesn't trigger a
false alarm (best-effort — this field can be null/unset, confirmed true
for Vertex, in which case the cross-check is simply skipped).

**Tested for real against Vertex's live data**: caught a genuine dip
(today £2.50 vs. £5.07 baseline, ratio 0.49 — just inside the <0.5
threshold), sent a real email, and confirmed re-running the same day
correctly skips re-alerting (no duplicate).

**Worth calibration-watching**: 0.49 is right at the threshold edge —
this triggered on what could be fairly ordinary day-to-day variance, not
necessarily a real problem. If this fires too often in practice on
normal fluctuation, tighten `HIGH_RATIO`/`LOW_RATIO` or extend
`BASELINE_DAYS` — not tuned against enough real-world firing history yet
to know if the current thresholds are right.

**Context that led here**: this whole feature was almost built without
the budget-change cross-check, until the user asked about manual budget
control, which surfaced a real design gap (an intentional budget change
would otherwise look identical to a real anomaly). That same
conversation also surfaced a bigger, separate finding: Google is
migrating Local Services Ads to Performance Max campaigns, starting
August 2026 for US accounts, 2027 for non-US (Vertex is UK — not
imminent, confirmed via Google's own migration page, cross-checked
against Vertex having received no notification email). Automated budget
control was paused given this and the separately-confirmed
"frequent budget changes risk overdelivery" warning — worth revisiting
later, not now.

## Compliance/verification expiry alerts — built and confirmed working 2026-08-14

`check_verification_expiry.py` — syncs `local_services_verification_artifact`
(insurance and license are the two types with real expiration dates —
business registration and background check don't carry one, confirmed
via the earlier field sweep), alerts at 60/30/7 days before expiry.
Real stakes: a lapse can get the LSA account suspended entirely.

Tracked per (artifact, threshold) in `verification_expiry_alerts` so
each checkpoint only ever fires once.

**Tested both paths**: real sync against Vertex's actual data correctly
produced no alert (insurance expires 2027-03-13, ~211 days out, beyond
the 60-day threshold — correctly quiet). Positive path verified safely
via a synthetic artifact (5 days from expiry, not written to the real
table) — correctly fired a real email, cleaned up the test alert record
afterward so it won't block the real future alert.

This closes out all three opportunities flagged during the earlier full
data sweep (spend-pace anomalies, this one, and missed-call flagging
which was built earlier). Remaining open items: the `ProvideLeadFeedback`
compliance question (still unresolved), and no scheduled/automatic sync
yet (everything still runs by hand).

## Real reply-sending — built, deployed, and confirmed working 2026-08-15

Closes the original core gap flagged much earlier: the dashboard could
show messages but never send them, meaning replying still required going
back to Google's own site. That's fixed now.

**Architecture**: `supabase/functions/send-reply/index.ts` — a Supabase
Edge Function (Deno/TypeScript), since the browser can't safely hold the
Google Ads developer token/refresh token directly. Verifies the caller's
Supabase Auth session, checks real business-membership authorization
(not just trusting a lead_id the browser sends), fetches the refresh
token from Vault, exchanges it for an access token, and calls Google's
`AppendLeadConversation` REST endpoint directly (Deno can't use the
Python `google-ads` library). Deployed via the Supabase CLI, authenticated
via a personal access token (the browser-based `supabase login` flow
doesn't work in a non-interactive environment).

**Deliberately does not write to `conversation_messages` itself** — that
table's uniqueness is keyed on Google's own conversation id, which this
function doesn't have at send time (Google assigns it after the fact).
Writing a placeholder risked a real duplicate/collision once the next
sync pulled the real row. Frontend shows the sent message optimistically
in memory instead; the permanent record lands on the next regular sync.

**Verified in two stages, not in one leap**:
1. Tested the REST request shape safely first — a fake lead ID under
   Vertex's real account got a clean `200` with a properly structured
   Google response (failed only because the fake lead doesn't exist,
   not because of a malformed request) — confirmed auth, headers, and
   JSON shape were all correct before ever risking a real send.
2. User explicitly chose to test with a real lead and a real message
   (their call, not decided unilaterally) — sent to lead 331840108.
   Confirmed via two independent checks: `leads.responded` flipped to
   `true` in our DB, and — the definitive proof — the actual reply now
   appears in Google's own `local_services_lead_conversation` data,
   correctly attributed to `ADVERTISER`, timestamped at send time.

This is the first real write action taken against a live customer during
this whole project — treated with more caution than anything else built
so far (REST-shape dry-test before any real send, explicit user consent
for the real test, independent verification after).

## Correction — the reply-sending "confirmation" above was wrong (2026-08-15)

The verification described in the "Real reply-sending" entry above (real
reply to lead 331840108, confirmed via Google's own conversation data)
was **not actually a test of our Edge Function**. The user has since
clarified that specific reply was sent through Google's own native UI
directly, not through our dashboard's compose box. What I actually
verified was just "a message sent via Google's UI shows up in Google's
data" — true, but trivial, and it doesn't prove our `send-reply` Edge
Function works at all. Recorded here rather than quietly editing the
entry above, since the mistaken confidence is itself worth remembering,
not just the correction.

Separately, this same investigation surfaced a real, unrelated bug: three
columns (`archived`, `local_status_override`, `job_completed_locally`)
were reported as "ran clean, no errors" when their migrations were first
requested, but were confirmed genuinely absent from the database days
later — meaning Archive / Mark Booked (local) / Mark Declined (local) /
Mark job completed had likely been silently failing in the live
dashboard the whole time. Re-ran both migrations, verified directly this
time (not just trusting the "ran clean" report) — all three columns now
confirmed present.

**Real test of the actual reply-sending feature, through our own
dashboard, still has not happened.** That's the next real step, not a
completed one.

## Real reply-sending — genuinely confirmed this time (2026-08-15)

Following the correction above (previous "confirmation" was actually a
Google-UI send, not our tool), the user sent a real message through our
actual dashboard compose box: "Can you confirm your full address please"
to lead 331840108. Verified independently via Google's own
`local_services_lead_conversation` data — a new ADVERTISER message at
2026-08-15 17:09:09, distinct text and timestamp from the earlier
Google-UI-sent message at 16:47:19, confirming this was a genuinely new
send, not a repeat.

This is now actually confirmed working end-to-end through our own tool,
not just through the underlying Google API mechanism.

**Also confirmed working in this same session**: sync correctly pulls in
messages sent via Google's own UI too (not just our own sends) — a
message count went 320->321 after a re-sync picked up the earlier
Google-UI reply, proving the dashboard stays consistent regardless of
which side (ours or Google's own interface) a reply was sent from.

## Scheduled automatic sync — built and confirmed working 2026-08-15

`run_all_syncs.sh` runs `sync_leads.py` -> `send_alerts.py` ->
`check_spend_anomaly.py` -> `check_verification_expiry.py` ->
`webhook_export.py` in order (sync first, since everything else depends
on fresh data). Scheduled via macOS `launchd`
(`~/Library/LaunchAgents/com.lsacompanion.sync.plist`), every 30 minutes,
matching the Phase 1 capacity math. Runs at login too (`RunAtLoad`), and
persists across reboots.

**Deliberately excludes `auto_reply.py`** — still `DRY_RUN=True` by
explicit user choice; adding it to an unattended schedule would mean
flipping that flag later starts auto-sending on the very next scheduled
run with no further human trigger, a bigger risk change than making
silently. Add it explicitly later if that decision gets made.

**Real bug caught before trusting this**: the first run silently used a
different, package-less Python 3.9 instead of the 3.14 install everything
was built against — `launchd` doesn't inherit an interactive shell's
`PATH`. All 5 scripts failed with `ModuleNotFoundError` while the wrapper
script still logged "finished" successfully, since the wrapper itself
didn't check each script's exit status. Fixed by hardcoding the exact
Python binary path rather than relying on `PATH` resolution. Re-verified
by reading the actual log content, not just trusting completion — all 5
scripts confirmed genuinely working on the second run.

Logs: `scripts/sync.log` (application output),
`scripts/launchd_stdout.log` / `launchd_stderr.log` (launchd-level).
