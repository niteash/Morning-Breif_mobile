-- Read-only schema inspection. Run on the source and staging targets before 001.
-- Returns schema metadata only; does not read user records or execute application RPCs.
BEGIN READ ONLY;

SELECT current_database() AS database_name, current_user AS database_role,
       current_setting('server_version') AS postgres_version;

WITH required(name) AS (
  VALUES ('profiles'), ('categories'), ('user_categories'), ('briefings')
)
SELECT required.name, c.oid IS NOT NULL AS present,
       c.relrowsecurity AS rls_enabled, c.relforcerowsecurity AS rls_forced
FROM required
LEFT JOIN pg_catalog.pg_namespace n ON n.nspname = 'public'
LEFT JOIN pg_catalog.pg_class c ON c.relnamespace = n.oid AND c.relname = required.name;

SELECT table_name, column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN ('profiles', 'categories', 'user_categories', 'briefings')
ORDER BY table_name, ordinal_position;

SELECT c.relname AS table_name, i.relname AS index_name,
       x.indisunique AS is_unique, x.indisvalid AS is_valid,
       pg_get_indexdef(x.indexrelid) AS definition
FROM pg_catalog.pg_index x
JOIN pg_catalog.pg_class c ON c.oid = x.indrelid
JOIN pg_catalog.pg_class i ON i.oid = x.indexrelid
JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relname IN ('briefings', 'user_categories');

SELECT conrelid::regclass AS table_name, conname AS constraint_name,
       pg_get_constraintdef(oid) AS definition
FROM pg_catalog.pg_constraint
WHERE conrelid IN (to_regclass('public.briefings'), to_regclass('public.user_categories'));

SELECT tablename, policyname, permissive, roles, cmd, qual, with_check
FROM pg_catalog.pg_policies
WHERE schemaname = 'public'
  AND tablename IN ('profiles', 'categories', 'user_categories', 'briefings');

-- information_schema.table_privileges is incomplete for the read-only inspection role.
-- Inspect effective access for the actual application roles instead.
SELECT r.rolname AS grantee, c.relname AS table_name,
       has_table_privilege(r.rolname, c.oid, 'SELECT') AS can_select,
       has_table_privilege(r.rolname, c.oid, 'INSERT') AS can_insert,
       has_table_privilege(r.rolname, c.oid, 'UPDATE') AS can_update,
       has_table_privilege(r.rolname, c.oid, 'DELETE') AS can_delete
FROM pg_catalog.pg_roles r CROSS JOIN pg_catalog.pg_class c
JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
WHERE r.rolname IN ('anon', 'authenticated', 'service_role')
  AND n.nspname = 'public'
  AND c.relname IN ('profiles', 'categories', 'user_categories', 'briefings')
ORDER BY c.relname, r.rolname;

SELECT p.oid::regprocedure AS signature, p.prosecdef AS security_definer,
       p.proconfig AS configuration, p.proacl AS grants
FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
WHERE n.nspname = 'public' AND p.proname IN (
  'claim_briefing_generation', 'replace_my_categories',
  'claim_briefing_v2', 'finish_briefing_v2', 'fail_briefing_v2'
);

SELECT to_regclass('public.briefing_generation_jobs') IS NOT NULL AS jobs_table_exists;

ROLLBACK;
