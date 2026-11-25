# Morning Brief whole-project audit — updated 2026-11-13

**Verdict: substantial MVP implementation, not ready for production release.**
The staging database and core Auth/API/storage integration are verified. Phone OTP,
real AI/TTS news generation, scheduled device delivery, subscriptions and signed-device
acceptance are not complete. No completion percentage is justified by current evidence.

## Scope and evidence

Reviewed mobile routes, Auth/session handling, API services, player and notifications;
backend routes, ingestion/selection/ranking/clustering, generation, scheduler, storage,
database migrations/RLS, tests, dependencies, CI and Expo/EAS configuration. Findings
below distinguish inspected code from live checks. Existing changes were preserved.

- Expo 57 / React Native 0.86.3 / React 19 / TypeScript 6; FastAPI/Python; Supabase,
  Gemini, Azure Speech and Firebase. Android is the implemented notification target.
- Current checks: **105 backend tests**, **16 mobile service/flow tests**, lint, TypeScript,
  Python compilation, pip dependency consistency and `git diff --check` pass.
- Hosted staging SQL verified atomic categories, ownership, eight competing claims,
  fencing, quotas and cooldowns. See `backend/migrations/STAGING_REPORT.md`.
- Approved hosted integration used real email/password sessions and actual backend
  authentication. Preferences, categories, news reads, operator denial, service upload,
  saved-briefing signing and signed download passed; cross-user/public access denied.
- Authenticated integration used FastAPI's **in-process ASGI client**. The local staging
  HTTP server also passed health, five-category retrieval and anonymous-denial checks;
  a deployed HTTPS server is still unverified.
  Audio was an encoded-frame fixture, not Gemini/Azure-generated Burmese speech.
- Disposable users/sessions/profile/briefing/job/audio records are absent after cleanup.
  Five seeded categories and a private 20 MiB audio/mpeg bucket remain on staging.
- Staging `.env.staging` exists privately; AI/speech credentials are blank, push and
  scheduler are disabled. Production/default `.env` files remain unchanged.
- ADB reports no attached Android device/emulator. Previous JS export/Expo Doctor
  results are useful baseline evidence, not a signed APK/AAB or native acceptance test.
- The last recorded npm audit reports **14 affected packages: 11 moderate, three high, zero
  critical**. High entries include expo-router, query-string and decode-uri-component;
  these include transitive propagation, not necessarily 14 independent vulnerabilities.
  Suggested router remediation crosses an SDK major; no forced upgrade was performed.
  Registry-reported high advisories: [malformed decoding](https://github.com/advisories/GHSA-vcc3-ghjq-m6fr)
  and [percent-encoded runs](https://github.com/advisories/GHSA-qr28-fpjm-wq7f).

## Launch blockers, in priority order

### 1. Finish environment wiring and phone authentication

- The current mobile `.env` still targets the original Supabase project and a temporary
  tunnel API. The default backend also targets the original project, where the new
  migrations have intentionally NOT been applied. New write flows fail closed there.
- A guarded local staging launcher now supplies only public staging values to Expo,
  disables dotenv fallback and leaves the default files untouched. API/Metro startup
  and an Android Hermes export passed. Use `RUNNING.md`; this is not a distinct signed
  native build. EAS profiles still need explicit release environment mapping.
- Staging phone Auth is disabled. Configure an SMS provider and verify actual send,
  resend, invalid/expired code, recovery and logout on a real phone. Email test sessions
  do not establish that the phone onboarding works.

### 2. Fix confirmed mobile/session workflow gaps

- **Implemented and service-tested:** the main-route guard checks profile/category
  completion for restart, OTP and deep-link entry. Existing users go through the same
  decision; missing profiles use setup, while API/network failures show a retry.
- **Implemented and service-tested:** logout waits for pending push registration,
  deactivates remembered tokens while authenticated, then signs out this device.
  Cleanup failure keeps the session for retry. Tokens from older app versions that
  were never persisted and are no longer obtainable remain a native migration concern.
- Category/time editors now preload saved choices, preserve timezone and disable writes
  if loading fails. Focus resets the categories navigation lock after Back.
- These are code and service-test results. Back navigation, account switching, offline
  logout and permission/token lifecycle still need rendered/native acceptance checks.
- Complete session expiry/re-login handling, accessibility/text-size checks and a
  deliberate Burmese/English UI language pass. Current automated mobile tests cover
  service utilities, not rendered screens, navigation, audio or native notifications.

### 3. Complete the actual news-to-audio flow

- Run reviewed feeds on staging, inspect accepted/rejected stories and validate ranking,
  publisher attribution and event clustering with real cases. Category reference data
  exists; no staged production news corpus has been copied.
- **Implemented and tested offline:** independent opt-in periodic ingestion uses the
  same reviewed-feed batch as the operator API, with four concurrent feeds, accurate
  article totals and partial-failure reporting. The real APScheduler execution path
  was tested with substituted feed work. Live feed quality, deployment and uptime
  acceptance remain open; periodic jobs are disabled in staging. See `backend/WORKERS.md`.
- Review category-aware duplicate behavior: the title-hash lookup in
  `backend/app/services/news/ingest.py:233` is global and concurrent feeds can race on
  title hashes. Add fixtures/constraints consistent with the intended cross-category model.
- Configure approved Gemini/Azure credentials, test the live consolidated MP3 pipeline,
  measure latency/cost and conduct Burmese factual/pronunciation review. Prompt rules
  and offline fixtures alone cannot verify factual accuracy or speech quality.
- **Implemented and service-tested:** generation intents persist before the request,
  are scoped to Supabase project/user and survive ambiguous failure/app restart. Double
  taps share a request; a confirmed response clears the intent for a new generation.
  Recovery still depends on the backend's current per-day job/replay rules; durable
  multi-intent history and user-visible job polling are not implemented.
- Separate generation progress from a long synchronous HTTP request, or verify a bounded
  polling/recovery design. The mobile generation timeout is four minutes; primary plus
  fallback AI and TTS timeouts can consume that window before storage/DB overhead.

### 4. Make daily delivery and notifications recoverable

- DB coordination is verified; multiple actual API/scheduler processes have not been
  tested through provider calls. Configure a dedicated worker and test restart/catch-up.
- **Implemented and tested offline:** profile pagination uses an ID cursor, a bounded
  queue and four delivery workers. A test scans 1,150 profiles through a simulated
  lower server cap and deletion between pages. Staging accepted the equivalent read-only
  SQL queries (zero profiles). Live SDK pagination under load is still unverified.
  Capacity planning is required so queued jobs finish inside the two-hour catch-up window.
- **Implemented and database-tested:** ready-briefing writes atomically enqueue per-device
  notifications. Service-only claims have leases, bounded exponential retry and expiry;
  unregistered tokens are deactivated with account/token checks. Migration is applied only
  to staging; hosted rollback checks and cleanup passed. Real FCM remains disabled.
- Delivery is at-least-once after ambiguous provider responses, with stable Android tags
  to reduce duplicates. Test duplicate display/sound, restart and logout races on devices.
  Firebase Admin 7.7 warns that `Message.token` is deprecated in favor of installation
  IDs (`fid`); current Expo registration supplies FCM tokens. Validate/migrate the native
  identifier flow before release; simply putting an existing token in `fid` is incorrect.
- Verify real FCM registration, token rotation, permission denial, account switching,
  foreground/background/killed-app delivery and cold-start tap routing. Current routing
  registers listeners; no explicit last-notification startup handling was found.
- Retain the documented two-hour same-day catch-up limit or implement a product-approved
  recovery rule for longer downtime and midnight boundaries.

### 5. Implement subscriptions and protect entitlements

- `src/app/(main)/paywall.tsx` is a placeholder. No RevenueCat SDK, purchase/restore
  flow, billing webhook verification or server entitlement enforcement was found.
- Decide products/pricing/free access, configure Play/RevenueCat and test purchase,
  restore, expiry, cancellation/refund and offline entitlement behavior.
- **Do not trust `profiles.subscription_status` for paid access yet.** Hosted catalog
  inspection confirms authenticated users have UPDATE privilege on this column, with
  own-profile RLS. Restrict billing state to trusted server writes before using it for
  authorization. No current paid entitlement check exists, so this is not a verified
  bypass of an already-implemented payment system.

### 6. Finish privacy, operations and native release validation

- Account-deletion UI/API, durable worker and private RLS helper are implemented and
  verified with local tests and real disposable staging Auth/Storage. Requests and worker
  remain disabled by default; device acceptance, deployment/alerting, orphan reconciliation
  and privacy/terms documents are still needed. Session revocation and current profile/
  device/audio cleanup passed staging checks; backup retention remains a policy concern.
- Finish the log audit: profile/preference responses and user IDs are still printed;
  Azure failures include raw response bodies (`backend/app/services/tts/azure.py:75`).
  Some fixes are already present, but redaction is not complete across all runtime paths.
- Implement retention for superseded/orphaned audio and news data; add failure/cost
  monitoring, actionable alerts, backups and restore verification. `/health` currently
  reports process health only, not readiness of critical dependencies.
- Move synchronous Supabase calls out of async route/event-loop paths or use an async
  client; load-test realistic concurrency and enforce operational request/cost limits.
- RSS fetches have timeouts/retries, but `response.read()` has no body-size cap. Add
  feed/response bounds and review allowed article URL schemes before opening links.
- Review unused legacy briefing modules and live-provider scripts. For example, the
  old `briefing/service.py` uses direct writes and a `briefing_stories` table absent from
  the inspected schema. It is not used by current routes; quarantine/document it so it
  cannot be mistaken for the verified pipeline. Preserve recovery backups until reviewed.
- Deploy a stable HTTPS backend and worker with reproducible configuration, secrets,
  restart behavior and monitoring. No deployment manifest was found in this repository.
- Review npm advisories with SDK-compatible remediation. Confirm clean-checkout CI:
  `.github/workflows/checks.yml` and other new work are still untracked/uncommitted, so
  their execution in GitHub has not been established. Preserve work and commit only after review.
- Firebase Android configuration exists locally but is ignored; configure the build
  service's file secret. Verify EAS signing, production settings, store listing/assets
  and subscription/privacy declarations. No signed release was produced this session.
- Test playback, seeking, audio interruptions, lock screen/background mode, signed-URL
  expiry, app restart, midnight rollover and unreliable networks on physical Android.
  iOS push currently returns early; iOS support would require additional implementation
  and acceptance if it becomes a release target.

## Recommended sequence

1. Device-test the repaired onboarding/logout/retry flows using the local staging launcher;
   prepare a distinct signed staging build.
2. Configure phone SMS and approved AI/TTS; prove one real news-to-audio daily journey.
3. Deploy/test the opt-in ingestion, paginated scheduler and durable push worker; add
   retention/monitoring and verify Firebase identifier compatibility.
4. Implement subscriptions, entitlement protection and account/privacy flows.
5. Complete dependency/deployment work, clean-checkout CI and signed-device acceptance.

Items 1 and most of 3 are code work. SMS/provider/store credentials, billing decisions,
hosting access and physical-device testing are external completion gates. Staging access
is no longer a blocker, and the approved Supabase-only runtime setup is complete.


## Account-deletion verification update — 2026-11-13

Staging has both account-deletion migrations. Typed confirmation submits only for the
currently displayed authenticated account, and UI distinguishes acceptance from completion.
Hosted verification removed test audio/Auth, preserved another user's audio/Auth and left
no test records; the original Auth/API/storage smoke suite also still passes. Android
Hermes export succeeds, but no rendered-screen or physical-device test was performed.
New backend code requires all six staging migrations even with deletion flags disabled;
production/default `.env` remains intentionally unmigrated and must not be used for this
version. Use the guarded staging launcher. Do not expose new requests until a monitored
worker is deployed. Current advisor warning: Auth leaked-password protection disabled;
private helper exposure is fixed. See migration report for remediation links.
