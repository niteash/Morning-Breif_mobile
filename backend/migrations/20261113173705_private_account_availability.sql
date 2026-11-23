-- RLS needs an own-account lookup, but it need not be a public Data API RPC.
BEGIN;
CREATE SCHEMA morning_brief_private;
REVOKE ALL ON SCHEMA morning_brief_private FROM PUBLIC, anon, authenticated, service_role;
GRANT USAGE ON SCHEMA morning_brief_private TO authenticated, service_role;
-- PostgreSQL policy dependencies follow the function OID to its new schema.
ALTER FUNCTION public.my_account_is_active() SET SCHEMA morning_brief_private;
COMMIT;
