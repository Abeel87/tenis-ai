-- SECURITY DEFINER identity helpers are exposed to authenticated clients because
-- RLS policies call them. Keep that contract, but prevent a signed-in user from
-- probing another profile's admin/staff/community state by supplying its UUID.
-- service_role remains allowed for trusted server-side diagnostics.

create or replace function public.can_access_community(check_uid uuid default auth.uid())
returns boolean
language sql
stable
security definer
set search_path = public, auth
as $$
  select (
    coalesce(auth.role(), '') = 'service_role'
    or (auth.uid() is not null and check_uid = auth.uid())
  )
  and exists (
    select 1
    from public.profiles p
    where p.id = check_uid
      and p.age_confirmed_at is not null
      and p.community_access = true
      and p.banned_at is null
  );
$$;

create or replace function public.is_admin(check_uid uuid default auth.uid())
returns boolean
language sql
stable
security definer
set search_path = public, auth
as $$
  select (
    coalesce(auth.role(), '') = 'service_role'
    or (auth.uid() is not null and check_uid = auth.uid())
  )
  and exists (
    select 1
    from public.profiles p
    where p.id = check_uid
      and p.role = 'admin'
      and p.banned_at is null
  );
$$;

create or replace function public.is_staff(check_uid uuid default auth.uid())
returns boolean
language sql
stable
security definer
set search_path = public, auth
as $$
  select (
    coalesce(auth.role(), '') = 'service_role'
    or (auth.uid() is not null and check_uid = auth.uid())
  )
  and exists (
    select 1
    from public.profiles p
    where p.id = check_uid
      and p.role in ('admin', 'moderator')
      and p.banned_at is null
  );
$$;

-- Do not rely on PostgreSQL's default function EXECUTE grant to PUBLIC.
revoke all on function public.can_access_community(uuid) from public;
revoke all on function public.is_admin(uuid) from public;
revoke all on function public.is_staff(uuid) from public;

grant execute on function public.can_access_community(uuid) to authenticated, service_role;
grant execute on function public.is_admin(uuid) to authenticated, service_role;
grant execute on function public.is_staff(uuid) to authenticated, service_role;
