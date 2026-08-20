-- Tenis AI v6.4 — Accounts + Community foundation
-- Run once in Supabase SQL Editor.
-- NEVER expose a service_role key in the browser.

create extension if not exists pgcrypto;

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  username text not null check (char_length(trim(username)) between 3 and 24),
  avatar_url text,
  bio text check (bio is null or char_length(bio) <= 300),
  last_seen_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create unique index if not exists profiles_username_lower_idx
  on public.profiles ((lower(trim(username))));

alter table public.profiles enable row level security;

drop policy if exists "profiles public read" on public.profiles;
create policy "profiles public read" on public.profiles for select to anon, authenticated using (true);

drop policy if exists "profiles owner update" on public.profiles;
create policy "profiles owner update" on public.profiles for update to authenticated
  using ((select auth.uid()) = id) with check ((select auth.uid()) = id);

grant select on public.profiles to anon, authenticated;
grant update on public.profiles to authenticated;
grant all on public.profiles to service_role;

create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = '' as $$
declare wanted_username text;
begin
  wanted_username := nullif(trim(new.raw_user_meta_data ->> 'username'), '');
  if wanted_username is null then wanted_username := 'user_' || left(new.id::text, 8); end if;
  insert into public.profiles (id, username, last_seen_at) values (new.id, wanted_username, now());
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created after insert on auth.users
  for each row execute procedure public.handle_new_user();

create table if not exists public.coupons (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  bookmaker text not null default 'other' check (bookmaker in ('superbet','betclic','sts','fortuna','other')),
  share_url text,
  title text,
  description text check (description is null or char_length(description) <= 1000),
  odds numeric(12,4),
  status text not null default 'pending' check (status in ('pending','won','lost','cashout','void')),
  verified boolean not null default false,
  settlement_source text not null default 'user' check (settlement_source in ('user','auto','manual')),
  is_public boolean not null default true,
  screenshot_url text,
  slip_data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  settled_at timestamptz
);

create index if not exists coupons_user_idx on public.coupons(user_id, created_at desc);
create index if not exists coupons_public_idx on public.coupons(is_public, created_at desc);
create index if not exists coupons_bookmaker_idx on public.coupons(bookmaker, created_at desc);
alter table public.coupons enable row level security;

drop policy if exists "coupons visible public or owner" on public.coupons;
create policy "coupons visible public or owner" on public.coupons for select to anon, authenticated
  using (is_public or (select auth.uid()) = user_id);
drop policy if exists "coupons owner insert" on public.coupons;
create policy "coupons owner insert" on public.coupons for insert to authenticated with check ((select auth.uid()) = user_id);
drop policy if exists "coupons owner update" on public.coupons;
create policy "coupons owner update" on public.coupons for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
drop policy if exists "coupons owner delete" on public.coupons;
create policy "coupons owner delete" on public.coupons for delete to authenticated using ((select auth.uid()) = user_id);

grant select on public.coupons to anon, authenticated;
grant insert, update, delete on public.coupons to authenticated;
grant all on public.coupons to service_role;

create table if not exists public.coupon_legs (
  id uuid primary key default gen_random_uuid(),
  coupon_id uuid not null references public.coupons(id) on delete cascade,
  external_match_id text,
  event_name text not null,
  event_start timestamptz,
  market text,
  pick text not null,
  line numeric(12,4),
  odds numeric(12,4),
  result text not null default 'pending' check (result in ('pending','won','lost','void')),
  created_at timestamptz not null default now()
);
create index if not exists coupon_legs_coupon_idx on public.coupon_legs(coupon_id);
alter table public.coupon_legs enable row level security;

drop policy if exists "coupon legs readable with coupon" on public.coupon_legs;
create policy "coupon legs readable with coupon" on public.coupon_legs for select to anon, authenticated using (
  exists (select 1 from public.coupons c where c.id = coupon_id and (c.is_public or c.user_id = (select auth.uid())))
);
drop policy if exists "coupon legs owner insert" on public.coupon_legs;
create policy "coupon legs owner insert" on public.coupon_legs for insert to authenticated with check (
  exists (select 1 from public.coupons c where c.id = coupon_id and c.user_id = (select auth.uid()))
);
drop policy if exists "coupon legs owner update" on public.coupon_legs;
create policy "coupon legs owner update" on public.coupon_legs for update to authenticated using (
  exists (select 1 from public.coupons c where c.id = coupon_id and c.user_id = (select auth.uid()))
) with check (
  exists (select 1 from public.coupons c where c.id = coupon_id and c.user_id = (select auth.uid()))
);
drop policy if exists "coupon legs owner delete" on public.coupon_legs;
create policy "coupon legs owner delete" on public.coupon_legs for delete to authenticated using (
  exists (select 1 from public.coupons c where c.id = coupon_id and c.user_id = (select auth.uid()))
);

grant select on public.coupon_legs to anon, authenticated;
grant insert, update, delete on public.coupon_legs to authenticated;
grant all on public.coupon_legs to service_role;

create table if not exists public.coupon_comments (
  id uuid primary key default gen_random_uuid(),
  coupon_id uuid not null references public.coupons(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  body text not null check (char_length(trim(body)) between 1 and 500),
  created_at timestamptz not null default now()
);
alter table public.coupon_comments enable row level security;

drop policy if exists "comments public read" on public.coupon_comments;
create policy "comments public read" on public.coupon_comments for select to anon, authenticated using (
  exists (select 1 from public.coupons c where c.id=coupon_id and c.is_public) or user_id=(select auth.uid())
);
drop policy if exists "comments own insert" on public.coupon_comments;
create policy "comments own insert" on public.coupon_comments for insert to authenticated with check (user_id=(select auth.uid()));
drop policy if exists "comments own delete" on public.coupon_comments;
create policy "comments own delete" on public.coupon_comments for delete to authenticated using (user_id=(select auth.uid()));

grant select on public.coupon_comments to anon, authenticated;
grant insert, delete on public.coupon_comments to authenticated;
grant all on public.coupon_comments to service_role;

create table if not exists public.coupon_likes (
  coupon_id uuid not null references public.coupons(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (coupon_id,user_id)
);
alter table public.coupon_likes enable row level security;

drop policy if exists "likes public read" on public.coupon_likes;
create policy "likes public read" on public.coupon_likes for select to anon, authenticated using (true);
drop policy if exists "likes own insert" on public.coupon_likes;
create policy "likes own insert" on public.coupon_likes for insert to authenticated with check (user_id=(select auth.uid()));
drop policy if exists "likes own delete" on public.coupon_likes;
create policy "likes own delete" on public.coupon_likes for delete to authenticated using (user_id=(select auth.uid()));

grant select on public.coupon_likes to anon, authenticated;
grant insert, delete on public.coupon_likes to authenticated;
grant all on public.coupon_likes to service_role;

create or replace function public.set_coupon_updated_at()
returns trigger language plpgsql set search_path = '' as $$
begin new.updated_at := now(); return new; end;
$$;

drop trigger if exists coupons_set_updated_at on public.coupons;
create trigger coupons_set_updated_at before update on public.coupons
  for each row execute procedure public.set_coupon_updated_at();

-- Future ranking rule: only verified=true coupons should count toward public win-rate/rankings.
