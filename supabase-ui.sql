-- Presentation persistence only; no model, pipeline or existing table changes.
begin;
create table if not exists public.ui_coupons (
 id uuid primary key default gen_random_uuid(),
 user_id uuid not null references auth.users(id) on delete cascade,
 title text not null check (char_length(title) between 1 and 100),
 stake numeric(12,2) not null default 0 check (stake >= 0),
 legs jsonb not null default '[]'::jsonb check (jsonb_typeof(legs)='array'),
 updated_at timestamptz not null default now(),
 created_at timestamptz not null default now()
);
alter table public.ui_coupons enable row level security;
create index if not exists ui_coupons_owner_updated_idx on public.ui_coupons(user_id,updated_at desc);
revoke all on public.ui_coupons from anon,authenticated;
grant select,insert,update,delete on public.ui_coupons to authenticated;
drop policy if exists "ui coupons own read" on public.ui_coupons;
create policy "ui coupons own read" on public.ui_coupons for select to authenticated using (user_id=(select auth.uid()));
drop policy if exists "ui coupons own insert" on public.ui_coupons;
create policy "ui coupons own insert" on public.ui_coupons for insert to authenticated with check (user_id=(select auth.uid()) and exists(select 1 from public.profiles where id=(select auth.uid()) and banned_at is null));
drop policy if exists "ui coupons own update" on public.ui_coupons;
create policy "ui coupons own update" on public.ui_coupons for update to authenticated using(user_id=(select auth.uid())) with check(user_id=(select auth.uid()) and exists(select 1 from public.profiles where id=(select auth.uid()) and banned_at is null));
drop policy if exists "ui coupons own delete" on public.ui_coupons;
create policy "ui coupons own delete" on public.ui_coupons for delete to authenticated using(user_id=(select auth.uid()));
create table if not exists public.ui_match_moderation (
 match_id text primary key,
 hidden boolean not null default false,
 problem text not null default '' check(char_length(problem)<=1000),
 updated_by uuid not null references auth.users(id),
 updated_at timestamptz not null default now()
);
alter table public.ui_match_moderation enable row level security;
revoke all on public.ui_match_moderation from anon,authenticated;
grant select,insert,update on public.ui_match_moderation to authenticated;
drop policy if exists "ui moderation read" on public.ui_match_moderation;
create policy "ui moderation read" on public.ui_match_moderation for select to authenticated using(true);
drop policy if exists "ui moderation staff insert" on public.ui_match_moderation;
create policy "ui moderation staff insert" on public.ui_match_moderation for insert to authenticated with check((select public.is_staff(auth.uid())) and updated_by=(select auth.uid()));
drop policy if exists "ui moderation staff update" on public.ui_match_moderation;
create policy "ui moderation staff update" on public.ui_match_moderation for update to authenticated using((select public.is_staff(auth.uid()))) with check((select public.is_staff(auth.uid())) and updated_by=(select auth.uid()));
commit;
