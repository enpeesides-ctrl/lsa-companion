-- Real gap flagged during an earlier review and never fixed: marking a
-- lead "Booked" in the dashboard never captured when the job is
-- actually scheduled. Adds a plain date field for that, independent of
-- Google's own lead_status/local_status_override tracking.

alter table leads add column if not exists booked_job_date date;
