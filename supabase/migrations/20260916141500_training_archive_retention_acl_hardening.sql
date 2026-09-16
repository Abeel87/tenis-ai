-- Harden direct privileges for retention metadata created by #353.
-- Supabase default privileges may grant service_role full table/sequence access.
-- The SECURITY DEFINER observer writes as its owner; direct service_role access
-- to these metadata tables is intentionally read-only.

revoke all on table public.training_archive_gc_candidates
  from service_role;
grant select on table public.training_archive_gc_candidates
  to service_role;

revoke all on table public.training_archive_retention_audit
  from service_role;
grant select on table public.training_archive_retention_audit
  to service_role;

-- No browser or service role needs direct sequence access. The owner-backed
-- SECURITY DEFINER observer can allocate identity values without these grants.
revoke all on sequence public.training_archive_retention_audit_observation_id_seq
  from public, anon, authenticated, service_role;
