-- Final release operations: user personalization, a cross-process RSS lease,
-- and explicit recovery controls. All worker-only objects remain service-role only.
BEGIN;

ALTER TABLE public.profiles
  ADD COLUMN horoscope_sign text,
  ADD COLUMN crypto_watchlist text[] NOT NULL DEFAULT '{}';

ALTER TABLE public.profiles
  ADD CONSTRAINT profiles_horoscope_sign_check CHECK (
    horoscope_sign IS NULL OR horoscope_sign IN (
      'aries','taurus','gemini','cancer','leo','virgo',
      'libra','scorpio','sagittarius','capricorn','aquarius','pisces'
    )
  ),
  ADD CONSTRAINT profiles_crypto_watchlist_check CHECK (
    cardinality(crypto_watchlist) <= 10
    AND crypto_watchlist <@ ARRAY['BTC','ETH','SOL','XRP','BNB','DOGE','ADA','AVAX','DOT','LINK']::text[]
  );

CREATE TABLE public.worker_leases (
  name text PRIMARY KEY CHECK (name ~ '^[a-z][a-z0-9_]{2,63}$'),
  lease_token uuid NOT NULL,
  lease_until timestamptz NOT NULL,
  owner_hint text CHECK (owner_hint IS NULL OR length(owner_hint) <= 80),
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
ALTER TABLE public.worker_leases ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.worker_leases FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.worker_leases TO service_role;

CREATE FUNCTION public.claim_worker_lease(
  p_name text, p_seconds integer DEFAULT 900, p_owner_hint text DEFAULT NULL
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE token uuid := gen_random_uuid();
BEGIN
  IF p_name IS NULL OR p_name !~ '^[a-z][a-z0-9_]{2,63}$'
     OR p_seconds NOT BETWEEN 30 AND 3600
     OR p_owner_hint IS NOT NULL AND length(p_owner_hint) > 80 THEN
    RAISE EXCEPTION 'Invalid worker lease request' USING ERRCODE='22023';
  END IF;
  INSERT INTO public.worker_leases(name,lease_token,lease_until,owner_hint)
    VALUES(p_name,token,clock_timestamp()+make_interval(secs=>p_seconds),p_owner_hint)
  ON CONFLICT(name) DO UPDATE SET
    lease_token=excluded.lease_token, lease_until=excluded.lease_until,
    owner_hint=excluded.owner_hint, updated_at=clock_timestamp()
  WHERE public.worker_leases.lease_until <= clock_timestamp();
  IF NOT FOUND THEN RETURN NULL; END IF;
  RETURN token;
END;
$$;

CREATE FUNCTION public.release_worker_lease(p_name text, p_token uuid)
RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
BEGIN
  DELETE FROM public.worker_leases WHERE name=p_name AND lease_token=p_token;
  RETURN FOUND;
END;
$$;

CREATE FUNCTION public.retry_failed_operations()
RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE deletion_count integer; generation_count integer; notification_count integer;
BEGIN
  UPDATE public.account_deletion_jobs
    SET state='pending', available_at=clock_timestamp(), lease_token=NULL, lease_until=NULL
    WHERE state='failed' AND attempts < 20;
  GET DIAGNOSTICS deletion_count = ROW_COUNT;

  UPDATE public.briefing_requests
    SET state='queued', progress=0, message='Waiting to retry', error_code=NULL,
        lease_token=NULL, lease_until=NULL, finished_at=NULL, updated_at=clock_timestamp()
    WHERE state='failed' AND attempts < 3
      AND updated_at >= clock_timestamp() - interval '7 days';
  GET DIAGNOSTICS generation_count = ROW_COUNT;

  UPDATE public.notification_deliveries
    SET state='pending', available_at=clock_timestamp(), lease_token=NULL, lease_until=NULL
    WHERE state='dead' AND attempts < 5
      AND available_at >= clock_timestamp() - interval '7 days';
  GET DIAGNOSTICS notification_count = ROW_COUNT;

  RETURN jsonb_build_object(
    'account_deletions',deletion_count,
    'generation_requests',generation_count,
    'notifications',notification_count
  );
END;
$$;

REVOKE ALL ON FUNCTION public.claim_worker_lease(text,integer,text),
  public.release_worker_lease(text,uuid), public.retry_failed_operations()
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.claim_worker_lease(text,integer,text),
  public.release_worker_lease(text,uuid), public.retry_failed_operations()
  TO service_role;

COMMIT;
