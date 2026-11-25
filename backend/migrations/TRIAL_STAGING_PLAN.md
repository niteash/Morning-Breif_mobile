# Account trial staging rollout plan — 2026-11-14

Target **only** Supabase staging project `wwtntxknfjagdjdgiaxu`.
Production `kobsywjfynjvhcarbqxo` must not be accessed.
Applied to staging on 2026-11-14 as hosted migration **`20261114180421`** (`account_trial`).
The original local SQL filename and contents are unchanged. See the verified rollout below.

## Read-only preflight result

- The authenticated staging account from the supplied API log has a verified email,
  profile, four active selected categories and zero inactive selections.
- Current Supabase migration history ends at `20261113173842`; the trial migration
  `20261114063822` is not recorded.
- `public.account_trials`, `public.get_account_trial(uuid)`, and
  `public.claim_staging_account_trial(uuid)` are absent. A PostgreSQL signature lookup
  for the missing GET RPC returned SQLSTATE `42883` (undefined function).
- All required existing columns in `auth.users`, `public.profiles`,
  `public.user_categories`, and `public.categories` are present. The private schema has
  service-role `USAGE`; `public.account_is_active(uuid)` exists and is executable by
  `service_role`.
- Staging currently has one profile with `subscription_status = 'free'` and no non-free
  profiles. Recheck this immediately
  before any migration because the migration intentionally aborts if this changes.
- The staging backend configuration matches the staging project, and the launcher
  leaves `TRIAL_STAGING_ACCOUNT_ENABLED` false. No public claim path is enabled.

## Migration and dependencies

Apply only the existing, reviewed `20261114063822_account_trial.sql` after explicit
approval and a staging backup. It is transactional and does not backfill or grant a trial.
It requires `auth.users`, `public.profiles`, `public.user_categories`, `public.categories`,
`morning_brief_private` and `public.account_is_active(uuid)` from earlier migrations.
It adds `public.account_trials` (RLS enabled, no client policies), private date/status/
claim functions and service-only public RPC wrappers.

The public function signatures are `get_account_trial(p_user_id uuid) RETURNS jsonb` and
`claim_staging_account_trial(p_user_id uuid) RETURNS jsonb`. The JSON includes `status`,
`started_at`, `expires_at`, `server_now`, and `grant_scope`; the FastAPI service adds
`can_generate` and `claim_mode`. Both public functions are invoker wrappers with an empty
search path. Only `service_role` receives EXECUTE; `anon` and `authenticated` are revoked.
The service role also needs USAGE on `morning_brief_private`, which is already present in
staging. The private status/claim functions are security definer with an empty search path.

The existing account will have `claim_required` in SQL, which the current API maps to
`claim_unavailable` while device enforcement and staging account claims are disabled.
GET `/api/v1/entitlements/me` should then return HTTP 200 with `can_generate=false`.
News ingestion remains a separate, disabled staging capability.

## Local validation completed

The repository's prior migrations and database fixture passed in a disposable local
PostgreSQL 16 cluster. The trial migration applied there without SQL errors. A synthetic
verified/onboarded account returned `claim_required`, then `trial_active` on the first
local test claim; a repeat claim preserved one row. Jan 31 + three UTC calendar months
resolved to Apr 30, and access at the exact expiry boundary returned false. The local
claim used only a synthetic fixture and did not touch staging.

## Checks before and after staging application

1. Re-run read-only staging preflight; confirm exact project reference, zero non-free
   profiles, no `account_trials`, and no existing trial RPCs. Save schema-only backup.
2. Apply the single SQL file once using the authorized staging migration connection.
   Do not run the older source-bootstrap or other already-applied migrations again.
3. Check table/RPC existence, execution grants and RLS. Anonymous/authenticated roles
   must not be able to read/write the table or invoke the service-only RPCs.
4. With the existing test account, GET entitlement status through the authenticated
   staging API. Expect HTTP 200 and an unclaimed status with `can_generate=false`.
5. Verify the original start/expiry remains unchanged across repeated reads and that
   generation remains denied before any paid provider call. Do not trigger a trial claim
   or paid generation as part of this migration verification.

## Compatibility and rollback

No existing account receives a trial automatically. Existing non-free profile values
abort the migration so they can be reviewed separately. Accounts lacking verified email,
profile or valid categories return verification/onboarding states. While public device
verification is unavailable, all unclaimed accounts remain unable to generate new audio.

If the migration fails, PostgreSQL rolls back the transaction. If it succeeds but no
trial row has been created, a reviewed reverse migration can revoke/drop the two public
RPCs, private functions and the `account_trials` table in dependency order. If any trial
row exists, first preserve and reconcile it: dropping the table would erase entitlement
history and could enable an unintended second trial later. Restore from the staging
backup only after assessing data created since the migration. Do not roll back by
disabling the API entitlement check.


## Approved rollout completed — 2026-11-14

- Exact project identity verified through the connected Supabase tool: staging
  `wwtntxknfjagdjdgiaxu`, ACTIVE_HEALTHY, PostgreSQL 17.11. No production access.
- Fresh preflight: one profile, zero non-free/null subscription statuses, one verified
  onboarded account, all dependency columns present, private-schema USAGE and account
  availability EXECUTE available to service_role. No prior trial table/functions/history.
- Reviewed local SQL SHA-256:
  `cbda77133af926832f5213a4d0857149b4ce952b430caac34b2f6ce63db3d60b`.
  No edits, backfill, existing-table DML, or invocation of a claim function.
- Applied that exact SQL using the connector's migration operation. Its real hosted
  history records `20261114180421` / `account_trial`; do not reapply the local file.
- Verified `account_trials`, two public uuid→jsonb RPCs and four private helpers.
  RLS enabled, no client policies. Anon/authenticated have no table privileges and no
  EXECUTE on any trial function. Service role has table SELECT only and EXECUTE only
  on status/claim wrappers and their private bodies; arithmetic helpers remain private.
- Profiles, subscriptions, categories and selected-category row fingerprints match
  before/after. Trial row count remains zero. No manual or automatic claim was made.
- Live PostgREST/backend service returned `claim_unavailable`, `claim_mode=device_required`,
  `can_generate=false`, null start/expiry/scope, and a valid database `server_now`.
  `require_generation_access` denied this account before any generation work.
- The user then refreshed the authenticated Android app and supplied **five HTTP 200**
  access-log entries for GET `/api/v1/entitlements/me`. These are real phone observations;
  the response body was independently checked through the real service/RPC, not captured
  from the phone. No auth bypass or fabricated session was used for this live check.
- `TRIAL_STAGING_ACCOUNT_ENABLED=false` in the guarded staging environment; public
  device claims remain unavailable. No backend restart was needed for schema discovery.
  The verified local staging process was subsequently restarted to load stricter
  timestamp validation; health is 200, anonymous entitlement requests are 401, and
  scheduler/ingestion/push/deletion workers remain disabled.
- Advisors: intentional INFO for service-only RLS with no client policies; the existing
  leaked-password-protection WARN remains. No new privilege warning.

### Backup coverage and recovery limitations

`backups/pre_trial_staging_schema.dump` exists, is ignored by Git and now owner-readable
only (0600). Size 67,068 bytes; custom archive made by pg_dump 17.12 from server 17.11.
Header has 139 TOC entries (132 selected listing rows). Both `pg_restore --list` and
complete archive decoding with PG17 `pg_restore --file=/dev/null` succeeded.
SHA-256: `35d9cb792f3b5a4e240c5f9266ce38c5cdfa5f64fd5d9ab046b93cfdf1dc4718`.

It includes public/morning_brief_private definitions, grants, RLS, and nine table-data
sections. It excludes Supabase-managed Auth/Storage schemas, project settings, roles and
migration history. Recovery of these application schemas requires those dependencies
and Auth users to remain intact; this is not a standalone full-project disaster backup.
No restore was run against staging. Archive integrity was verified; a full restoration
with Supabase-managed dependencies has not been rehearsed.

The migration is additive and does not change the existing schemas' data. Prefer a
reviewed reverse migration for its new objects if rollback becomes necessary, rather
than restoring over live user data. Do not drop trial history after claims have started.
Keep enforcement enabled during any rollback; the API will fail closed if RPCs disappear.
