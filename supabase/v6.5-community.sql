-- Tenis AI v6.5 — shared coupons, reactions, follows, avatars
-- Run once in Supabase SQL Editor before deploying v6.5 frontend.

alter table public.coupons add column if not exists title text;
alter table public.coupons add column if not exists description text;
alter table public.coupons add column if not exists odds numeric(12,4);
alter table public.coupons add column if not exists updated_at timestamptz not null default now();
alter table public.coupons add column if not exists settled_at timestamptz;
alter table public.coupons add column if not exists settlement_source text not null default 'user';

create table if not exists public.coupon_comments (
  id uuid primary key default gen_random_uuid(), coupon_id uuid not null references public.coupons(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade, body text not null check (char_length(trim(body)) between 1 and 300),
  created_at timestamptz not null default now()
);
create table if not exists public.coupon_likes (
  coupon_id uuid not null references public.coupons(id) on delete cascade, user_id uuid not null references public.profiles(id) on delete cascade,
  created_at timestamptz not null default now(), primary key (coupon_id,user_id)
);
create table if not exists public.profile_follows (
  follower_id uuid not null references public.profiles(id) on delete cascade, following_id uuid not null references public.profiles(id) on delete cascade,
  created_at timestamptz not null default now(), primary key (follower_id,following_id), check (follower_id <> following_id)
);

alter table public.coupon_comments enable row level security;
alter table public.coupon_likes enable row level security;
alter table public.profile_follows enable row level security;

drop policy if exists "comments public read" on public.coupon_comments;
create policy "comments public read" on public.coupon_comments for select to anon, authenticated using (true);
drop policy if exists "comments own insert" on public.coupon_comments;
create policy "comments own insert" on public.coupon_comments for insert to authenticated with check (user_id=auth.uid());
drop policy if exists "comments own delete" on public.coupon_comments;
create policy "comments own delete" on public.coupon_comments for delete to authenticated using (user_id=auth.uid());

drop policy if exists "likes public read" on public.coupon_likes;
create policy "likes public read" on public.coupon_likes for select to anon, authenticated using (true);
drop policy if exists "likes own insert" on public.coupon_likes;
create policy "likes own insert" on public.coupon_likes for insert to authenticated with check (user_id=auth.uid());
drop policy if exists "likes own delete" on public.coupon_likes;
create policy "likes own delete" on public.coupon_likes for delete to authenticated using (user_id=auth.uid());

drop policy if exists "follows public read" on public.profile_follows;
create policy "follows public read" on public.profile_follows for select to anon, authenticated using (true);
drop policy if exists "follows own insert" on public.profile_follows;
create policy "follows own insert" on public.profile_follows for insert to authenticated with check (follower_id=auth.uid());
drop policy if exists "follows own delete" on public.profile_follows;
create policy "follows own delete" on public.profile_follows for delete to authenticated using (follower_id=auth.uid());

drop policy if exists "coupons owner delete" on public.coupons;
create policy "coupons owner delete" on public.coupons for delete to authenticated using (user_id=auth.uid());

grant select on public.coupon_comments, public.coupon_likes, public.profile_follows to anon, authenticated;
grant insert, delete on public.coupon_comments, public.coupon_likes, public.profile_follows to authenticated;
grant select, insert, update, delete on public.coupons to authenticated;

insert into storage.buckets (id,name,public,file_size_limit,allowed_mime_types)
values ('avatars','avatars',true,4194304,array['image/jpeg','image/png','image/webp'])
on conflict (id) do update set public=true,file_size_limit=4194304,allowed_mime_types=array['image/jpeg','image/png','image/webp'];

drop policy if exists "avatars public read" on storage.objects;
create policy "avatars public read" on storage.objects for select to public using (bucket_id='avatars');
drop policy if exists "avatars own insert" on storage.objects;
create policy "avatars own insert" on storage.objects for insert to authenticated with check (bucket_id='avatars' and (storage.foldername(name))[1]=auth.uid()::text);
drop policy if exists "avatars own update" on storage.objects;
create policy "avatars own update" on storage.objects for update to authenticated using (bucket_id='avatars' and (storage.foldername(name))[1]=auth.uid()::text) with check (bucket_id='avatars' and (storage.foldername(name))[1]=auth.uid()::text);
