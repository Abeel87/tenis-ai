-- Preserve policy predicates and roles; evaluate stable JWT helpers once per statement.
SET lock_timeout = '5s';

ALTER POLICY "ai scenarios own delete" ON public."ai_scenarios" USING ((user_id = (select auth.uid())));

ALTER POLICY "ai scenarios own insert" ON public."ai_scenarios" WITH CHECK ((user_id = (select auth.uid())));

ALTER POLICY "ai scenarios own read" ON public."ai_scenarios" USING ((user_id = (select auth.uid())));

ALTER POLICY "ai scenarios own update" ON public."ai_scenarios" USING ((user_id = (select auth.uid()))) WITH CHECK ((user_id = (select auth.uid())));

ALTER POLICY "access request own insert" ON public."community_access_requests" WITH CHECK (((user_id = (select auth.uid())) AND (status = 'pending'::text) AND (reviewed_at IS NULL) AND (reviewed_by IS NULL)));

ALTER POLICY "access request own read" ON public."community_access_requests" USING ((user_id = (select auth.uid())));

ALTER POLICY "community messages members read" ON public."community_messages" USING (can_access_community((select auth.uid())));

ALTER POLICY "community messages own delete" ON public."community_messages" USING ((can_access_community((select auth.uid())) AND (user_id = (select auth.uid()))));

ALTER POLICY "community messages own insert" ON public."community_messages" WITH CHECK ((can_access_community((select auth.uid())) AND (user_id = (select auth.uid()))));

ALTER POLICY "comments community read" ON public."coupon_comments" USING ((can_access_community((select auth.uid())) AND (EXISTS ( SELECT 1
   FROM coupons c
  WHERE ((c.id = coupon_comments.coupon_id) AND ((c.is_public = true) OR (c.user_id = (select auth.uid()))))))));

ALTER POLICY "comments own delete" ON public."coupon_comments" USING ((can_access_community((select auth.uid())) AND (user_id = (select auth.uid()))));

ALTER POLICY "comments own insert" ON public."coupon_comments" WITH CHECK ((can_access_community((select auth.uid())) AND (user_id = (select auth.uid())) AND (EXISTS ( SELECT 1
   FROM coupons c
  WHERE ((c.id = coupon_comments.coupon_id) AND ((c.is_public = true) OR (c.user_id = (select auth.uid()))))))));

ALTER POLICY "likes community read" ON public."coupon_likes" USING ((can_access_community((select auth.uid())) AND (EXISTS ( SELECT 1
   FROM coupons c
  WHERE ((c.id = coupon_likes.coupon_id) AND ((c.is_public = true) OR (c.user_id = (select auth.uid()))))))));

ALTER POLICY "likes own delete" ON public."coupon_likes" USING ((can_access_community((select auth.uid())) AND (user_id = (select auth.uid()))));

ALTER POLICY "likes own insert" ON public."coupon_likes" WITH CHECK ((can_access_community((select auth.uid())) AND (user_id = (select auth.uid())) AND (EXISTS ( SELECT 1
   FROM coupons c
  WHERE ((c.id = coupon_likes.coupon_id) AND ((c.is_public = true) OR (c.user_id = (select auth.uid()))))))));

ALTER POLICY "coupons community own delete" ON public."coupons" USING ((can_access_community((select auth.uid())) AND (user_id = (select auth.uid()))));

ALTER POLICY "coupons community own insert" ON public."coupons" WITH CHECK ((can_access_community((select auth.uid())) AND (user_id = (select auth.uid()))));

ALTER POLICY "coupons community own update" ON public."coupons" USING ((can_access_community((select auth.uid())) AND (user_id = (select auth.uid())))) WITH CHECK ((can_access_community((select auth.uid())) AND (user_id = (select auth.uid()))));

ALTER POLICY "coupons community read" ON public."coupons" USING ((can_access_community((select auth.uid())) AND ((is_public = true) OR (user_id = (select auth.uid())))));

ALTER POLICY "follows community read" ON public."profile_follows" USING (can_access_community((select auth.uid())));

ALTER POLICY "follows own delete" ON public."profile_follows" USING ((can_access_community((select auth.uid())) AND (follower_id = (select auth.uid()))));

ALTER POLICY "follows own insert" ON public."profile_follows" WITH CHECK ((can_access_community((select auth.uid())) AND (follower_id = (select auth.uid())) AND (following_id <> (select auth.uid())) AND (EXISTS ( SELECT 1
   FROM profiles p
  WHERE ((p.id = profile_follows.following_id) AND (p.community_access = true) AND (p.age_confirmed_at IS NOT NULL) AND (p.banned_at IS NULL))))));

ALTER POLICY "profiles owner update safe" ON public."profiles" USING ((id = (select auth.uid()))) WITH CHECK ((id = (select auth.uid())));

ALTER POLICY "profiles self or community read" ON public."profiles" USING (((id = (select auth.uid())) OR (can_access_community((select auth.uid())) AND (community_access = true) AND (age_confirmed_at IS NOT NULL) AND (banned_at IS NULL))));

ALTER POLICY "ui moderation staff insert" ON public."ui_match_moderation" WITH CHECK ((( SELECT is_staff((select auth.uid())) AS is_staff) AND (updated_by = ( SELECT auth.uid() AS uid))));

ALTER POLICY "ui moderation staff update" ON public."ui_match_moderation" USING (( SELECT is_staff((select auth.uid())) AS is_staff)) WITH CHECK ((( SELECT is_staff((select auth.uid())) AS is_staff) AND (updated_by = ( SELECT auth.uid() AS uid))));

CREATE INDEX IF NOT EXISTS ineed_bankroll_ledger_bet_id_idx ON public.ineed_bankroll_ledger (bet_id);

CREATE INDEX IF NOT EXISTS ineed_email_events_experiment_id_idx ON public.ineed_email_events (experiment_id);

CREATE INDEX IF NOT EXISTS ineed_experiments_created_by_idx ON public.ineed_experiments (created_by);

CREATE INDEX IF NOT EXISTS ineed_signal_events_experiment_id_idx ON public.ineed_signal_events (experiment_id);

CREATE INDEX IF NOT EXISTS ui_match_moderation_updated_by_idx ON public.ui_match_moderation (updated_by);

REVOKE EXECUTE ON FUNCTION public.is_admin(uuid), public.is_staff(uuid), public.can_access_community(uuid) FROM anon;
-- Public registration helpers and authenticated staff RPCs retain their existing access.
-- No iNeed system RPC grants or function bodies are changed.

