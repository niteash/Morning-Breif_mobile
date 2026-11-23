# Staging auth transport and empty news investigation — 2026-11-15

Target: `wwtntxknfjagdjdgiaxu` only. No production access, article insertion,
schema mutation, scheduling, AI/TTS call, or trial grant was performed.

## Confirmed evidence and limits

- Supplied logs identify `ReadError` inside `get_verified_user`. The only network
  operation in that try block is `admin_supabase.auth.get_user(token)`.
- Installed supabase-auth 2.31.0 resolves this to `GET /auth/v1/user`, through a
  shared synchronous HTTPX client with HTTP/2 enabled. HTTPX supplies its default
  per-operation timeout (5 seconds). Home starts several independent resources.
  Before this fix each request made its own remote Auth call, without retry.
- `ReadError` is a network receive failure, distinct from `ReadTimeout` and
  `PoolTimeout`. It does not establish which host/network component broke the
  connection. No matching local file log or live authenticated reproduction was
  available. Disabling HTTP/2 or rebuilding pools is not justified by this evidence.
- `token_expiry=valid` is an unverified diagnostic only. Supabase still verifies
  the actual JWT. No decoding result authorizes a request.
- Fresh staging catalog/count queries returned 0 news rows, 0 rows within 24h,
  newest timestamp NULL, 0 saved briefings, and only an authenticated SELECT
  policy on `public.news_items`. No authenticated INSERT policy exists.
- The News endpoint applies selected category IDs and returns `{news: [...]}`;
  `src/services/newsApi.ts` and Home consume that same shape. Empty DB explains
  the empty screen; no confirmed frontend mapping defect was found.

## Applied auth fix

`backend/app/dependencies/auth.py` now shares only verification already in flight
for the same exact token (SHA-256 map key, never logged). Completed results are
removed immediately. Different tokens never share an identity. At most 32 token
verifications can be in flight per event loop. Request cancellation does not cancel
other waiters. One retry with 50–150ms jitter is allowed for transient network,
remote-protocol and network-timeout exceptions on the read-only Auth GET.
Credential rejection, pool exhaustion, rate limits and arbitrary provider errors
are not retried. Persistent transport failures remain 503; invalid credentials
remain 401 (unauthorized credentials remain 403).

Each request still runs `account_is_active` after successful verification. RLS,
entitlement checks and the existing provider verification remain intact. There
is no success cache and no acceptance of unverified tokens. Local JWKS-only
verification was considered but not introduced: it would require an explicit
revocation/deleted-account security design and is not a small transport fix.
This preserves existing protections; it does not promise stronger immediate
access-token invalidation on sign-out than Supabase currently provides.

## RSS state and prerequisites

The immutable importer already exists. It validates saved rows, project, digest,
run ID, source registry, category IDs, URL policy, age and limits without refetching
feeds during import. New reports use schema v2. The latest local report is schema
v1 (`rss_staging_dry_run_20261114T214248Z_6bfad763-bbd4-40ef-b81e-e0b2dc6d753a.json`)
and cannot be used, even though its expiry had not elapsed at inspection time.

The fresh guarded dry-run stopped at `authentication_preflight` because
`RSS_IMPORT_ACCESS_TOKEN` is missing from ignored `backend/.env.staging`.
It attempted 0 writes and committed 0 rows; it did not generate a new report.
Do not reuse the old report, recompute its digest, or fabricate a new approval.

### Proposed RLS policy — review only, NOT APPLIED

A separate dedicated staging operator account needs an admin-controlled claim
`app_metadata.rss_ingestion_operator=true` and a fresh authenticated access token.
Never use user-editable `user_metadata` for this permission. Selecting that account
and granting its claim require approval; no account was changed here.

Proposed policy SQL, to be packaged as a migration only after fresh preflight:

```sql
CREATE POLICY staging_rss_operator_insert ON public.news_items
FOR INSERT TO authenticated
WITH CHECK (
  (SELECT auth.jwt()) -> 'app_metadata' ->> 'rss_ingestion_operator' = 'true'
  AND COALESCE((SELECT auth.jwt()) ->> 'is_anonymous', 'false') = 'false'
);
```

Preflight must confirm exact staging identity, existing grants/RLS/policies,
unique content_hash constraint, and absence of a conflicting policy name. The
policy grants INSERT only; no UPDATE/DELETE, existing row change or trial grant.
An operator token can insert directly while its claim remains authorized, so
keep the account dedicated and the permission temporary. Removing the claim
alone does not remove it from an already-issued JWT until refresh/expiry.
Rollback is `DROP POLICY staging_rss_operator_insert ON public.news_items;` and
revocation of the operator claim. Rollback does not delete imported articles.
Before article import, verify ordinary/anonymous users cannot insert and the
operator can insert in a separately approved transaction-rollback test.

After policy verification, configure only locally in the ignored staging env:
`RSS_IMPORT_ACCESS_TOKEN` and `RSS_IMPORT_RLS_POLICY_VERIFIED=true`. Never paste
JWTs in chat, command arguments, reports, or source control. The policy flag
is an operator assertion; database RLS remains the actual enforcement.

Then prepare a new batch:

```sh
.venv/bin/python backend/scripts/staging_news.py --dry-run --limit-per-feed 20 --max-inserts 100 --max-age-hours 24
```

That command will print the exact proposed write command with the new report,
run ID and digest. A separate explicit approval of that batch is still required.
There is no valid exact write command for the currently available report.

## Voice path

RSS insertion → selected category stories within 24h → `generate_and_save`
entitlement gate → durable generation claim → Gemini Burmese script → Azure
Burmese TTS → measured single MP3 → private `briefings` storage upload → completed
DB briefing → signed URL from saved endpoint → PlaybackProvider / native player.

Current blockers are empty articles; absent Gemini/Azure keys in isolated staging;
and account-specific generation entitlement, which must independently allow
`can_generate`. Public/staging claims and scheduling remain disabled. The extra
read-only trial-count query was not executed because automatic approval review
hit its usage limit, so no new live account entitlement assertion is made here.
Signed URL renewal and playback have existing code/tests, but real generated
staging audio and Android playback were not exercised in this task.

## Validation and device check

- Final full backend suite: 209 passed (13 upstream deprecation warnings).
- Final focused auth suite: 14 passed, including those additional identity-isolation
  and capacity-limit cases. ReadError retry, outage, concurrency, cancellation,
  invalid/expired JWT and per-request account checks are covered with mocks.
- npm typecheck, lint and all 44 mobile tests passed.
- Python compilation and git diff whitespace checks passed.
- Fresh staging dry-run correctly failed before work due missing operator JWT.

Restart the existing staging backend to load the auth change (stop the current
process first to free port 8000):

```sh
.venv/bin/python backend/scripts/run_staging.py backend --host 0.0.0.0 --port 8000
```

On the signed-in Android phone, refresh Home repeatedly, then background/resume
and logout/login. Check request IDs and status codes; successful transient recovery
should show one Authentication retry followed by HTTP 200. Persistent outages must
still return 503 and rejected credentials 401/403. Do not share bearer tokens.
The network incident has only been reproduced through fault-injected tests;
live resolution has not been claimed.
