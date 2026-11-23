# Source preflight — 2026-11-08

Historical source inspection below. A separate staging project is now migrated and
database-tested; see [STAGING_REPORT.md](STAGING_REPORT.md). Source remains unchanged.

Target inspected: existing `morning-brief` project. Treat this as production/source.
**Read-only inspection completed; no remote writes, provisioning or migrations performed.**

Continuation recheck: project/branch listings still expose only the source project.
All nine queries in the updated `preflight.sql` succeeded, including effective table
privileges for application roles (12 role/table combinations). Lint and TypeScript
checks passed. Staging migration remains blocked on a separate accessible target.

## Confirmed

- Management project listing succeeded. One project is visible to the token; its
  branch listing returned an empty list. No staging target is currently identified.
- Nine schema inspection queries succeeded through the Management API's read-only
  endpoint as `supabase_read_only_user`, on PostgreSQL 17.6.
- Required tables exist: profiles, categories, user_categories, briefings.
- All four tables have RLS enabled. Inspected policies constrain user-owned records
  through `auth.uid()`; category reads permit active categories.
- Briefings have a valid unique `(user_id, briefing_date)` index/constraint, nullable
  script/audio fields and pending/generating/ready/failed status values.
- User categories have a composite primary key and foreign keys to categories and
  auth.users. Unlike the simplified local fixture, its owner FK references auth.users
  directly. The new category RPC separately requires the caller's profile row.
- App roles currently have broad table grants, with RLS restricting row access.
  Migration 001 intentionally revokes direct client briefing writes.
- `claim_briefing_generation(uuid,date,integer)` exists and is executable by PUBLIC,
  anon, authenticated and service_role. Its body was reviewed without executing it.
  It has no token fencing; it can also insert a generating row and immediately decline
  to claim that same fresh row. The replacement does not call this function.
- The new jobs table is absent. No migration 001 installation was observed.

## Limits and next action

- This is source schema inspection, not staging acceptance or an end-to-end RLS test.
- Organization metadata returned HTTP 403. Organization plan/cost and provisioning
  capability could not be established; no project creation was attempted.
- A separate target such as `morning-brief-staging` must be created or made accessible.
  Grant database/migration write access only to that target; keep source access read-only.
- Export and restore the application schema/policies to staging without production
  user records, then rerun preflight there before applying migration 001.
- Raw metadata and the old function definition are stored only under ignored
  `.cache/migration-preflight/`, with restricted filesystem permissions.

## Credential handling

A management token had also been placed in `backend/.env.example`. It was replaced
with a placeholder; the ignored `backend/.env` credential was preserved. The token
was not printed. Never put live credentials in example files.
