# Run Morning Brief locally on staging

Use two terminals from `/Users/nikki/Downloads/mobile_app copy/morning-brief`.
The commands below use the approved private `backend/.env.staging`. They do not edit
or load the existing production/default `.env` files.

## Dependencies

Dependencies are already installed on this machine. On a fresh setup:

```sh
nvm use
npm ci
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-dev.txt
```

Use Node 22 from `.nvmrc`. Staging is `wwtntxknfjagdjdgiaxu`; its migrations, category
seed and private audio bucket are already applied. Do not reapply migrations. A fresh
checkout also needs the private staging environment prepared through
`backend/scripts/README.md`; credentials are deliberately not committed.

## Terminal 1: staging API

```sh
cd "/Users/nikki/Downloads/mobile_app copy/morning-brief"
.venv/bin/python backend/scripts/run_staging.py backend --host 0.0.0.0
```

Check `http://localhost:8000/health`; API docs are at `http://localhost:8000/docs`.
Omit `--host 0.0.0.0` to restrict the server to this Mac. Stop it with Ctrl+C.

For an explicitly authorized local end-to-end generation test, use the isolated
`backend/.env.audio-test` provider configuration while retaining the staging database:

```sh
.venv/bin/python backend/scripts/run_staging.py backend --host 0.0.0.0 --enable-generation
```

This enables the durable on-demand generation worker. The mobile request returns
immediately, progress survives app restarts, and the worker performs reviewed-feed
selection followed by AI/TTS generation.

To test the user-selected daily schedule, automatic news refresh, and audio generation:

```sh
.venv/bin/python backend/scripts/run_staging.py backend --host 0.0.0.0 --enable-generation --enable-automation
```

Push delivery additionally requires a Firebase Admin service-account JSON (the Android
`google-services.json` is not an Admin credential). Copy
`backend/.env.push-test.example` to the ignored `backend/.env.push-test`, set its absolute
credential path, then add `--enable-push` to the command above. This machine does not yet
have that credential, so push cannot be sent until it is supplied.

## Terminal 2: staging mobile app

For an Android emulator:

```sh
cd "/Users/nikki/Downloads/mobile_app copy/morning-brief"
nvm use
npm run start:staging
```

This defaults to `http://10.0.2.2:8000`. For a physical Android device on the same Wi-Fi,
replace the example address below with your Mac's LAN IP and keep Terminal 1 bound to
`0.0.0.0`:

```sh
npm run start:staging -- --api-url http://192.168.1.20:8000
```

When the backend is running with `--enable-push`, register the installed development app
by starting Metro through the guarded launcher:

```sh
.venv/bin/python backend/scripts/run_staging.py mobile --api-url http://192.168.1.20:8000 --enable-push
```

Ads require a rebuilt native development app because the AdMob SDK is native. Development
uses Google's test ad IDs; after rebuilding, add `--enable-ads` to the mobile launcher.
Production ads remain disabled until real `ADMOB_ANDROID_APP_ID` and
`EXPO_PUBLIC_ADMOB_BANNER_UNIT_ID` values are configured for the production build.

Open the installed Morning Brief development build and connect to Metro. A development
build and configured Android/Firebase toolchain are still needed for native acceptance;
Expo startup and a Hermes export do not install or sign an Android app. No physical
device was available during these checks. Stop Metro with Ctrl+C.

After adding or updating native modules (including background Wi-Fi downloads), rebuild
the development app once before starting Metro:

```sh
npx expo run:android
```

The launcher validates the staging project, forwards only public Supabase values to Expo,
rejects hosted/nonlocal API addresses, and disables automatic dotenv loading. Provider
keys remain blank and scheduling/push stay off unless their explicit flags above are used.
It refuses provider-enabled configuration rather than falling back to another environment.
This is a local staging launch, not a separately identified/signed staging build.

**Current functional limits:** phone Auth/SMS is intentionally not used. Verify Google
OAuth and email credential restoration in the physical-device build. Gemini/Azure
generation and device push still depend on the protected staging configuration. There is
no mobile authentication bypass. The local API can still serve health/categories.

The ordinary `npm start` and direct Uvicorn commands load the default environment,
which currently contains a placeholder Supabase URL and will fail fast. Use the guarded
staging commands for this milestone.
`SUPABASE_ACCESS_TOKEN_STAGING` is an administrative token, never a mobile app key.

## Checks

```sh
EXPO_NO_DOTENV=1 npm run lint
npm run typecheck
npm test
cd backend
../.venv/bin/python -m pytest -q
```

Database tests use a disposable local PostgreSQL database; see
`backend/migrations/README.md`. Hosted Auth/storage smoke tests are separate opt-in checks
in `backend/scripts/README.md`. Remaining release work is in `APPLICATION_AUDIT.md`.

Expo environment loading follows the [official Expo environment guide](https://docs.expo.dev/guides/environment-variables/).
