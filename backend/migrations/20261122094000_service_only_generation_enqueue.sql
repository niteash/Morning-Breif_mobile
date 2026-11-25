DROP FUNCTION public.enqueue_briefing_request(date,text,text);

CREATE FUNCTION public.enqueue_briefing_request(
  p_user_id uuid,p_date date,p_request_key text,p_length text DEFAULT 'standard')
RETURNS public.briefing_requests
LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE queued public.briefing_requests;
BEGIN
  IF p_user_id IS NULL OR p_request_key IS NULL OR length(p_request_key) NOT BETWEEN 8 AND 128
     OR p_length NOT IN ('quick','standard','detailed') THEN
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
  INSERT INTO public.briefing_requests(user_id,briefing_date,request_key,length)
    VALUES(p_user_id,p_date,p_request_key,p_length) RETURNING * INTO queued;
  RETURN queued;
END $$;
REVOKE ALL ON FUNCTION public.enqueue_briefing_request(uuid,date,text,text)
  FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.enqueue_briefing_request(uuid,date,text,text) TO service_role;
