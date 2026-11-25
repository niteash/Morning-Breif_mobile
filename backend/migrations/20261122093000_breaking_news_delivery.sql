CREATE TABLE public.breaking_news_deliveries (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  news_id uuid NOT NULL REFERENCES public.news_items(id) ON DELETE CASCADE,
  device_id uuid NOT NULL REFERENCES public.device_tokens(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  fcm_token text NOT NULL,
  headline text NOT NULL,
  publisher text NOT NULL,
  state text NOT NULL DEFAULT 'pending'
    CHECK (state IN ('pending','sending','sent','dead','cancelled')),
  attempts integer NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 5),
  available_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  expires_at timestamptz NOT NULL DEFAULT clock_timestamp()+interval '2 hours',
  lease_token uuid,
  lease_until timestamptz,
  sent_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE(news_id,device_id)
);
CREATE INDEX breaking_news_deliveries_due_idx ON public.breaking_news_deliveries(available_at,id)
  WHERE state='pending';
CREATE INDEX breaking_news_deliveries_device_idx ON public.breaking_news_deliveries(device_id);
CREATE INDEX breaking_news_deliveries_user_idx ON public.breaking_news_deliveries(user_id);
ALTER TABLE public.breaking_news_deliveries ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.breaking_news_deliveries FROM PUBLIC,anon,authenticated;

CREATE OR REPLACE FUNCTION public.enqueue_breaking_news(p_since timestamptz)
RETURNS integer LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE inserted integer;
BEGIN
  IF p_since IS NULL OR p_since < clock_timestamp()-interval '2 hours'
     OR p_since > clock_timestamp()+interval '1 minute' THEN
    RAISE EXCEPTION 'Invalid alert window' USING ERRCODE='22023';
  END IF;
  INSERT INTO public.breaking_news_deliveries(
    news_id,device_id,user_id,fcm_token,headline,publisher)
  SELECT n.id,d.id,p.id,d.fcm_token,left(n.title,240),left(n.source,120)
  FROM public.news_items n
  JOIN public.user_categories uc ON uc.category_id=n.category_id
  JOIN public.profiles p ON p.id=uc.user_id AND p.breaking_news_enabled
  JOIN public.device_tokens d ON d.user_id=p.id AND d.is_active AND d.platform='android'
  WHERE n.created_at>=p_since
    AND n.published_at>=clock_timestamp()-interval '6 hours'
    AND n.title ~* '(^|[[:space:]:—-])(breaking|urgent|အရေးပေါ်|လတ်တလော)([[:space:]:—-]|$)'
  ON CONFLICT(news_id,device_id) DO NOTHING;
  GET DIAGNOSTICS inserted=ROW_COUNT;
  RETURN inserted;
END $$;

CREATE OR REPLACE FUNCTION public.claim_breaking_news_delivery()
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE job public.breaking_news_deliveries; token uuid:=gen_random_uuid();
BEGIN
  UPDATE public.breaking_news_deliveries SET state='dead',lease_token=NULL,lease_until=NULL
    WHERE state IN ('pending','sending') AND (expires_at<=clock_timestamp() OR attempts>=5);
  UPDATE public.breaking_news_deliveries SET state='pending',lease_token=NULL,lease_until=NULL
    WHERE state='sending' AND lease_until<clock_timestamp() AND attempts<5 AND expires_at>clock_timestamp();
  SELECT * INTO job FROM public.breaking_news_deliveries
    WHERE state='pending' AND available_at<=clock_timestamp() AND expires_at>clock_timestamp()
    ORDER BY available_at,id FOR UPDATE SKIP LOCKED LIMIT 1;
  IF NOT FOUND THEN RETURN NULL; END IF;
  UPDATE public.breaking_news_deliveries SET state='sending',attempts=attempts+1,
      lease_token=token,lease_until=clock_timestamp()+interval '1 minute'
    WHERE id=job.id RETURNING * INTO job;
  RETURN to_jsonb(job)||jsonb_build_object('lease_token',token);
END $$;

CREATE OR REPLACE FUNCTION public.finish_breaking_news_delivery(
  p_id uuid,p_lease_token uuid,p_outcome text)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
BEGIN
  IF p_outcome NOT IN ('sent','retry','invalid') THEN RETURN false; END IF;
  UPDATE public.breaking_news_deliveries SET
    state=CASE WHEN p_outcome='sent' THEN 'sent' WHEN p_outcome='invalid' THEN 'cancelled' ELSE 'pending' END,
    sent_at=CASE WHEN p_outcome='sent' THEN clock_timestamp() ELSE sent_at END,
    available_at=CASE WHEN p_outcome='retry' THEN clock_timestamp()+make_interval(secs=>least(300,15*(2^attempts)::integer)) ELSE available_at END,
    lease_token=NULL,lease_until=NULL
    WHERE id=p_id AND lease_token=p_lease_token AND state='sending' AND lease_until>clock_timestamp();
  RETURN FOUND;
END $$;

REVOKE ALL ON FUNCTION public.enqueue_breaking_news(timestamptz),
  public.claim_breaking_news_delivery(),public.finish_breaking_news_delivery(uuid,uuid,text)
  FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.enqueue_breaking_news(timestamptz),
  public.claim_breaking_news_delivery(),public.finish_breaking_news_delivery(uuid,uuid,text)
  TO service_role;
