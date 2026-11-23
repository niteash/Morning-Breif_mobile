# Nay Thit redesign handoff — 2026-11-14

This describes the current client implementation and offline checks, not device acceptance.
The written monochrome direction was available; no reference image was attached. Earlier
audit documents describe the pre-redesign UI.

## Changes and important files

| Area | Files | Behavior |
| --- | --- | --- |
| Theme / typography | `src/theme/tokens.ts`, `src/components/ui/primitives.tsx`, `assets/fonts/` | Monochrome tokens, rounded panels/pills, scalable Padauk regular/bold with fallback, keyboard-aware scroll screens and safe-area padding. Bundled fonts include OFL license. |
| Orb | `src/components/DottedOrb.tsx` | Stable native dot geometry; playing animation respects focus, foreground and reduced motion. Decorative, not measured audio amplitude. |
| Welcome / auth | `src/app/index.tsx`, `src/app/(auth)/phone-login.tsx`, `otp-verify.tsx`, `src/lib/phoneAuth.ts` | Start still checks session on tap. Real Myanmar OTP, six digits and 60-second resend protection remain. Configuration/rate/delivery errors use safe copy. |
| Onboarding | `src/app/(onboarding)/categories.tsx`, `delivery-time.tsx` | Saved selections and category route parameters retained. Selection stays local until delivery setup. Preferences save before categories; partial failure stays visible. Native picker and editable web fallback retained. |
| Auth / ownership | `src/components/AuthGate.tsx`, `src/app/(main)/_layout.tsx`, `src/features/playback/PlaybackProvider.tsx` | Existing non-anonymous auth/setup checks retained. Only profile 404 means missing setup. Account-keyed subtree owns one native player above tabs and Player. |
| Main tabs | `src/app/(main)/(tabs)/_layout.tsx`, `home.tsx`, `news.tsx`, `settings.tsx` | `/home` and `/settings` retained; `/news` added. Mini player above tabs. Truthful briefing status, explicit generation, interests and compact news on Home. News separates ranked stories from latest articles. Settings retains preferences, category editing, coordinated logout and deletion entry. |
| Player | `src/app/(main)/player.tsx`, `src/components/PlaybackControls.tsx`, `src/lib/playback.ts` | `/player`; shared play/pause, ±15 seconds, drag/accessibility seeking, 0.75–2× speed, date, matching transcript and explicit audio-link recovery. |
| Articles | `src/components/ArticleCard.tsx` | Publisher/timestamp, optional images with failure fallback, HTTP(S) external links and visible open errors. |
| Deletion | `src/app/delete-account.tsx` | Outside the profile/onboarding guard. Exact `DELETE`, pending/completed distinctions and unavailable/auth/retry states retained. |
| Read refresh / contracts | `src/hooks/useReadResource.ts`, `src/lib/readResource.ts`, `src/services/briefingApi.ts` | In-flight/recent focus reads coalesce; explicit retry bypasses cooldown. Generation response categories correctly live at the top level. |

Home/Settings moved into `(tabs)` without duplicate URL implementations. No History,
premium, bookmarks or mock data were added. The existing paywall placeholder is not linked.

## State guarantees and limits

- Ready requires ready status **and** an audio URL. Script alone is not playable. Missing
  signed URLs offer recovery, not automatic regeneration or synthetic progress.
- Generation remains explicit and uses the existing persisted/account/environment-scoped
  request coordinator. No paid automatic retry was added.
- Audio remains usable if news reads fail. Player transcript and audio come from the same
  selected saved response; generated script cannot override another recording.
- One controller/player serves mini and full controls across main navigation. Logout or
  account replacement tears down the owner; the native hook owns player release.
- Signed-query changes do not change asset identity. Same-asset refresh preserves latest
  position and play/pause intent, including pauses during fetch/load. A different asset
  requires explicit selection and resets position/transcript together.
- Stale responses after source replacement/disposal/account change are ignored. Failed
  refresh stops playback and offers recovery without exposing raw provider errors.
- The API exposes today's recording only. An expired URL for yesterday cannot be renewed
  through this contract. The client retains that selection and directs users to Home
  instead of silently substituting today's audio.
- Date/reads update on focus and foreground, with no background polling. Receipt of a
  `briefing_ready` notification refreshes saved data; taps still target `/home`. Cold-start
  and terminated-app notification behavior have not been verified on a device.
- History, offline downloads, chapters, synchronized captions and exact saved-audio/story
  associations remain unsupported.

## OTP blocker and owner setup steps

Read-only `/auth/v1/settings` checks returned HTTP 200 with phone authentication disabled
for both the configured default mobile target and guarded staging target. A management
access token does not configure SMS delivery. No remote settings were changed or SMS sent.

1. Open the **staging** project in the Supabase Dashboard.
2. Go to **Authentication → Sign In / Providers → Phone** and enable Phone sign-in.
3. Configure a supported SMS provider using that provider's account credentials. Confirm
   delivery to Myanmar `+95` numbers. Keep credentials in provider/Supabase settings;
   never put them in chat or the mobile environment.
4. Save, then follow `RUNNING.md` for the guarded staging launch. The mobile command is
   `npm run start:staging`; ordinary `npm start` uses the default environment.
5. On a device, request one real OTP, verify it, and test resend after the cooldown.
   If delivery still fails, inspect Supabase Auth and SMS-provider delivery logs.

Reference: [Supabase phone login](https://supabase.com/docs/guides/auth/phone-login).
No authentication bypass was added. Provider credentials and real delivery verification
are external prerequisites.

## Checks actually performed

- `npm run typecheck`: pass (installed Expo route generator refreshed ignored local types).
- `EXPO_NO_DOTENV=1 npm run lint`: pass.
- `npm test`: **37 pass**, including existing generation/onboarding/logout/deletion tests
  and new readiness, shared-source, refresh, pause/load races, account isolation,
  transcript consistency, recovery, timezone, deduplicated-read and OTP-privacy tests.
- Expo Android and iOS Hermes exports: pass, using dotenv-disabled dummy public endpoints
  and disabled push. Both Padauk fonts are included. Exports do not install/sign apps.
- `git diff --check`: pass.
- Scope hashes: 3,585 original snapshot files unchanged, including backend files,
  `app.json`, `eas.json`, `package.json`, `package-lock.json` and backend dependencies.
- Device inventory: no connected Android device and no booted iOS simulator. No rendered
  screenshots or native interaction/acceptance verification claimed.

## Preserved scope and remaining acceptance

Existing tracked/untracked work was preserved. No commit, reset, stash, deployment,
migration, backend service, generation, SMS send, push send or database write was run.
No environment values were changed. Application IDs, slug, scheme, EAS association,
permissions, API/storage contracts, channel ID/payload type and persistence keys remain.
Client playback metadata and notification-channel display name use Nay Thit. Native
launcher/splash branding and backend push copy remain unchanged. Existing generated
Android `RECORD_AUDIO` drift is outside this redesign.

- [ ] Native layout: Burmese shaping/clipping and native-speaker copy review, small phones,
  large text, keyboards, safe areas, TalkBack/VoiceOver and reduced motion.
- [ ] Real OTP after staging setup: success, invalid/expired code, resend and Back.
- [ ] First-time/interrupted onboarding, settings editing and partial-save failure.
- [ ] Main tabs, mini/full Player, direct links and notification taps without duplicate
  players; Android back navigation and actual native release on account/logout.
- [ ] Drag/seek/speed, buffering/interruption/headphones, background/lock-screen controls,
  renewal while paused, explicit new recording and timezone rollover.
- [ ] Image/link failures, offline/retry, missing audio, pending/failed briefing and
  deletion unavailable/reauthentication/accepted states.
- [ ] Broader release work in `RELEASE_READINESS.md` / `APPLICATION_AUDIT.md`: providers,
  deployed workers, real device/push checks, signing, store and privacy requirements.

Offline tests and bundle success are implementation evidence, not device certification.
