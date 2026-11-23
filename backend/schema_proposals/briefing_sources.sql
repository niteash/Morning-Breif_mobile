-- REVIEW ONLY. Apply to authorized staging only after approval; never auto-run.
BEGIN;
ALTER TABLE public.briefings ADD COLUMN source_metadata jsonb;
ALTER TABLE public.briefings ADD CONSTRAINT briefing_sources_object
 CHECK (source_metadata IS NULL OR jsonb_typeof(source_metadata)='object');
CREATE FUNCTION public.briefing_sources_ready() RETURNS boolean
 LANGUAGE sql SECURITY INVOKER SET search_path='' AS $$ SELECT true $$;
CREATE FUNCTION public.finish_briefing_with_sources(
 p_user_id uuid,p_date date,p_token uuid,p_script text,p_audio_path text,p_duration integer,p_metadata jsonb)
 RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE saved jsonb; section jsonb; source jsonb; assembled text;
BEGIN
 IF p_metadata IS NULL OR jsonb_typeof(p_metadata->'sections') IS DISTINCT FROM 'array'
 OR jsonb_array_length(p_metadata->'sections')=0 OR p_metadata->>'script' IS DISTINCT FROM p_script
 OR coalesce(length(trim(p_metadata->>'title')),0)=0 THEN
 RAISE EXCEPTION 'Invalid source metadata'; END IF;
 IF p_metadata->>'briefing_date' IS DISTINCT FROM p_date::text
 OR coalesce(p_metadata->>'generated_at','')='' THEN
   RAISE EXCEPTION 'Missing source generation identity';
 END IF;
 FOR section IN SELECT value FROM jsonb_array_elements(p_metadata->'sections') LOOP
   IF jsonb_typeof(section->'sources') IS DISTINCT FROM 'array'
      OR coalesce(length(trim(section->>'narration')),0)=0
      OR coalesce(section->>'category_id','')='' THEN
     RAISE EXCEPTION 'Invalid source section';
   END IF;
   IF jsonb_array_length(section->'sources')=0 THEN RAISE EXCEPTION 'Missing sources'; END IF;
   FOR source IN SELECT value FROM jsonb_array_elements(section->'sources') LOOP
     IF coalesce(source->>'id','')='' OR coalesce(source->>'title','')=''
        OR coalesce(source->>'source','')=''
        OR coalesce(source->>'url','') !~ '^https?://' THEN
       RAISE EXCEPTION 'Invalid publisher reference';
     END IF;
   END LOOP;
 END LOOP;
 SELECT string_agg(value->>'narration', E'\n\n' ORDER BY ordinal)
 INTO assembled FROM jsonb_array_elements(p_metadata->'sections') WITH ORDINALITY AS s(value,ordinal);
 IF assembled IS DISTINCT FROM p_script THEN RAISE EXCEPTION 'Transcript/source mismatch'; END IF;
 saved := public.finish_briefing_v2(p_user_id,p_date,p_token,p_script,p_audio_path,p_duration);
 IF saved IS NULL THEN RETURN NULL; END IF;
 UPDATE public.briefings SET source_metadata=p_metadata,title=p_metadata->>'title'
 WHERE user_id=p_user_id AND briefing_date=p_date RETURNING to_jsonb(briefings.*) INTO saved;
 RETURN saved;
END $$;
REVOKE ALL ON FUNCTION public.briefing_sources_ready(),public.finish_briefing_with_sources(uuid,date,uuid,text,text,integer,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.briefing_sources_ready(),public.finish_briefing_with_sources(uuid,date,uuid,text,text,integer,jsonb) TO service_role;
-- A later legacy regeneration must never display references for the old script.
CREATE FUNCTION public.clear_stale_briefing_sources() RETURNS trigger
 LANGUAGE plpgsql SET search_path='' AS $$
BEGIN
 IF NEW.source_metadata IS NOT NULL AND NEW.source_metadata->>'script' IS DISTINCT FROM NEW.script THEN
   NEW.source_metadata := NULL;
 END IF;
 RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION public.clear_stale_briefing_sources() FROM PUBLIC,anon,authenticated;
CREATE TRIGGER clear_stale_briefing_sources BEFORE INSERT OR UPDATE ON public.briefings
 FOR EACH ROW EXECUTE FUNCTION public.clear_stale_briefing_sources();
COMMIT;
-- Existing briefing ownership RLS applies to metadata. Legacy rows stay NULL.
-- Finish/audio metadata writes share a transaction with the existing ready trigger.
-- Rollback: disable BRIEFING_SOURCES_ENABLED first. Preserve/export metadata; then
-- approved rollback may drop the two new functions and column. Never delete trials/audio.
