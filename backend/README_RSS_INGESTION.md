# Nay Thit RSS ingestion

## Scope and safety

The new 23-source registry is used only by the explicit manual staging command.
The existing background ingestion, scheduler, API configuration and production
feed list are unchanged. The staging launcher continues to disable scheduled
ingestion, push delivery, provider calls and trial claims. Records use the
existing `public.news_items` table and unique `content_hash` constraint; a
staging-only RLS policy migration is still required before authenticated inserts.

The staging CLI accepts only `APP_ENV=staging` and the Supabase URL for project
`wwtntxknfjagdjdgiaxu`. It loads the isolated `backend/.env.staging`; it does not
fall back to either `.env` file. Never copy keys into a command line or report.
The RSS preparation and import clients must carry a short-lived authenticated
staging operator JWT in `RSS_IMPORT_ACCESS_TOKEN`; neither flow uses its
service-role client for `categories` or `news_items` reads or inserts. The
authenticated role still needs an explicit RLS INSERT policy for imports.
The additional `RSS_IMPORT_RLS_POLICY_VERIFIED=true` guard must be set only after
that policy has been reviewed and verified; it does not disable or bypass RLS.

## Dry run

From the repository root, run:

```sh
.venv/bin/python backend/scripts/staging_news.py --dry-run --limit-per-feed 20 --max-inserts 100 --max-age-hours 24
```

The command reads active staging categories and existing news, then fetches
bounded RSS/Atom metadata. It performs no database writes. It writes a JSON
snapshot and a Markdown source table under `backend/reports/`. The JSON stores
the exact database rows, source IDs, category mapping, limits, staging project
reference, source-registry fingerprint, creation time and one-hour expiration.
Its canonical SHA-256 digest binds all those fields and the complete row set.
New reports are created exclusively with owner read-only permissions and are
never overwritten. Feed health counters are kept in a mode-0600 local temporary
file and contain no feed bodies or credentials. Undated entries are counted in
the audit report but excluded from import proposals because their freshness
cannot be rechecked.

The human review must inspect the report and its digest. A report, file name or
run ID alone does not authorize an import. The later command requires the user
to explicitly provide the exact SHA-256 digest with `--approve-batch-sha256`.

## First staging write

Do not run write mode until the user has reviewed and explicitly approved one
specific snapshot digest. Stage B reads the snapshot and current staging
reference data; it does not fetch any RSS feed. It verifies the run ID and
digest, snapshot expiry, target project, limits, source registry, source and
category mappings, article URL allowlist, canonical URL and content fingerprints,
and publication age before attempting any insert. Any invalid or stale row
rejects the batch before writes. Changes to live feeds after preparation do not
alter the saved batch.

The importer compares approved rows with current staging news and skips existing
URL/hash or conservative near-title duplicates. It uses the existing unique
`content_hash` conflict rule to handle races and retries without replacing
existing article rows. Partial failures are reported per source with confirmed
commits and uncertain commit statuses; the command does not retry automatically.
Rerunning the same unexpired approved batch is idempotent: committed rows are
skipped and only still-missing approved rows can be attempted.

Staging inspection found RLS enabled on `public.news_items` with a SELECT policy
but no authenticated INSERT policy. Therefore imports are currently blocked by
RLS. Do not use the service-role key to work around this. A dedicated, reviewed
staging-only operator INSERT policy and a short-lived authenticated operator
session are prerequisites; no policy or schema change is included here. Until
then, an approved import attempt is expected to fail closed without inserting.

After approval, use the JSON filename and `run_id` printed in the report:

```sh
.venv/bin/python backend/scripts/staging_news.py \
  --write \
  --confirm-staging-project wwtntxknfjagdjdgiaxu \
  --approved-report backend/reports/<reviewed-report>.json \
  --confirm-approved-run-id <reviewed-run-id> \
  --approve-batch-sha256 <reviewed-batch-sha256> \
  --limit-per-feed 20 \
  --max-inserts 100 \
  --max-age-hours 24
```

The report prints this exact command without executing it. Approval expires
after one hour; a stale or modified batch is rejected, and a new dry-run is
required. The write run stores an outcome report with inserted, skipped,
rejected and failed counts. The schema and unique index already support the row
shape, but the missing staging RLS INSERT policy is a database authorization
prerequisite and must be addressed through a separately reviewed migration.

## Source and article handling

- `app/services/news/rss_registry.py` holds the 23 supplied candidates, category
  defaults, source metadata, enable/disable decisions and bounded health state.
- `app/services/news/safe_rss.py` handles RSS/Atom parsing, timeouts, redirects,
  public-address checks on every hop, response/decompression bounds, gzip,
  validators, 304 responses, retry limits and rate-limit cooldowns. A 429 stops
  in-run retries and preserves the publisher's bounded `Retry-After` delay.
- `app/services/news/rss_processing.py` normalizes publisher links, strips
  common trackers, preserves UTC/unknown publication dates and Burmese text,
  filters obvious promotional copy, classifies from title/summary plus source
  defaults, and performs conservative title matching.
- `app/services/news/manual_ingestion.py` prepares bounded dated rows and later
  imports only a verified immutable batch. The category/source-balanced cap does
  not favor the first feed group. Undated entries remain visible in dry-run
  counts but cannot enter an import snapshot.
- `app/services/news/approved_batch.py` binds the digest to exact rows and policy
  metadata, rejects non-staging/expired/tampered snapshots, and revalidates every
  row against the registry, categories, URL rules, hashes and freshness window.
- `app/routes/news.py` remains authenticated and returns the existing schema,
  ordered by publication time and then ID. Briefing selection continues to use
  the 24-hour window and now prefers no more than two items per publisher when
  multiple publishers are available.

The inspected staging categories are Myanmar, Technology, Football, Business
and World. Asia-Pacific and Legal remain secondary audit labels in the dry-run
report and are mapped to an available primary category; the current schema does
not persist secondary category labels. The current schema also has no RSS GUID
column, so GUID deduplication is source-scoped within a run. Across runs and
workers, canonical URL hashes are atomically unique; fuzzy cross-publisher
matching is deterministic in the manual reader but is not a database uniqueness
constraint. Stronger persistent GUID/near-duplicate guarantees would need a
reviewed schema migration; none is included here.

The in-process HTTP cache supports ETag/Last-Modified and 304 responses. The
manual command is one-shot, so validators are not persisted across separate CLI
processes. Publisher feeds provide metadata and excerpts only; article bodies
are not fetched or stored, and AI or audio generation is not part of ingestion.

## Verification

Unit tests use mocked feed responses and database writers. A fresh staging
dry-run is required after code changes. An explicitly approved staging import is
still required before the authenticated News API/Home/briefing path can be
verified against newly ingested rows. Physical-device acceptance is separate.
