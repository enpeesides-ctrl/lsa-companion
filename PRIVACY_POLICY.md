# Privacy Policy — LSA Companion

**Status: DRAFT — not reviewed by a solicitor, not published, not legally
binding yet.** Prepared with AI assistance based on the product's actual
current schema and infrastructure. Before this is shown to any real
business as a binding document — even Vertex — have it reviewed by a
qualified solicitor. Several items below are marked `[TO CONFIRM]` or
`[TO BUILD]` because they're either facts only you can supply, or
commitments this policy would make that the product doesn't technically
enforce yet. Do not remove those markers without actually resolving them.

Last drafted: 2026-08-20.

## 1. Who we are

LSA Companion is operated by **[YOUR FULL LEGAL NAME] `[TO CONFIRM]`**,
trading as "LSA Companion," a sole trader with no separate registered
company at this stage. Contact for any privacy matter:
**enpee.sides@gmail.com**.

## 2. What data we process, and in what role

This product has two distinct kinds of personal data, with two
different legal relationships attached. Conflating them would misstate
our actual obligations, so they're kept separate here.

### 2a. Business account data — we are the **data controller**

Data about the businesses (and their staff) who use LSA Companion
directly:

- Login email address (Supabase Auth)
- Business name and Google Ads Customer ID
- Business settings: business hours, alert email, webhook URL if
  configured
- The business's own Google Local Services Ads verification/compliance
  status (e.g. insurance coverage amount and expiry) — this describes
  the business itself, not their customers

We process this to provide the service under contract with the
business.

### 2b. End-customer lead data — we are a **data processor**

Data about the *business's own customers* — the people who contacted a
business (e.g. Vertex Property Care) through Google Local Services Ads.
This is not our data to decide the purpose of; we process it strictly
on the business's instructions, as their processor. The business
remains the data controller for their own customers' data.

What's actually stored (confirmed directly against the current
database schema, not estimated):

- Contact phone number
- Message content / conversation text exchanged with the business
- Call duration (used only to detect missed calls, not for content)
- Lead type, status, and timestamps, sourced directly from Google's
  Local Services Ads platform via the Google Ads API — **we never
  collect this directly from the end customer**; it is synced from
  Google, where the end customer originally submitted it to the
  business.

We never sell this data, use it for our own marketing, or use it for
any purpose beyond operating the service for the business that
received the lead.

## 3. Legal basis for processing

- **Business account data**: performance of a contract (providing the
  service you've signed up for).
- **End-customer lead data**: we process this under Article 28-style
  processor instructions from the business. Our lawful basis derives
  from the business's own lawful basis with their customer (typically
  legitimate interest or contract — e.g. responding to a quote
  enquiry), not a separate basis of our own.

## 4. Who else processes this data (sub-processors)

- **Supabase** (database, authentication, backend functions) — hosted
  in the EU (`eu-west-1`, Ireland), confirmed directly against the live
  project configuration.
- **Google LLC** — the original source of all end-customer lead data,
  via the Google Ads API. Google's own privacy terms govern their side
  of this.
- **Resend** — used to send email alerts (new-lead notifications,
  spend/compliance alerts) to the business. These emails can contain
  lead contact details. `[TO CONFIRM]`: Resend's data residency and
  whether an adequate international-transfer mechanism (e.g. SCCs) is
  in place has not been independently verified — check Resend's own
  DPA/subprocessor terms before treating this as settled.
- **GitHub Pages** — hosts only the static dashboard frontend
  (HTML/JS/CSS). It never receives or stores lead data itself; the
  dashboard talks directly to Supabase from the browser.

## 5. Where data is hosted

Primary database and backend: Supabase, `eu-west-1` (Ireland) —
confirmed directly, not assumed.

## 6. Data retention

**Policy commitment**: end-customer lead data is retained for **90
days after a business disconnects** from LSA Companion (`businesses.status
= 'disconnected'`), then permanently deleted.

**Enforced as of 2026-08-20.** A daily job (`purge_disconnected_business_data()`,
scheduled via Supabase Cron at 03:00 UTC) deletes `leads` rows — and
their associated messages, via cascade — for any business disconnected
more than 90 days. The business's own account row is not deleted, only
its former customers' lead data. Verified with synthetic test data
(never real customer data): a business disconnected 100 days ago had
its lead correctly purged (cascade-deleting the message too), a
business disconnected only 10 days ago was correctly left untouched,
and an audit record (`data_retention_purges`) was correctly created for
the purge and correctly absent for the non-purge. Real Vertex data
confirmed untouched throughout.

## 7. Security measures

- Row-level security (RLS) on every table holding business or lead
  data, scoped to `business_members` — a user can only ever see data
  for businesses they belong to.
- Google account refresh tokens are never stored in plain text —
  encrypted at rest via Supabase Vault, accessed only through a
  locked-down `security definer` function.
- All traffic over HTTPS.
- No personal data is placed in URL query strings or logs by design.

## 8. Data subject rights

If you are an end customer who contacted a business via Google Local
Services Ads, and that business uses LSA Companion: the business you
contacted is the correct first point of contact for any request to
access, correct, or delete your data, since they are the data
controller. If you contact us directly, we will support that request
and relay/action it in coordination with the relevant business, as
required of a processor.

If you are a business using LSA Companion directly: contact
enpee.sides@gmail.com for any request regarding your own account data.

## 9. International transfers

Primary hosting (Supabase) is within the EU. Google (source data) and
Resend (email delivery) are separate processors with their own
international-transfer position — see section 4's `[TO CONFIRM]` note
on Resend specifically before relying on this section as complete.

## 10. Changes to this policy

This is a draft. A real version history will be added once this
document is actually reviewed and published.
