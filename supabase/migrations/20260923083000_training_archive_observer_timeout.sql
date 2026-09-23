-- The retention observer updates every eligible candidate during each scheduled preview.
-- Production has >1,000 candidates and the PostgREST default 8s statement timeout
-- interrupted the preview before the seven-day grace gate could be audited.
-- Scope the longer budget to this maintenance RPC only; the 168h grace,
-- latest-two/pin protection and all eligibility checks remain unchanged.
alter function public.training_archive_retention_observe(integer, integer)
  set statement_timeout = '30s';
