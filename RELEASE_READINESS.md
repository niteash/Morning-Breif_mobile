> Current development update: see `RUNNING.md` for startup commands. Category writes
> and generation require `backend/migrations/001_reliable_writes.sql`, now applied and
> database-tested on `morning-brief-staging` only. Production is unchanged. Migration and
> backend must be deployed together. Staging runtime/provider/device acceptance remains
> required; see `backend/migrations/STAGING_REPORT.md` for verified scope.

# Release readiness

**Not approved for production release.** See `DEVELOPMENT_PLAN.md` for verified
milestones and unfinished work. No release was built, signed, submitted or deployed.

Latest whole-project review: [APPLICATION_AUDIT.md](APPLICATION_AUDIT.md).
Approved staging Auth/API/private-storage smoke checks pass with disposable real
email/password sessions. The product uses Google and email credentials; phone OTP/SMS is
intentionally out of scope. Provider generation and native device flows remain open.

## Local development

From this directory, select Node 22 (`nvm use` if available), then:

```sh
npm ci
npm run lint
npm run typecheck
npm test
npx expo-doctor
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-dev.txt
cd backend
../.venv/bin/python -m pytest -q
../.venv/bin/python -m compileall -q app
```

Pytest collects only `backend/tests`; legacy provider scripts in `backend/test_*.py`
may incur charges or write live data. The four safe news scripts run within pytest.
Offline tests substitute dummy credentials and prohibit socket connections.

Copy `.env.example` to `.env` and `backend/.env.example` to `backend/.env` locally.
The mobile environment needs only the three `EXPO_PUBLIC_*` values. Keep service-role,
Gemini, Azure and Firebase credentials exclusively on the backend. Do not paste keys
into tickets or commit local environment files. Existing environment files were preserved.

Start the API from `backend`:

```sh
SCHEDULER_ENABLED=false ../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

From the app directory use `npm start` with a development build. Configure a reachable
API URL for the device; its localhost is different from your computer's localhost.
Do not use a temporary tunnel URL for production.

## Deployment gates

1. Staging schema, category seed, private bucket and separate backend runtime keys are
   configured. Connect a distinct mobile staging build; existing mobile settings still
   point to the original database and temporary API tunnel.
2. Durable generation/atomic category SQL is verified on hosted staging, including RLS,
   concurrent claims, fencing, quotas and cooldowns. Real email Auth and API/Storage
   smoke tests passed through an ASGI client. Deployed HTTP/provider and running
   multi-instance integration remain release gates.
3. Keep `SCHEDULER_ENABLED=false` , `NEWS_INGESTION_ENABLED=false` and `PUSH_DELIVERY_ENABLED=false` in ordinary API
   workers. One dedicated process may enable the selected jobs after staging acceptance.
   ID-cursor pagination and bounded queueing are implemented and tested offline; delivery
   uses four workers within a two-hour same-day catch-up window. Live capacity, downtime
   recovery and real notification delivery remain gates. Durable retry is database-tested;
   Firebase token/FID compatibility and native duplicate behavior remain unverified. See `backend/WORKERS.md`.
4. Configure `INGESTION_OPERATOR_IDS` with authorized Supabase UUIDs in backend secrets.
   Clients cannot supply arbitrary feed URLs or grant themselves operator access.
5. Verify Google OAuth and email credential login, session restoration, password reset,
   logged-out deep links and logout on real devices. Keep phone Auth disabled.
6. Verify Gemini, Azure, private storage signing and FCM on staging; record costs,
   failures and retry behavior. Set retention for superseded/orphaned audio objects.
7. Resolve remaining dependency advisories without downgrading Expo blindly. Re-run
   compatibility checks, Android export and a native build after dependency changes.
8. Configure Play/RevenueCat products and server-validated entitlements before charging
   users. Paywall remains a placeholder; `subscription_status` is not purchase proof.
9. Supply EAS project access, Android Firebase configuration, signing credentials and
   Play Console service account through private build settings. Decide final pricing,
   support contact, privacy policy, retention and account-deletion workflow.

## Device acceptance evidence required

- Google/email login succeeds; logged-out deep links redirect to login; app restart
  restores a valid session; password reset and logout are verified.
- Onboarding and settings persist categories and timezone/time; errors are actionable.
- One combined MP3 per successful attempt; measured duration matches playback.
- Play/pause, replay, ±15-second seeking, buffering and network recovery work.
- Audio survives screen lock/background operation; lock-screen controls work. Playback
  remains screen-owned, so navigation behavior must also be checked.
- Expired signed URL refresh restores playback; no credentials/signed URLs in logs.
- Notification permissions, foreground refresh, background taps, killed-app startup and
  token rotation/logout behavior are checked. Cold-start notification routing is pending.
- Delivery around UTC midnight, local midnight, DST, downtime and worker crashes is tested.
- RLS blocks cross-user preferences, briefing reads/writes, tokens and storage access.
- Monthly/yearly purchase, restore, cancellation, renewal and grace-period tests pass.

## Verified scope

Read-only Supabase table/column discovery, local offline tests, lint, typecheck,
Expo Doctor, API health and Android bundle export
are development evidence. They do not verify deployed schema, SMS delivery, provider
credentials, Burmese narration quality, Android background behavior or billing.

API references used: [Expo SDK 57 audio](https://docs.expo.dev/versions/v57.0.0/sdk/audio/)
and [Supabase Google login](https://supabase.com/docs/guides/auth/social-login/auth-google).

## Latest deletion milestone — 2026-11-13

Account deletion is implemented and verified using disposable staging Auth/Storage users,
plus offline and PostgreSQL tests. The mobile confirmation screen exports for Android but
still needs device testing. Enable requests only after deploying and monitoring the cleanup
worker; both flags remain off by default. All six migrations are required by this backend.
Complete orphan/retention sweeps, failed-job recovery, public privacy/deletion documentation,
real AI/TTS/FCM acceptance, subscriptions, hosting, signing and store submission.
Staging currently also reports Auth leaked-password protection disabled; see the staging
report. This is development progress, not production-release approval.
