-- The mobile redesign needs real chat bubbles (customer messages on one
-- side, business replies on the other) — message_text on leads is just
-- everything concatenated with no sender info, which can't support that.
-- local_services_lead_conversation.participant_type (CONSUMER vs
-- business) was available all along, just never captured. This table
-- stores each message as its own row instead.

create table conversation_messages (
  id uuid primary key default gen_random_uuid(),
  business_id uuid not null references businesses(id) on delete cascade,
  lead_id uuid not null references leads(id) on delete cascade,
  google_conversation_id bigint not null,
  participant_type text not null,
  channel text not null,
  text text,
  event_date_time timestamptz,
  synced_at timestamptz not null default now(),
  unique (business_id, google_conversation_id)
);

alter table conversation_messages enable row level security;

create policy "members can access their business's conversation messages"
  on conversation_messages for all
  using (
    exists (
      select 1 from business_members
      where business_members.business_id = conversation_messages.business_id
      and business_members.user_id = auth.uid()
    )
  );

create index conversation_messages_lead_id_idx on conversation_messages(lead_id);
