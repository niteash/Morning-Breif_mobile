# Staging runtime preparation

Target: `morning-brief-staging` (`wwtntxknfjagdjdgiaxu`). Production is unchanged.

The user approved the narrower Supabase-only setup. `prepare_staging.py` has run and
created ignored, owner-only `backend/.env.staging`. Existing production configuration
is preserved. Do not rerun preparation over this file; the script refuses to overwrite it.

For a fresh approved staging setup, from the app directory:

```sh
.venv/bin/python backend/scripts/prepare_staging.py
```

The script reads only `SUPABASE_ACCESS_TOKEN_STAGING` from ignored `backend/.env`,
retrieves API keys for the fixed staging reference, and exclusively creates
`backend/.env.staging` with permissions 0600. Existing files are preserved. It does not
copy Gemini/Azure/Firebase credentials; AI/speech keys are blank and scheduling/push are
disabled. It does not create accounts, storage buckets, or send messages.

Management credentials and backend service keys must never enter mobile environment
variables.

## Hosted smoke checks

```sh
.venv/bin/python backend/scripts/staging_smoke.py
```

This opt-in runner only accepts the fixed staging URL, blank provider/push settings and
disabled scheduling. It disables fallback `.env` loading, creates two disposable Auth
accounts, and tests FastAPI routes through an in-process ASGI client against real
Supabase Auth/PostgREST/Storage. It uses an encoded MP3 fixture, not generated news/TTS.

It creates a private `briefings` bucket if absent (20 MiB, audio/mpeg only), tests signed
download and public/cross-user denial, then revokes sessions and removes test users and
objects. The bucket and category seed remain. Hosted checks passed; cleanup was verified
separately through database metadata. This does not test SMS or a deployed HTTP server.

## Local staging API and Expo

From the app directory, in separate terminals:

```sh
.venv/bin/python backend/scripts/run_staging.py backend --host 0.0.0.0
npm run start:staging -- --api-url http://10.0.2.2:8000
```

Use Node 22 for Expo. For a physical device, replace `10.0.2.2` with this Mac's LAN IP.
The launcher validates the fixed staging reference and disabled providers/scheduler,
uses an allowlist of child-process environment settings and disables dotenv fallback.
Expo receives only public staging keys/API URL; management and service credentials are
excluded. Push registration is disabled. The `.env.staging` file is read, not changed.

Automatic briefing testing is deliberately opt-in. Use `--enable-generation
--enable-automation` for scheduled feed refresh plus AI/audio generation. Add
`--enable-push` only after preparing the ignored `.env.push-test` from
`.env.push-test.example` with an absolute Firebase Admin service-account path. The mobile
launcher accepts matching `--enable-push` and `--enable-ads` flags; ads need a rebuilt
native development client. See `../../RUNNING.md` for complete commands.

API/Metro startup, real HTTP health/categories/anonymous denial and Android Hermes export
were verified on 2026-11-09. These checks do not establish SMS login or device behavior.
See `../../RUNNING.md` for full instructions and current limitations.

## Disposable account-deletion check

`../../.venv/bin/python account_deletion_smoke.py --disposable-staging` (from this directory)
uses only the validated `.env.staging` and creates two synthetic email users/test objects.
It pauses after printing the deletion user's UUID. Either wait 15 minutes or, on the
already authorized staging project only, advance `account_deletion_jobs.available_at`
for exactly that UUID and confirm the associated Auth email starts `deletion-smoke-`.
Then press Enter. It verifies cleanup and other-user isolation and removes test fixtures.
No sessions, passwords or keys are written/printed. Never run against production; the
script rejects other URLs or enabled provider settings. Inspect remaining test queue rows
if interrupted; the script deliberately cannot bypass worker lease checks to delete them.
