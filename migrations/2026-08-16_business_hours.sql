-- Business hours, for after-hours auto-reply logic. Deliberately simple
-- for v1: one start/end hour, assumed same every day — not per-weekday,
-- not multi-timezone. Fine for Vertex (single UK-based business); would
-- need extending before this could serve businesses in different
-- timezones or with day-specific hours.

alter table businesses
  add column business_hours_start int not null default 8,
  add column business_hours_end int not null default 18;
