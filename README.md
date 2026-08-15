# LSA Companion (working name)

A standalone companion tool for **Google Local Services Ads (LSA)** — usable
by any business running LSA, not tied to one company's CRM.

## The problem

Google's own LSA lead inbox is hard to work with day to day:
- Poor lead ordering — hard to find what you need.
- No visible "responded / not responded" status without opening each lead.
- No way to connect leads to your own CRM or other tools (optional, later — see Scope).
- Since August 2024, Google removed manual lead disputes and replaced them
  with an automated credit system — there's no real appeal path for most
  denied credits, only a "Lead Feedback Survey" that isn't a guaranteed fix.
- **Validated against Vertex's real account data, 2026-08-14**: submitting
  the Lead Feedback Survey and getting credited appear completely
  uncorrelated. 2 leads had feedback submitted and were never credited;
  the one lead that WAS credited in 5.5 months of history had no feedback
  submitted at all — it was Google's own automated system acting
  independently. Manually flagging leads through Google's own UI is, in
  practice, a dead end — this isn't a perception problem, it's a confirmed
  pattern in real data.

## Who it's for

Any business using Google LSA. First real test user: **Vertex Property
Care** (window/exterior cleaning, Nottingham UK) — but the tool itself is
general-purpose, not built against Vertex's own CRM/Portal (that's a
separate, unrelated codebase at `~/businesses/vertex-property-care/`).

## Core scope (v1 — building both together)

1. **Spend/credit audit** — track charged leads, flag ones that look
   invalid, and **quantify the real cost** with a defensible number (not
   an exact per-lead figure — cost isn't attributable per-lead via the
   API, so this is an estimate: average cost-per-lead applied to flagged,
   uncredited, declined-and-charged leads). Given the validated finding
   above, this does **not** promise "submit feedback and get credited" —
   that path is proven ineffective. Instead: surface the real number, and
   build a clean, exportable evidence record usable for escalating to a
   human at Google directly, since the automated survey channel isn't it.
2. **Inbox / UX layer** — better sorting and filtering, a visible
   responded/needs-reply status per lead (not buried behind a click-through),
   and a way to flag/follow up on **unanswered calls** specifically (answered
   calls are handled live on the phone — nothing for this tool to do there;
   unanswered calls need a deliberate follow-up mechanism).
3. **Messages are the primary lead type this tool handles day to day** —
   calls are mostly a "did it get answered, yes/no" concern, not a live
   conversation the tool manages.

## Explicitly out of scope for v1

- Direct CRM integration (e.g. syncing into Vertex's or anyone else's CRM)
  — optional future add-on, not core.
- Any UI/branding decisions — working name only, not finalized.

## Known open technical risk

Google's Ads API exposes a `local_services_lead` resource, so this is
buildable against real data. [UNVERIFIED]: exact approval requirements for
pulling *other businesses'* lead data (needed since this is multi-tenant,
not single-business) haven't been confirmed — check before committing to
an architecture that assumes easy API access.
