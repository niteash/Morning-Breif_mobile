ALTER TABLE public.briefing_requests
  ADD COLUMN priority integer NOT NULL DEFAULT 0 CHECK (priority BETWEEN 0 AND 10);

DROP INDEX public.briefing_requests_claim_idx;
CREATE INDEX briefing_requests_claim_idx
  ON public.briefing_requests(priority DESC,created_at,id)
  WHERE state='queued';

DROP FUNCTION public.enqueue_briefing_request(uuid,date,text,text);
CREATE FUNCTION public.enqueue_briefing_request(
  p_user_id uuid,p_date date,p_request_key text,p_length text DEFAULT 'standard',p_priority integer DEFAULT 0)
RETURNS public.briefing_requests
LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE queued public.briefing_requests;
BEGIN
  IF p_user_id IS NULL OR p_request_key IS NULL OR length(p_request_key) NOT BETWEEN 8 AND 128
     OR p_length NOT IN ('quick','standard','detailed') OR p_priority NOT BETWEEN 0 AND 10 THEN
    RAISE EXCEPTION 'Invalid generation request' USING ERRCODE='22023';
  END IF;
  SELECT * INTO queued FROM public.briefing_requests
    WHERE user_id=p_user_id AND request_key=p_request_key;
  IF FOUND THEN RETURN queued; END IF;
  SELECT * INTO queued FROM public.briefing_requests
    WHERE user_id=p_user_id
      AND state IN ('queued','selecting','checking_sources','writing','synthesizing','finalizing')
    ORDER BY created_at DESC LIMIT 1;
  IF FOUND THEN RETURN queued; END IF;
  INSERT INTO public.briefing_requests(user_id,briefing_date,request_key,length,priority)
    VALUES(p_user_id,p_date,p_request_key,p_length,p_priority) RETURNING * INTO queued;
  RETURN queued;
END $$;
REVOKE ALL ON FUNCTION public.enqueue_briefing_request(uuid,date,text,text,integer)
  FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.enqueue_briefing_request(uuid,date,text,text,integer) TO service_role;

CREATE OR REPLACE FUNCTION public.claim_briefing_request()
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE job public.briefing_requests; token uuid:=gen_random_uuid();
BEGIN
  UPDATE public.briefing_requests SET state='queued',lease_token=NULL,lease_until=NULL,
      message='Waiting to resume',updated_at=clock_timestamp()
    WHERE state IN ('selecting','checking_sources','writing','synthesizing','finalizing')
      AND lease_until<clock_timestamp() AND attempts<3;
  UPDATE public.briefing_requests SET state='failed',error_code='retry_limit',progress=100,
      finished_at=clock_timestamp(),lease_token=NULL,lease_until=NULL,updated_at=clock_timestamp()
    WHERE state IN ('queued','selecting','checking_sources','writing','synthesizing','finalizing')
      AND attempts>=3 AND (lease_until IS NULL OR lease_until<clock_timestamp());
  SELECT * INTO job FROM public.briefing_requests WHERE state='queued'
    ORDER BY priority DESC,created_at,id FOR UPDATE SKIP LOCKED LIMIT 1;
  IF NOT FOUND THEN RETURN NULL; END IF;
  UPDATE public.briefing_requests SET state='selecting',progress=10,
      message='Finding current stories',lease_token=token,
      lease_until=clock_timestamp()+interval '15 minutes',attempts=attempts+1,
      started_at=coalesce(started_at,clock_timestamp()),updated_at=clock_timestamp()
    WHERE id=job.id RETURNING * INTO job;
  RETURN to_jsonb(job)||jsonb_build_object('lease_token',token);
END $$;
