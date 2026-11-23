-- Authorized staging only. All synthetic records roll back; no push provider calls.
BEGIN;
SET LOCAL statement_timeout='30s';
DO $test$
DECLARE u uuid:=gen_random_uuid(); v uuid:=gen_random_uuid(); d uuid:=gen_random_uuid();
  b uuid:=gen_random_uuid(); job jsonb; old_job jsonb; claimed jsonb; owner_role text:=current_user;
BEGIN
  IF EXISTS(SELECT 1 FROM public.notification_deliveries) THEN
    RAISE EXCEPTION 'Smoke test requires an empty notification queue';
  END IF;
  INSERT INTO auth.users(id) VALUES(u),(v);
  INSERT INTO public.device_tokens(id,user_id,fcm_token) VALUES(d,u,'fixture-only-'||d);
  INSERT INTO public.briefings(id,user_id,briefing_date,status,audio_url)
    VALUES(b,u,current_date,'ready','fixture-only.mp3');
  UPDATE public.briefings SET audio_url='regenerated-fixture.mp3' WHERE id=b;
  IF (SELECT count(*) FROM public.notification_deliveries)<>1 THEN RAISE EXCEPTION 'Queue deduplication failed'; END IF;
  PERFORM set_config('role','service_role',true);
  job:=public.claim_notification_delivery();
  IF job IS NULL OR public.claim_notification_delivery() IS NOT NULL THEN RAISE EXCEPTION 'Lease claim failed'; END IF;
  PERFORM set_config('role',owner_role,true);
  UPDATE public.notification_deliveries SET lease_until=now()-interval '1 second';
  PERFORM set_config('role','service_role',true);
  old_job:=job; job:=public.claim_notification_delivery();
  IF public.finish_notification_delivery((old_job->>'id')::uuid,(old_job->>'lease_token')::uuid,'sent')
    THEN RAISE EXCEPTION 'Stale lease accepted'; END IF;
  IF NOT public.finish_notification_delivery((job->>'id')::uuid,(job->>'lease_token')::uuid,'retry')
    THEN RAISE EXCEPTION 'Retry rejected'; END IF;
  IF public.claim_notification_delivery() IS NOT NULL THEN RAISE EXCEPTION 'Backoff bypassed'; END IF;
  PERFORM set_config('role',owner_role,true);
  UPDATE public.notification_deliveries SET available_at=now();
  PERFORM set_config('role','service_role',true);
  job:=public.claim_notification_delivery();
  IF NOT public.finish_notification_delivery((job->>'id')::uuid,(job->>'lease_token')::uuid,'invalid')
    THEN RAISE EXCEPTION 'Invalid-token acknowledgement failed'; END IF;
  PERFORM set_config('role',owner_role,true);
  IF (SELECT is_active FROM public.device_tokens WHERE id=d) THEN RAISE EXCEPTION 'Invalid device remained active'; END IF;
  UPDATE public.device_tokens SET is_active=true WHERE id=d;
  INSERT INTO public.briefings(user_id,briefing_date,status,audio_url) VALUES(u,current_date+1,'ready','fixture.mp3');
  UPDATE public.device_tokens SET user_id=v WHERE id=d;
  PERFORM set_config('role','service_role',true);
  IF public.claim_notification_delivery() IS NOT NULL THEN RAISE EXCEPTION 'Reassigned device received old account job'; END IF;
  PERFORM set_config('role','authenticated',true);
  BEGIN
    PERFORM 1 FROM public.notification_deliveries;
    RAISE EXCEPTION 'Client queue access accepted';
  EXCEPTION WHEN insufficient_privilege THEN NULL; END;
  BEGIN
    PERFORM public.claim_notification_delivery();
    RAISE EXCEPTION 'Client claim accepted';
  EXCEPTION WHEN insufficient_privilege THEN NULL; END;
  PERFORM set_config('role',owner_role,true);
END $test$;
SELECT 'PASS: enqueue, dedupe, leases, retry, invalid-token cleanup, account isolation and client denial' AS result;
ROLLBACK;
