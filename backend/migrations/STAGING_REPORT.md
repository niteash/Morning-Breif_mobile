# Staging database milestone — 2026-11-08

Target: **morning-brief-staging**, project `wwtntxknfjagdjdgiaxu`, PostgreSQL 17.11,
region ap-southeast-1. Source: `kobsywjfynjvhcarbqxo` (read-only throughout).

## Applied and verified

- Verified the user's `SUPABASE_ACCESS_TOKEN_STAGING` can read the staging identity.
  Used the connected Supabase tools to apply and verify migrations.
- Initial staging inspection confirmed zero public tables, users and storage buckets.
- Captured source catalogs for six application tables: 48 columns, 18 constraints,
  16 indexes, 12 policies, one function and grants. No custom types, triggers or
  publications were present. No production user, preference, news or audio data copied.
- Restored the source schema. All ten inspected metadata groups matched the source,
  including extensions, grants and function definitions. This is an application-schema
  snapshot, not a full backup of platform/Auth/Storage configuration.
- All nine queries in `preflight.sql` passed on restored staging before migration 001.
- Applied `reliable_writes`, including a fix discovered during source grant review:
  revoke client TRUNCATE, REFERENCES and TRIGGER privileges on application tables.
- Applied advisor follow-up: remove obsolete client briefing write policies, use scalar
  auth UID checks for briefing/device-token reads, add the category foreign-key index,
  and remove one confirmed duplicate news index.
- Migration history confirms three entries; exact versions and local files are in README.

## Checks

- Hosted `staging_smoke.sql` passed against actual Supabase policies/roles: two-user
  read/write isolation, category deduplication/validation, denied client job access and
  briefing writes, expired leases, stale-token fencing, completed-request replay,
  three-attempt cap, failure cooldown and retention of previously ready briefings.
- Eight concurrently submitted hosted service-role claims produced **one claimed and
  seven busy** outcomes. The synthetic Auth user and cascaded job/briefing were removed.
- Rollback/cleanup verified: zero Auth users, profiles, categories, briefings and jobs.
  These SQL tests simulate authenticated database roles; they do not verify phone login.
- Fresh local PostgreSQL 16 integration suite passed, including forced category insert
  failure rollback, concurrency and inherited PUBLIC table-wide privilege denial.
- Backend: **39 tests passed**. Mobile service tests: **6 passed**. Lint and TypeScript
  passed. One existing Starlette/httpx deprecation warning remains.
- Final source catalog comparison is unchanged. No production migration, application
  deployment, SMS, paid provider call or push notification was performed.

## Advisors

No security/performance WARN or ERROR findings remain. Informational findings:

- [RLS enabled with no policy](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy)
  on `briefing_generation_jobs` is intentional: client table grants are revoked and
  only the service generation RPCs should access jobs. Do not add a public read policy.
- [Unused indexes](https://supabase.com/docs/guides/database/database-linter?lint=0005_unused_index)
  are expected on empty staging. Evaluate representative workloads before removing them.

## Remaining integration and release gates

Update after this database milestone: the five categories are now seeded and inspected.
Ingestion now resolves category UUIDs by slug in the active environment. The user approved
and we completed the Supabase-only runtime setup and hosted Auth/storage smoke checks.
Phone Auth is still disabled; disposable email/password accounts were used for testing.

- Backend staging configuration is ready in ignored `.env.staging`; the mobile app has
  not been switched to staging. Existing `.env` files were preserved.
- Private `briefings` bucket is configured for audio/mpeg, maximum 20 MiB. Signed
  downloads work; public and direct cross-user downloads are denied.
- Configure staging phone Auth/SMS and verify real sessions. Test authenticated HTTP
  flows, provider generation, storage signing, FCM and multiple running workers.
- Complete device acceptance, subscriptions, privacy/account deletion, hosting and signing.
  **Database migration verified; end-to-end staging and release readiness are not complete.**

## Approved Auth and storage smoke result

- Real Supabase email/password sessions validated by the actual backend Auth dependency.
- FastAPI ASGI checks passed for health, unauthenticated/invalid-token rejection, public
  categories, owned preference creation/read, atomic category save and invalid-category
  rejection, cross-user profile isolation, news read and non-operator ingestion denial.
- Service-only claim/completion with an uploaded MP3 frame fixture passed. The saved
  briefing API signed its path; downloaded bytes matched. Another user saw no briefing.
- Sessions revoked, users deleted and audio removed. Independent verification found
  zero Auth users/sessions, profiles, briefings, generation jobs and audio objects.
  Five category records and the private bucket remain intentionally.
- No Gemini, Azure, SMS, FCM or scheduled generation calls. No production writes.
- Current offline suite: 49 backend tests, six mobile service tests, lint, TypeScript,
  Python compilation and dependency consistency checks pass.


## Notification queue — 2026-11-09

Applied hosted version `20261109024635` (`durable_notification_delivery`) after read-only
preflight and local PostgreSQL tests. Source/production was not accessed or changed.
Hosted rollback checks passed for enqueue/dedupe, service-role claims, lease fencing,
backoff, invalid-token cleanup, account reassignment and client queue/RPC denial.
Cleanup verified independently: users=0, devices=0, briefings=0, notification_deliveries=0.
Security/performance advisors: no WARN/ERROR; intentional service-only RLS INFO and unused
index INFO remain. See migration README for links and rationale. Actual FCM is disabled
and unverified; the Firebase token-to-FID compatibility review remains a release gate.

## Account cleanup — 2026-11-13

- Read-only preflight verified owned-table RLS, cascading Auth references, absent deletion
  objects and an empty user dataset. No source/production access this milestone.
- Applied `recoverable_account_deletion` as `20261113173531`, then
  `private_account_availability` as `20261113173842`. Local files retain CLI timestamps.
- Local PostgreSQL covered idempotent competing requests, RLS/service-write denial,
  competing claims, expired leases, stale-worker fencing, bounded inventory, retry,
  partial cleanup recovery, attempt exhaustion, and cross-user/bucket isolation.
- `scripts/account_deletion_smoke.py --disposable-staging` used real email/password Auth
  and Storage through the API's ASGI client. Request returned 202; old-token access was
  denied; cleanup removed audio then Auth and retained the other user's objects/account.
  Only this generated fixture job's due time was advanced for the test. No real user data.
- Reran the existing staging smoke after private-helper migration: preferences/categories,
  operator denial, owned briefing signing/download and cross-user isolation all passed.
- Independent cleanup: users, sessions, profiles, briefings, devices, generation jobs,
  notification deliveries, deletion jobs and briefing audio objects all zero.
- Security advisor initially flagged the exposed definer helper; fixed by private schema.
  Remaining WARN: [leaked password protection disabled](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection).
  No password login is offered in the mobile app, and test users were removed; resolve
  before password-based release use. No Auth configuration was changed by these checks.
- INFO: [service-only tables with RLS/no policies](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy)
  and [unused indexes](https://supabase.com/docs/guides/database/database-linter?lint=0005_unused_index).
  Performance advisor has no WARN/ERROR. Do not add public policies to worker tables.

Deletion remains disabled in default runtime environments. Bounded operator recovery is
implemented; worker monitoring/alerts, ambiguous late-upload reconciliation, device
acceptance and production deployment remain release gates. Phone SMS is intentionally
out of scope. No Gemini/Azure request, FCM send, production modification or release.


## Account trials — 2026-11-14

Applied the explicitly approved `20261114063822_account_trial.sql` as hosted version
`20261114180421` after fresh staging-only preflight and archive verification. Existing
profiles/subscriptions/category selections are unchanged, trial rows=0, RLS enabled,
service-only RPC execution verified. Live service result is `claim_unavailable` with
`can_generate=false`; the user supplied five authenticated phone GET HTTP 200 entries.
The persistent missing-RPC 503 is resolved. Public claims remain disabled. No production
access occurred. See [TRIAL_STAGING_PLAN.md](TRIAL_STAGING_PLAN.md) for full evidence.
