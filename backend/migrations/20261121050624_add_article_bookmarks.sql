CREATE TABLE public.article_bookmarks (
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  article_id uuid NOT NULL REFERENCES public.news_items(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, article_id)
);

ALTER TABLE public.article_bookmarks ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.article_bookmarks FROM anon;
REVOKE ALL ON TABLE public.article_bookmarks FROM authenticated;
GRANT SELECT, INSERT, DELETE ON TABLE public.article_bookmarks TO authenticated;
GRANT ALL PRIVILEGES ON TABLE public.article_bookmarks TO service_role;

CREATE POLICY "Users can read own bookmarks"
ON public.article_bookmarks
FOR SELECT
TO authenticated
USING (
  (SELECT auth.uid()) = user_id
  AND (SELECT morning_brief_private.my_account_is_active())
);

CREATE POLICY "Users can insert own bookmarks"
ON public.article_bookmarks
FOR INSERT
TO authenticated
WITH CHECK (
  (SELECT auth.uid()) = user_id
  AND (SELECT morning_brief_private.my_account_is_active())
);

CREATE POLICY "Users can delete own bookmarks"
ON public.article_bookmarks
FOR DELETE
TO authenticated
USING (
  (SELECT auth.uid()) = user_id
  AND (SELECT morning_brief_private.my_account_is_active())
);

CREATE INDEX article_bookmarks_user_created_idx
ON public.article_bookmarks (user_id, created_at DESC, article_id DESC);

CREATE INDEX article_bookmarks_article_id_idx
ON public.article_bookmarks (article_id);
