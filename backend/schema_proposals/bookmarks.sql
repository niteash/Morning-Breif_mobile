-- REVIEW ONLY. Not applied. Package with Supabase CLI migration new after approval.
-- Requires the existing private-account-availability migration.
BEGIN;
CREATE TABLE public.article_bookmarks (
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  article_id uuid NOT NULL REFERENCES public.news_items(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, article_id)
);
CREATE INDEX article_bookmarks_owner_date ON public.article_bookmarks(user_id, created_at DESC, article_id DESC);
ALTER TABLE public.article_bookmarks ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.article_bookmarks FROM anon, authenticated;
GRANT SELECT, INSERT, DELETE ON public.article_bookmarks TO authenticated;
CREATE POLICY bookmarks_read ON public.article_bookmarks FOR SELECT TO authenticated USING ((SELECT auth.uid()) = user_id);
CREATE POLICY bookmarks_insert ON public.article_bookmarks FOR INSERT TO authenticated WITH CHECK ((SELECT auth.uid()) = user_id);
CREATE POLICY bookmarks_delete ON public.article_bookmarks FOR DELETE TO authenticated USING ((SELECT auth.uid()) = user_id);
CREATE POLICY bookmarks_active_account ON public.article_bookmarks AS RESTRICTIVE
  FOR ALL TO authenticated
  USING ((SELECT morning_brief_private.my_account_is_active()))
  WITH CHECK ((SELECT morning_brief_private.my_account_is_active()));
COMMIT;
-- Rollback: revoke table grants / disable feature first; export any rows before
-- a separately approved DROP TABLE. Never discard user bookmarks automatically.
