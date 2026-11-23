-- Production operations: durable billing cache, webhook idempotency, feedback,
-- and bounded retention. Private operational tables are service-role only.

BEGIN;

CREATE TABLE public.purchase_entitlements (
  user_id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  active boolean NOT NULL DEFAULT false,
  expires_at timestamptz,
  environment text NOT NULL DEFAULT 'unknown' CHECK (environment IN ('production','sandbox','unknown')),
  source text NOT NULL DEFAULT 'revenuecat' CHECK (source = 'revenuecat'),
  checked_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX purchase_entitlements_checked_idx ON public.purchase_entitlements(checked_at);
ALTER TABLE public.purchase_entitlements ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.purchase_entitlements FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.purchase_entitlements TO service_role;

CREATE TABLE public.billing_events (
  event_id text PRIMARY KEY CHECK (length(event_id) BETWEEN 1 AND 160),
  event_type text NOT NULL CHECK (length(event_type) BETWEEN 1 AND 80),
  app_user_id uuid,
  environment text NOT NULL DEFAULT 'unknown' CHECK (environment IN ('production','sandbox','unknown')),
  received_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  processed_at timestamptz,
  error_code text CHECK (error_code IS NULL OR length(error_code) <= 80)
);

CREATE INDEX billing_events_received_idx ON public.billing_events(received_at);
ALTER TABLE public.billing_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.billing_events FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.billing_events TO service_role;

CREATE TABLE public.pronunciation_reports (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  briefing_id uuid NOT NULL REFERENCES public.briefings(id) ON DELETE CASCADE,
  phrase text NOT NULL CHECK (length(btrim(phrase)) BETWEEN 1 AND 160),
  notes text CHECK (notes IS NULL OR length(notes) <= 500),
  status text NOT NULL DEFAULT 'new' CHECK (status IN ('new','reviewed','resolved')),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX pronunciation_reports_owner_idx ON public.pronunciation_reports(user_id,created_at DESC);
CREATE INDEX pronunciation_reports_status_idx ON public.pronunciation_reports(status,created_at);
ALTER TABLE public.pronunciation_reports ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.pronunciation_reports FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT ON public.pronunciation_reports TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.pronunciation_reports TO service_role;
CREATE POLICY pronunciation_reports_select_own ON public.pronunciation_reports
  FOR SELECT TO authenticated USING ((SELECT auth.uid()) = user_id);
CREATE POLICY pronunciation_reports_insert_own ON public.pronunciation_reports
  FOR INSERT TO authenticated WITH CHECK ((SELECT auth.uid()) = user_id);

CREATE TABLE public.pronunciation_lexicon (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  term text NOT NULL UNIQUE CHECK (length(btrim(term)) BETWEEN 1 AND 120),
  spoken_form text NOT NULL CHECK (length(btrim(spoken_form)) BETWEEN 1 AND 240),
  locale text NOT NULL DEFAULT 'my-MM' CHECK (locale IN ('my-MM')),
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

ALTER TABLE public.pronunciation_lexicon ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.pronunciation_lexicon FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.pronunciation_lexicon TO service_role;

CREATE FUNCTION public.run_production_retention(
  p_request_days integer DEFAULT 30,
  p_notification_days integer DEFAULT 30,
  p_billing_days integer DEFAULT 90,
  p_deletion_days integer DEFAULT 30
) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE result jsonb := '{}'::jsonb; affected integer;
BEGIN
  IF p_request_days NOT BETWEEN 7 AND 365
     OR p_notification_days NOT BETWEEN 7 AND 365
     OR p_billing_days NOT BETWEEN 30 AND 730
     OR p_deletion_days NOT BETWEEN 7 AND 365 THEN
    RAISE EXCEPTION 'Retention values are outside allowed bounds';
  END IF;

  DELETE FROM public.briefing_requests
   WHERE state IN ('ready','failed') AND updated_at < clock_timestamp() - make_interval(days => p_request_days);
  GET DIAGNOSTICS affected = ROW_COUNT;
  result := result || jsonb_build_object('briefing_requests', affected);

  DELETE FROM public.notification_deliveries
   WHERE state IN ('sent','dead','cancelled')
     AND coalesce(sent_at, available_at, created_at) < clock_timestamp() - make_interval(days => p_notification_days);
  GET DIAGNOSTICS affected = ROW_COUNT;
  result := result || jsonb_build_object('notification_deliveries', affected);

  DELETE FROM public.billing_events
   WHERE received_at < clock_timestamp() - make_interval(days => p_billing_days);
  GET DIAGNOSTICS affected = ROW_COUNT;
  result := result || jsonb_build_object('billing_events', affected);

  DELETE FROM public.account_deletion_jobs
   WHERE state = 'failed' AND available_at < clock_timestamp() - make_interval(days => p_deletion_days);
  GET DIAGNOSTICS affected = ROW_COUNT;
  RETURN result || jsonb_build_object('account_deletion_jobs', affected);
END;
$$;

REVOKE ALL ON FUNCTION public.run_production_retention(integer,integer,integer,integer) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.run_production_retention(integer,integer,integer,integer) TO service_role;

COMMIT;
