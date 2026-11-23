-- Follow-up to reliable_writes, applied to staging only.
-- Preserve ownership semantics while evaluating auth.uid() once per statement.
ALTER POLICY "Users can view their own device tokens" ON public.device_tokens
  USING ((SELECT auth.uid()) = user_id);
ALTER POLICY "Users can read their own briefings" ON public.briefings
  USING ((SELECT auth.uid()) = user_id);
-- Generation is service-only; obsolete client write policies are no longer needed.
DROP POLICY "Users can insert their own briefings" ON public.briefings;
DROP POLICY "Users can update their own briefings" ON public.briefings;
CREATE INDEX user_categories_category_id_idx ON public.user_categories(category_id);
-- Preflight confirmed identical (category_id, published_at DESC) definitions.
DROP INDEX public.news_items_category_published_idx;
