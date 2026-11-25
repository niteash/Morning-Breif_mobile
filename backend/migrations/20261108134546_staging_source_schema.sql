-- Application schema captured from source catalogs on 2026-11-08.

-- Staging bootstrap only: contains no user records, credentials, bucket objects or category data.

-- Source grants/policies are preserved here; reliable_writes immediately restricts generation.

SET LOCAL search_path = public, pg_catalog;

CREATE TABLE public."briefings" (
  "id" uuid DEFAULT gen_random_uuid() NOT NULL,
  "user_id" uuid NOT NULL,
  "briefing_date" date NOT NULL,
  "title" text DEFAULT 'Morning Brief'::text NOT NULL,
  "script" text,
  "audio_url" text,
  "duration_seconds" integer,
  "status" text DEFAULT 'pending'::text NOT NULL,
  "created_at" timestamp with time zone DEFAULT now() NOT NULL,
  "updated_at" timestamp with time zone DEFAULT now() NOT NULL,
  "generated_at" timestamp with time zone
);

CREATE TABLE public."categories" (
  "id" uuid DEFAULT gen_random_uuid() NOT NULL,
  "slug" text NOT NULL,
  "name_en" text NOT NULL,
  "name_my" text NOT NULL,
  "active" boolean DEFAULT true NOT NULL,
  "created_at" timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE public."device_tokens" (
  "id" uuid DEFAULT gen_random_uuid() NOT NULL,
  "user_id" uuid NOT NULL,
  "fcm_token" text NOT NULL,
  "platform" text DEFAULT 'android'::text NOT NULL,
  "is_active" boolean DEFAULT true NOT NULL,
  "created_at" timestamp with time zone DEFAULT now() NOT NULL,
  "updated_at" timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE public."news_items" (
  "id" uuid DEFAULT gen_random_uuid() NOT NULL,
  "category_id" uuid NOT NULL,
  "source" text NOT NULL,
  "title" text NOT NULL,
  "description" text,
  "content" text,
  "url" text NOT NULL,
  "image_url" text,
  "author" text,
  "published_at" timestamp with time zone,
  "content_hash" text,
  "created_at" timestamp with time zone DEFAULT now() NOT NULL,
  "title_hash" text
);

CREATE TABLE public."profiles" (
  "id" uuid NOT NULL,
  "name" text,
  "timezone" text DEFAULT 'Asia/Yangon'::text NOT NULL,
  "delivery_hour" integer DEFAULT 7 NOT NULL,
  "delivery_minute" integer DEFAULT 0 NOT NULL,
  "subscription_status" text DEFAULT 'free'::text NOT NULL,
  "created_at" timestamp with time zone DEFAULT now() NOT NULL,
  "updated_at" timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE public."user_categories" (
  "user_id" uuid NOT NULL,
  "category_id" uuid NOT NULL,
  "created_at" timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE public."categories" ADD CONSTRAINT "categories_pkey" PRIMARY KEY (id);

ALTER TABLE public."categories" ADD CONSTRAINT "categories_slug_key" UNIQUE (slug);

ALTER TABLE public."profiles" ADD CONSTRAINT "profiles_pkey" PRIMARY KEY (id);

ALTER TABLE public."user_categories" ADD CONSTRAINT "user_categories_pkey" PRIMARY KEY (user_id, category_id);

ALTER TABLE public."device_tokens" ADD CONSTRAINT "device_tokens_fcm_token_key" UNIQUE (fcm_token);

ALTER TABLE public."device_tokens" ADD CONSTRAINT "device_tokens_pkey" PRIMARY KEY (id);

ALTER TABLE public."device_tokens" ADD CONSTRAINT "device_tokens_platform_check" CHECK ((platform = ANY (ARRAY['android'::text, 'ios'::text, 'web'::text])));

ALTER TABLE public."news_items" ADD CONSTRAINT "news_items_content_hash_key" UNIQUE (content_hash);

ALTER TABLE public."news_items" ADD CONSTRAINT "news_items_pkey" PRIMARY KEY (id);

ALTER TABLE public."briefings" ADD CONSTRAINT "briefings_pkey" PRIMARY KEY (id);

ALTER TABLE public."briefings" ADD CONSTRAINT "briefings_status_check" CHECK ((status = ANY (ARRAY['pending'::text, 'generating'::text, 'ready'::text, 'failed'::text])));

ALTER TABLE public."briefings" ADD CONSTRAINT "briefings_user_id_briefing_date_key" UNIQUE (user_id, briefing_date);

ALTER TABLE public."profiles" ADD CONSTRAINT "profiles_id_fkey" FOREIGN KEY (id) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE public."user_categories" ADD CONSTRAINT "user_categories_category_id_fkey" FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE;

ALTER TABLE public."user_categories" ADD CONSTRAINT "user_categories_user_id_fkey" FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE public."device_tokens" ADD CONSTRAINT "device_tokens_user_id_fkey" FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE public."news_items" ADD CONSTRAINT "news_items_category_id_fkey" FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE;

ALTER TABLE public."briefings" ADD CONSTRAINT "briefings_user_id_fkey" FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;

CREATE INDEX idx_news_items_published_category ON public.news_items USING btree (category_id, published_at DESC);

CREATE INDEX news_items_published_at_idx ON public.news_items USING btree (published_at DESC);

CREATE INDEX news_items_category_id_idx ON public.news_items USING btree (category_id);

CREATE INDEX idx_device_tokens_user_id ON public.device_tokens USING btree (user_id);

CREATE INDEX news_items_category_published_idx ON public.news_items USING btree (category_id, published_at DESC);

CREATE INDEX idx_news_items_title_hash ON public.news_items USING btree (title_hash);

ALTER TABLE public."briefings" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public."briefings" FROM PUBLIC, anon, authenticated, service_role;

GRANT ALL ON public."briefings" TO anon, authenticated, service_role;

ALTER TABLE public."categories" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public."categories" FROM PUBLIC, anon, authenticated, service_role;

GRANT ALL ON public."categories" TO anon, authenticated, service_role;

ALTER TABLE public."device_tokens" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public."device_tokens" FROM PUBLIC, anon, authenticated, service_role;

GRANT ALL ON public."device_tokens" TO anon, authenticated, service_role;

ALTER TABLE public."news_items" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public."news_items" FROM PUBLIC, anon, authenticated, service_role;

GRANT ALL ON public."news_items" TO anon, authenticated, service_role;

ALTER TABLE public."profiles" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public."profiles" FROM PUBLIC, anon, authenticated, service_role;

GRANT ALL ON public."profiles" TO anon, authenticated, service_role;

ALTER TABLE public."user_categories" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public."user_categories" FROM PUBLIC, anon, authenticated, service_role;

GRANT ALL ON public."user_categories" TO anon, authenticated, service_role;

CREATE POLICY "Anyone can read active categories" ON public."categories" AS PERMISSIVE FOR SELECT TO "anon", "authenticated" USING ((active = true));

CREATE POLICY "Users can create own profile" ON public."profiles" AS PERMISSIVE FOR INSERT TO "authenticated" WITH CHECK ((( SELECT auth.uid() AS uid) = id));

CREATE POLICY "Users can read own profile" ON public."profiles" AS PERMISSIVE FOR SELECT TO "authenticated" USING ((( SELECT auth.uid() AS uid) = id));

CREATE POLICY "Users can update own profile" ON public."profiles" AS PERMISSIVE FOR UPDATE TO "authenticated" USING ((( SELECT auth.uid() AS uid) = id)) WITH CHECK ((( SELECT auth.uid() AS uid) = id));

CREATE POLICY "Users can delete own categories" ON public."user_categories" AS PERMISSIVE FOR DELETE TO "authenticated" USING ((( SELECT auth.uid() AS uid) = user_id));

CREATE POLICY "Users can insert own categories" ON public."user_categories" AS PERMISSIVE FOR INSERT TO "authenticated" WITH CHECK ((( SELECT auth.uid() AS uid) = user_id));

CREATE POLICY "Users can read own categories" ON public."user_categories" AS PERMISSIVE FOR SELECT TO "authenticated" USING ((( SELECT auth.uid() AS uid) = user_id));

CREATE POLICY "Users can view their own device tokens" ON public."device_tokens" AS PERMISSIVE FOR SELECT TO "authenticated" USING ((auth.uid() = user_id));

CREATE POLICY "Authenticated users can read news" ON public."news_items" AS PERMISSIVE FOR SELECT TO "authenticated" USING (true);

CREATE POLICY "Users can insert their own briefings" ON public."briefings" AS PERMISSIVE FOR INSERT TO PUBLIC WITH CHECK ((auth.uid() = user_id));

CREATE POLICY "Users can read their own briefings" ON public."briefings" AS PERMISSIVE FOR SELECT TO "authenticated" USING ((auth.uid() = user_id));

CREATE POLICY "Users can update their own briefings" ON public."briefings" AS PERMISSIVE FOR UPDATE TO PUBLIC USING ((auth.uid() = user_id));

CREATE OR REPLACE FUNCTION public.claim_briefing_generation(p_user_id uuid, p_briefing_date date, p_stale_after_minutes integer DEFAULT 30)
 RETURNS TABLE(briefing_id uuid, briefing_status text, claimed boolean)
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
DECLARE
    v_briefing public.briefings%ROWTYPE;
BEGIN
    IF p_user_id IS NULL OR p_briefing_date IS NULL THEN
        RAISE EXCEPTION 'User ID and briefing date are required';
    END IF;

    IF p_stale_after_minutes < 1 THEN
        RAISE EXCEPTION 'Stale timeout must be at least one minute';
    END IF;

    INSERT INTO public.briefings (
        user_id,
        briefing_date,
        title,
        status
    )
    VALUES (
        p_user_id,
        p_briefing_date,
        'Morning Brief',
        'generating'
    )
    ON CONFLICT (user_id, briefing_date) DO NOTHING;

    SELECT b.*
    INTO v_briefing
    FROM public.briefings AS b
    WHERE b.user_id = p_user_id
      AND b.briefing_date = p_briefing_date
    FOR UPDATE;

    IF v_briefing.status = 'ready' THEN
        RETURN QUERY
        SELECT v_briefing.id, v_briefing.status, FALSE;
        RETURN;
    END IF;

    IF v_briefing.status = 'generating'
       AND v_briefing.updated_at >
           now() - make_interval(mins => p_stale_after_minutes)
    THEN
        RETURN QUERY
        SELECT v_briefing.id, v_briefing.status, FALSE;
        RETURN;
    END IF;

    UPDATE public.briefings AS b
    SET
        status = 'generating',
        updated_at = now()
    WHERE b.id = v_briefing.id;

    RETURN QUERY
    SELECT v_briefing.id, 'generating'::TEXT, TRUE;
END;
$function$;

GRANT EXECUTE ON FUNCTION public.claim_briefing_generation(uuid,date,integer) TO PUBLIC, anon, authenticated, service_role;
