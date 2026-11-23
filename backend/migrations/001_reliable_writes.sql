-- Apply to staging first. Requires existing schema, RLS and unique user/date briefings.
BEGIN;

CREATE OR REPLACE FUNCTION public.replace_my_categories(p_category_ids uuid[])
RETURNS SETOF public.user_categories
LANGUAGE plpgsql SECURITY INVOKER SET search_path = public, pg_temp AS $$
DECLARE actor uuid := auth.uid();
BEGIN
  IF actor IS NULL THEN RAISE EXCEPTION 'Authentication required' USING ERRCODE = '42501'; END IF;
  IF cardinality(p_category_ids) IS NULL OR cardinality(p_category_ids) NOT BETWEEN 1 AND 50
     OR array_position(p_category_ids, NULL) IS NOT NULL THEN
    RAISE EXCEPTION 'Select between 1 and 50 categories' USING ERRCODE = '22023';
  END IF;
  -- Serialize simultaneous preference changes for the same user, including an empty selection.
  PERFORM 1 FROM public.profiles WHERE id = actor FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Profile required' USING ERRCODE = '22023'; END IF;
  IF EXISTS (SELECT 1 FROM unnest(p_category_ids) selected(id)
             WHERE NOT EXISTS (SELECT 1 FROM public.categories c WHERE c.id = selected.id AND c.active)) THEN
    RAISE EXCEPTION 'Unknown or inactive category' USING ERRCODE = '22023';
  END IF;
  DELETE FROM public.user_categories WHERE user_id = actor;
  INSERT INTO public.user_categories(user_id, category_id)
    SELECT actor, id FROM (SELECT DISTINCT unnest(p_category_ids) id) selected;
  RETURN QUERY SELECT * FROM public.user_categories WHERE user_id = actor;
END $$;
REVOKE ALL ON FUNCTION public.replace_my_categories(uuid[]) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.replace_my_categories(uuid[]) TO authenticated;

CREATE TABLE public.briefing_generation_jobs (
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  briefing_date date NOT NULL,
  token uuid,
  request_id text,
  lease_until timestamptz,
  attempts integer NOT NULL DEFAULT 0,
  state text NOT NULL DEFAULT 'pending' CHECK (state IN ('pending','generating','ready','failed')),
  PRIMARY KEY (user_id, briefing_date)
);
ALTER TABLE public.briefing_generation_jobs ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.briefing_generation_jobs FROM PUBLIC, anon, authenticated;

CREATE FUNCTION public.claim_briefing_v2(p_user_id uuid, p_date date, p_force boolean DEFAULT false, p_request_id text DEFAULT NULL)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE job public.briefing_generation_jobs; saved public.briefings; new_token uuid;
BEGIN
  INSERT INTO public.briefing_generation_jobs(user_id, briefing_date) VALUES(p_user_id,p_date)
    ON CONFLICT DO NOTHING;
  SELECT * INTO job FROM public.briefing_generation_jobs
    WHERE user_id=p_user_id AND briefing_date=p_date FOR UPDATE;
  SELECT * INTO saved FROM public.briefings WHERE user_id=p_user_id AND briefing_date=p_date;
  IF job.state='generating' AND job.lease_until > clock_timestamp() THEN
    RETURN jsonb_build_object('outcome','busy');
  END IF;
  IF saved.status='ready' AND (NOT p_force OR
      (job.state='ready' AND p_request_id IS NOT NULL AND job.request_id=p_request_id)) THEN
    RETURN jsonb_build_object('outcome','ready','briefing',to_jsonb(saved));
  END IF;
  IF job.attempts >= 3 THEN RETURN jsonb_build_object('outcome','limited'); END IF;
  IF job.state='failed' AND job.lease_until > clock_timestamp() THEN
    RETURN jsonb_build_object('outcome','busy');
  END IF;
  new_token := gen_random_uuid();
  UPDATE public.briefing_generation_jobs SET token=new_token, request_id=p_request_id, attempts=attempts+1,
    state='generating', lease_until=clock_timestamp()+interval '10 minutes'
    WHERE user_id=p_user_id AND briefing_date=p_date;
  INSERT INTO public.briefings(user_id,briefing_date,status) VALUES(p_user_id,p_date,'generating')
    ON CONFLICT(user_id,briefing_date) DO UPDATE SET status='generating'
    WHERE public.briefings.status <> 'ready';
  RETURN jsonb_build_object('outcome','claimed','token',new_token);
END $$;

CREATE FUNCTION public.finish_briefing_v2(p_user_id uuid, p_date date, p_token uuid,
  p_script text, p_audio_path text, p_duration integer)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE job public.briefing_generation_jobs; saved public.briefings;
BEGIN
  SELECT * INTO job FROM public.briefing_generation_jobs
    WHERE user_id=p_user_id AND briefing_date=p_date FOR UPDATE;
  IF NOT FOUND OR job.token IS DISTINCT FROM p_token OR job.state <> 'generating'
     OR job.lease_until <= clock_timestamp() THEN RETURN NULL; END IF;
  IF length(trim(p_script))=0 OR p_script IS NULL OR p_duration IS NULL OR p_duration <= 0
     OR p_audio_path IS NULL OR p_audio_path NOT LIKE p_user_id::text || '/' || p_date::text || '/%.mp3' THEN
    RAISE EXCEPTION 'Invalid briefing artifact' USING ERRCODE='22023';
  END IF;
  INSERT INTO public.briefings(user_id,briefing_date,title,script,audio_url,duration_seconds,status,generated_at)
    VALUES(p_user_id,p_date,'Morning Brief',p_script,p_audio_path,p_duration,'ready',clock_timestamp())
    ON CONFLICT(user_id,briefing_date) DO UPDATE SET script=excluded.script,audio_url=excluded.audio_url,
      duration_seconds=excluded.duration_seconds,status='ready',generated_at=excluded.generated_at,
      updated_at=clock_timestamp()
    RETURNING * INTO saved;
  UPDATE public.briefing_generation_jobs SET state='ready', lease_until=NULL
    WHERE user_id=p_user_id AND briefing_date=p_date;
  RETURN to_jsonb(saved);
END $$;

CREATE FUNCTION public.fail_briefing_v2(p_user_id uuid, p_date date, p_token uuid)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
  UPDATE public.briefing_generation_jobs SET state='failed',lease_until=clock_timestamp()+interval '5 minutes'
    WHERE user_id=p_user_id AND briefing_date=p_date AND token=p_token AND state='generating';
  IF NOT FOUND THEN RETURN false; END IF;
  UPDATE public.briefings SET status='failed',updated_at=clock_timestamp()
    WHERE user_id=p_user_id AND briefing_date=p_date AND status='generating';
  RETURN true;
END $$;
REVOKE ALL ON FUNCTION public.claim_briefing_v2(uuid,date,boolean,text) FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.finish_briefing_v2(uuid,date,uuid,text,text,integer) FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.fail_briefing_v2(uuid,date,uuid) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.claim_briefing_v2(uuid,date,boolean,text) TO service_role;
GRANT EXECUTE ON FUNCTION public.finish_briefing_v2(uuid,date,uuid,text,text,integer) TO service_role;
GRANT EXECUTE ON FUNCTION public.fail_briefing_v2(uuid,date,uuid) TO service_role;
-- Generation now writes only through service-only RPCs. User clients retain read access/RLS.
REVOKE INSERT, UPDATE, DELETE ON public.briefings FROM PUBLIC, anon, authenticated;
-- RLS does not protect TRUNCATE. Existing Supabase table grants can include it.
-- Client roles must never perform table-wide operations on application data.
DO $client_ddl$ DECLARE table_name text; BEGIN
  FOR table_name IN SELECT c.relname FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relkind='r'
      AND c.relname IN ('profiles','categories','user_categories','briefings','device_tokens','news_items')
  LOOP
    EXECUTE format('REVOKE TRUNCATE, REFERENCES, TRIGGER ON TABLE public.%I FROM PUBLIC, anon, authenticated', table_name);
  END LOOP;
END $client_ddl$;
-- Retire every overload of the historical unfenced RPC; never leave a bypass.
DO $revoke$ DECLARE signature text; BEGIN
  FOR signature IN SELECT p.oid::regprocedure::text FROM pg_proc p
    JOIN pg_namespace n ON n.oid=p.pronamespace
    WHERE n.nspname='public' AND p.proname='claim_briefing_generation'
  LOOP EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC, anon, authenticated, service_role', signature); END LOOP;
END $revoke$;
COMMIT;
