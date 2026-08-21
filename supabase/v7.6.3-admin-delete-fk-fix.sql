-- Tenis AI v7.6.3 — admin delete FK hardening
-- OPTIONAL / run once in Supabase SQL Editor.
begin;

alter table public.community_access_requests
  drop constraint if exists community_access_requests_reviewed_by_fkey;

alter table public.community_access_requests
  add constraint community_access_requests_reviewed_by_fkey
  foreign key (reviewed_by)
  references public.profiles(id)
  on delete set null;

commit;
