# Home enhancement milestone — 2026-11-14

The existing Home layout, Burmese copy, navigation destinations, data sources and
playback ownership are retained. This is a scoped enhancement, not a replacement app.

## Implementation

- `src/theme/home.ts`: scoped cream/peach/coral/gold and lavender/blue gradient tokens;
  darker ink, muted text and accent colors retain contrast on the pale surfaces.
- `src/components/home/HomePresentation.tsx`: gradient panels, pill actions, clear
  error panels, static loading placeholders with one reveal, saved-category labels,
  and an empty-news panel with the existing refresh action. No fabricated stories.
- `src/components/ui/Motion.tsx`: Reanimated entrance (280ms, up to 220ms stagger)
  and damped spring press feedback (220ms, scale 0.98). Opacity/transform only;
  no looping gradients, blur, WebGL, JS frame timers or persistent decorative motion.
  System reduced-motion settings are read initially and updated through accessibility
  events. React-compiler-compatible shared-value get/set APIs are used.
- `src/app/(main)/(tabs)/home.tsx`: warm greeting, peach briefing centerpiece, status
  reveals, interest chips, staggered story cards and intentional empty/error/loading
  states. Entitlement reads use the existing deduplicated, account-scoped read lifecycle
  and refresh on focus/foreground/pull-to-refresh. Reads never claim trials. The prior
  explicit staging claim action is preserved but unavailable in this environment.
  Failed/in-flight entitlement reads cannot leave a cached generation action enabled.
- `src/components/ArticleCard.tsx`: opt-in `appearance="sunrise"` for Home only;
  existing external-link validation/error handling remains. Other screens retain their
  default appearance. Home category chips remain noninteractive saved-interest labels;
  no selection behavior was invented.
- `package.json` / `package-lock.json`: `expo-linear-gradient ~57.0.2` installed through
  `expo install` using the SDK 57 compatibility map. No other app dependency added.

## Backend verification

The approved trial migration was applied only to staging. Exact hosted version,
checksums, backup limitations and actual phone HTTP 200 evidence are recorded in
`backend/migrations/TRIAL_STAGING_PLAN.md`. No trial was granted; `can_generate=false`.
The backend now rejects malformed timezone/date fields or inconsistent active/expired
states using the database-provided clock. The local staging API was restarted on its
existing LAN port to load this check; health/worker flags and anonymous 401 were verified.
Regression tests cover invalid payloads,
disabled claims, missing records, permission/database errors and generation denial.

## Checks

- TypeScript: pass.
- Lint: pass, zero errors/warnings after correcting the shared-value setter.
- Mobile unit/service tests: 44 passed, covering auth refresh, session/account isolation,
  onboarding, read deduplication, requests, playback and logout.
- Backend suite: 131 passed. Existing Starlette/httpx and Firebase deprecation warnings
  remain; warnings were not suppressed.
- Android Hermes and web production exports: pass using dummy public configuration,
  dotenv loading disabled and push disabled. No deployment or release build performed.
- Offline Chromium UI check with the actual exported web app: Home renders without
  page errors at 390px and 320px; absent briefing/empty news, Home → News → Home,
  entitlement 503 and successful retry, reduced motion, and no horizontal page overflow
  pass. No fixture action made a POST or accessed an external/backend service. These
  tests use clearly synthetic session/API fixtures, not staging authentication.
- Screenshots inspected: `/tmp/nay-thit-home-top.png`, `/tmp/nay-thit-home-empty.png`,
  `/tmp/nay-thit-home-small.png`. Temporary browser tooling lives outside this repository.
- Actual Android auth/API: user supplied five entitlement GET HTTP 200 log entries.
  No Android device/emulator is attached to ADB; native UI acceptance is still pending.

## Remaining device checks

1. Restart/reload Metro using the guarded staging command in `RUNNING.md`. If using a
   custom development client, rebuild it to include the new native gradient module;
   Expo Go SDK 57 already includes this module.
2. On the physical phone, check Home's Burmese shaping, long category labels, large
   system font settings, small-screen wrapping, safe areas and scrolling.
3. Enable Android's Remove animations option and TalkBack: confirm stable content,
   intelligible labels, focus order and reachable retry/actions. Check spring feedback
   and scrolling with animations enabled on an ordinary phone.
4. Test offline/error → retry, pull-to-refresh, navigation, returning from background,
   logout/login and real onboarding. These flows have unit coverage; this milestone
   did not rerun all of them on a physical phone.
5. With a legitimately authorized saved briefing later, test the Listen/player path
   and real news link taps. Do not grant a trial or invent news merely to populate Home.

The staging news dataset remains empty and ingestion stays disabled. Public trial claims
remain blocked until the device-enforcement integration is available. Installation's
npm audit reports 14 vulnerabilities (11 moderate, 3 high); no unrelated forced upgrades
were attempted. The initial installer used Node 26 and emitted an engine warning;
verification used the project's supported Node 22.23.3. Expo web also reports its existing
unsupported notification-listener warning, and exports report terminal color warnings.
No production access, credential changes, account data changes, claims or deployments.
