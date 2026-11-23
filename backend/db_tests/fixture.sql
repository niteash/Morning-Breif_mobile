-- Disposable test schema only. Never apply to Supabase or a populated database.
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN CREATE ROLE anon; END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN CREATE ROLE authenticated; END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='service_role') THEN CREATE ROLE service_role; END IF;
END $$;
CREATE SCHEMA auth;
CREATE TABLE auth.users(id uuid PRIMARY KEY);
CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS
$$ SELECT nullif(current_setting('request.jwt.claim.sub',true),'')::uuid $$;
GRANT USAGE ON SCHEMA auth TO authenticated;
CREATE TABLE profiles(id uuid PRIMARY KEY REFERENCES auth.users ON DELETE CASCADE);
CREATE TABLE categories(id uuid PRIMARY KEY, active boolean DEFAULT true);
CREATE TABLE user_categories(user_id uuid REFERENCES auth.users ON DELETE CASCADE, category_id uuid REFERENCES categories,
  PRIMARY KEY(user_id,category_id));
CREATE TABLE briefings(id uuid PRIMARY KEY DEFAULT gen_random_uuid(),user_id uuid REFERENCES auth.users ON DELETE CASCADE,
  briefing_date date,title text DEFAULT 'Morning Brief',script text,audio_url text,duration_seconds integer,
  status text DEFAULT 'pending',generated_at timestamptz,created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),UNIQUE(user_id,briefing_date));
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE briefings ENABLE ROW LEVEL SECURITY;
CREATE POLICY own_profile ON profiles TO authenticated USING(id=auth.uid()) WITH CHECK(id=auth.uid());
CREATE POLICY own_categories ON user_categories TO authenticated USING(user_id=auth.uid()) WITH CHECK(user_id=auth.uid());
CREATE POLICY own_briefings ON briefings TO authenticated USING(user_id=auth.uid()) WITH CHECK(user_id=auth.uid());
GRANT SELECT,INSERT,UPDATE,DELETE ON profiles,user_categories,briefings TO authenticated;
GRANT SELECT ON categories TO authenticated;
GRANT INSERT,UPDATE,DELETE ON briefings TO PUBLIC;
-- Match the broad source grants so the migration must close non-RLS operations too.
GRANT TRUNCATE,REFERENCES,TRIGGER ON profiles,categories,user_categories,briefings TO PUBLIC,anon,authenticated;
INSERT INTO auth.users VALUES ('00000000-0000-0000-0000-000000000001'),('00000000-0000-0000-0000-000000000002');
INSERT INTO profiles SELECT id FROM auth.users;
INSERT INTO categories VALUES ('10000000-0000-0000-0000-000000000001',true),('10000000-0000-0000-0000-000000000002',true),('10000000-0000-0000-0000-000000000003',false);

CREATE FUNCTION claim_briefing_generation(uuid) RETURNS boolean LANGUAGE sql SECURITY DEFINER AS $$ SELECT true $$;
GRANT EXECUTE ON FUNCTION claim_briefing_generation(uuid) TO anon,authenticated,service_role;

CREATE TABLE device_tokens(id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users ON DELETE CASCADE, fcm_token text UNIQUE NOT NULL,
  platform text DEFAULT 'android',is_active boolean DEFAULT true,updated_at timestamptz DEFAULT now());

ALTER TABLE device_tokens ENABLE ROW LEVEL SECURITY;
CREATE POLICY own_devices ON device_tokens TO authenticated USING(user_id=auth.uid()) WITH CHECK(user_id=auth.uid());
CREATE SCHEMA storage;
CREATE TABLE storage.objects(id uuid PRIMARY KEY DEFAULT gen_random_uuid(),bucket_id text,name text);
