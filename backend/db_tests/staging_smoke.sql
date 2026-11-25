-- Run only against the designated staging project after migration 001.
-- Synthetic users and data are rolled back; no provider calls or messages are sent.
BEGIN;
SET LOCAL statement_timeout = '30s';
DO $test$
DECLARE
  a uuid := gen_random_uuid(); b uuid := gen_random_uuid();
  c uuid := gen_random_uuid(); inactive uuid := gen_random_uuid();
  d date := current_date;
  claim jsonb; saved jsonb; old_token uuid; new_token uuid; b_token uuid;
  n integer; role_name text; table_name text; privilege_name text;
BEGIN
  INSERT INTO auth.users(id) VALUES(a),(b);
  INSERT INTO public.profiles(id) VALUES(a),(b);
  INSERT INTO public.categories(id,slug,name_en,name_my,active) VALUES
    (c,'test-'||c,'Test','Test',true),
    (inactive,'test-'||inactive,'Inactive','Inactive',false);

  PERFORM set_config('request.jwt.claim.sub',a::text,true);
  PERFORM set_config('role','authenticated',true);
  SELECT count(*) INTO n FROM public.profiles WHERE id IN (a,b);
  IF n <> 1 THEN RAISE EXCEPTION 'Profile read isolation failed'; END IF;
  UPDATE public.profiles SET name='forbidden' WHERE id=b;
  GET DIAGNOSTICS n = ROW_COUNT;
  IF n <> 0 THEN RAISE EXCEPTION 'Profile write isolation failed'; END IF;
  PERFORM public.replace_my_categories(ARRAY[c,c]);
  SELECT count(*) INTO n FROM public.user_categories WHERE user_id=a;
  IF n <> 1 THEN RAISE EXCEPTION 'Category deduplication failed'; END IF;
  BEGIN
    PERFORM public.replace_my_categories(ARRAY[inactive]);
    RAISE EXCEPTION 'Inactive category accepted';
  EXCEPTION WHEN invalid_parameter_value THEN NULL; END;
  SELECT count(*) INTO n FROM public.user_categories WHERE user_id=a AND category_id=c;
  IF n <> 1 THEN RAISE EXCEPTION 'Failed replacement lost saved categories'; END IF;
  BEGIN
    INSERT INTO public.user_categories(user_id,category_id) VALUES(b,c);
    RAISE EXCEPTION 'Cross-user category insertion accepted';
  EXCEPTION WHEN insufficient_privilege THEN NULL; END;
  BEGIN
    PERFORM public.claim_briefing_v2(a,d);
    RAISE EXCEPTION 'Client claim accepted';
  EXCEPTION WHEN insufficient_privilege THEN NULL; END;
  BEGIN
    INSERT INTO public.briefings(user_id,briefing_date) VALUES(a,d);
    RAISE EXCEPTION 'Client briefing insertion accepted';
  EXCEPTION WHEN insufficient_privilege THEN NULL; END;
  BEGIN
    PERFORM 1 FROM public.briefing_generation_jobs;
    RAISE EXCEPTION 'Client job read accepted';
  EXCEPTION WHEN insufficient_privilege THEN NULL; END;
  BEGIN
    TRUNCATE public.briefings;
    RAISE EXCEPTION 'Client truncate accepted';
  EXCEPTION WHEN insufficient_privilege THEN NULL; END;

  PERFORM set_config('request.jwt.claim.sub',b::text,true);
  PERFORM public.replace_my_categories(ARRAY[c]);
  SELECT count(*) INTO n FROM public.user_categories WHERE user_id IN (a,b);
  IF n <> 1 THEN RAISE EXCEPTION 'Category read isolation failed'; END IF;

  PERFORM set_config('role','service_role',true);
  claim := public.claim_briefing_v2(a,d,false,'first');
  IF claim->>'outcome' <> 'claimed' THEN RAISE EXCEPTION 'Initial claim failed'; END IF;
  old_token := (claim->>'token')::uuid;
  claim := public.claim_briefing_v2(a,d,false,'first');
  IF claim->>'outcome' <> 'busy' THEN RAISE EXCEPTION 'Active lease not protected'; END IF;
  PERFORM set_config('role','postgres',true);
  UPDATE public.briefing_generation_jobs SET lease_until=clock_timestamp()-interval '1 second'
    WHERE user_id=a AND briefing_date=d;
  PERFORM set_config('role','service_role',true);
  saved := public.finish_briefing_v2(a,d,old_token,'script',a||'/'||d||'/test.mp3',42);
  IF saved IS NOT NULL THEN RAISE EXCEPTION 'Expired owner published'; END IF;
  claim := public.claim_briefing_v2(a,d,false,'replacement');
  IF claim->>'outcome' <> 'claimed' THEN RAISE EXCEPTION 'Expired lease not reclaimed'; END IF;
  new_token := (claim->>'token')::uuid;
  saved := public.finish_briefing_v2(a,d,old_token,'script',a||'/'||d||'/test.mp3',42);
  IF saved IS NOT NULL THEN RAISE EXCEPTION 'Superseded owner published'; END IF;
  IF public.fail_briefing_v2(a,d,old_token) THEN RAISE EXCEPTION 'Superseded owner failed job'; END IF;
  saved := public.finish_briefing_v2(a,d,new_token,'script',a||'/'||d||'/test.mp3',42);
  IF saved->>'status' <> 'ready' OR (saved->>'duration_seconds')::integer <> 42 THEN
    RAISE EXCEPTION 'Valid completion not saved';
  END IF;
  claim := public.claim_briefing_v2(a,d,true,'replacement');
  IF claim->>'outcome' <> 'ready' THEN RAISE EXCEPTION 'Completed replay spent another attempt'; END IF;
  claim := public.claim_briefing_v2(a,d,true,'regeneration');
  IF claim->>'outcome' <> 'claimed' THEN RAISE EXCEPTION 'Regeneration failed'; END IF;
  IF NOT public.fail_briefing_v2(a,d,(claim->>'token')::uuid) THEN
    RAISE EXCEPTION 'Failure transition failed';
  END IF;
  claim := public.claim_briefing_v2(a,d,true,'fourth');
  IF claim->>'outcome' <> 'limited' THEN RAISE EXCEPTION 'Attempt cap not enforced'; END IF;
  claim := public.claim_briefing_v2(a,d,false,NULL);
  IF claim->>'outcome' <> 'ready' THEN RAISE EXCEPTION 'Failed regeneration lost ready briefing'; END IF;
  claim := public.claim_briefing_v2(b,d,false,'failure');
  b_token := (claim->>'token')::uuid;
  IF NOT public.fail_briefing_v2(b,d,b_token) THEN RAISE EXCEPTION 'Initial failure not saved'; END IF;
  claim := public.claim_briefing_v2(b,d,false,'retry');
  IF claim->>'outcome' <> 'busy' THEN RAISE EXCEPTION 'Failure cooldown not enforced'; END IF;

  PERFORM set_config('role','authenticated',true);
  PERFORM set_config('request.jwt.claim.sub',a::text,true);
  SELECT count(*) INTO n FROM public.briefings WHERE user_id IN (a,b);
  IF n <> 1 THEN RAISE EXCEPTION 'Briefing read isolation failed'; END IF;
  SELECT count(*) INTO n FROM public.briefings WHERE user_id=a AND status='ready';
  IF n <> 1 THEN RAISE EXCEPTION 'Ready briefing not preserved'; END IF;
  PERFORM set_config('request.jwt.claim.sub',b::text,true);
  SELECT count(*) INTO n FROM public.briefings WHERE user_id=b AND status='failed';
  IF n <> 1 THEN RAISE EXCEPTION 'First-time failed briefing not persisted'; END IF;
  PERFORM set_config('role','anon',true);
  BEGIN
    PERFORM public.replace_my_categories(ARRAY[c]);
    RAISE EXCEPTION 'Anonymous category write accepted';
  EXCEPTION WHEN insufficient_privilege THEN NULL; END;
  PERFORM set_config('role','postgres',true);

  FOREACH role_name IN ARRAY ARRAY['anon','authenticated'] LOOP
    FOREACH table_name IN ARRAY ARRAY['profiles','categories','user_categories','briefings','device_tokens','news_items'] LOOP
      FOREACH privilege_name IN ARRAY ARRAY['TRUNCATE','REFERENCES','TRIGGER'] LOOP
        IF has_table_privilege(role_name,'public.'||table_name,privilege_name) THEN
          RAISE EXCEPTION 'Unexpected % on % for %',privilege_name,table_name,role_name;
        END IF;
      END LOOP;
    END LOOP;
    IF has_function_privilege(role_name,'public.claim_briefing_generation(uuid,date,integer)','EXECUTE') THEN
      RAISE EXCEPTION 'Legacy claim still callable';
    END IF;
  END LOOP;
END $test$;
SELECT 'PASS: RLS, atomic category validation, client grants, leases, fencing, replay, quotas, failure preservation and cooldown' AS result;
ROLLBACK;
