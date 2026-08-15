-- Two gaps found in the data sweep: message content was never synced
-- (the dashboard showed metadata but never what the customer actually
-- said), and category_id/service_id (which service was requested) was
-- never captured either.

alter table leads
  add column message_text text,
  add column category_id bigint,
  add column service_id bigint;
