-- Data model fix before building status actions: lead_status stays
-- Google's real, synced, read-only status (sync_leads.py overwrites it
-- every run). These two new columns are purely local and never touched
-- by sync, so they survive re-syncs correctly.

alter table leads
  add column archived boolean not null default false,
  add column local_status_override text;
