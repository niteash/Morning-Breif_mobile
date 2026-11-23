# Reliable writes migration

`001_reliable_writes.sql` is a one-time migration, not an empty-project schema.
It requires the existing `profiles`, `categories`, `user_categories`, `briefings`
and `auth.users` tables. It requires a unique `(user_id, briefing_date)` constraint,
nullable script/audio fields while generating, the documented status values, and
existing user-isolation RLS policies. Obtain a SQL schema/policy export before rollout.

## Staging migration completed — 2026-11-08

Target: `morning-brief-staging` (`wwtntxknfjagdjdgiaxu`).
The user's `SUPABASE_ACCESS_TOKEN_STAGING` in ignored `backend/.env` was verified.
The connected Supabase tools performed the schema migration and database checks.
The source project `kobsywjfynjvhcarbqxo` was inspected read-only and is unchanged.
See [STAGING_REPORT.md](STAGING_REPORT.md) for verification and remaining release gates.

Applied order (do not sort these local filenames or reapply them):

| Hosted version | Local SQL | Purpose |
| --- | --- | --- |
| 20261108134617 | `20261108134546_staging_source_schema.sql` | Restore source schema to an empty staging project |
| 20261108134745 | `001_reliable_writes.sql` | Atomic preferences, fenced generation and role restrictions |
| 20261108134945 | `20261108134859_staging_policy_indexes.sql` | Ownership-policy and index improvements |
| 20261109024635 | `20261109024013_durable_notification_delivery.sql` | Atomic per-device notification queue and service-only retry RPCs |
| 20261113173531 | `20261109025525_recoverable_account_deletion.sql` | Durable account deletion and write fencing |
| 20261113173842 | `20261113173705_private_account_availability.sql` | Private account availability helper for RLS |
| 20261114180421 | `20261114063822_account_trial.sql` | Three-calendar-month trial storage and service-only status/claim RPCs (no grants/backfill) |

The bootstrap was reconstructed from inspected source catalog definitions; all ten
inspected metadata groups matched after restoration. It contains no user/category/news
records, storage buckets, Auth provider settings or secrets. Never apply this bootstrap
to an existing project. These files are reviewed rollout SQL, not a linked CLI migration
directory; hosted versions are recorded above because the connector assigns them.

Runtime environment URLs and credentials have not been switched. Management tokens
authorize administration and cannot substitute for the app's publishable/service keys.

## Changes

- Atomic category replacement runs with caller privileges and `auth.uid()`. A profile
  row lock serializes simultaneous saves. Validation or insertion failure rolls back
  the delete. Inactive/unknown categories are rejected and duplicates are removed.
- A private job table and service-only claim/finish/fail RPCs coordinate all API and
  scheduler generation. No mobile user can claim a job or write briefing content.
- Claims expire after ten minutes. A token is required to complete/fail a claim;
  expired/superseded workers cannot publish results. This prevents stale writes, but
  an expired provider call may still incur cost before its result is rejected.
- Three provider attempts per user/local date (including forced regeneration) and
  a five-minute failure cooldown bound retries. These are operational cost safeguards,
  not a subscription entitlement policy. Replay of the most recently completed request
  ID returns the saved result. IDs are not a permanent request-history ledger.
- Failed regeneration preserves a previously ready briefing. First-time failures are
  recorded as failed. Audio objects from rejected/failed commits require retention cleanup.
- Every overload of the historical `claim_briefing_generation` RPC is revoked from
  API roles. Direct briefing writes by public/anonymous/authenticated roles are revoked.
- Client TRUNCATE, REFERENCES and TRIGGER grants are revoked on the six application
  tables. RLS alone does not restrict TRUNCATE; source preflight exposed these grants.

## Safe rollout

1. Create/select a separate Supabase staging project and copy the authoritative schema
   and policies (without copying user records unnecessarily). Configure backend/mobile
   staging environments. Do not apply the disposable fixture schema to Supabase.
2. Back up schema/policies, confirm prerequisites and stop old generation workers.
   Run `preflight.sql` on source and staging first; it returns read-only schema,
   constraint, policy and grant metadata without reading user records. Review the
   existing claim function body separately using authorized SQL access. API keys
   alone do not provide a database migration connection. A connected Supabase
   integration, authorized Management API access or a database connection is required.
3. Apply the migration once through the staging SQL editor or an authenticated migration
   connection. The whole file runs in one transaction; failure rolls back all changes.
4. Deploy this backend together with the migration. Without these RPCs, category writes
   and generation fail closed. There is deliberately no fallback to destructive writes.
5. Verify two-user isolation, simultaneous manual/scheduled requests, provider failure,
   expired workers, quota errors, saved audio access and notification delivery on staging.
6. Only then plan production application and worker rollout. Staging SQL is applied;
   production application is not authorized or performed. Avoid rolling back the backend alone: older code
   uses direct writes that are intentionally revoked by this migration.

## Local integration test

Use an empty, disposable PostgreSQL 16 database named `morning_brief_test*` on localhost.
The test role must create schema, functions and the fixture roles. This script does not
read `.env`, and refuses remote hosts/non-test database names or populated public schemas.

```sh
createdb -h 127.0.0.1 -p 55439 morning_brief_test_fresh
DATABASE_TEST_URL=postgresql://127.0.0.1:55439/morning_brief_test_fresh \
  .venv/bin/python backend/db_tests/run.py
```

Run these commands from the app directory. PostgreSQL must already be running on that
port. Choose a fresh database name for each run. CI creates a disposable PostgreSQL 16
service. The fixture tests intended RLS behavior; it does not verify deployed policies.

`backend/db_tests/staging_smoke.sql` additionally tests the restored Supabase RLS and
RPCs with two synthetic users inside a transaction that ends in ROLLBACK. Run it only
on the designated staging target. It makes no provider calls or notifications.


## Notification delivery migration — 2026-11-09

The fourth migration is applied to staging only. Preflight confirmed the expected table
columns, briefing/device primary keys, generation completion RPC, absent queue/functions,
and no ready briefings or active devices. No existing records were backfilled.

A trigger enqueues one notification per ready briefing/device in the same transaction as
briefing completion. The queue is inaccessible to anonymous/authenticated clients;
service-only RPCs claim one job with a five-minute lease and acknowledge an exact lease.
Retry/expiry/attempt limits are documented in `../WORKERS.md`. Deploy this migration before
the new backend: the previous direct notification sends have been removed.

Local PostgreSQL tests verified concurrent claims, stale workers, transaction rollback,
backoff, five-attempt cap, expiry, logout/reassignment and privilege denial.
`../db_tests/notification_staging_smoke.sql` passed on staging in a rolled-back transaction.
Independent metadata checks confirmed zero users, devices, briefings and deliveries after
cleanup. No FCM request or production change was made.

Post-migration security/performance advisors reported no WARN/ERROR findings. INFO findings
are expected for service-only tables with [RLS and no client policies](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy)
and [unused indexes](https://supabase.com/docs/guides/database/database-linter?lint=0005_unused_index)
on the empty staging dataset. Keep the indexes needed for queue/FK operations.

## Account deletion migrations — 2026-11-13

Apply in order after notification delivery:

1. `20261109025525_recoverable_account_deletion.sql`
2. `20261113173705_private_account_availability.sql`

Both are already applied to authorized staging; do not reapply there. Hosted versions are
`20261113173531` and `20261113173842`. The first file was generated in earlier development;
the hosted apply date is November 13. Production is untouched. Preflight confirmed RLS on
owned tables, cascading Auth foreign keys, absent deletion functions/table and no users.
Local PostgreSQL tests passed before each apply. The private-schema follow-up preserves
policy dependencies while removing the helper from the public RPC surface.

The queue intentionally has no Auth foreign key: it survives user removal until verified
cleanup. Clients cannot read or mutate it. The private policy helper returns only the
caller's own availability; mutation/worker RPCs remain service-only. Storage object bytes
must be removed using Storage API, never SQL deletion from `storage.objects`.

New backend authentication requires the availability RPC even with deletion disabled.
Deploy migrations and backend together; do not point this build at unmigrated production.
See `../WORKERS.md` for enablement and pending operations work. Live disposable Auth/Storage
checks passed, and cleanup was independently confirmed. Native UI/device tests are open.


## Account trial migration — 2026-11-14

Applied only to staging as hosted version `20261114180421`. The existing account now
receives HTTP 200 for entitlement status, without generation access or a trial grant.
See [TRIAL_STAGING_PLAN.md](TRIAL_STAGING_PLAN.md) for checksum, fresh preflight, backup
coverage, permissions, actual phone result and rollback limitations. Public claims remain
disabled. Do not reapply the SQL or run a claim to verify this rollout.
