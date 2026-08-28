-- v9.1.9 audit: interactions must respect the referenced coupon's visibility.
-- This migration only tightens policies; it preserves all existing rows.
-- Apply after v6.6 Community Security, then verify with two non-admin accounts.

begin;

alter policy "comments own insert" on public.coupon_comments
with check (
  public.can_access_community(auth.uid())
  and user_id = auth.uid()
  and exists (
    select 1 from public.coupons c
    where c.id = coupon_comments.coupon_id
      and (c.is_public = true or c.user_id = auth.uid())
  )
);

alter policy "likes community read" on public.coupon_likes
using (
  public.can_access_community(auth.uid())
  and exists (
    select 1 from public.coupons c
    where c.id = coupon_likes.coupon_id
      and (c.is_public = true or c.user_id = auth.uid())
  )
);

alter policy "likes own insert" on public.coupon_likes
with check (
  public.can_access_community(auth.uid())
  and user_id = auth.uid()
  and exists (
    select 1 from public.coupons c
    where c.id = coupon_likes.coupon_id
      and (c.is_public = true or c.user_id = auth.uid())
  )
);

commit;
