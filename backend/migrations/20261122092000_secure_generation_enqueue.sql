CREATE OR REPLACE FUNCTION public.enqueue_briefing_request(
  p_date date, p_request_key text, p_length text DEFAULT 'standard')
RETURNS public.briefing_requests
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE actor uuid := auth.uid(); queued public.briefing_requests;
BEGIN
  IF actor IS NULL THEN RAISE EXCEPTION 'Authentication required' USING ERRCODE='42501'; END IF;
  IF p_request_key IS NULL OR length(p_request_key) NOT BETWEEN 8 AND 128
     OR p_length NOT IN ('quick','standard','detailed') THEN
    RAISE EXCEPTION 'Invalid generation request' USING ERRCODE='22023';
  END IF;
  SELECT * INTO queued FROM public.briefing_requests
    WHERE user_id=actor AND request_key=p_request_key;
  IF FOUND THEN RETURN queued; END IF;
  SELECT * INTO queued FROM public.briefing_requests
    WHERE user_id=actor
      AND state IN ('queued','selecting','checking_sources','writing','synthesizing','finalizing')
    ORDER BY created_at DESC LIMIT 1;
  IF FOUND THEN RETURN queued; END IF;
  INSERT INTO public.briefing_requests(user_id,briefing_date,request_key,length)
    VALUES(actor,p_date,p_request_key,p_length) RETURNING * INTO queued;
  RETURN queued;
END $$;
REVOKE ALL ON FUNCTION public.enqueue_briefing_request(date,text,text) FROM PUBLIC,anon;
GRANT EXECUTE ON FUNCTION public.enqueue_briefing_request(date,text,text) TO authenticated;
