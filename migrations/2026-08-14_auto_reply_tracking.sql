alter table leads
  add column auto_reply_sent boolean not null default false,
  add column auto_reply_sent_at timestamptz;
