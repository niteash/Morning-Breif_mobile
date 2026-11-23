"""Bounded RSS preparation plus explicit immutable-batch staging import."""
import asyncio
from datetime import datetime, timedelta, timezone
import logging
import os
import re
from uuid import uuid4

from app.lib.supabase import create_supabase_client
from .approved_batch import build_approved_batch, validate_approved_batch
from .rss_processing import canonical_article_url, classify, normalize_entry, similar_story, title_fingerprint, title_specific_tokens
from .rss_registry import HEALTH, SOURCES, load_health, record_health, save_health
from .safe_rss import FeedFailure, fetch_feed, parse_feed

logger = logging.getLogger(__name__)
MAX_CONCURRENT_SOURCES = 4
MAX_STORIES_PER_SOURCE = 50
MAX_GLOBAL_STORIES = 100
MAX_EXISTING_ROWS = 5000
DEFAULT_MAX_AGE_HOURS = 24
MAX_MAX_AGE_HOURS = 168


class IngestionDiagnosticError(RuntimeError):
    """Safe, structured failure for the guarded manual ingestion workflow."""

    def __init__(self, stage: str, category: str, condition: str, *,
                 metadata: dict | None = None, error: Exception | None = None):
        super().__init__(condition)
        self.stage = stage
        self.category = category
        self.condition = condition
        self.metadata = metadata or {}
        self.error_type = type(error).__name__ if error is not None else None
        code = getattr(error, "code", None) or getattr(error, "sqlstate", None)
        self.database_error_code = code if isinstance(code, str) and re.fullmatch(r"[0-9A-Z]{5}", code) else None


def _safe_database_code(error: Exception) -> str | None:
    code = getattr(error, "code", None) or getattr(error, "sqlstate", None)
    return code if isinstance(code, str) and re.fullmatch(r"[0-9A-Z]{5}", code) else None


def select_source_balanced(candidates: list[tuple], limit: int) -> list[tuple]:
    """Select a stable round-robin slice so early registry entries do not own the cap."""
    source_order: list[str] = []
    by_source: dict[str, list[tuple]] = {}
    for candidate in candidates:
        source_id = candidate[0]["source_id"]
        if source_id not in by_source:
            source_order.append(source_id)
            by_source[source_id] = []
        by_source[source_id].append(candidate)
    selected = []
    while len(selected) < limit:
        advanced = False
        for source_id in source_order:
            rows = by_source[source_id]
            if rows:
                selected.append(rows.pop(0))
                advanced = True
                if len(selected) == limit:
                    break
        if not advanced:
            break
    return selected


def select_category_source_balanced(candidates: list[tuple], limit: int) -> list[tuple]:
    """Rotate recent articles across existing categories, then across publishers."""
    category_priority = (
        "myanmar", "football", "business", "world", "technology",
        "crypto", "psychology", "horoscope",
    )
    remaining = []
    for dated_pool in (
        [item for item in candidates if item[1]["published_at"] is not None],
        [item for item in candidates if item[1]["published_at"] is None],
    ):
        by_category: dict[str, list[tuple]] = {}
        for item in dated_pool:
            by_category.setdefault(item[1]["category_slug"], []).append(item)
        ordered_categories = [slug for slug in category_priority if slug in by_category]
        ordered_categories.extend(sorted(set(by_category) - set(ordered_categories)))
        category_queues = {
            slug: select_source_balanced(by_category[slug], len(by_category[slug]))
            for slug in ordered_categories
        }
        while len(remaining) < limit:
            advanced = False
            for slug in ordered_categories:
                if category_queues[slug]:
                    remaining.append(category_queues[slug].pop(0))
                    advanced = True
                    if len(remaining) == limit:
                        break
            if not advanced:
                break
        if len(remaining) >= limit:
            break
    return remaining


def _load_reference_data(client):
    rows = (client.table("categories").select("id,slug")
            .eq("active", True).execute().data or [])
    category_ids = {row["slug"]: row["id"] for row in rows}
    required = {
        "myanmar", "technology", "football", "business", "world",
        "crypto", "psychology", "horoscope",
    }
    if not required.issubset(category_ids):
        raise RuntimeError("Required staging news categories are unavailable")
    existing = []
    offset = 0
    while offset < MAX_EXISTING_ROWS:
        page = (client.table("news_items")
                .select("id,title,url,published_at,content_hash,title_hash,source,category_id")
                .order("created_at", desc=True).range(offset, offset + 999).execute().data or [])
        existing.extend(page)
        if len(page) < 1000:
            break
        offset += len(page)
    return category_ids, existing


async def run_manual_ingestion(*, limit_per_feed: int = 20, max_inserts: int = 100,
                               write: bool = False, retry_failed_sources: bool = False,
                               max_age_hours: int = DEFAULT_MAX_AGE_HOURS,
                               _progress: dict | None = None) -> dict:
    progress = _progress if _progress is not None else {}
    progress.update({"stage": "argument_validation", "database_write_attempted": False,
                     "rows_attempted": 0, "rows_committed": 0,
                     "write_failures": 0, "uncertain_rows": 0})
    if not 1 <= limit_per_feed <= MAX_STORIES_PER_SOURCE or not 1 <= max_inserts <= MAX_GLOBAL_STORIES:
        raise ValueError("Article limits exceed the staging safety bounds")
    if not 1 <= max_age_hours <= MAX_MAX_AGE_HOURS:
        raise ValueError("The publication window must be between 1 and 168 hours")
    if write:
        raise IngestionDiagnosticError("approval_validation", "immutable_batch_required",
                                       "live_feed_write_mode_is_disabled")
    operator_token = os.getenv("RSS_IMPORT_ACCESS_TOKEN", "").strip()
    if not operator_token:
        raise IngestionDiagnosticError("authentication_preflight", "rls_operator_authentication_required",
                                       "authenticated_operator_access_token_missing")
    rls_client = create_supabase_client(operator_token)

    run_id = str(uuid4())
    progress["run_id"] = run_id
    started = datetime.now(timezone.utc)
    load_health()
    progress["stage"] = "reference_data_read"
    try:
        category_ids, existing = await asyncio.to_thread(_load_reference_data, rls_client)
    except RuntimeError as error:
        if str(error) == "Required staging news categories are unavailable":
            raise IngestionDiagnosticError("reference_data_validation", "missing_required_categories",
                                           "required_staging_category_set_incomplete", error=error) from None
        raise IngestionDiagnosticError("reference_data_read", "database_read_failure",
                                       "staging_reference_data_query_failed", error=error) from None
    except Exception as error:
        raise IngestionDiagnosticError("reference_data_read", "database_read_failure",
                                       "staging_reference_data_query_failed", error=error) from None
    valid_slugs = set(category_ids)
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_SOURCES)
    source_results: list[dict] = []

    async def inspect_source(source):
        base = {"source_id": source.source_id, "source": source.name, "url": source.url,
                "candidate_url": source.candidate_url or source.url,
                "enabled": source.enabled, "disabled_reason": source.disabled_reason,
                "http_status": None, "parsed": 0,
                "feed_parse_result": "not_attempted", "fetch_duration_ms": None,
                "evaluated": 0, "valid": 0, "valid_recent": 0, "valid_undated": 0,
                "inserted": 0, "duplicates": 0, "rejected": 0, "rejected_uncategorized": 0,
                "eligible": 0, "proposed": 0, "valid_by_category": {},
                "valid_recent_by_category": {}, "valid_undated_by_category": {},
                "rejected_by_category": {}, "duplicate_by_category": {},
                "eligible_by_category": {}, "proposed_by_category": {},
                "failure_category": None, "database_error_code": None,
                "database_write_failures": 0, "articles": []}
        if not source.enabled:
            prior_health = HEALTH[source.source_id]
            base["http_status"] = prior_health.get("last_http_status")
            base["failure_category"] = source.disabled_reason or "disabled_by_operator"
            return base
        health = HEALTH[source.source_id]
        cooldown_active = (isinstance(health.get("retry_after_epoch"), (int, float))
                           and health["retry_after_epoch"] > started.timestamp())
        rate_limit_active = cooldown_active and health.get("last_http_status") == 429
        if cooldown_active and (not retry_failed_sources or rate_limit_active):
            base.update(http_status=health.get("last_http_status"), failure_category="source_cooldown",
                        feed_parse_result="not_retried_after_recent_failure")
            return base
        if source.primary_category not in valid_slugs and source.primary_category not in {"asia_pacific", "legal"}:
            base["failure_category"] = "category_unavailable"
            return base
        retry_after_seconds = None
        async with semaphore:
            try:
                fetched = await asyncio.to_thread(fetch_feed, source)
                base["http_status"] = fetched.status
                base["fetch_duration_ms"] = fetched.elapsed_ms
                parsed = await asyncio.to_thread(parse_feed, fetched.body, source)
                base["parsed"] = len(parsed)
                base["feed_parse_result"] = "ok"
                base["evaluated"] = len(parsed[:limit_per_feed])
                record_health(source.source_id, attempted=datetime.now(timezone.utc),
                              http_status=fetched.status, failure_category=None, parsed=len(parsed))
                return {**base, "articles": parsed[:limit_per_feed]}
            except FeedFailure as error:
                base["http_status"] = error.status
                base["failure_category"] = error.category
                base["feed_parse_result"] = "failed"
                retry_after_seconds = error.retry_after_seconds
            except Exception as error:
                # Error messages can contain request details or provider text.
                base["failure_category"] = "internal_" + type(error).__name__.lower()
                base["feed_parse_result"] = "failed"
            record_health(source.source_id, attempted=datetime.now(timezone.utc),
                          http_status=base["http_status"], failure_category=base["failure_category"],
                          retry_after_seconds=retry_after_seconds)
            return base

    progress["stage"] = "feed_fetch_and_validation"
    source_results = list(await asyncio.gather(*(inspect_source(source) for source in SOURCES)))
    now = datetime.now(timezone.utc)
    candidates = []
    staged_seen: list[dict] = []
    existing_urls = {canonical_article_url(row["url"]) for row in existing if row.get("url")}
    existing_urls.discard(None)
    existing_hashes = {row.get("content_hash") for row in existing if row.get("content_hash")}
    staged_urls: set[str] = set()
    staged_hashes: set[str] = set()
    existing_titles: dict[str, list[dict]] = {}
    existing_by_specific_token: dict[str, list[dict]] = {}
    for row in existing:
        if row.get("title"):
            # Preserve legacy and URL-only title hashes during transition.
            existing_titles.setdefault(title_fingerprint(row["title"]), []).append(row)
            for token in title_specific_tokens(row["title"]):
                existing_by_specific_token.setdefault(token, []).append(row)
    guids_seen: set[tuple[str, str]] = set()
    max_age = timedelta(hours=max_age_hours)

    for result in source_results:
        source = next(item for item in SOURCES if item.source_id == result["source_id"])
        for raw in result.pop("articles", []):
            article = normalize_entry(raw, source, valid_slugs, now)
            if not article:
                result["rejected"] += 1
                rejected_category, _ = classify(raw, source, valid_slugs)
                if rejected_category:
                    result["rejected_by_category"][rejected_category] = result["rejected_by_category"].get(rejected_category, 0) + 1
                else:
                    result["rejected_uncategorized"] += 1
                continue
            published = datetime.fromisoformat(article["published_at"]) if article["published_at"] else None
            if published is not None and now - published > max_age:
                result["rejected"] += 1
                result["rejected_by_category"][article["category_slug"]] = result["rejected_by_category"].get(article["category_slug"], 0) + 1
                continue
            result["valid"] += 1
            category = article["category_slug"]
            if published is None:
                result["valid_undated"] += 1
                result["valid_undated_by_category"][category] = result["valid_undated_by_category"].get(category, 0) + 1
            else:
                result["valid_recent"] += 1
                result["valid_recent_by_category"][category] = result["valid_recent_by_category"].get(category, 0) + 1
            result["valid_by_category"][category] = result["valid_by_category"].get(category, 0) + 1
            # Unknown publication times remain visible in the audit totals, but
            # cannot satisfy the freshness policy required for an approved import.
            if published is None:
                continue
            guid = raw.get("guid")
            guid_key = (source.source_id, guid) if guid else None
            possible_existing = {id(row): row for row in existing_titles.get(article["title_hash"], [])}
            for token in title_specific_tokens(article["title"]):
                for row in existing_by_specific_token.get(token, []):
                    possible_existing[id(row)] = row
            if (article["url"] in existing_urls or article["content_hash"] in existing_hashes
                    or article["url"] in staged_urls or article["content_hash"] in staged_hashes
                    or (guid_key and guid_key in guids_seen)
                    or any(similar_story(article, old) for old in possible_existing.values())
                    or any(similar_story(article, old) for old in staged_seen)):
                result["duplicates"] += 1
                result["duplicate_by_category"][category] = result["duplicate_by_category"].get(category, 0) + 1
                continue
            if guid_key:
                guids_seen.add(guid_key)
            staged_urls.add(article["url"])
            staged_hashes.add(article["content_hash"])
            staged_seen.append(article)
            result["eligible"] += 1
            result["eligible_by_category"][category] = result["eligible_by_category"].get(category, 0) + 1
            row = {"category_id": category_ids[article["category_slug"]],
                   "source": article["source"], "title": article["title"],
                   "description": article["description"], "url": article["url"],
                   "image_url": article["image_url"], "author": article["author"],
                   "published_at": article["published_at"], "content_hash": article["content_hash"],
                   "title_hash": article["title_hash"]}
            candidates.append((result, article, row))

    proposed = select_category_source_balanced(candidates, max_inserts)
    for result, article, _ in proposed:
        result["proposed"] += 1
        category = article["category_slug"]
        result["proposed_by_category"][category] = result["proposed_by_category"].get(category, 0) + 1
    proposed_metadata = [{"source": article["source"], "title": article["title"],
                          "description": article["description"], "url": article["url"],
                          "author": article["author"], "image_url": article["image_url"],
                          "published_at": article["published_at"],
                          "publication_date_unknown": article["publication_date_unknown"],
                          "category": article["category_slug"], "category_id": row["category_id"],
                          "topic_group": article["topic_group"], "language": article["language"],
                          "content_hash": row["content_hash"], "title_hash": row["title_hash"]}
                         for _, article, row in proposed]
    for result in source_results:
        if result["feed_parse_result"] == "ok":
            record_health(result["source_id"], attempted=datetime.now(timezone.utc),
                          http_status=result["http_status"], failure_category=None,
                          parsed=result["parsed"], inserted=result["inserted"],
                          duplicates=result["duplicates"], rejected=result["rejected"])

    totals = {key: sum(item[key] for item in source_results)
              for key in ("parsed", "evaluated", "valid", "valid_recent", "valid_undated",
                          "inserted", "duplicates", "rejected", "rejected_uncategorized",
                          "eligible", "proposed")}
    category_counts = {slug: {
        "valid": sum(item["valid_by_category"].get(slug, 0) for item in source_results),
        "valid_recent": sum(item["valid_recent_by_category"].get(slug, 0) for item in source_results),
        "valid_undated": sum(item["valid_undated_by_category"].get(slug, 0) for item in source_results),
        "rejected": sum(item["rejected_by_category"].get(slug, 0) for item in source_results),
        "duplicates": sum(item["duplicate_by_category"].get(slug, 0) for item in source_results),
        "eligible": sum(item["eligible_by_category"].get(slug, 0) for item in source_results),
        "proposed": sum(item["proposed_by_category"].get(slug, 0) for item in source_results),
    } for slug in sorted(valid_slugs)}
    progress["stage"] = "report_generation"
    batch_rows = [{"source_id": result["source_id"],
                   "category_slug": article["category_slug"],
                   "topic_group": article["topic_group"],
                   "language": article["language"],
                   "publication_date_unknown": article["publication_date_unknown"],
                   "row": row}
                  for result, article, row in proposed]
    limits = {"per_source": limit_per_feed, "global": max_inserts,
              "max_age_hours": max_age_hours}
    approved_batch, batch_sha256 = build_approved_batch(run_id=run_id, rows=batch_rows, limits=limits)
    progress["stage"] = "dry_run_complete"
    summary = {"run_id": run_id, "environment": "staging", "dry_run": not write,
               "total_sources": len(SOURCES), "successful_sources": sum(x["failure_category"] is None for x in source_results),
               "failed_or_disabled_sources": sum(x["failure_category"] is not None for x in source_results),
               "limits": limits,
               "created_at": approved_batch["created_at"],
               "expires_at": approved_batch["expires_at"],
               "batch_sha256": batch_sha256,
               "approved_batch": approved_batch,
               "total_runtime_ms": round((datetime.now(timezone.utc)-started).total_seconds()*1000),
               "totals": {**totals, "over_global_limit": max(0, len(candidates) - len(proposed))},
               "database_write": {
                   "attempted": False,
                   "rows_attempted": progress["rows_attempted"],
                   "rows_committed": progress["rows_committed"],
                   "write_failures": progress["write_failures"],
                   "rows_with_unknown_commit_status": progress["uncertain_rows"],
               },
               "existing_rows_read": len(existing),
               "existing_rows_read_capped": len(existing) >= MAX_EXISTING_ROWS,
               "proposed": proposed_metadata,
               "category_counts": category_counts,
               "category_mapping_counts": {slug: category_counts[slug]["proposed"] for slug in sorted(valid_slugs)},
               "sources": [{**{key: value for key, value in result.items() if key != "articles"},
                            **{key: HEALTH[result["source_id"]][key] for key in
                               ("last_attempt", "last_success", "last_http_status")}}
                           for result in source_results]}
    logger.info("RSS preparation complete: run_id=%s sources=%s succeeded=%s parsed=%s valid=%s duplicates=%s proposed=%s",
                run_id, len(SOURCES), summary["successful_sources"], totals["parsed"], totals["valid"],
                totals["duplicates"], len(proposed))
    progress["stage"] = "health_state_persist"
    save_health()
    progress["stage"] = "complete"
    return summary


async def import_approved_batch(*, batch: dict, expected_digest: str, expected_run_id: str,
                                confirmed_project_ref: str, limits: dict,
                                _progress: dict | None = None) -> dict:
    """Insert only rows in a verified snapshot; this path never fetches RSS feeds."""
    progress = _progress if _progress is not None else {}
    progress.update({"stage": "approval_validation", "database_write_attempted": False,
                     "rows_attempted": 0, "rows_committed": 0,
                     "write_failures": 0, "uncertain_rows": 0})
    if os.getenv("MANUAL_INGESTION_WRITE", "false").lower() != "true":
        raise IngestionDiagnosticError("environment_guard", "write_guard_rejected",
                                       "single_run_write_enablement_missing")
    if (os.getenv("APP_ENV") != "staging"
            or os.getenv("SUPABASE_URL", "").rstrip("/") != "https://wwtntxknfjagdjdgiaxu.supabase.co"):
        raise IngestionDiagnosticError("environment_guard", "wrong_staging_target",
                                       "only_authorized_staging_project_is_allowed")
    if confirmed_project_ref != "wwtntxknfjagdjdgiaxu":
        raise IngestionDiagnosticError("environment_guard", "wrong_staging_target",
                                       "explicit_project_confirmation_is_not_staging")
    operator_token = os.getenv("RSS_IMPORT_ACCESS_TOKEN", "").strip()
    if not operator_token:
        raise IngestionDiagnosticError("authentication_preflight", "rls_operator_authentication_required",
                                       "authenticated_operator_access_token_missing")
    if os.getenv("RSS_IMPORT_RLS_POLICY_VERIFIED", "false").lower() != "true":
        raise IngestionDiagnosticError("authorization_preflight", "staging_rls_insert_policy_not_verified",
                                       "staging_operator_insert_policy_must_be_reviewed_and_verified")
    try:
        # Digest, project, run, time, limits and registry checks that do not
        # require remote state run before the first database query.
        if not isinstance(batch, dict) or batch.get("project_ref") != "wwtntxknfjagdjdgiaxu":
            raise IngestionDiagnosticError("approval_validation", "wrong_project",
                                           "batch_is_not_bound_to_authorized_staging_project")
        if batch.get("run_id") != expected_run_id:
            raise IngestionDiagnosticError("approval_validation", "approved_run_id_mismatch",
                                           "confirmation_id_does_not_match_batch")
        if batch.get("limits") != limits:
            raise IngestionDiagnosticError("approval_validation", "approved_limits_mismatch",
                                           "confirmation_limits_do_not_match_batch")
    except IngestionDiagnosticError:
        raise

    # Use the authenticated JWT for category/news reads and inserts. The
    # service-role key is never used by the RSS preparation/import path.
    rls_writer = create_supabase_client(operator_token)

    progress["stage"] = "reference_data_read"
    try:
        category_ids, existing = await asyncio.to_thread(_load_reference_data, rls_writer)
    except Exception as error:
        raise IngestionDiagnosticError("reference_data_read", "database_read_failure",
                                       "staging_reference_data_query_failed", error=error) from None
    if len(existing) >= MAX_EXISTING_ROWS:
        raise IngestionDiagnosticError("duplicate_preflight", "existing_rows_scan_capped",
                                       "complete_duplicate_preflight_unavailable")
    progress["stage"] = "approval_policy_validation"
    try:
        approved_rows = validate_approved_batch(
            batch, expected_run_id=expected_run_id, expected_digest=expected_digest,
            confirmed_project_ref=confirmed_project_ref, expected_limits=limits,
            category_ids=category_ids,
        )
    except Exception as error:
        # The CLI handles safe structured validation errors. Preserve only the
        # category/condition, never arbitrary error text from a snapshot.
        if hasattr(error, "category") and hasattr(error, "condition"):
            raise IngestionDiagnosticError("approval_policy_validation", error.category,
                                           error.condition, metadata={"rejected_rows": getattr(error, "rejected_rows", 0)}) from None
        raise IngestionDiagnosticError("approval_policy_validation", "snapshot_validation_failed",
                                       "approved_rows_failed_policy_validation") from None

    existing_urls = {canonical_article_url(row.get("url") or "") for row in existing}
    existing_urls.discard(None)
    existing_hashes = {row.get("content_hash") for row in existing if row.get("content_hash")}
    existing_titles: dict[str, list[dict]] = {}
    existing_by_specific_token: dict[str, list[dict]] = {}
    for row in existing:
        if row.get("title"):
            existing_titles.setdefault(title_fingerprint(row["title"]), []).append(row)
            for token in title_specific_tokens(row["title"]):
                existing_by_specific_token.setdefault(token, []).append(row)

    source_results: dict[str, dict] = {}
    category_results: dict[str, dict] = {}
    insert_rows = []
    for item in approved_rows:
        row, article = item["row"], item["article"]
        source_result = source_results.setdefault(item["source_id"], {
            "source_id": item["source_id"], "source": row["source"],
            "category": item["category_slug"], "inserted": 0, "skipped": 0,
            "rejected": 0, "failed": 0, "rows_attempted": 0,
        })
        category_result = category_results.setdefault(item["category_slug"], {
            "inserted": 0, "skipped": 0, "rejected": 0, "failed": 0,
        })
        possible_existing = {id(old): old for old in existing_titles.get(title_fingerprint(row["title"]), [])}
        for token in title_specific_tokens(row["title"]):
            for old in existing_by_specific_token.get(token, []):
                possible_existing[id(old)] = old
        duplicate = (row["url"] in existing_urls or row["content_hash"] in existing_hashes
                     or any(similar_story(article, old) for old in possible_existing.values()))
        if duplicate:
            source_result["skipped"] += 1
            category_result["skipped"] += 1
        else:
            insert_rows.append((source_result, category_result, row))

    progress["stage"] = "database_write"
    # All operations in this flow use the publishable key with the authenticated
    # operator's JWT, so staging table RLS is enforced on reads and writes.
    for source_result, category_result, row in insert_rows:
        progress["database_write_attempted"] = True
        progress["rows_attempted"] += 1
        source_result["rows_attempted"] += 1
        try:
            response = await asyncio.to_thread(lambda: rls_writer.table("news_items")
                .upsert(row, on_conflict="content_hash", ignore_duplicates=True).execute())
            if response.data:
                progress["rows_committed"] += 1
                source_result["inserted"] += 1
                category_result["inserted"] += 1
            else:
                # A concurrent approved batch may have inserted the same hash.
                source_result["skipped"] += 1
                category_result["skipped"] += 1
        except Exception as error:
            progress["write_failures"] += 1
            progress["uncertain_rows"] += 1
            source_result["failed"] += 1
            category_result["failed"] += 1
            source_result.setdefault("database_error_codes", []).append(_safe_database_code(error))
            logger.error("RSS approved batch row failed: run_id=%s source_id=%s error_type=%s db_code=%s",
                         expected_run_id, source_result["source_id"], type(error).__name__,
                         _safe_database_code(error) or "unavailable")

    totals = {key: sum(item[key] for item in source_results.values())
              for key in ("inserted", "skipped", "rejected", "failed", "rows_attempted")}
    return {
        "run_id": str(uuid4()), "approved_run_id": expected_run_id,
        "environment": "staging", "dry_run": False,
        "batch_sha256": expected_digest,
        "totals": totals,
        "database_write": {
            "attempted": progress["database_write_attempted"],
            "rows_attempted": progress["rows_attempted"],
            "rows_committed": progress["rows_committed"],
            "write_failures": progress["write_failures"],
            "rows_with_unknown_commit_status": progress["uncertain_rows"],
        },
        "sources": list(source_results.values()),
        "category_counts": category_results,
    }
