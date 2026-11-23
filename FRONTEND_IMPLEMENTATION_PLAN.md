# Nay Thit frontend implementation and staging acceptance

## Phase 1: discover and save news

- [x] Preserve personalized `/api/v1/news`; add bounded, authenticated search and article detail.
- [x] Extend the existing News screen with category discovery, debounced search, paging, skeletons, retry, and saved-article navigation.
- [x] Add article detail with metadata, short publisher-provided summary, attribution, and validated publisher link.
- [x] Add per-account bookmark endpoints using caller JWT and RLS. The table/policies are a local proposal only; the screen reports an error until staging schema is approved and installed.
- [x] Make Home loading/error states clearer and keep reduced-motion behavior.
- [x] Add route, paging, and authorization tests.

Files: `backend/app/routes/news.py`, `backend/app/routes/bookmarks.py`, `backend/app/main.py`, `backend/schema_proposals/bookmarks.sql`, `src/services/newsApi.ts`, `src/services/categoryApi.ts`, `src/app/(main)/(tabs)/news.tsx`, `src/app/(main)/article/[id].tsx`, `src/app/(main)/saved-articles.tsx`, `src/components/ArticleCard.tsx`, `src/lib/pagedResource.ts`.

## Phase 2: listen, history, and offline audio

- [x] Add paginated, caller-owned briefing history with a fresh signed URL only after ownership and storage-path checks.
- [x] Renew URLs for the selected historical briefing while retaining its identity and playback position.
- [x] Show actual playback progress as fixed ticks; do not fabricate waveform amplitudes or transcript timestamps.
- [x] Add private account-scoped downloads, five-file/40 MiB/7-day limits, temporary-file validation, and logout cleanup.
- [ ] Verify downloads, background playback, lock-screen controls, and interruption recovery on Android and iOS. No device was connected at this check.
- [ ] Cold offline launch remains unavailable: existing AuthGate requires session/profile/onboarding network validation. Downloaded audio can be played during an authenticated session without fetching a new audio URL.

Files: `backend/app/routes/briefings.py`, `src/services/briefingApi.ts`, `src/lib/playback.ts`, `src/features/playback/PlaybackProvider.tsx`, `src/app/(main)/history.tsx`, `src/app/(main)/downloads.tsx`, `src/services/offlineAudioStorage.ts`, `src/lib/offlineAudio.ts`, `src/components/AudioProgressVisual.tsx`.

## Phase 3: preferences and polish

- [x] Persist Burmese/English and light/dark choices on device; use palette-aware shared controls.
- [x] Translate app-owned copy from an explicit dictionary. Publisher articles and generated transcripts bypass translation.
- [x] Show OS notification permission separately from server delivery status. A settings button requests permission only after the user taps it.
- [x] Show authoritative entitlement status and expiry; reject malformed or contradictory responses. No UI-side trial grant or purchase was added.
- [x] Add existing-account email/password settings actions and retain delivery-time, categories, logout, and account deletion.
- [ ] Review all English copy and contrast with Burmese/English screen readers and large font scaling on actual devices.

## Why staging Home and News may still be empty

A successful HTTP response with `news: []` means the API query ran but found no rows for that user/category/time window. It does not mean generation failed. The staging RSS pipeline is manual, and its background scheduler is intentionally disabled. The previously approved write attempt failed; a new immutable dry-run batch/report must be reviewed and explicitly approved before importing. Do not reuse a stale report or bypass its hash/freshness checks.

Safe order:

1. Keep the backend pointed only at the staging project. Run its existing manual RSS dry-run and inspect feed health, recent eligible rows, deduplication, and exact proposed inserts. Dry-run must report zero writes.
2. If the report is current, check the exact staging project and obtain approval for that immutable report and its bounded write command. If stale, create a fresh report and request approval for that new batch. The previous report approval does not cover changed stories.
3. After an approved import, verify nonzero staging `news_items` rows and GET `/api/v1/news`, `/api/v1/news/discover`, and `/api/v1/briefings/today` for the signed-in staging user. Confirm selected category IDs match existing categories.
4. Only then test `POST /api/v1/briefings/generate`. It also needs a configured TTS/AI provider and authoritative `can_generate: true`. Do not invoke a paid provider without explicit approval. The existing GET today/story endpoint does not generate audio.
5. Verify `/api/v1/briefings/today/saved` returns `status: ready` and a renewed signed URL. Then test playback on a device.

Do not add sample/fabricated stories, widen RLS, grant a trial, or enable scheduled ingestion to hide an empty staging database. Bookmark endpoints also require the unapplied `article_bookmarks` schema proposal.

## Validation

Latest local checks: `npm run typecheck`, `npm run lint`, `npm test` (57 passed), and `.venv/bin/python -m pytest backend/tests -q` (217 passed). These are local tests only. No live staging RSS write, paid generation call, migration, deployment, or device verification was performed in this phase.
