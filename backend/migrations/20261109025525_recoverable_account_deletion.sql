-- Apply after the durable notification migration. Storage objects are deleted only
-- through the Storage API; SQL below reads metadata, never deletes storage rows.
BEGIN;
CREATE TABLE public.account_deletion_jobs (
  user_id uuid PRIMARY KEY, -- Intentionally survives Auth deletion until cleanup is verified.
  state text NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','processing','failed')),
  requested_at timestamptz NOT NULL DEFAULT now(),
  available_at timestamptz NOT NULL DEFAULT (now()+interval '15 minutes'),
  attempts integer NOT NULL DEFAULT 0 CHECK(attempts BETWEEN 0 AND 20),
  lease_token uuid,
  lease_until timestamptz
);
ALTER TABLE public.account_deletion_jobs ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.account_deletion_jobs FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON public.account_deletion_jobs TO service_role;
CREATE INDEX account_deletion_due_idx ON public.account_deletion_jobs(available_at)
  WHERE state IN ('pending','processing');

CREATE FUNCTION public.account_is_active(p_user_id uuid) RETURNS boolean
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
  SELECT EXISTS(SELECT 1 FROM auth.users WHERE id=p_user_id)
    AND NOT EXISTS(SELECT 1 FROM public.account_deletion_jobs WHERE user_id=p_user_id)
$$;
REVOKE ALL ON FUNCTION public.account_is_active(uuid) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.account_is_active(uuid) TO service_role;
CREATE FUNCTION public.my_account_is_active() RETURNS boolean
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
  SELECT public.account_is_active(auth.uid())
$$;
REVOKE ALL ON FUNCTION public.my_account_is_active() FROM PUBLIC,anon;
GRANT EXECUTE ON FUNCTION public.my_account_is_active() TO authenticated;

-- Stale JWTs must not retain direct PostgREST access after a deletion request.
DO $policies$ DECLARE target text; BEGIN
  FOREACH target IN ARRAY ARRAY['profiles','user_categories','briefings','device_tokens'] LOOP
    EXECUTE format('CREATE POLICY account_must_be_active ON public.%I AS RESTRICTIVE FOR ALL TO authenticated USING ((SELECT public.my_account_is_active())) WITH CHECK ((SELECT public.my_account_is_active()))',target);
  END LOOP;
END $policies$;

CREATE FUNCTION public.reject_deleted_account_write() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
DECLARE actor uuid;
BEGIN
  actor:=CASE WHEN TG_TABLE_NAME='profiles' THEN (to_jsonb(NEW)->>'id')::uuid ELSE (to_jsonb(NEW)->>'user_id')::uuid END;
  -- Serialize with the request; service workers cannot resurrect queued accounts.
  PERFORM 1 FROM auth.users WHERE id=actor FOR KEY SHARE;
  IF NOT public.account_is_active(actor) THEN
    RAISE EXCEPTION 'Account is unavailable' USING ERRCODE='42501';
  END IF;
  RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION public.reject_deleted_account_write() FROM PUBLIC,anon,authenticated,service_role;
DO $guards$ DECLARE target text; BEGIN
  FOREACH target IN ARRAY ARRAY['profiles','user_categories','briefings','device_tokens','briefing_generation_jobs','notification_deliveries'] LOOP
    EXECUTE format('CREATE TRIGGER account_write_guard BEFORE INSERT OR UPDATE ON public.%I FOR EACH ROW EXECUTE FUNCTION public.reject_deleted_account_write()',target);
  END LOOP;
END $guards$;

CREATE FUNCTION public.request_account_deletion(p_user_id uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
DECLARE job public.account_deletion_jobs;
BEGIN
  PERFORM 1 FROM auth.users WHERE id=p_user_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Account not found' USING ERRCODE='22023'; END IF;
  SELECT * INTO job FROM public.account_deletion_jobs WHERE user_id=p_user_id;
  IF FOUND THEN RETURN to_jsonb(job); END IF;
  UPDATE public.device_tokens SET is_active=false,updated_at=clock_timestamp() WHERE user_id=p_user_id;
  DELETE FROM public.notification_deliveries WHERE user_id=p_user_id;
  INSERT INTO public.account_deletion_jobs(user_id) VALUES(p_user_id) RETURNING * INTO job;
  RETURN to_jsonb(job);
END $$;

CREATE FUNCTION public.claim_account_deletion() RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
DECLARE job public.account_deletion_jobs;
BEGIN
  UPDATE public.account_deletion_jobs SET state='failed',lease_until=NULL,lease_token=NULL
    WHERE state='processing' AND lease_until<=clock_timestamp() AND attempts>=20;
  SELECT * INTO job FROM public.account_deletion_jobs
    WHERE state IN ('pending','processing') AND available_at<=clock_timestamp() AND attempts<20
      AND (lease_until IS NULL OR lease_until<=clock_timestamp())
    ORDER BY available_at,user_id LIMIT 1 FOR UPDATE SKIP LOCKED;
  IF NOT FOUND THEN RETURN NULL; END IF;
  UPDATE public.account_deletion_jobs SET state='processing',attempts=attempts+1,
    lease_token=gen_random_uuid(),lease_until=clock_timestamp()+interval '5 minutes'
    WHERE user_id=job.user_id RETURNING * INTO job;
  RETURN to_jsonb(job);
END $$;

-- Renew the exact lease while inventorying bounded batches of this user's objects.
CREATE FUNCTION public.deletion_object_paths(p_user_id uuid,p_lease_token uuid)
RETURNS SETOF text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
BEGIN
  UPDATE public.account_deletion_jobs SET lease_until=clock_timestamp()+interval '5 minutes'
    WHERE user_id=p_user_id AND lease_token=p_lease_token AND state='processing'
      AND lease_until>clock_timestamp();
  IF NOT FOUND THEN RAISE EXCEPTION 'Deletion lease lost' USING ERRCODE='40001'; END IF;
  RETURN QUERY SELECT name FROM storage.objects
    WHERE bucket_id='briefings' AND name LIKE p_user_id::text||'/%' ORDER BY name LIMIT 100;
END $$;

CREATE FUNCTION public.finish_account_deletion(p_user_id uuid,p_lease_token uuid,p_success boolean)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
DECLARE job public.account_deletion_jobs;
BEGIN
  SELECT * INTO job FROM public.account_deletion_jobs WHERE user_id=p_user_id FOR UPDATE;
  IF NOT FOUND OR job.lease_token IS DISTINCT FROM p_lease_token OR job.state<>'processing'
    OR job.lease_until<=clock_timestamp() THEN RETURN false; END IF;
  IF p_success THEN
    IF EXISTS(SELECT 1 FROM auth.users WHERE id=p_user_id)
      OR EXISTS(SELECT 1 FROM storage.objects WHERE bucket_id='briefings' AND name LIKE p_user_id::text||'/%') THEN
      RAISE EXCEPTION 'Account cleanup is incomplete' USING ERRCODE='22023';
    END IF;
    DELETE FROM public.account_deletion_jobs WHERE user_id=p_user_id;
  ELSE
    UPDATE public.account_deletion_jobs SET state=CASE WHEN attempts>=20 THEN 'failed' ELSE 'pending' END,
      available_at=clock_timestamp()+interval '5 minutes',lease_token=NULL,lease_until=NULL WHERE user_id=p_user_id;
  END IF;
  RETURN true;
END $$;
REVOKE ALL ON FUNCTION public.request_account_deletion(uuid) FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.claim_account_deletion() FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.deletion_object_paths(uuid,uuid) FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.finish_account_deletion(uuid,uuid,boolean) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.request_account_deletion(uuid) TO service_role;
GRANT EXECUTE ON FUNCTION public.claim_account_deletion() TO service_role;
GRANT EXECUTE ON FUNCTION public.deletion_object_paths(uuid,uuid) TO service_role;
GRANT EXECUTE ON FUNCTION public.finish_account_deletion(uuid,uuid,boolean) TO service_role;
COMMIT;
