-- Confirmed real problem: lead_status stays 'BOOKED' at the API level
-- forever, even after Google's own UI shows the job as "Completed" —
-- there is no API field for completion (confirmed via broad field
-- search). All 4 of Vertex's current BOOKED leads are 46-73 days old,
-- meaning the "Booked" tab was showing stale, likely-finished jobs.
-- This has to be tracked locally since Google won't tell us.

alter table leads
  add column job_completed_locally boolean not null default false;
