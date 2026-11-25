# First staging Burmese audio test — preparation, 2026-11-15

Status: offline rehearsal passes. Real AI/TTS, Storage upload, trial claim and Android
playback have NOT been executed. Only staging `wwtntxknfjagdjdgiaxu` is permitted.

## Observed prerequisites

Read-only database checks for the previously identified staging test account
`e726b864-c879-4b8f-9ac1-c5cb73ae8a58` confirmed verified email, zero trials,
zero generation jobs and zero saved briefings. Existing generation RPCs and the
private `briefings` bucket were verified in the preceding audit.

After the user renewed the session in the correct worktree, the authenticated
read-only rehearsal succeeded. Current saved interests yielded 9 stories:
Technology 5, Myanmar 4, World 0. This differs from the earlier reported 14-story
selection; the runner did not change interests. Local briefing date: 2026-11-15.
Batch SHA-256: `5c794ddd6dbf01ecefaf32a5e08aec5ae89db17daa10f9eb53195e9a964362ce`.
The 6,136-character prompt entered the real pipeline with mocked providers,
entitlement, Storage and DB writes; a 3-second synthetic MP3 produced a simulated
ready record. Real entitlement remains `claim_unavailable`, can_generate=false.
Machine-readable result: `audio_rehearsal_20261115.json`.

The automatic-delivery preference proposal is NOT required for this isolated
one-shot generation. It remains required before enabling the new scheduler/reminder
behavior. No migration or scheduler activation belongs in this test.

## Configuration, server only

Existing `backend/.env.staging` supplies `SUPABASE_URL`,
`SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, and a valid account JWT in
`AUDIO_TEST_ACCESS_TOKEN` or the existing `RSS_IMPORT_ACCESS_TOKEN` (first takes
precedence). The runner verifies the JWT through staging Auth and requires the
exact test account. It does not trust decoded JWT claims for authorization.

Put provider configuration only in the ignored, owner-readable file
`backend/.env.audio-test` when ready. Never put these keys in Expo variables,
app config, command arguments, source files or chat:

```dotenv
GEMINI_API_KEY=
AZURE_SPEECH_KEY=
AZURE_SPEECH_REGION=
AZURE_SPEECH_VOICE=my-MM-NilarNeural
```

The first three are required and currently missing. Voice defaults to
`my-MM-NilarNeural`; `my-MM-ThihaNeural` is also allowed. Output is
`audio-24khz-96kbitrate-mono-mp3`, stored as `audio/mpeg`. Azure regional
availability and actual pronunciation remain unverified. SSML escapes narration;
invalid region/voice configuration is rejected before the real attempt.

The ordinary staging launcher strips AI/TTS credentials from its child environment,
even if the protected staging file contains them. It still rejects configured
Firebase/operator credentials and enabled workers. The dedicated audio runner reads only the two named staging files,
disables dotenv fallback, fixes APP_ENV to staging, and disables all worker,
ingestion, public trial-claim and push flags in its own process. It does not start
the FastAPI app. Provider credentials never go to the mobile process.

## Read-only rehearsal

From the project root:

```bash
.venv/bin/python backend/scripts/staging_operator_login.py
.venv/bin/python backend/scripts/staging_audio_test.py
```

Login prompts locally with hidden password input; no password/token belongs in
chat. Login is only needed to renew the existing session. Rehearsal defaults to
no execution: it reads the saved profile, current user-selected news, entitlement
and existing job/briefing state. It validates UUIDs, category assignment, publisher
URLs, attribution and a 24-hour freshness window.

The real selection then enters the real coordinator and MP3 pipeline with mocked
entitlement success, AI, TTS, Storage and DB RPCs. This explicitly simulated grant
never changes the real entitlement. A synthetic MP3 frame fixture exercises
Mutagen duration extraction and owner/date paths, not speech quality. No database
claim is made. Output includes category counts, local date, approval digest,
configuration names, real entitlement availability and mock results only.

## Approval needed before any real action

1. Approve a staging-account trial for this exact account. The existing supported
   operation is the service-only `public.claim_staging_account_trial(uuid)` RPC,
   invoked once by the trusted staging operator. It checks verified email,
   account availability, profile and category setup, and preserves an existing
   trial. DO NOT insert rows, change subscription statuses, enable public claims,
   or alter expiry manually. This grants **three calendar months**, not one day
   or a one-use entitlement. A shorter grant needs a separately reviewed design;
   the present database constraint does not support it. Keep
   `TRIAL_STAGING_ACCOUNT_ENABLED=false` in the API.
2. Configure provider credentials locally and confirm provider billing/resource
   limits. The app and any other processes must not request generation during
   this test. Scheduler/push/ingestion remain disabled everywhere.
3. Repeat the dry run. Approve the exact account, printed local date, batch SHA-256
   and maximum one generation attempt. Review the actual selection in the Android
   news view. If the selection changes, the approval digest must be renewed.
4. Only after explicit approval, run the following with the reviewed output:

```bash
.venv/bin/python backend/scripts/staging_audio_test.py --execute \
  --approve-project wwtntxknfjagdjdgiaxu \
  --approve-user e726b864-c879-4b8f-9ac1-c5cb73ae8a58 \
  --approve-date YYYY-MM-DD \
  --approve-batch REVIEWED_SHA256
```

This is an approval template, NOT an executable authorization for today. The
runner refuses absent entitlement, wrong approval, stale/changed news, existing
briefings/jobs or a previous local attempt marker. It reserves an exclusive
`.audio-test/<account>-<date>.attempt` marker before one coordinator invocation;
retain it even after failure. This is a local guard in addition to database
coordination, not a distributed one-use entitlement. Use one operator process.

The real run can create one job, one account/date briefing and one private audio
object, plus pending notification-outbox rows from the existing database trigger.
No push dispatch occurs. No scheduler is activated. Never turn on push to flush
these rows as part of this test.

## Usage, limits and failure handling

- At most one Gemini request to `gemini-2.5-flash` in this runner. SDK attempts=1;
  runner forces `BRIEFING_SINGLE_ATTEMPT=true`, disabling the fallback model.
- Maximum prompt: 24,000 characters. Maximum output: 4,096 tokens, thinking disabled.
- Reject blocked/truncated AI responses (completion reason must be STOP).
- Before TTS: narration must be nonempty, contain Myanmar letters and be at most
  12,000 characters. These checks do not prove factual accuracy or fluent Burmese.
- At most one Azure synthesis request; no redirect following or automatic retry.
- Validate MP3 frames/duration before upload, then finish the owned database lease.
- Existing ready jobs are reused by the service; busy/cooldown/attempt-limited jobs
  stop before providers. The runner additionally refuses ANY existing job that day.
- A timeout can still be billable. Never retry `--execute` automatically or remove
  the marker. First inspect the job/briefing state and provider usage. If upload
  succeeded but finish failed, an orphan object may remain; cleanup needs review.
- Service errors print stage/type/sanitized code only. Raw response bodies, keys,
  tokens, scripts, private signed URLs and tracebacks are suppressed by the runner.

Gemini's published standard text rate for 2.5 Flash is $0.30/1M input tokens and
$2.50/1M output tokens. 4,096 output tokens are at most $0.01024 at that rate, plus
input tokens. Character counts are not token counts. Azure Speech charges depend
on character usage, resource tier and region; verify the actual Azure resource's
price before approval. Storage/egress can also be chargeable. No exact total has
been measured. References:
- https://ai.google.dev/gemini-api/docs/pricing
- https://azure.microsoft.com/en-us/pricing/details/speech/
- https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support

## Android acceptance after the approved run

Keep the normal provider-disabled staging backend running for read/playback only.

1. Refresh Home on the signed-in account; `/today/saved` must return an owned,
   ready record with a nonempty script, positive measured duration and a signed URL.
   The date must match the saved timezone. Do not press Generate again.
2. Tap Listen: verify actual audible Burmese speech, source attribution, no repeated
   narration, sensible pacing and no invented facts against the selected stories.
3. Pause/resume, seek and change speed; check the mini-player and full player share
   the same position and recording across navigation.
4. Background/lock the phone after explicit playback; test interruption by another
   audio app or a phone call. Resume manually and verify position. Native Android
   behavior cannot be established by unit tests.
5. Test a signed-URL expiry and use the player's renewal action. It must fetch the
   selected account-owned record and preserve position without generating audio.
6. Temporarily disconnect networking to verify playback/renewal failure and retry.
   A failed signing/read request must not trigger a generation request.
7. Logout must stop playback. Another account must not load this briefing. Avoid
   sharing signed URLs or tokens in test evidence.

No-briefing, pending/generating, failed and ready UI states are covered by existing
availability tests. URL renewal, source ownership, pause while loading, native
status updates and recovery have controller tests. Physical playback remains pending.

## Verification completed

- Backend offline suite: 259 passed (13 upstream deprecation warnings).
- Frontend tests: 60 passed; TypeScript and ESLint passed.
- Read-only staging account inspection: no trial, briefing or generation job.
- Real-data dry-run: passed after session renewal, using 9 current selected stories.
  Mocked AI/TTS/Storage/DB coordination; zero external writes, paid calls or pushes.
- No device test, provider billing or real generated voice verified.
