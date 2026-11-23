-- Staging rollout only. No backfill and no public/device grant path.
BEGIN;
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM public.profiles WHERE subscription_status <> 'free') THEN
    RAISE EXCEPTION 'Review existing non-free entitlements before applying trial enforcement';
  END IF;
END $$;
CREATE TABLE public.account_trials (
  user_id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  started_at timestamptz NOT NULL,
  expires_at timestamptz NOT NULL CHECK (expires_at > started_at),
  grant_scope text NOT NULL CHECK (grant_scope IN ('staging_account','android_device')),
  CHECK (expires_at = ((started_at AT TIME ZONE 'UTC') + interval '3 months') AT TIME ZONE 'UTC')
);
ALTER TABLE public.account_trials ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.account_trials FROM PUBLIC, anon, authenticated, service_role;
GRANT SELECT ON public.account_trials TO service_role;
-- UTC calendar arithmetic clamps the original day to the destination month's last day.
CREATE FUNCTION morning_brief_private.trial_expiry(p_start timestamptz) RETURNS timestamptz
LANGUAGE sql IMMUTABLE STRICT SET search_path='' AS $$
  SELECT ((p_start AT TIME ZONE 'UTC') + interval '3 months') AT TIME ZONE 'UTC'
$$;
CREATE FUNCTION morning_brief_private.trial_active_at(p_end timestamptz, p_now timestamptz) RETURNS boolean
LANGUAGE sql IMMUTABLE STRICT SET search_path='' AS $$ SELECT p_now < p_end $$;

CREATE FUNCTION morning_brief_private.trial_status(p_user_id uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE trial public.account_trials; moment timestamptz := clock_timestamp(); state text;
BEGIN
  IF NOT public.account_is_active(p_user_id) THEN RAISE EXCEPTION 'Account unavailable'; END IF;
  SELECT * INTO trial FROM public.account_trials WHERE user_id=p_user_id;
  IF FOUND THEN
    RETURN jsonb_build_object('status',CASE WHEN morning_brief_private.trial_active_at(trial.expires_at,moment) THEN 'trial_active' ELSE 'trial_ended' END,
      'started_at',trial.started_at,'expires_at',trial.expires_at,'server_now',moment,'grant_scope',trial.grant_scope);
  END IF;
  IF NOT EXISTS(SELECT 1 FROM auth.users WHERE id=p_user_id AND email_confirmed_at IS NOT NULL AND coalesce(email,'')<>'' AND NOT coalesce(is_anonymous,false)) THEN
    state := 'verification_required';
  ELSIF NOT EXISTS(SELECT 1 FROM public.profiles WHERE id=p_user_id)
    OR NOT EXISTS(SELECT 1 FROM public.user_categories WHERE user_id=p_user_id)
    OR EXISTS(SELECT 1 FROM public.user_categories uc LEFT JOIN public.categories c ON c.id=uc.category_id WHERE uc.user_id=p_user_id AND c.active IS DISTINCT FROM true) THEN
    state := 'onboarding_required';
  ELSE state := 'claim_required'; END IF;
  RETURN jsonb_build_object('status',state,'started_at',NULL,'expires_at',NULL,'server_now',moment,'grant_scope',NULL);
END $$;

CREATE FUNCTION morning_brief_private.claim_staging_trial(p_user_id uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE result jsonb; moment timestamptz;
BEGIN
  -- Serializes all requests for the account, including across API processes/devices.
  PERFORM 1 FROM auth.users WHERE id=p_user_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Account unavailable'; END IF;
  -- Category replacement already takes this profile lock. Validate under that lock.
  PERFORM 1 FROM public.profiles WHERE id=p_user_id FOR UPDATE;
  result := morning_brief_private.trial_status(p_user_id);
  IF result->>'status' <> 'claim_required' THEN RETURN result; END IF;
  moment := clock_timestamp();
  INSERT INTO public.account_trials(user_id,started_at,expires_at,grant_scope)
    VALUES(p_user_id,moment,morning_brief_private.trial_expiry(moment),'staging_account')
    ON CONFLICT(user_id) DO NOTHING;
  RETURN morning_brief_private.trial_status(p_user_id);
END $$;

-- PostgREST entry points are service-only invokers. Privileged bodies stay private.
CREATE FUNCTION public.get_account_trial(p_user_id uuid) RETURNS jsonb LANGUAGE sql
SECURITY INVOKER SET search_path='' AS $$ SELECT morning_brief_private.trial_status(p_user_id) $$;
CREATE FUNCTION public.claim_staging_account_trial(p_user_id uuid) RETURNS jsonb LANGUAGE sql
SECURITY INVOKER SET search_path='' AS $$ SELECT morning_brief_private.claim_staging_trial(p_user_id) $$;
REVOKE ALL ON FUNCTION morning_brief_private.trial_expiry(timestamptz),
  morning_brief_private.trial_active_at(timestamptz,timestamptz),
  morning_brief_private.trial_status(uuid),morning_brief_private.claim_staging_trial(uuid),
  public.get_account_trial(uuid),public.claim_staging_account_trial(uuid) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION morning_brief_private.trial_status(uuid),morning_brief_private.claim_staging_trial(uuid),
  public.get_account_trial(uuid),public.claim_staging_account_trial(uuid) TO service_role;
COMMIT;
