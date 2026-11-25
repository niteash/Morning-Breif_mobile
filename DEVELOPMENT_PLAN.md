# Morning Brief development plan

Last updated: 2026-11-15. Requirements: `../Pasted text(1).txt` plus the Nay Thit client redesign request.
Checkboxes indicate verified work; implementation alone is not release verification.

## Automatic personalized daily briefing — 2026-11-15

- [x] Verify staging-only state: 100 news rows, all within 24 hours; one profile has
  valid timezone/delivery values; no trial grants exist. No production access.
- [x] Trace the existing category-backed selector, Burmese Gemini prompt, Azure `my-MM`
  MP3 path, service-side entitlement gate, private Storage upload, durable generation
  claims, Firebase outbox, and Expo player.
- [x] Move scheduler eligibility to 30 minutes before the user's local delivery time;
  support a 24-hour same-local-date catch-up and handle just-after-midnight dates.
- [x] Add client-side foreground auto-play consent checks and a persistent per-account,
  per-briefing start gate; add unit coverage for ownership, local time, weekday, and errors.
  Keep the native start gate disabled until Android audio-focus behavior is verified.
- [x] Add opt-in reminder, weekday schedule, and foreground auto-play profile API/UI
  contracts; push payloads now identify the saved briefing without carrying a signed URL,
  and notification taps open the authenticated player route.
- [x] Prepare review-only SQL proposal and preflight/rollback notes in
  `backend/schema_proposals/`; confirm on staging that preference columns are absent.
- [x] Pass `npm run typecheck`, `npm run lint`, `npm test` (60 tests), and the full
  backend pytest suite (226 tests). No mobile device, provider, push, scheduler, or
  database write was used for these checks.
- [ ] Approve and create a numbered staging migration with Supabase CLI, then apply only
  to staging. CLI is not installed in the current workspace; no schema was changed.
- [ ] Configure approved staging Gemini, Azure Speech, Firebase, and a dedicated single
  worker. Current staging config has those provider credentials unset and all workers
  remain off. No paid calls, generation, or push sends were performed.
- [ ] Verify entitlement through authenticated backend; staging currently has zero trial
  grants, so generation remains denied until a legitimate approved entitlement exists.
- [ ] Verify generated Burmese script/audio, private storage and signed playback, delayed
  FCM delivery, notification tap and consented foreground playback on physical Android.
- [ ] Confirm worker capacity/monitoring and restart recovery before routine daily use.

## Critical staging paths — 2026-11-15

- [x] Diagnose the earlier empty staging database. A fresh read-only query on 2026-11-15
  now shows 100 `news_items`, all published within 24 hours; authenticated API visibility
  was not rechecked in this milestone.
- [x] Reject the earlier approved RSS proposal when its live feed-derived batch changed. Fresh read-only report `backend/reports/rss_staging_dry_run_20261114T203122Z_d650d9ce-37b0-4102-bdd3-d68814d463c7.json` contains 100 proposed rows and records zero write attempts; it needs separate approval.
- [x] Confirm 23 RSS sources checked, 20 parseable, 170 recent valid items and 189 eligible; proposal has 29 business, 26 football, 41 technology, 4 world and 0 Myanmar items. No category or URL constraints were bypassed.
- [x] Trace generation through entitlement gate, Burmese script, Azure `my-MM` MP3 synthesis, private user-scoped storage, signed URL refresh and the existing Expo audio player. Staging has the expected generation RPCs; only `service_role` can execute them.
- [x] Pass `npm run typecheck`, `npm run lint`, `npm test` (44 tests), and backend tests (181 tests). Provider calls and device playback were not performed.
- [ ] Verify nonempty authenticated `/api/v1/news` results after the database now contains 100 recent articles.
- [ ] After news is present, approve staging-only Gemini/Azure configuration and paid generation testing; verify active entitlement, generated Burmese output, persisted MP3, signed URL and playback on a device.

## Nay Thit client redesign — 2026-11-14

- [x] Implement monochrome reusable UI, bundled licensed Burmese fonts and reduced-motion-aware dotted orb.
- [x] Introduce Home/News/Settings tabs and full/mini Player with one authenticated audio owner; preserve existing URLs and auth/onboarding/deletion contracts.
- [x] Verify readiness, URL refresh/pause intent, stale source/account responses, transcript consistency and deduplicated reads through offline state tests.
- [x] Improve OTP configuration/rate/delivery errors. Read-only Auth settings confirm Phone Auth disabled on configured default and staging targets; no SMS sent or remote setting changed.
- [x] Pass lint, typecheck, 37 offline tests, Android/iOS Hermes exports and diff whitespace check. Scope snapshot confirms backend/package/app/deployment configuration unchanged.
- [ ] Configure staging Supabase Phone Auth and SMS provider, then verify real OTP delivery.
- [ ] Validate redesigned screens, Burmese typography/accessibility, native audio lifecycle, background/lock-screen and notification flows on devices. No connected Android device or booted iOS simulator was available.
- [ ] Complete existing provider, worker, signing/store and privacy release gates below.

See `REDESIGN_HANDOFF.md` for changed paths, preserved behavior, exact OTP setup steps and acceptance checklist. Earlier milestone evidence below remains historical; it is not a device sign-off for the new UI.

## Current staging rollout status

- [x] Verify Management API access and inspect source schema through the read-only endpoint.
- [x] Identify user-provided `morning-brief-staging` (`wwtntxknfjagdjdgiaxu`).
- [x] Prepare migration 001 and verify its critical flows in disposable local PostgreSQL.
- [x] Verify separate staging access using `SUPABASE_ACCESS_TOKEN_STAGING`.
- [x] Export inspected application schema/policies and restore them to empty staging.
- [x] Run staging preflight, apply migration 001, and verify database role isolation and claims.
- [x] Seed five category records and resolve feed category IDs per environment.
- [x] Configure separate backend staging credentials and verify private storage.
- [ ] Configure mobile staging and phone Auth/SMS.
- [ ] Verify authenticated HTTP/provider/device flows against staging.

**Staging database milestone verified.** Production is unchanged. End-to-end app and
release checks remain open. See `backend/migrations/STAGING_REPORT.md`.

**Latest whole-project audit:** `APPLICATION_AUDIT.md` records current verified scope,
concrete code gaps, external dependencies and prioritized release work.

## Repository baseline

- Expo SDK 57, React Native 0.86.3, React 19, TypeScript 6, Expo Router;
  Supabase Auth/Storage, expo-audio and native FCM registration. Zustand is installed.
- Python 3.13 locally; FastAPI, Supabase, Gemini, Azure REST TTS, Firebase Admin,
  APScheduler and RSS ingestion/ranking/clustering.
- `main` at `400986f`, matching cached `origin/main`; clean initial working tree.
  Rebase already completed; `backup-before-rebase` preserved. No remote fetch yet.
- Initial handoff claimed OTP and settings; inspection found navigation-only OTP and
  diagnostic-only settings. Both now have real service calls, not yet device verified.
- Other existing code not reverified end-to-end: onboarding, story feed,
  manual generation, scheduled generation, signed audio and push notifications.
- Paywall remains a placeholder. The initially empty `briefing/pipeline.py` now
  holds the shared script/TTS/duration/upload flow. Persistence still has separate callers.
- Migration 001 is deployed to staging. Source catalog definitions were captured and
  restored with a verified metadata comparison; production remains unchanged.
- Initial risks identified (see fixes below): public administrative ingestion (including arbitrary URLs), UTC versus
  local briefing dates, process-only generation lock, no API generation limit,
  nontransactional category replacement, missing duration, sensitive result logging,
  default-on scheduler in every API worker, no purchase validation.
- Original backup Python files are preserved for recovery review.

## Milestone 1 — reproducible baseline and first blockers

- [x] Read requirements and repository instructions; inspect Git and architecture.
- [x] Run existing offline relevance, ranking, clustering and pipeline scripts: pass.
- [x] Compile backend Python: pass.
- [x] Install locked mobile and initial backend dependencies.
- [x] Declare missing direct backend dependencies and isolate offline tests from paid/live scripts.
- [x] Establish supported Node version, lint, typecheck and Expo Doctor baseline.
- [x] Start API and Metro; record environment/device limitations.
- [x] Add placeholder environment examples and repeatable check commands.

## Milestone 2 — security and delivery correctness

- [x] Restrict ingestion to authenticated operators and configured feeds.
- [x] Validate timezone preferences and use local dates consistently.
- [x] Make scheduler activation explicit and safe for API-only deployment.
- [ ] Remove sensitive logs and public exception details.
- [x] Add negative authorization and date-boundary regression tests.
- [x] Replace destructive category update with a transactional database operation;
  verified against inspected schema/RLS on hosted staging.

## Milestone 3 — reliable generation and audio

- [x] Share provider generation and persist measured MP3 duration (offline tested).
- [x] Persist failed/generating states with safe retry and worker ownership (database tested).
- [x] Add database-backed claims, fencing, quotas and bounded retries; verify against
  local PostgreSQL and hosted staging. Running multiple app workers remains unverified.
- [x] Preserve one consolidated MP3; no generated content when stories are unavailable (offline tested).
- [ ] Verify expired URL recovery, progress/seeking, network failure and background audio.
- [ ] Test provider failures and notification failure after successful persistence.

## Milestone 4 — news quality and mobile resilience

- [ ] Audit publisher extraction, source trust and category-aware deduplication.
- [ ] Extend regression fixtures for actual false positives and distinct events.
- [ ] Improve source attribution and prompt injection resistance; editorial Burmese review.
- [ ] Verify auth/session recovery, loading/empty/error states and notification navigation.
- [ ] Profile home list rerenders on an Android device before performance changes.

## Milestone 5 — release and subscriptions

- [x] Capture schema/RLS definitions and verify database user isolation on staging.
- [x] Verify private storage through real sessions and the saved-briefing API (ASGI client).
- [ ] Verify that storage/audio flow on a physical Android device.
- [ ] Configure stable HTTPS backend, production secrets, monitoring and retention.
- [ ] Configure RevenueCat/Play products, pricing/free-tier policy and verified entitlements.
- [ ] Verify signing, Firebase configuration, privacy policy, account deletion and store listing.
- [ ] Run Android release build and physical-device acceptance matrix (OTP, preferences,
  midnight/timezone delivery, killed/background app, push, playback and purchases).
- [ ] Release only after all required acceptance checks pass.

## Verification log and external blockers

- Baseline offline scripts pass (8 relevance cases plus ranking/clustering/pipeline assertions).
- npm initial install reports 14 advisories; investigate compatible fixes, no forced upgrades.
- Host Node 23 is outside React Native's supported engine range; use Node 22 LTS.
- Initial backend requirements omitted APScheduler and google-genai; requests was only transitive. Fixed.
- Local service credentials, deployed schema, device access and store/billing credentials
  must be verified without printing or committing secrets. Live provider scripts may
  incur costs or mutate data and are not part of offline discovery.

Each milestone update records changes, exact checks and remaining blockers below.

## Milestone results — 2026-11-08

### Baseline (local checks complete)

- Installed dependencies in `.venv` and `node_modules`; declared APScheduler,
  google-genai, requests, mutagen and a separate pytest development requirement.
- Added Node 22 selection, ESLint configuration, typecheck and offline test commands.
- Updated eight Expo SDK 57 patches using Expo installer: Doctor **21/21**.
- API started with scheduler disabled; `GET /health` returned 200/ok.
- Metro started on localhost. Android Hermes bundle export succeeded using dummy
  public configuration; this is **not** an APK/AAB, signed build or device test.
- Final lint and TypeScript checks pass, including audio UI changes.
- 21 backend tests and six mobile service tests pass; network disabled for Python tests.
- No attached Android device/emulator. Docker daemon unavailable. PostgreSQL CLI exists.

### Security/authentication increment

- Ingestion requires verified identity plus server-side operator allowlist and exact
  configured feed/category/source tuple. Empty allowlist denies access by default.
- Anonymous sessions rejected on protected backend routes and mobile screens.
- Actual Supabase SMS send/verify/resend implemented with loading/error states;
  no anonymous account creation or accepting arbitrary six-digit input.
- Settings now saves delivery preferences and signs out. Onboarding failures are visible.
- HTTP client trims its base URL, bounds request time, respects cancellation and hides
  raw provider/proxy responses. Removed full generated-response logging.
- Local dates used in all briefing reads/manual generation; invalid timezone rejected.
- Backend scheduler is opt-in (`SCHEDULER_ENABLED=true`) and remains single-instance only.

### Audio increment

- Shared provider pipeline generates one MP3, measures duration from frames and cleans
  temporary files on success/failure. Tests cover two-category consolidation and upload failure.
- Unique storage paths prevent concurrent audio overwrites but do **not** provide DB fencing
  or prevent duplicate provider charges. Unreferenced objects need a retention policy.
- Empty/titleless stories cannot reach Gemini. Prompt now requires attribution and treats
  article instructions as untrusted; factual correctness still needs editorial validation.
- Player gains elapsed/total time, ±15-second seeking, buffering/error text, explicit refresh,
  expired-link refresh before play and lock-screen/background configuration. Native behavior
  is **unverified** until a new Android build is installed on a device.
- Removed recording permission; this app only plays audio.

### Remaining release gates

- Source columns, RLS, constraints and the legacy RPC have been inspected. A separate
  staging target is still required. User delegated environment choice; use isolated staging.
- Distributed generation claims/fencing, persistent quotas/retries and transactional
  category writes are locally tested but not deployed. Do not enable multiple workers
  until the staging migration and deployment checks pass.
- SMS provider delivery, authenticated persistence, live Gemini/TTS/storage/FCM and paid
  billing are not verified in this session. Existing historical tests are not proof.
- Latest npm audit after compatible fixes: 14 advisories (11 moderate, three high). Several suggested fixes downgrade
  Expo or require another SDK; no forced upgrades applied. Review patched transitive versions.
- Supabase staging setup, production hosting, EAS signing, Play/RevenueCat products, pricing,
  privacy/account deletion and real-device acceptance remain external/release work.

### Final verification and handoff

- `npm run lint`, `npm run typecheck`, `npm test`: pass (six service tests).
- `cd backend && ../.venv/bin/python -m pytest -q`: 21 pass; one upstream
  Starlette/httpx deprecation warning. `compileall` and `pip check`: pass.
- Expo Doctor: 21/21 after SDK updates. Android export repeated after audio changes.
- Added GitHub Actions offline checks; workflow itself has not run on GitHub.
- `git diff --check`: clean. Local environment/Firebase files remain ignored;
  no credentials added to source. Git history and backup branch preserved.
- API/storage signing failure regression verifies the saved briefing remains successful
  and does not ask users to regenerate. Anonymous backend access rejection tested.
- `RELEASE_READINESS.md` contains setup commands, staging prerequisites and device gates.
- **Release readiness is not achieved.** Next milestone requires SQL/RLS inspection
  and a staging database for durable claiming, quotas and transactional preferences.

### Read-only Supabase inspection

- Existing configured service returned HTTP 200 for its OpenAPI schema. No user records
  were read and no database mutations or RPCs were executed.
- Confirmed all six expected tables and columns, including `duration_seconds`,
  `generated_at`, profile timezone/time, `device_tokens.is_active`, and category names.
- `claim_briefing_generation` exists. Its body, permissions, fencing and RLS are not exposed
  by this response, so it remains unused. A SQL/RLS export and staging target are still needed.

## Database reliability milestone — 2026-11-08 (local implementation)

- [x] Implement atomic category replacement with caller RLS, validation and per-user locking.
- [x] Route both manual and scheduled generation through service-only durable claims.
- [x] Add ten-minute leases, token fencing, three attempts per local day and five-minute cooldown.
- [x] Preserve playable audio on failed regeneration and replay the latest completed request ID.
- [x] Deny client briefing writes/job access and revoke historical unsafe claim RPC overloads.
- [x] Test migration against isolated PostgreSQL 16, including eight concurrent claim requests,
  category rollback after forced insert failure, stale owners, quota and role permissions.
- [x] Add same-day two-hour scheduler catch-up and four concurrent provider jobs per process.
- [x] Add `RUNNING.md` and migration rollout/test instructions.
- [x] Apply and verify migration against a separate Supabase staging environment with actual RLS.
- [ ] Verify provider timing, notification recovery, object retention and multi-instance deployment.

**Deployment prerequisite:** the new backend requires
`backend/migrations/001_reliable_writes.sql`. It is applied to staging, not production.
Against an unmigrated target, category saving and generation return unavailable errors before unsafe writes
or paid provider calls. Read endpoints and health remain available. Stop old workers before
rollout; migration and backend must be deployed together. The old RPC is never reused.

Earlier unchecked database items now have a locally tested implementation; deployment
verification remains open. CI includes a new PostgreSQL integration job (not yet run remotely).
The local fixture is not an authoritative export of deployed RLS.

### Verification for database milestone

- Backend: **39 tests passed**; Python compilation passed. One upstream Starlette/httpx
  deprecation warning remains.
- Mobile service tests: **6 passed**. Lint and TypeScript passed.
- PostgreSQL 16 final integration suite passed on a fresh disposable database: validation,
  rollback, ownership, eight concurrent claims, stale lease rejection, attempt quota,
  cooldown, most-recent request replay and role restrictions (including PUBLIC grants).
- `git diff --check`: clean. No connected Supabase data/schema changes, deployments or
  new credentials. Existing user changes and backup branch retained.
- Setup commands: `RUNNING.md`. Staging rollout: `backend/migrations/README.md`.

### Staging rollout access check — 2026-11-08

- User authorized proceeding with staging rollout. Workspace configuration contains
  API credentials, but no database URL, management access token, linked Supabase CLI
  project or identified staging target. No secrets were printed or changed.
- Supabase integration found and offered for installation/connection; connection is
  not yet confirmed. External schema verification and migration application await access.
- Added `backend/migrations/preflight.sql` for read-only schema/constraint/RLS/grant
  inspection. It is prepared, not yet executed against source or staging.
- No remote migrations or database mutations have been performed.

### Source preflight completed — 2026-11-08

- Locally configured management token successfully listed projects and ran nine
  schema-only SQL queries through Supabase's read-only endpoint.
- Required tables, RLS, uniqueness, status values and nullable generation fields
  are confirmed. Effective app-role grants and the legacy claim function were inspected.
- See `backend/migrations/PREFLIGHT_REPORT.md` for findings and remaining limits.
- One project is visible (`morning-brief`), with no database branches. No staging
  target is identified. Organization metadata returns 403, so plan/provisioning
  details remain unavailable. No remote writes were attempted.
- Removed a real management token from the example environment file while preserving
  the ignored local credential. Private inspection artifacts remain ignored.
- Next dependency: an accessible separate staging project and scoped staging write
  access, followed by source schema export/restoration and staging preflight.

## Staging database milestone completed — 2026-11-08

- [x] Verified user-provided staging token name and exact project reference.
- [x] Compared restored schema to source; all ten inspected metadata groups match.
- [x] Passed nine staging preflight queries before applying reliable writes.
- [x] Closed inherited client TRUNCATE/REFERENCES/TRIGGER grants with a local regression.
- [x] Applied bootstrap, reliable writes and advisor policy/index follow-up to staging only.
- [x] Verified two-user RLS and generation lifecycle with rolled-back synthetic records.
- [x] Submitted eight hosted claims: one owner, seven busy; cleaned up test records.
- [x] Rechecked source catalogs unchanged and staging test data absent.
- [x] Local PostgreSQL suite, 39 backend tests, six mobile tests, lint and typecheck pass.
- [ ] Configure and verify staging application/provider/device flows before release.

Staging has schema only: categories, private storage and SMS still need setup. Runtime
environment values were preserved. SQL-role tests do not establish real Auth/HTTP/device
acceptance. See `backend/migrations/STAGING_REPORT.md` for applied versions and limits.

## Staging integration preparation — 2026-11-08

- [x] Seed all five required categories with Burmese labels on staging; verify rows.
- [x] Remove production-generated category UUIDs from API and command-line ingestion.
  Resolve active categories by slug once per batch; missing/inactive configuration
  returns 503 before any feed fetch, and mismatched feed/category requests return 422.
- [x] Redact provider response bodies from batch-ingestion errors and Gemini console logs.
- [x] Initialize Gemini lazily so non-generation API features can start without an AI key.
- [x] Prepare and unit-test `backend/scripts/prepare_staging.py`: staging Supabase keys
  only, exclusive owner-only file creation, provider keys blank, scheduler/push disabled.
- [ ] Execute that prepared setup and then verify hosted Auth/API/private-storage flows.
- [ ] Enable and configure phone Auth with an SMS provider; inspection confirms phone
  Auth is currently disabled. A provider name in config does not establish working SMS.

Automatic approval review rejected the earlier environment-copy command because it
included existing Gemini/Azure credentials. No staging environment file was written.
The narrower Supabase-only setup is prepared and awaits the user's explicit approval.
No provider messages, paid generation, or production database changes were performed.
Verification: **48 backend tests passed**; lint, TypeScript, Python compilation and
`git diff --check` passed. Staging anonymous-role inspection sees all five active
categories. Private runtime/storage/Auth integration tests have not run yet.

### Remaining work to finish the app

| Work | Current status / completion evidence needed |
| --- | --- |
| Staging API and storage | Database verified; runtime environment, private bucket and real-session HTTP flows pending |
| Phone login | UI/service code implemented; staging phone Auth disabled, SMS delivery and device recovery unverified |
| News and generation | Offline pipeline tested; feed quality, real Gemini/Azure audio, Burmese editorial/pronunciation review pending |
| Daily delivery | DB claims verified; actual scheduler workers, timezone/device delivery, FCM and notification recovery pending |
| Mobile acceptance | Loading/error/audio controls implemented; physical Android playback/background/expiry/offline/navigation checks pending |
| Subscriptions | Paywall placeholder; RevenueCat/Play products, pricing, entitlement checks and purchase/restore flows not complete |
| Privacy and operations | Account deletion, privacy policy, log audit, audio retention, monitoring and stable HTTPS hosting pending |
| Release | Dependency advisory review, Firebase/EAS signing, store assets and signed Android acceptance/submission pending |

## Approved staging Auth/storage milestone — 2026-11-08

- [x] User approved the Supabase-only setup; private `.env.staging` created with mode 0600.
- [x] AI/speech keys blank; push, ingestion operator access and scheduler disabled.
- [x] Hosted smoke tests pass with two real email/password sessions, actual Auth validation,
  owned preferences/categories, cross-user denial and non-operator ingestion rejection.
- [x] Private audio bucket configured; service upload, RPC completion, API signing and
  signed download pass. Direct public/cross-user downloads fail as expected.
- [x] Disposable users/sessions/audio cleaned up and independently verified absent.
- [x] 49 backend tests, six mobile service tests, lint, typecheck, compilation and pip check pass.
- [ ] Phone OTP, paid generation, deployed network API, push and physical-device acceptance.

The earlier automatic-review blocker is resolved for the explicitly approved staging-only
setup. The prior command that included provider credentials was never executed. See
`APPLICATION_AUDIT.md` for the remaining launch blockers; production remains unchanged.

## Whole-project audit — 2026-11-08

- [x] Review mobile entry/onboarding/settings/player/notifications, backend services,
  schema/access controls, dependency audit, tests and release configuration.
- [x] Record concrete findings and the recommended order in `APPLICATION_AUDIT.md`.
- [x] Implement onboarding completion routing, push cleanup on logout and persisted request IDs;
  service tests pass. Native acceptance remains open.
- [x] Implement and offline-test periodic ingestion and scheduler pagination.
- [ ] Deploy/load-test those workers; add notification delivery retries and retention.
- [ ] Restrict client writes to billing state before implementing paid entitlements.
- [ ] Complete outstanding runtime/device/product/operations gates detailed in the audit.

Current environment inspection: mobile still uses the original Supabase project and a
temporary tunnel; default backend still targets source; the separate staging backend
works. Staging phone Auth is disabled. ADB lists no device/emulator. npm audit remains
14 affected packages (11 moderate, three high). No forced upgrades or production writes.


## Mobile recovery and staging launch milestone — 2026-11-09

- [x] Use one main-route onboarding gate for restart, successful OTP and deep links.
  Distinguish missing profile from network/auth failures and offer retry.
- [x] Preload saved categories/delivery time/timezone; prevent writes after failed load;
  reset category navigation lock when returning from delivery-time.
- [x] Serialize push registration/logout, persist attempted tokens before registration,
  unregister while authenticated, and retain the session if cleanup fails. Local signout
  leaves other devices signed in. Native token/permission acceptance is still pending.
- [x] Persist generation intent before POST, reuse it after ambiguous failure/restart,
  coalesce double taps and isolate by user/project. Do not generate if persistence fails.
- [x] Add staging API/Expo launcher with a fixed project guard, dotenv fallback disabled,
  public-only Expo variables and blank provider credentials. Default env files preserved.
- [x] Start the real local staging API and Metro. Verify HTTP health, five categories,
  anonymous preferences denial and Metro status. Android Hermes export passes.
- [x] 62 backend tests and 14 mobile tests pass; lint, typecheck and diff whitespace pass.
- [ ] Physical Android checks for rendered navigation, playback, notifications, logout,
  recovery and the new staging launch. JavaScript export is not a signed native build.
- [ ] Configure staging SMS and approved Gemini/Azure credentials for the real daily flow.
- [ ] Remaining code: periodic ingestion, durable notification retry, worker pagination,
  retention, subscriptions/entitlement protection, account deletion and release operations.

No database migration, production write, SMS or paid provider request was made in this
milestone. See `RUNNING.md` for the isolated staging commands and `APPLICATION_AUDIT.md`
for the current remaining work. Automated tests exercise workflow services, not rendered
screens or native modules. Existing dependency advisories remain open.


## Scheduler pagination and recurring ingestion — 2026-11-09

- [x] Replace single-page profile retrieval with ordered ID-cursor pagination, continuing
  until an empty page even when the server returns fewer rows than requested.
- [x] Bound pending deliveries to eight queued profiles and four workers; recheck the
  delivery window after waiting. Log scan completion/attempts/errors separately from
  successful briefing generation. Drain queued work on read failure; later ticks retry.
- [x] Share reviewed-feed batches between the operator API and periodic ingestion, with
  four feed workers, per-feed failure isolation and a per-process overlap guard.
- [x] Correct articles-seen totals and report partial insert failures without losing
  successful-insert counts. Single-feed responses also report write failures accurately.
- [x] Add independent `NEWS_INGESTION_ENABLED` (default false) and a validated interval
  (30 minutes by default, allowed 5–1440). An enabled ingestion worker runs immediately
  on startup and then periodically; it does not enable paid briefing generation.
- [x] Force ingestion off in staging launch/smoke environments and offline tests, including
  inherited enabled flags. Preserve all private environment files.
- [x] 78 backend tests and 14 mobile tests pass, plus lint, typecheck, Python compilation
  and whitespace checks. Test a 1,150-profile dataset, deletions, short pages, read errors,
  queue expiry, partial writes, overlap, bounded feed concurrency and actual timer startup.
- [x] Read-only staging SQL accepts both initial and terminal cursor queries; both pages
  are empty, as expected after disposable-account cleanup. No schema/data writes.
- [ ] Verify live SDK pagination and production-sized worker capacity with approved
  staging workloads; equivalent SDK requests are covered by mocked HTTP tests locally.
- [ ] Live feed quality, worker deployment/monitoring, durable notification retry,
  invalid-token cleanup and retention remain open. See `backend/WORKERS.md`.

The local-network Python verification did not run because automatic approval review
expired. The connected Supabase tool completed an equivalent read-only SQL check instead.
This is not a live worker/load test. No RSS fetches, provider calls, push messages,
production operations or migrations ran in this milestone.


## Durable notification delivery — 2026-11-09

- [x] Generate migration through Supabase CLI; inspect staging columns/keys/functions
  and run read-only preflight before applying any change.
- [x] Enqueue per-device notifications atomically with ready briefing saves. Dedupe by
  briefing/device; no historical backfill. Remove direct API/scheduler sends.
- [x] Service-only claims use row locks, five-minute leases and fencing. Bound attempts
  to five and queue lifetime to 24 hours, with 1/2/4/8-minute retry delays.
- [x] Recheck device ownership/token/active status at claim; cancel obsolete deliveries.
  Deactivate only confirmed unregistered tokens, conditional on unchanged owner/token.
- [x] Add independent `PUSH_DELIVERY_ENABLED=false` default, four bounded workers,
  no claim consumption if Firebase is unavailable, redacted failures and stable Android
  notification identifiers. FCM TTL is limited to remaining queue lifetime.
- [x] Force push delivery off in staging launcher/smoke runner and offline tests.
- [x] Local PostgreSQL tests pass for eight competing claims, crash recovery, stale
  acknowledgements, rollback on enqueue failure, retry caps/expiry and access denial.
- [x] Apply migration to staging as `20261109024635`; hosted rollback smoke passes.
  Cleanup confirmed independently; no real tokens, messages or users remain.
- [x] 91 backend tests, 14 mobile tests, lint, typecheck, compilation, pip consistency
  and whitespace checks pass. Database test runner includes the notification migration.
- [x] Security/performance advisors show no WARN/ERROR; intentional service-only RLS
  and unused-index INFO findings are recorded in the migration report.
- [ ] Real Firebase/device validation, token/FID compatibility, deployed worker capacity,
  monitoring, queue/audio retention and account deletion remain unfinished.

No production changes or provider sends. At-least-once delivery can duplicate a push
if FCM accepted it before acknowledgement was lost; stable notification tags mitigate
rather than eliminate that risk. Existing Firebase `Message.token` and Starlette/httpx
API deprecation warnings remain recorded; no unsupported identifier substitution made.


## Recoverable account deletion — 2026-11-13

- [x] Add authenticated, exact-confirmation DELETE request and own-account status API.
  Persist the request before revoking sessions; retries are idempotent. Disabling new
  requests does not hide already accepted requests.
- [x] Deny protected API and direct RLS access after acceptance, including old JWTs.
  Fence service writes and audio uploads; deactivate devices and remove queued pushes.
- [x] Add a durable service-only cleanup queue, 15-minute settling period, five-minute
  renewable leases, bounded batches/retries and a retained failed state after 20 attempts.
  Delete audio through Storage API before deleting Auth; recover after partial completion.
- [x] Add Settings → Delete account, exact DELETE confirmation, loading/error/retry/status
  states and sign-out after acceptance. Bind requests to the displayed account. Service
  tests and Android export pass; rendered/native interaction is not yet verified.
- [x] Generate migration files with Supabase CLI, run read-only preflight and local
  PostgreSQL concurrency/isolation tests, then apply only to authorized staging.
- [x] Move the own-account RLS helper into a private schema after advisor review.
- [x] Verify real staging Auth/Storage cleanup using two disposable accounts: accepted
  request, old-token denial, audio removal, Auth removal and preservation of the other
  user. Advance only the disposable job's due time to avoid waiting 15 minutes.
- [x] Rerun existing hosted Auth/preferences/categories/private-storage regression suite.
  Independently verify zero users/sessions/profiles/briefings/devices/jobs/audio afterward.
- [x] 105 backend tests, 16 mobile flow tests, local database integration tests, lint,
  typecheck, Python compilation, pip consistency and Android Hermes export pass.
- [ ] Enable requests only after deploying and monitoring the dedicated deletion worker.
  Both deletion flags remain false by default and in guarded staging launchers.
- [ ] Verify confirmation/restart/expired-session/accessibility flows on a physical device;
  finish cleanup alerting, operator recovery, retention/orphan sweeps and privacy policy.
- [ ] Resolve the staging Auth leaked-password-protection advisory before password-based
  release use. Review existing dependency advisories and Firebase API deprecation.

No production access/change, SMS, paid provider call or actual push send in this milestone.
The server checks current cleanup, not erasure from provider backups or already downloaded
files. A crashed upload completing late still needs orphan-retention reconciliation.
See `backend/WORKERS.md` and `backend/migrations/STAGING_REPORT.md` for deployment details.


## Staging trial migration + Home enhancement — 2026-11-14

- [x] Verify exact staging identity, fresh dependency/privilege preflight, zero non-free
  subscriptions, unchanged reviewed SQL checksum and readable/ignored PG17 backup.
- [x] Apply only `20261114063822_account_trial.sql` as real hosted version
  `20261114180421`; record it in migration docs. Verify RLS/service-only execution,
  unchanged profile/category fingerprints and zero trial rows.
- [x] Verify live service returns `claim_unavailable`, `device_required`, `can_generate=false`
  and denies generation. User's authenticated Android phone reports five HTTP 200s.
- [x] Reject malformed timestamps/inconsistent trial state; cover unavailable/invalid
  responses, disabled claims, unclaimed accounts and generation denial in backend tests.
- [x] Add scoped Home gradient tokens, short Reanimated entrances/press feedback,
  readable Burmese hierarchy, saved-interest labels and intentional empty/loading/error
  panels. Preserve actual saved-briefing readiness, playback and navigation contracts.
- [x] Deduplicate Home entitlement refreshes with the existing resource lifecycle;
  disable generation UI while entitlement is unavailable/loading. Public claims stay off.
- [x] TypeScript, lint, 44 mobile tests and 131 backend tests pass; Android/web exports pass.
- [x] Render real web Home with offline fixtures at 320px/390px; check navigation,
  entitlement failure/retry, reduced motion, no fabricated content and no runtime errors.
- [ ] Physical Android UI acceptance: gradients/native module availability, font scaling,
  TalkBack, reduced motion, smooth scrolling, real playback and logout/login/onboarding.
- [ ] Public device enforcement remains unavailable; no public trial claim or automatic
  entitlement grant is enabled. News ingestion and paid providers stay disabled.

Details: `HOME_ENHANCEMENT_REPORT.md` and `backend/migrations/TRIAL_STAGING_PLAN.md`.
The backup is an application-schema archive, not a full Supabase/Auth disaster backup.


## RSS ingestion engine — 2026-11-15

- [x] Reuse the existing `news_items`, category IDs, unique `content_hash` index,
  authenticated News API and briefing selector. No database migration or mobile
  contract change was needed.
- [x] Add an audited 23-feed registry and staging-only one-shot CLI. Background
  ingestion, scheduler, AI/TTS, push and trial claims remain disabled.
- [x] Add bounded RSS/Atom networking, per-redirect public-IP checks, response and
  gzip limits, retries, ETag/Last-Modified/304 support, cooldowns, text cleaning,
  UTC normalization, category mapping, URL/GUID/title deduplication and stable API
  ordering. Slashdot now uses a verified HTTPS URL; inaccessible candidates are
  disabled rather than scraped or silently substituted.
- [x] Replace live-feed reconstruction at write time with immutable staging batches:
  the exact reviewed database rows are digest-bound and imported without refetching.
- [x] Limit dated records to the requested 24-hour window; report undated entries
  separately. Rotate the global proposal cap across existing categories, then
  publishers, prioritizing dated items.
- [x] Complete staging read-only dry run: 23 sources checked; 20 successful,
-  3 failed/disabled; 616 parsed, 347 evaluated under per-feed caps, 171 dated
  within 24 hours, 20 undated, 156 rejected, 1 duplicate, 190 eligible, 100
  proposed, **0 inserts**. Report run ID:
  `062f33cc-691c-455f-8f97-12168c9abdfd`. Category counts in the capped batch:
  Myanmar 1, Football 25, Business 31, World 4, Technology 39. See
  `backend/reports/rss_staging_dry_run_20261114T194027Z.md` and its JSON sidecar.
- [ ] Review one exact JSON proposal report and explicitly approve the first
  staging write. No staging write was performed.
- [ ] After approval, verify inserted stories through authenticated `/api/v1/news`,
  category selection and the existing briefing path. Review source results again
  because feeds change between dry runs and writes.
- [ ] Retry VentureBeat only after its rate-limit cooldown; obtain publisher-approved
  replacements for The Next Web and e27. Current findings are in the source report.
- [ ] Validate article quality/category mappings and Burmese rendering on device;
  verify source variety with real inserted content.

Checks after this milestone: 44 RSS tests and 175 backend tests passed. No mobile
source changed in this increment; prior `npm run typecheck`, `npm run lint`, and
44 mobile tests remain applicable. Python compilation and `git diff --check` passed.
The final dry run made no database writes.

See `backend/README_RSS_INGESTION.md` for operator commands and limitations.

### Immutable RSS batch approval — 2026-11-15

- [x] Preserve the original live-feed mismatch as history; Stage B now reads and
  validates only the immutable approved report and never fetches feeds.
- [x] Bind the exact batch rows, project, source registry, limits, timestamps and
  run ID to a deterministic digest; reject modified, expired, stale or mis-targeted
  batches before write attempts.
- [x] Require explicit user-approved digest and run ID, validate saved rows against
  current source/category/URL/freshness rules, and keep URL/hash/title deduplication,
  strict caps and idempotent conflict handling.
- [x] Use a user-scoped authenticated staging JWT for both reads and writes; the
  service-role client is not used by RSS preparation/import. Require an explicit
  verified-policy guard; no INSERT can bypass table RLS.
- [x] Run a read-only staging diagnostic: 23 sources checked, 20 parseable,
  3 failed/disabled; 621 parsed; 181 within 24 hours; 3 duplicates;
  178 eligible; 100 proposed; 0 writes. This first report was prepared with the
  prior service-role read path and is **not eligible for approval**; schema v2
  explicitly rejects it. Keep it only as diagnostic history.
- [ ] Add and verify a staging-only authenticated operator INSERT RLS policy before
  import. Current staging `news_items` has SELECT RLS only; no schema changes were
  made and no article batch has been imported.
- [x] Re-run the guarded dry-run command after enforcing authenticated reads. It stops
  at `authentication_preflight` because `RSS_IMPORT_ACCESS_TOKEN` is absent; zero
  database reads, feed fetches, writes, or new reports occur.
- [ ] Add a short-lived authenticated staging operator JWT in ignored
  `backend/.env.staging`, then generate a new report whose batch records
  `database_read_role=authenticated_operator` and whose reads pass RLS.
- [ ] Obtain explicit approval of that new report's digest and run ID, then import
  through the authenticated RLS path only after the policy prerequisite is satisfied.

Backend regression tests cover digest tampering, expiry, registry/project/source/category/
URL/freshness failures, explicit approval, rejection of legacy service-role reports,
no feed refetch, RLS-token and policy-guard requirements, deduplication, replay,
concurrency and partial write outcomes. All 201 tests under `backend/tests` passed;
compileall and `git diff --check` passed. A broader `pytest backend` collection is
blocked by two legacy top-level scripts that execute at import time.

### Auth ReadError and empty-news follow-up — 2026-11-15

- [x] Confirm staging has 0 articles/recent articles and 0 saved briefings; verify
  Home/API news response contracts and missing authenticated INSERT policy.
- [x] Add one bounded transient Auth GET retry and share in-flight same-token
  verification; preserve fresh checks for subsequent requests and account deletion.
- [x] Add safe transport categories and concurrency/cancellation/isolation tests.
- [x] Run backend regression suite (209 passed), final focused auth suite (14 passed),
  mobile typecheck/lint/44 tests, compilation and whitespace checks.
- [x] Retry guarded RSS preparation: blocked before work by absent operator JWT;
  the existing v1 report remains ineligible, and no article write occurred.
- [x] Prepare reviewable operator RLS policy, rollback and acceptance plan in
  `backend/reports/AUTH_NEWS_DIAGNOSIS.md`; do not apply without explicit approval.
- [ ] Configure approved operator session/policy, prepare fresh batch and request
  approval of its exact digest before the first import.
- [ ] Restart local backend and verify ReadError recovery on authenticated Android.
- [ ] Approve/configure providers and authorized generation separately, then verify
  real Burmese script/audio/storage/signed-URL/playback. No provider invoked here.

Additional live trial-count inspection was blocked by automatic approval review's
usage limit and was not executed. No production resources were accessed.

### Grounded personalized audio milestone — 2026-11-15
- [x] Add optional structured Burmese narration with validated selected-source IDs and durable metadata contract.
- [x] Extend existing player with source snapshots, publisher links and shared sunrise motion; preserve playback controller.
- [x] Share bounded publisher-balanced selection across manual/scheduled generation and retain overlapping reports in approval hashes.
- [x] Add source-aware coordination, fail-closed schema check and offline rehearsal/regression coverage.
- [ ] Approve and transaction-test `backend/schema_proposals/briefing_sources.sql` on staging; it is not applied.
- [ ] Separately approve existing automatic-delivery preference proposal and feature activation.
- [ ] Fresh reviewed batch, separately approved one-time provider test, then physical Android validation.
- [ ] Separately authorize recurring paid worker and live push only after end-to-end success.
See `backend/reports/GROUNDED_BRIEFING_HANDOFF.md` for dependencies, rollback and verification. No live end-to-end success is claimed.
