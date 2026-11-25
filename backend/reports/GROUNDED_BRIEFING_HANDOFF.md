# Grounded personalized briefing handoff — 2026-11-15

## Implemented locally

The existing account/date lease, entitlement gate, private MP3 pipeline, timezone scheduler, signed URL renewal, and playback controller remain the execution path. No second generator was added.

`BRIEFING_SOURCES_ENABLED=true` selects structured Gemini JSON. Validation rejects unknown article IDs, category mismatches, absent/unsafe original URLs, absent attribution, malformed sections, and invalid/oversized Burmese scripts. Narration is assembled from validated sections. Source metadata records title, sections, category IDs, original publisher snapshots, local briefing date and generation timestamp. ID validation establishes traceability, not factual truth; Burmese editorial/audio quality still needs human review.

The source-aware coordinator checks the new schema capability RPC before claims/provider work and completes audio plus metadata through one transaction using the existing lease. Saved-today and historical-detail endpoints include source metadata only when enabled. Historical references do not depend on live news rows. A proposed trigger clears old references if a legacy regeneration changes the script.

The existing player now uses the shared reduced-motion-aware sunrise orb, source title, transcript and original publisher cards; existing seek/speed/mini-player/background mechanics remain. Home uses the same orb and a secondary manual recovery action. No fake waveform or timing metadata was added.

Manual and scheduled selection use publisher-balanced cluster leaders; up to three overlapping reports accompany each leader. `BRIEFING_STORIES_PER_CATEGORY` defaults to 5 and permits 1–10. Existing freshness/relevance/ranking applies; the scheduler also excludes future publications. The controlled audio runner retains its explicit 5-story bound. Supporting reports are included in the approval digest and freshness checks. Any previous digest must be replaced by a fresh reviewed rehearsal.

## Approval boundary — nothing activated

Review-only SQL:
1. `backend/schema_proposals/briefing_sources.sql`: nullable JSON metadata on existing owner-scoped briefings, metadata constraint, capability RPC, service-only atomic completion wrapper, stale-reference trigger. Legacy records retain NULL metadata. Existing trial/subscription data is untouched.
2. `backend/schema_proposals/automatic_briefing_preferences.sql`: existing separate proposal for notification opt-in, delivery schedule and foreground playback preferences. Required before enabling corresponding preference features or live reminder dispatch.

Neither proposal has been applied or tested against PostgreSQL in this work. No database connection, provider request, claim, push, worker, secret-file modification or deployment was performed. Existing staging trial is reported active by the user; this work neither rechecks nor grants it.

Before any approved migration: verify exact staging project `wwtntxknfjagdjdgiaxu`; inspect fresh schema/function signatures, briefing RLS and grants, existing constraints/triggers and dependency versions; make and verify a recoverable schema backup. Review SQL and use an isolated transactional migration test first. Confirm anon/authenticated cannot execute completion/capability RPCs, another user cannot read source metadata, and a failed metadata update rolls back both ready status and notification queue. Test stale leases, legacy records, regenerated scripts, and transcript/source equality. Do not query production.

Rollback: first disable source-aware generation and stop the separately authorized worker. Export source metadata before any removal. Leave the nullable column/data in place for a nondestructive application rollback. If later approved, drop `clear_stale_briefing_sources` trigger then its function, the completion/capability functions, and finally constraint/column only after preserving metadata. Do not delete audio, change trials or alter subscription status.

## Controlled verification after explicit approval

Apply only reviewed staging proposals, verify grants/RLS/atomicity, then explicitly enable source metadata for the staging API and controlled test environment. Preserve normal staging's provider stripping. Run `backend/scripts/staging_audio_test.py` in default mocked/read-only mode first; inspect configuration, current trial, current local date and refreshed batch SHA-256. Approve exactly one account/date/digest and one provider attempt separately. Do not reuse an earlier approval digest. Never activate scheduler or live push as a side effect of this test.

The real test must verify MP3 decoding, one owner-scoped storage object, one ready saved record, matching transcript/references, signed URL renewal, history, and foreign-account denial. Only then separately approve recurring generation and push activation, including spend/retry limits and the notification preference migration.

## Android checks still required

Play/pause, seek, speed, progress, navigation/mini-player, interruption/resumption, screen-off behavior, signed URL expiry, logout/account switching, historical references, publisher links, Burmese wrapping/font scaling, reduced-motion mode, and notification deep links. Native performance and Burmese voice quality are not verified by unit tests.
