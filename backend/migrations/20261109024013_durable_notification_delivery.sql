-- Requires 001_reliable_writes.sql and the inspected device_tokens schema.
BEGIN;
CREATE TABLE public.notification_deliveries (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  briefing_id uuid NOT NULL REFERENCES public.briefings(id) ON DELETE CASCADE,
  device_id uuid NOT NULL REFERENCES public.device_tokens(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  briefing_date date NOT NULL,
  fcm_token text NOT NULL,
  state text NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','sending','sent','dead','cancelled')),
  attempts integer NOT NULL DEFAULT 0 CHECK(attempts BETWEEN 0 AND 5),
  available_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL DEFAULT (now()+interval '24 hours'),
  lease_token uuid,
  lease_until timestamptz,
  sent_at timestamptz,
  last_outcome text CHECK(last_outcome IN ('sent','retry','invalid')),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(briefing_id,device_id)
);
ALTER TABLE public.notification_deliveries ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.notification_deliveries FROM PUBLIC,anon,authenticated;
GRANT SELECT ON public.notification_deliveries TO service_role;
CREATE INDEX notification_deliveries_due_idx ON public.notification_deliveries(available_at,id)
  WHERE state IN ('pending','sending');
CREATE INDEX notification_deliveries_device_idx ON public.notification_deliveries(device_id);
CREATE INDEX notification_deliveries_user_idx ON public.notification_deliveries(user_id);

-- Runs inside the briefing completion transaction; a failed enqueue rolls it back.
CREATE FUNCTION public.enqueue_briefing_notifications() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
BEGIN
  IF NEW.status='ready' AND NEW.audio_url IS NOT NULL THEN
    INSERT INTO public.notification_deliveries(briefing_id,device_id,user_id,briefing_date,fcm_token)
      SELECT NEW.id,d.id,NEW.user_id,NEW.briefing_date,d.fcm_token
      FROM public.device_tokens d WHERE d.user_id=NEW.user_id AND d.is_active AND d.platform='android'
      ON CONFLICT(briefing_id,device_id) DO NOTHING;
  END IF;
  RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION public.enqueue_briefing_notifications() FROM PUBLIC,anon,authenticated,service_role;
CREATE TRIGGER enqueue_ready_briefing AFTER INSERT OR UPDATE OF status,audio_url ON public.briefings
  FOR EACH ROW EXECUTE FUNCTION public.enqueue_briefing_notifications();

-- Service-only RPCs deliberately use definer rights to mutate the client-inaccessible
-- queue. Ownership comes from the saved briefing and current device, never caller input.
CREATE FUNCTION public.claim_notification_delivery() RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE job public.notification_deliveries;
BEGIN
  -- Reclaim abandoned leases; terminal rows cannot consume more attempts.
  UPDATE public.notification_deliveries q SET state='dead',lease_token=NULL,lease_until=NULL
    WHERE q.state IN ('pending','sending') AND (q.lease_until IS NULL OR q.lease_until<=clock_timestamp())
      AND (q.expires_at<=clock_timestamp() OR q.attempts>=5);
  UPDATE public.notification_deliveries q SET state='cancelled',lease_token=NULL,lease_until=NULL
    WHERE q.state IN ('pending','sending') AND (q.lease_until IS NULL OR q.lease_until<=clock_timestamp())
      AND NOT EXISTS(SELECT 1 FROM public.device_tokens d WHERE d.id=q.device_id
        AND d.user_id=q.user_id AND d.fcm_token=q.fcm_token AND d.is_active);
  SELECT q.* INTO job FROM public.notification_deliveries q
    JOIN public.device_tokens d ON d.id=q.device_id AND d.user_id=q.user_id
      AND d.fcm_token=q.fcm_token AND d.is_active
    WHERE q.state IN ('pending','sending') AND q.available_at<=clock_timestamp()
      AND (q.lease_until IS NULL OR q.lease_until<=clock_timestamp())
      AND q.expires_at>clock_timestamp() AND q.attempts<5
    ORDER BY q.available_at,q.id LIMIT 1 FOR UPDATE OF q SKIP LOCKED;
  IF NOT FOUND THEN RETURN NULL; END IF;
  UPDATE public.notification_deliveries SET state='sending',attempts=attempts+1,
    lease_token=gen_random_uuid(),lease_until=clock_timestamp()+interval '5 minutes'
    WHERE id=job.id RETURNING * INTO job;
  RETURN to_jsonb(job);
END $$;

CREATE FUNCTION public.finish_notification_delivery(p_id uuid,p_lease_token uuid,p_outcome text)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE job public.notification_deliveries;
BEGIN
  IF p_outcome IS NULL OR p_outcome NOT IN ('sent','retry','invalid') THEN
    RAISE EXCEPTION 'Invalid delivery outcome' USING ERRCODE='22023';
  END IF;
  SELECT * INTO job FROM public.notification_deliveries WHERE id=p_id FOR UPDATE;
  IF NOT FOUND OR job.state<>'sending' OR job.lease_token IS DISTINCT FROM p_lease_token
     OR job.lease_until<=clock_timestamp() THEN RETURN false; END IF;
  IF p_outcome='invalid' THEN
    -- Never deactivate a token that has since rotated or changed account.
    UPDATE public.device_tokens SET is_active=false,updated_at=clock_timestamp()
      WHERE id=job.device_id AND user_id=job.user_id AND fcm_token=job.fcm_token;
  END IF;
  UPDATE public.notification_deliveries SET
    state=CASE WHEN p_outcome='sent' THEN 'sent' WHEN p_outcome='invalid' OR attempts>=5
      OR expires_at<=clock_timestamp() THEN 'dead' ELSE 'pending' END,
    sent_at=CASE WHEN p_outcome='sent' THEN clock_timestamp() ELSE NULL END,
    available_at=clock_timestamp()+make_interval(secs => (60*power(2,attempts-1))::integer),
    last_outcome=p_outcome,lease_token=NULL,lease_until=NULL WHERE id=p_id;
  RETURN true;
END $$;
REVOKE ALL ON FUNCTION public.claim_notification_delivery() FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.finish_notification_delivery(uuid,uuid,text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.claim_notification_delivery() TO service_role;
GRANT EXECUTE ON FUNCTION public.finish_notification_delivery(uuid,uuid,text) TO service_role;
COMMIT;
