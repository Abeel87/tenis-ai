
-- Tenis AI v6.6 — Community Security migration
-- Run ONCE in Supabase SQL Editor before deploying the v6.6 frontend.
-- Safe to re-run: the "existing testers" auto-approval executes only once.
-- IMPORTANT: this migration does NOT verify identity documents.
-- age_confirmed_at means only that the signed-in user declared they are 18+.

begin;

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------------
-- 1) Security state on profiles
-- ---------------------------------------------------------------------------
alter table public.profiles add column if not exists age_confirmed_at timestamptz;
alter table public.profiles add column if not exists community_access boolean not null default false;
alter table public.profiles add column if not exists role text not null default 'user';
alter table public.profiles add column if not exists banned_at timestamptz;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'profiles_role_check'
      and conrelid = 'public.profiles'::regclass
  ) then
    alter table public.profiles
      add constraint profiles_role_check check (role in ('user','moderator','admin'));
  end if;
end $$;

-- Migration marker: approve only accounts that already existed when v6.6 is first installed.
create table if not exists public.app_migrations (
  key text primary key,
  applied_at timestamptz not null default now()
);
revoke all on public.app_migrations from anon, authenticated;

do $$
begin
  if not exists (select 1 from public.app_migrations where key='v6.6_existing_testers_access') then
    update public.profiles set community_access = true;
    insert into public.app_migrations(key) values ('v6.6_existing_testers_access');
  end if;
end $$;

-- ---------------------------------------------------------------------------
-- 2) Access helpers. Users cannot grant themselves community_access/roles.
-- ---------------------------------------------------------------------------
create or replace function public.can_access_community(check_uid uuid default auth.uid())
returns boolean
language sql
stable
security definer
set search_path = public, auth
as $$
  select exists (
    select 1
    from public.profiles p
    where p.id = check_uid
      and p.age_confirmed_at is not null
      and p.community_access = true
      and p.banned_at is null
  );
$$;

revoke all on function public.can_access_community(uuid) from public;
grant execute on function public.can_access_community(uuid) to authenticated, service_role;

create or replace function public.confirm_age_18()
returns boolean
language plpgsql
security definer
set search_path = public, auth
as $$
declare uid uuid := auth.uid();
begin
  if uid is null then
    raise exception 'Musisz być zalogowany.';
  end if;

  update public.profiles
     set age_confirmed_at = coalesce(age_confirmed_at, now())
   where id = uid;

  if not found then
    raise exception 'Nie znaleziono profilu.';
  end if;

  return true;
end;
$$;

revoke all on function public.confirm_age_18() from public;
grant execute on function public.confirm_age_18() to authenticated, service_role;

-- Public page receives only three aggregate numbers, never member identities.
create or replace function public.community_public_stats()
returns jsonb
language sql
stable
security definer
set search_path = public
as $$
  select jsonb_build_object(
    'registered', (select count(*) from public.profiles),
    'online', (
      select count(*) from public.profiles p
      where p.community_access=true
        and p.age_confirmed_at is not null
        and p.banned_at is null
        and p.last_seen_at >= now() - interval '2 minutes'
    ),
    'coupons_today', (
      select count(*)
      from public.coupons c
      join public.profiles p on p.id=c.user_id
      where c.is_public=true
        and c.created_at >= date_trunc('day', now())
        and p.community_access=true
        and p.age_confirmed_at is not null
        and p.banned_at is null
    )
  );
$$;

revoke all on function public.community_public_stats() from public;
grant execute on function public.community_public_stats() to anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- 3) Access requests: a user may request access, never approve themselves.
-- ---------------------------------------------------------------------------
create table if not exists public.community_access_requests (
  user_id uuid primary key references public.profiles(id) on delete cascade,
  requested_at timestamptz not null default now(),
  status text not null default 'pending' check (status in ('pending','approved','rejected')),
  reviewed_at timestamptz,
  reviewed_by uuid references public.profiles(id)
);

alter table public.community_access_requests enable row level security;

do $$
declare p record;
begin
  for p in select policyname from pg_policies
           where schemaname='public' and tablename='community_access_requests'
  loop
    execute format('drop policy if exists %I on public.community_access_requests', p.policyname);
  end loop;
end $$;

create policy "access request own read"
on public.community_access_requests for select
to authenticated
using (user_id = auth.uid());

create policy "access request own insert"
on public.community_access_requests for insert
to authenticated
with check (user_id = auth.uid() and status='pending' and reviewed_at is null and reviewed_by is null);

revoke all on public.community_access_requests from anon, authenticated;
grant select on public.community_access_requests to authenticated;
grant insert (user_id) on public.community_access_requests to authenticated;
grant all on public.community_access_requests to service_role;

-- ---------------------------------------------------------------------------
-- 4) Chat with DB-level 3 second anti-spam
-- ---------------------------------------------------------------------------
create table if not exists public.community_messages (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  body text not null check (char_length(trim(body)) between 1 and 500),
  reply_to uuid references public.community_messages(id) on delete set null,
  created_at timestamptz not null default now()
);

create index if not exists community_messages_created_idx
  on public.community_messages(created_at desc);
create index if not exists community_messages_user_idx
  on public.community_messages(user_id, created_at desc);

alter table public.community_messages enable row level security;

create or replace function public.community_message_guard()
returns trigger
language plpgsql
security definer
set search_path = public, auth
as $$
declare uid uuid := auth.uid();
declare last_time timestamptz;
begin
  if uid is null or new.user_id <> uid then
    raise exception 'Brak uprawnień.';
  end if;

  if not public.can_access_community(uid) then
    raise exception 'Brak dostępu do społeczności.';
  end if;

  select max(created_at) into last_time
    from public.community_messages
   where user_id = uid;

  if last_time is not null and last_time > now() - interval '3 seconds' then
    raise exception 'Poczekaj 3 sekundy przed kolejną wiadomością.';
  end if;

  new.created_at := now();
  return new;
end;
$$;

drop trigger if exists community_messages_guard on public.community_messages;
create trigger community_messages_guard
before insert on public.community_messages
for each row execute procedure public.community_message_guard();

do $$
declare p record;
begin
  for p in select policyname from pg_policies
           where schemaname='public' and tablename='community_messages'
  loop
    execute format('drop policy if exists %I on public.community_messages', p.policyname);
  end loop;
end $$;

create policy "community messages members read"
on public.community_messages for select
to authenticated
using (public.can_access_community(auth.uid()));

create policy "community messages own insert"
on public.community_messages for insert
to authenticated
with check (public.can_access_community(auth.uid()) and user_id=auth.uid());

create policy "community messages own delete"
on public.community_messages for delete
to authenticated
using (public.can_access_community(auth.uid()) and user_id=auth.uid());

revoke all on public.community_messages from anon, authenticated;
grant select on public.community_messages to authenticated;
grant insert (user_id, body, reply_to) on public.community_messages to authenticated;
grant delete on public.community_messages to authenticated;
grant all on public.community_messages to service_role;

-- Realtime, but do not fail if the table is already in the publication.
do $$
begin
  if exists (select 1 from pg_publication where pubname='supabase_realtime')
     and not exists (
       select 1 from pg_publication_tables
       where pubname='supabase_realtime'
         and schemaname='public'
         and tablename='community_messages'
     )
  then
    alter publication supabase_realtime add table public.community_messages;
  end if;
end $$;

-- ---------------------------------------------------------------------------
-- 5) Profiles: no anonymous directory. Members see approved 18+ members;
--    everyone signed in can still read their own profile for account/gating.
-- ---------------------------------------------------------------------------
alter table public.profiles enable row level security;

do $$
declare p record;
begin
  for p in select policyname from pg_policies
           where schemaname='public' and tablename='profiles'
  loop
    execute format('drop policy if exists %I on public.profiles', p.policyname);
  end loop;
end $$;

create policy "profiles self or community read"
on public.profiles for select
to authenticated
using (
  id=auth.uid()
  or (
    public.can_access_community(auth.uid())
    and community_access=true
    and age_confirmed_at is not null
    and banned_at is null
  )
);

create policy "profiles owner update safe"
on public.profiles for update
to authenticated
using (id=auth.uid())
with check (id=auth.uid());

revoke all on public.profiles from anon, authenticated;
grant select on public.profiles to authenticated;
grant update (bio, avatar_url, last_seen_at) on public.profiles to authenticated;
grant all on public.profiles to service_role;

-- ---------------------------------------------------------------------------
-- 6) Coupons: community-only. Client can never forge verification state.
-- ---------------------------------------------------------------------------
-- These two fields already exist in the repository schema, but add them here
-- as well so the migration also works on the currently deployed v6.5 database.
alter table public.coupons add column if not exists screenshot_url text;
alter table public.coupons add column if not exists slip_data jsonb not null default '{}'::jsonb;

alter table public.coupons enable row level security;

create or replace function public.protect_coupon_verification()
returns trigger
language plpgsql
security definer
set search_path = public, auth
as $$
begin
  if tg_op='INSERT' then
    new.verified := false;
    new.settlement_source := 'user';
    new.created_at := now();
  else
    new.user_id := old.user_id;
    new.created_at := old.created_at;
    new.verified := old.verified;
    new.settlement_source := old.settlement_source;
  end if;
  return new;
end;
$$;

drop trigger if exists protect_coupon_verification on public.coupons;
create trigger protect_coupon_verification
before insert or update on public.coupons
for each row execute procedure public.protect_coupon_verification();

do $$
declare p record;
begin
  for p in select policyname from pg_policies
           where schemaname='public' and tablename='coupons'
  loop
    execute format('drop policy if exists %I on public.coupons', p.policyname);
  end loop;
end $$;

create policy "coupons community read"
on public.coupons for select
to authenticated
using (
  public.can_access_community(auth.uid())
  and (is_public=true or user_id=auth.uid())
);

create policy "coupons community own insert"
on public.coupons for insert
to authenticated
with check (
  public.can_access_community(auth.uid())
  and user_id=auth.uid()
);

create policy "coupons community own update"
on public.coupons for update
to authenticated
using (public.can_access_community(auth.uid()) and user_id=auth.uid())
with check (public.can_access_community(auth.uid()) and user_id=auth.uid());

create policy "coupons community own delete"
on public.coupons for delete
to authenticated
using (public.can_access_community(auth.uid()) and user_id=auth.uid());

revoke all on public.coupons from anon, authenticated;
grant select on public.coupons to authenticated;
-- v6.5 frontend still sends verified=false and settlement_source='user' on INSERT.
-- The DB trigger overwrites those fields, so they cannot be forged.
grant insert (
  user_id, bookmaker, share_url, title, description, odds, status,
  verified, settlement_source, is_public, screenshot_url, slip_data, settled_at
) on public.coupons to authenticated;
grant update (
  bookmaker, share_url, title, description, odds, status,
  is_public, screenshot_url, slip_data, updated_at, settled_at
) on public.coupons to authenticated;
grant delete on public.coupons to authenticated;
grant all on public.coupons to service_role;

-- ---------------------------------------------------------------------------
-- 7) Comments, likes and follows: community-only, own writes.
-- ---------------------------------------------------------------------------
alter table public.coupon_comments enable row level security;
alter table public.coupon_likes enable row level security;
alter table public.profile_follows enable row level security;

do $$
declare t text; p record;
begin
  foreach t in array array['coupon_comments','coupon_likes','profile_follows']
  loop
    for p in select policyname from pg_policies
             where schemaname='public' and tablename=t
    loop
      execute format('drop policy if exists %I on public.%I', p.policyname, t);
    end loop;
  end loop;
end $$;

create policy "comments community read"
on public.coupon_comments for select
to authenticated
using (
  public.can_access_community(auth.uid())
  and exists (
    select 1 from public.coupons c
    where c.id=coupon_id and (c.is_public=true or c.user_id=auth.uid())
  )
);

create policy "comments own insert"
on public.coupon_comments for insert
to authenticated
with check (public.can_access_community(auth.uid()) and user_id=auth.uid());

create policy "comments own delete"
on public.coupon_comments for delete
to authenticated
using (public.can_access_community(auth.uid()) and user_id=auth.uid());

create policy "likes community read"
on public.coupon_likes for select
to authenticated
using (public.can_access_community(auth.uid()));

create policy "likes own insert"
on public.coupon_likes for insert
to authenticated
with check (public.can_access_community(auth.uid()) and user_id=auth.uid());

create policy "likes own delete"
on public.coupon_likes for delete
to authenticated
using (public.can_access_community(auth.uid()) and user_id=auth.uid());

create policy "follows community read"
on public.profile_follows for select
to authenticated
using (public.can_access_community(auth.uid()));

create policy "follows own insert"
on public.profile_follows for insert
to authenticated
with check (
  public.can_access_community(auth.uid())
  and follower_id=auth.uid()
  and following_id<>auth.uid()
  and exists (
    select 1 from public.profiles p
    where p.id=following_id
      and p.community_access=true
      and p.age_confirmed_at is not null
      and p.banned_at is null
  )
);

create policy "follows own delete"
on public.profile_follows for delete
to authenticated
using (public.can_access_community(auth.uid()) and follower_id=auth.uid());

revoke all on public.coupon_comments from anon, authenticated;
grant select on public.coupon_comments to authenticated;
grant insert (coupon_id,user_id,body) on public.coupon_comments to authenticated;
grant delete on public.coupon_comments to authenticated;
grant all on public.coupon_comments to service_role;

revoke all on public.coupon_likes from anon, authenticated;
grant select on public.coupon_likes to authenticated;
grant insert (coupon_id,user_id) on public.coupon_likes to authenticated;
grant delete on public.coupon_likes to authenticated;
grant all on public.coupon_likes to service_role;

revoke all on public.profile_follows from anon, authenticated;
grant select on public.profile_follows to authenticated;
grant insert (follower_id,following_id) on public.profile_follows to authenticated;
grant delete on public.profile_follows to authenticated;
grant all on public.profile_follows to service_role;

commit;
