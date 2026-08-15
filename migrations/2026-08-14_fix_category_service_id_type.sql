-- category_id turned out to be a descriptive string (e.g.
-- "xcat:service_area_business_window_cleaner"), not numeric as assumed
-- when the columns were first created. Fixing both to text — safer to
-- match service_id too rather than assume it's numeric and hit the same
-- error a second time.

alter table leads
  alter column category_id type text,
  alter column service_id type text;
