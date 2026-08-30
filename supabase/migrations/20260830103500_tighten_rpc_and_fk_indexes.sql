-- Audit hardening: keep browser RPC surface minimal and add missing FK indexes.
-- No betting/model/training/settlement logic is touched.

-- Sensitive staff/admin RPCs stay callable by signed-in users because each
-- function performs its own role check. Anonymous execution is unnecessary.
revoke execute on function public.admin_delete_user(uuid) from anon;
revoke execute on function public.admin_set_role(uuid, text) from anon;
revoke execute on function public.staff_member_list() from anon;
revoke execute on function public.staff_review_access(uuid, text) from anon;
revoke execute on function public.staff_set_ban(uuid, boolean) from anon;
revoke execute on function public.confirm_age_18() from anon;

-- Internal trigger/event-trigger functions are not client RPCs.
revoke execute on function public.community_message_guard() from public;
revoke execute on function public.handle_new_user() from public;
revoke execute on function public.protect_coupon_verification() from public;
revoke execute on function public.rls_auto_enable() from public;

-- RLS helper functions are required by authenticated policies, but anonymous
-- callers do not need direct access to user/staff membership predicates.
revoke execute on function public.can_access_community(uuid) from public;
revoke execute on function public.is_admin(uuid) from public;
revoke execute on function public.is_staff(uuid) from public;
grant execute on function public.can_access_community(uuid) to authenticated;
grant execute on function public.is_admin(uuid) to authenticated;
grant execute on function public.is_staff(uuid) to authenticated;

-- Cover foreign keys reported by the database advisor. These are intentionally
-- normal CREATE INDEX statements so the migration remains transactional.
create index if not exists community_access_requests_reviewed_by_idx
  on public.community_access_requests(reviewed_by);
create index if not exists community_admin_audit_actor_id_idx
  on public.community_admin_audit(actor_id);
create index if not exists community_admin_audit_target_id_idx
  on public.community_admin_audit(target_id);
create index if not exists community_messages_reply_to_idx
  on public.community_messages(reply_to);
create index if not exists coupon_comments_coupon_id_idx
  on public.coupon_comments(coupon_id);
create index if not exists coupon_comments_user_id_idx
  on public.coupon_comments(user_id);
create index if not exists coupon_likes_user_id_idx
  on public.coupon_likes(user_id);
create index if not exists coupons_user_id_idx
  on public.coupons(user_id);
create index if not exists profile_follows_following_id_idx
  on public.profile_follows(following_id);
