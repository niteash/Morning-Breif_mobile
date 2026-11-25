-- Durable on-demand generation, chapter playback, personalization, and retention.
BEGIN;

ALTER TABLE public.profiles
  ADD COLUMN briefing_length text NOT NULL DEFAULT 'standard',
  ADD COLUMN weekend_delivery_hour integer NOT NULL DEFAULT 8,
  ADD COLUMN weekend_delivery_minute integer NOT NULL DEFAULT 0,
  ADD COLUMN separate_weekend_schedule boolean NOT NULL DEFAULT false,
  ADD COLUMN breaking_news_enabled boolean NOT NULL DEFAULT false,
  ADD COLUMN data_saver_enabled boolean NOT NULL DEFAULT false,
  ADD COLUMN auto_download_wifi boolean NOT NULL DEFAULT false,
  ADD COLUMN listening_streak_enabled boolean NOT NULL DEFAULT false;

ALTER TABLE public.profiles
  ADD CONSTRAINT profiles_briefing_length_check
    CHECK (briefing_length IN ('quick', 'standard', 'detailed')),
  ADD CONSTRAINT profiles_weekend_hour_check
    CHECK (weekend_delivery_hour BETWEEN 0 AND 23),
  ADD CONSTRAINT profiles_weekend_minute_check
    CHECK (weekend_delivery_minute BETWEEN 0 AND 59);

ALTER TABLE public.briefings
  ADD COLUMN chapters jsonb,
  ADD COLUMN target_minutes integer;

ALTER TABLE public.briefings
  ADD CONSTRAINT briefings_chapters_array_check
    CHECK (chapters IS NULL OR jsonb_typeof(chapters) = 'array'),
  ADD CONSTRAINT briefings_target_minutes_check
    CHECK (target_minutes IS NULL OR target_minutes BETWEEN 1 AND 30);

CREATE TABLE public.briefing_requests (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  briefing_date date NOT NULL,
  request_key text NOT NULL,
  length text NOT NULL DEFAULT 'standard'
    CHECK (length IN ('quick', 'standard', 'detailed')),
  state text NOT NULL DEFAULT 'queued'
    CHECK (state IN ('queued','selecting','checking_sources','writing','synthesizing','finalizing','ready','failed')),
  progress integer NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
  message text,
  error_code text,
  briefing_id uuid REFERENCES public.briefings(id) ON DELETE SET NULL,
  lease_token uuid,
  lease_until timestamptz,
  attempts integer NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 5),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  started_at timestamptz,
  finished_at timestamptz,
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE(user_id, request_key)
);

CREATE UNIQUE INDEX briefing_requests_one_active_user_idx
  ON public.briefing_requests(user_id)
  WHERE state IN ('queued','selecting','checking_sources','writing','synthesizing','finalizing');
CREATE INDEX briefing_requests_claim_idx
  ON public.briefing_requests(created_at, id)
  WHERE state = 'queued';
CREATE INDEX briefing_requests_owner_idx
  ON public.briefing_requests(user_id, created_at DESC);

ALTER TABLE public.briefing_requests ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.briefing_requests FROM PUBLIC, anon, authenticated;
GRANT SELECT ON public.briefing_requests TO authenticated;
CREATE POLICY "Users can read own briefing requests"
  ON public.briefing_requests FOR SELECT TO authenticated
  USING ((SELECT auth.uid()) = user_id);

CREATE TABLE public.story_feedback (
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  story_id uuid NOT NULL REFERENCES public.news_items(id) ON DELETE CASCADE,
  action text NOT NULL CHECK (action IN ('more_like_this','less_like_this','hide_topic','hide_publisher','report_incorrect')),
  reason text CHECK (reason IS NULL OR length(reason) <= 500),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY(user_id, story_id, action)
);
CREATE INDEX story_feedback_story_idx ON public.story_feedback(story_id);
ALTER TABLE public.story_feedback ENABLE ROW LEVEL SECURITY;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.story_feedback TO authenticated;
CREATE POLICY "Users manage own story feedback" ON public.story_feedback
  FOR ALL TO authenticated USING ((SELECT auth.uid()) = user_id)
  WITH CHECK ((SELECT auth.uid()) = user_id);

CREATE TABLE public.listening_progress (
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  briefing_id uuid NOT NULL REFERENCES public.briefings(id) ON DELETE CASCADE,
  position_seconds integer NOT NULL DEFAULT 0 CHECK (position_seconds >= 0),
  listened_seconds integer NOT NULL DEFAULT 0 CHECK (listened_seconds >= 0),
  completed boolean NOT NULL DEFAULT false,
  last_listened_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY(user_id, briefing_id)
);
CREATE INDEX listening_progress_weekly_idx
  ON public.listening_progress(user_id, last_listened_at DESC);
ALTER TABLE public.listening_progress ENABLE ROW LEVEL SECURITY;
GRANT SELECT, INSERT, UPDATE ON public.listening_progress TO authenticated;
CREATE POLICY "Users manage own listening progress" ON public.listening_progress
  FOR ALL TO authenticated USING ((SELECT auth.uid()) = user_id)
  WITH CHECK ((SELECT auth.uid()) = user_id);

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

CREATE OR REPLACE FUNCTION public.claim_briefing_request()
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE job public.briefing_requests; token uuid := gen_random_uuid();
BEGIN
  UPDATE public.briefing_requests SET state='queued',lease_token=NULL,lease_until=NULL,
      message='Waiting to resume',updated_at=clock_timestamp()
    WHERE state IN ('selecting','checking_sources','writing','synthesizing','finalizing')
      AND lease_until < clock_timestamp() AND attempts < 3;
  UPDATE public.briefing_requests SET state='failed',error_code='retry_limit',progress=100,
      finished_at=clock_timestamp(),lease_token=NULL,lease_until=NULL,updated_at=clock_timestamp()
    WHERE state IN ('queued','selecting','checking_sources','writing','synthesizing','finalizing')
      AND attempts >= 3 AND (lease_until IS NULL OR lease_until < clock_timestamp());
  SELECT * INTO job FROM public.briefing_requests WHERE state='queued'
    ORDER BY created_at,id FOR UPDATE SKIP LOCKED LIMIT 1;
  IF NOT FOUND THEN RETURN NULL; END IF;
  UPDATE public.briefing_requests SET state='selecting',progress=10,
      message='Finding current stories',lease_token=token,
      lease_until=clock_timestamp()+interval '15 minutes',attempts=attempts+1,
      started_at=coalesce(started_at,clock_timestamp()),updated_at=clock_timestamp()
    WHERE id=job.id RETURNING * INTO job;
  RETURN to_jsonb(job) || jsonb_build_object('lease_token',token);
END $$;

CREATE OR REPLACE FUNCTION public.update_briefing_request(
  p_id uuid,p_lease_token uuid,p_state text,p_progress integer,p_message text DEFAULT NULL)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
  IF p_state NOT IN ('selecting','checking_sources','writing','synthesizing','finalizing')
     OR p_progress NOT BETWEEN 1 AND 99 THEN RETURN false; END IF;
  UPDATE public.briefing_requests SET state=p_state,progress=p_progress,message=p_message,
      lease_until=clock_timestamp()+interval '15 minutes',updated_at=clock_timestamp()
    WHERE id=p_id AND lease_token=p_lease_token AND lease_until>clock_timestamp()
      AND state NOT IN ('ready','failed');
  RETURN FOUND;
END $$;

CREATE OR REPLACE FUNCTION public.finish_briefing_request(
  p_id uuid,p_lease_token uuid,p_briefing_id uuid)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
  UPDATE public.briefing_requests r SET state='ready',progress=100,message='Your briefing is ready',
      briefing_id=p_briefing_id,lease_token=NULL,lease_until=NULL,
      finished_at=clock_timestamp(),updated_at=clock_timestamp()
    WHERE r.id=p_id AND r.lease_token=p_lease_token AND r.lease_until>clock_timestamp()
      AND EXISTS(SELECT 1 FROM public.briefings b WHERE b.id=p_briefing_id AND b.user_id=r.user_id AND b.status='ready');
  RETURN FOUND;
END $$;

CREATE OR REPLACE FUNCTION public.fail_briefing_request(
  p_id uuid,p_lease_token uuid,p_error_code text,p_message text)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
  UPDATE public.briefing_requests SET state='failed',progress=100,
      error_code=left(coalesce(p_error_code,'generation_failed'),80),
      message=left(coalesce(p_message,'Generation failed temporarily'),240),
      lease_token=NULL,lease_until=NULL,finished_at=clock_timestamp(),updated_at=clock_timestamp()
    WHERE id=p_id AND lease_token=p_lease_token AND state NOT IN ('ready','failed');
  RETURN FOUND;
END $$;

REVOKE ALL ON FUNCTION public.claim_briefing_request(),
  public.update_briefing_request(uuid,uuid,text,integer,text),
  public.finish_briefing_request(uuid,uuid,uuid),
  public.fail_briefing_request(uuid,uuid,text,text)
  FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.claim_briefing_request(),
  public.update_briefing_request(uuid,uuid,text,integer,text),
  public.finish_briefing_request(uuid,uuid,uuid),
  public.fail_briefing_request(uuid,uuid,text,text)
  TO service_role;

-- Notify opted-in scheduled users at their chosen time and always notify a
-- manual requester immediately. The unique delivery key prevents duplicates.
CREATE OR REPLACE FUNCTION public.enqueue_briefing_notifications()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public AS $$
BEGIN
  IF NEW.status = 'ready' AND NEW.audio_url IS NOT NULL THEN
    INSERT INTO public.notification_deliveries(
      briefing_id,device_id,user_id,briefing_date,fcm_token,available_at)
    SELECT NEW.id,d.id,NEW.user_id,NEW.briefing_date,d.fcm_token,
      CASE WHEN EXISTS(
        SELECT 1 FROM public.briefing_requests r
        WHERE r.user_id=NEW.user_id AND r.briefing_date=NEW.briefing_date
          AND r.state IN ('queued','selecting','checking_sources','writing','synthesizing','finalizing')
      ) THEN clock_timestamp()
      ELSE greatest(clock_timestamp(),(NEW.briefing_date + make_time(p.delivery_hour,p.delivery_minute,0)) AT TIME ZONE p.timezone)
      END
    FROM public.device_tokens d JOIN public.profiles p ON p.id=d.user_id
    WHERE d.user_id=NEW.user_id AND d.is_active AND d.platform='android'
      AND (p.daily_reminder_enabled OR EXISTS(
        SELECT 1 FROM public.briefing_requests r
        WHERE r.user_id=NEW.user_id AND r.briefing_date=NEW.briefing_date
          AND r.state IN ('queued','selecting','checking_sources','writing','synthesizing','finalizing')
      ))
    ON CONFLICT(briefing_id,device_id) DO NOTHING;
  END IF;
  RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION public.enqueue_briefing_notifications() FROM PUBLIC,anon,authenticated,service_role;

COMMIT;
