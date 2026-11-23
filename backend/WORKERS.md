# Background jobs

All three jobs default to disabled. No live worker was enabled during development.
The ordinary backend `.env` still targets the protected source project. Use an explicitly
selected staging runtime for acceptance; do not enable jobs against that default file.

## Configuration

| Setting | Default | Behavior when enabled |
| --- | --- | --- |
| `NEWS_INGESTION_ENABLED` | `false` | Fetch the reviewed feeds in `app/services/news/sources.py` on startup, then periodically |
| `NEWS_INGESTION_INTERVAL_MINUTES` | `30` | Interval between ingestion batches; must be 5–1440 minutes |
| `PUSH_DELIVERY_ENABLED` | `false` | Retry persisted device notifications every minute; requires Firebase and the outbox migration |
| `SCHEDULER_ENABLED` | `false` | Check due users every minute and generate their daily briefings |
| `RETENTION_WORKER_ENABLED` | `false` | Remove terminal queue, notification, billing-event and failed-deletion records once per day |

The scheduler now opens a bounded generation window 30 minutes before each saved local
delivery time and allows catch-up during that same local date (up to 24 hours). It uses the scheduled
instant's local date, including deliveries just after midnight. The proposed
`delivery_schedule` profile column supports `daily` or `weekdays`; deploy the reviewed
schema proposal and set `AUTOMATIC_BRIEFING_PREFERENCES_ENABLED=true` before turning on
the worker. This flag also guards push delivery and preference writes; it defaults false.
Generation still uses durable DB claims
and fails closed for inactive or expired entitlements. The worker remains disabled by
default.

Ingestion is independent of briefing generation and needs staging Supabase runtime keys,
category seeds and network access to the reviewed feeds. Generation additionally needs
approved Gemini/Azure configuration; device notifications need Firebase credentials.
Enabling ingestion does not grant users operator API access. That still requires
`INGESTION_OPERATOR_IDS` and authenticated operator requests.

The current APScheduler lifecycle is attached to FastAPI. Deploy **one dedicated process**
with one Uvicorn worker and only its intended jobs enabled. Leave all three enable flags false in all
other API processes. Do not use `--reload` for a deployed worker. A separately supervised
worker deployment and monitoring are still required; this change does not deploy one.

The local staging launcher and hosted smoke runner intentionally force periodic ingestion
and delivery/push off. They reject an enabled ingestion flag in the staging file. No private
files need changing to run the offline tests.

## Work limits and recovery

- Profile scans select only scheduling fields, ordered by `id`, in pages of at most 100.
  An `id > previous_id` cursor avoids offset shifts when earlier rows are deleted. A short
  page does not end the scan; only an empty page does. New users inserted behind the cursor
  will be picked up on the next tick.
- Four delivery tasks consume a queue of at most eight profiles. The current page also
  remains in memory. Workers recheck the same-day two-hour delivery window after queueing.
  Scan failures drain already queued work and allow a later tick to rescan. Database
  generation claims still enforce ownership, cooldown and daily attempt limits.
- Scan logs report profiles scanned, queued, attempted, expired, task errors and whether
  the scan completed. Attempts are not successful deliveries: generation can defer, skip
  or fail internally. Use generation logs and database state to confirm actual results.
- Ingestion uses four feed tasks concurrently. A failed feed does not stop the rest.
  Totals include successful writes from partially failed feeds. `failed_feeds` and
  `skipped_insert_failure` must be monitored; HTTP 200 alone is not ingestion success.
- APScheduler coalesces missed ticks and allows only one execution of each job per process.
  The batch guard prevents overlapping normal API/timer batches in the same process;
  overlap returns HTTP 409 to the batch API. It is not a distributed lease. Single-feed
  operator requests are not covered by this batch guard.
- Cancellation does not forcibly stop an already running synchronous SDK/feed request.
  A deployment must allow in-flight requests to finish during shutdown. Cross-process
  ingestion coordination and atomic title-deduplication constraints remain work.

## Acceptance still required

Offline tests cover 1,150 profiles through a simulated 37-row API cap, deletion between
pages, scan failures, expiry while queued, feed partial failures, overlap, concurrency and
real APScheduler startup with substituted feed work. Equivalent cursor SQL ran read-only
on staging's empty profiles table. This is not a live SDK load or news-quality test.

Before enabling routine staging delivery, validate current feeds, article relevance and
publisher attribution; run approved real AI/TTS generation; measure queue time and cost;
verify catch-up after restart and physical-device delivery. At high volume, four workers
may not finish within the same-day preparation/catch-up window, so measure capacity before increasing usage.

Notification delivery records/retries and invalid-token cleanup are now implemented and
verified at the service/database layer. Bounded queue retention is implemented; alerts,
real FCM and deployed-worker acceptance remain unfinished. RSS ingestion now uses a
database lease in addition to the process-local guard, so only one API/worker instance
can run a feed batch at a time.

Scheduling options follow the [APScheduler 3.x guide](https://apscheduler.readthedocs.io/en/3.x/userguide.html).
Cursor requests use Supabase's [ordering](https://supabase.com/docs/reference/python/order)
and [greater-than filter](https://supabase.com/docs/reference/python/gt).


## Durable push delivery

Apply `20261109024013_durable_notification_delivery.sql` before deploying this backend.
It is already applied to staging. Each ready briefing save atomically queues active Android
devices belonging to that user. The same briefing/device queues once, including manual
regeneration. Devices registered after completion are not automatically backfilled.

This describes the currently applied staging migration. It queues active Android devices
as soon as a briefing is ready; it does not support user opt-out or delayed delivery.
`backend/schema_proposals/automatic_briefing_preferences.sql` proposes opt-in reminders,
local-time queueing and weekday delivery. Do not enable push delivery for the new product
behavior until that proposal is reviewed and applied to a non-production target. No
notification sends or database changes were made for this proposal.

The independent push job claims at most 20 records per tick, using four workers with
one in-flight claim each. Each claim lasts five minutes and has a unique lease token.
Transient failures retry after 1, 2, 4 and 8 minutes; five attempts or 24 hours ends the
job. Missing Firebase configuration consumes no attempts. Queue expiry also bounds FCM
message TTL. Unregistered tokens are deactivated; credential/payload/sender errors retry
without deactivating a possibly valid token. Pending deliveries for logged-out or
reassigned devices are cancelled when claimed.

FCM acceptance is not proof of device receipt. An acknowledgement lost after acceptance
may cause a duplicate send; stable notification IDs/Android tags reduce duplicates but
cannot promise exactly-once display or sound. A send already in flight can race logout.
Inspect queue states/attempts using trusted server access; client access is denied.
Terminal rows are removed by the bounded service-only retention job after the configured period.

Firebase Admin 7.7 still accepts `Message.token` but emits a deprecation warning; its new
`fid` field expects a Firebase installation ID, not the FCM token returned by the current
Expo client. Native identifier compatibility must be verified before release. See the
[Firebase message reference](https://firebase.google.com/docs/reference/admin/python/firebase_admin.messaging#message).
Do not relabel existing tokens as installation IDs to silence the warning.

## Account cleanup worker — 2026-11-13

Apply both account-deletion migrations before deploying this backend. Even with deletion
requests disabled, authenticated API calls now require `account_is_active`. Deploy a
separate worker with `ACCOUNT_DELETION_WORKER_ENABLED=true`, then enable
`ACCOUNT_DELETION_ENABLED=true` on the API only after checking its health and alerting.
Neither flag enables generation, RSS or push. Guarded staging launchers force both off;
the opt-in smoke runner enables requests only in its isolated ASGI process.

An accepted request immediately blocks API/RLS activity, stops device registrations,
deactivates devices and removes pending pushes. A push already handed to FCM or a signed
URL already issued cannot be recalled; audio cleanup removes its underlying object.
Cleanup waits 15 minutes for normal in-flight work, then claims a five-minute renewable
lease. Each minute the worker handles at most four jobs sequentially. One attempt removes
at most 2,000 objects in 100-object Storage API batches. Only `briefings/<user UUID>/...`
is eligible. Never delete Storage metadata directly. Auth deletion follows audio cleanup,
then a second sweep and database verification clear the job. The job survives Auth deletion
so crashes can recover. Retries wait five minutes and stop at 20 attempts, retaining a
`failed` marker which continues denying account access. Never remove a marker to retry.

Before enabling requests, monitor pending/processing/failed counts and oldest request age;
alert on failures and stalled leases. For a failed job, first inspect the cause without
logging tokens or full provider responses, repair the service/storage issue, and arrange a
reviewed operator retry preserving user_id/requested_at. The operator-only
`POST /api/v1/operations/recovery/retry` endpoint now requeues bounded retryable failures
without accepting user IDs. Alert deployment remains external. Objects owned in other buckets intentionally
block Auth deletion rather than being deleted indiscriminately.

Successful regeneration now removes the superseded audio object after the new database
commit. Ambiguous uploads whose process crashes during completion still require a
storage inventory reconciliation run; deleting them immediately could remove an object
whose database commit succeeded but response was lost. Provider backup retention and
already downloaded audio are outside this worker's erasure guarantees. Complete policy
and operational handling before calling deletion production ready.


## Normal staging provider isolation — 2026-11-15

`run_staging.py` now permits AI/TTS values to remain in the protected staging
file, but always blanks GEMINI_API_KEY and all AZURE_SPEECH settings in the
backend child. Expo receives none of these settings. Dotenv fallback is disabled.
The file is never rewritten. Existing Firebase/operator and enabled-worker
rejections remain in effect; unknown launch modes fail closed.

Normal LAN backend command (from repository root):
`.venv/bin/python backend/scripts/run_staging.py backend --host 0.0.0.0 --port 8000`

AI testing remains separate: `backend/scripts/staging_audio_test.py` reads provider
credentials only from the ignored `backend/.env.audio-test`. Its default is a
read-only/mock rehearsal. Real execution requires explicit account/date/batch
approval and an existing entitlement; it never starts a scheduler or grants access.
See `backend/reports/AUDIO_TEST_READINESS.md` for the bounded execution command.
