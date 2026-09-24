-- Preparing a grace-ready batch re-runs the retention observer and checks
-- physical object references. At >1,000 candidates the PostgREST 8s timeout
-- aborts the transaction before any apply audit or deletion is committed.
-- Scope the same bounded 30s budget already used by the observer to this
-- function only. All grace, pin, latest-two and physical-size guards remain.
alter function public.training_archive_gc_prepare(bigint, integer, text, integer, integer, integer)
  set statement_timeout = '30s';
