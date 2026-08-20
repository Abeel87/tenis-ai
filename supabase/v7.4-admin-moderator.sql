-- Tenis AI v7.4 — Admin / Moderator
-- Uruchom RAZ w Supabase SQL Editor.
-- Bez service_role w przeglądarce: wszystkie akcje administracyjne przechodzą przez SECURITY DEFINER RPC.

begin;

-- 1) Bootstrap jedynego właściciela aplikacji.
-- Username jest unikalny case-insensitive w profiles.
do $$
declare n integer;
begin
  update public.profiles
     set role = 'admin',
         community_access = true
   where lower(trim(username)) = 'abeelgod'
     and banned_at is null;

  get diagnostics n = row_count;
  if n <> 1 then
    raise exception 'Bootstrap admina przerwany: oczekiwano dokładnie 1 profilu AbeelGoD, znaleziono %.', n;
  end if;
end $$;

-- 2) Audit działań administracyjnych.
create table if not exists public.community_admin_audit (
  id uuid primary key default gen_random_uuid(),
  actor_id uuid not null references public.profiles(id) on delete restrict,
  target_id uuid references public.profiles(id) on delete set null,
  action text not null,
  detail jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

alter table public.community_admin_audit enable row level security;
revoke all on public.community_admin_audit from anon, authenticated;
grant all on public.community_admin_audit to service_role;

-- 3) Helpery ról.
create or replace function public.is_admin(check_uid uuid default auth.uid())
returns boolean
language sql
stable
security definer
set search_path = public, auth
as $$
  select exists (
    select 1 from public.profiles p
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
  select exists (
    select 1 from public.profiles p
    where p.id = check_uid
      and p.role in ('admin','moderator')
      and p.banned_at is null
  );
$$;

revoke all on function public.is_admin(uuid) from public;
revoke all on function public.is_staff(uuid) from public;
grant execute on function public.is_admin(uuid) to authenticated, service_role;
grant execute on function public.is_staff(uuid) to authenticated, service_role;

-- 4) Lista użytkowników dla panelu Admin/Moderator.
create or replace function public.staff_member_list()
returns jsonb
language plpgsql
stable
security definer
set search_path = public, auth
as $$
declare uid uuid := auth.uid();
declare payload jsonb;
begin
  if uid is null or not public.is_staff(uid) then
    raise exception 'Brak uprawnień moderatorskich.';
  end if;

  select coalesce(
    jsonb_agg(
      jsonb_build_object(
        'id', p.id,
        'username', p.username,
        'avatar_url', p.avatar_url,
        'role', p.role,
        'community_access', p.community_access,
        'age_confirmed_at', p.age_confirmed_at,
        'banned_at', p.banned_at,
        'last_seen_at', p.last_seen_at,
        'created_at', p.created_at,
        'request_status', r.status,
        'requested_at', r.requested_at
      )
      order by
        case when r.status='pending' then 0 else 1 end,
        case p.role when 'admin' then 0 when 'moderator' then 1 else 2 end,
        p.created_at desc
    ),
    '[]'::jsonb
  )
  into payload
  from public.profiles p
  left join public.community_access_requests r on r.user_id = p.id;

  return payload;
end;
$$;

revoke all on function public.staff_member_list() from public;
grant execute on function public.staff_member_list() to authenticated, service_role;

-- 5) Tylko ADMIN może nadawać/odbierać moderatora.
create or replace function public.admin_set_role(target_uid uuid, next_role text)
returns boolean
language plpgsql
security definer
set search_path = public, auth
as $$
declare uid uuid := auth.uid();
declare current_role text;
begin
  if uid is null or not public.is_admin(uid) then
    raise exception 'Tylko administrator może zmieniać role.';
  end if;

  next_role := lower(trim(next_role));
  if next_role not in ('user','moderator') then
    raise exception 'Dozwolone role: user, moderator.';
  end if;

  if target_uid = uid then
    raise exception 'Nie możesz zmienić własnej roli administratora.';
  end if;

  select role into current_role
  from public.profiles
  where id = target_uid
  for update;

  if current_role is null then
    raise exception 'Nie znaleziono użytkownika.';
  end if;

  if current_role = 'admin' then
    raise exception 'Nie można zmieniać roli innego administratora z tego panelu.';
  end if;

  update public.profiles
     set role = next_role
   where id = target_uid;

  insert into public.community_admin_audit(actor_id,target_id,action,detail)
  values(uid,target_uid,'set_role',jsonb_build_object('from',current_role,'to',next_role));

  return true;
end;
$$;

revoke all on function public.admin_set_role(uuid,text) from public;
grant execute on function public.admin_set_role(uuid,text) to authenticated, service_role;

-- 6) Admin i moderator mogą zatwierdzać dostęp.
-- Moderator nie może zmieniać dostępu adminowi/moderatorowi.
create or replace function public.staff_review_access(target_uid uuid, decision text)
returns boolean
language plpgsql
security definer
set search_path = public, auth
as $$
declare uid uuid := auth.uid();
declare actor_role text;
declare target_role text;
declare allow_access boolean;
begin
  if uid is null or not public.is_staff(uid) then
    raise exception 'Brak uprawnień moderatorskich.';
  end if;

  decision := lower(trim(decision));
  if decision not in ('approve','reject') then
    raise exception 'Dozwolone decyzje: approve, reject.';
  end if;

  select role into actor_role from public.profiles where id=uid;
  select role into target_role from public.profiles where id=target_uid for update;

  if target_role is null then
    raise exception 'Nie znaleziono użytkownika.';
  end if;

  if actor_role='moderator' and target_role in ('admin','moderator') then
    raise exception 'Moderator nie może zmieniać dostępu członków zespołu.';
  end if;

  if target_uid=uid then
    raise exception 'Nie możesz zmienić własnego dostępu z panelu.';
  end if;

  allow_access := decision='approve';

  update public.profiles
     set community_access = allow_access
   where id = target_uid;

  insert into public.community_access_requests(user_id,requested_at,status,reviewed_at,reviewed_by)
  values(
    target_uid,
    now(),
    case when allow_access then 'approved' else 'rejected' end,
    now(),
    uid
  )
  on conflict (user_id) do update
    set status = excluded.status,
        reviewed_at = excluded.reviewed_at,
        reviewed_by = excluded.reviewed_by;

  insert into public.community_admin_audit(actor_id,target_id,action,detail)
  values(uid,target_uid,'review_access',jsonb_build_object('decision',decision));

  return true;
end;
$$;

revoke all on function public.staff_review_access(uuid,text) from public;
grant execute on function public.staff_review_access(uuid,text) to authenticated, service_role;

-- 7) Ban/unban.
-- Moderator może blokować tylko zwykłych userów; admin może blokować user/moderator.
-- Administrator nie może zablokować siebie ani innego administratora.
create or replace function public.staff_set_ban(target_uid uuid, should_ban boolean)
returns boolean
language plpgsql
security definer
set search_path = public, auth
as $$
declare uid uuid := auth.uid();
declare actor_role text;
declare target_role text;
begin
  if uid is null or not public.is_staff(uid) then
    raise exception 'Brak uprawnień moderatorskich.';
  end if;

  if target_uid=uid then
    raise exception 'Nie możesz zablokować własnego konta.';
  end if;

  select role into actor_role from public.profiles where id=uid;
  select role into target_role from public.profiles where id=target_uid for update;

  if target_role is null then
    raise exception 'Nie znaleziono użytkownika.';
  end if;

  if target_role='admin' then
    raise exception 'Konta administratora nie można blokować z panelu.';
  end if;

  if actor_role='moderator' and target_role<>'user' then
    raise exception 'Moderator może blokować tylko zwykłych użytkowników.';
  end if;

  update public.profiles
     set banned_at = case when should_ban then now() else null end,
         community_access = case when should_ban then false else community_access end
   where id = target_uid;

  insert into public.community_admin_audit(actor_id,target_id,action,detail)
  values(uid,target_uid,'set_ban',jsonb_build_object('banned',should_ban));

  return true;
end;
$$;

revoke all on function public.staff_set_ban(uuid,boolean) from public;
grant execute on function public.staff_set_ban(uuid,boolean) to authenticated, service_role;

commit;
