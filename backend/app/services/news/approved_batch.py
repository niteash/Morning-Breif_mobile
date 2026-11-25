"""Integrity and policy checks for explicitly approved staging RSS snapshots."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import re
from pathlib import Path
import stat
from urllib.parse import urlsplit
import uuid

from .rss_processing import (
    article_url_allowed,
    classify,
    normalize_entry,
    similar_story,
)
from .rss_registry import SOURCES

STAGING_PROJECT_REF = "wwtntxknfjagdjdgiaxu"
BATCH_SCHEMA_VERSION = 2
BATCH_TTL = timedelta(hours=1)
MAX_BATCH_FILE_BYTES = 4 * 1024 * 1024
MAX_PER_SOURCE = 50
MAX_GLOBAL_ROWS = 100
MAX_AGE_HOURS = 168
DATABASE_ROW_FIELDS = frozenset({
    "category_id", "source", "title", "description", "url", "image_url",
    "author", "published_at", "content_hash", "title_hash",
})
APPROVED_ROW_FIELDS = frozenset({
    "source_id", "category_slug", "topic_group", "language", "publication_date_unknown", "row",
})


class ApprovedBatchError(ValueError):
    def __init__(self, category: str, condition: str, *, rejected_rows: int = 0):
        super().__init__(condition)
        self.category = category
        self.condition = condition
        self.rejected_rows = rejected_rows


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def batch_digest(batch: dict) -> str:
    """Hash all approval-bound data using deterministic canonical JSON."""
    return hashlib.sha256(_canonical_bytes(batch)).hexdigest()


def source_registry_digest(sources=None) -> str:
    registry = []
    sources = SOURCES if sources is None else sources
    for source in sorted(sources, key=lambda item: item.source_id):
        registry.append({
            "source_id": source.source_id,
            "name": source.name,
            "url": source.url,
            "publisher_domain": source.publisher_domain,
            "article_domains": list(getattr(source, "article_domains", ())),
            "external_article_urls": bool(getattr(source, "external_article_urls", False)),
            "primary_category": source.primary_category,
            "secondary_categories": list(source.secondary_categories),
            "language": source.language,
            "geographic_relevance": source.geographic_relevance,
            "enabled": source.enabled,
        })
    return hashlib.sha256(_canonical_bytes(registry)).hexdigest()


def build_approved_batch(*, run_id: str, rows: list[dict], limits: dict,
                         created_at: datetime | None = None) -> tuple[dict, str]:
    created = created_at or datetime.now(timezone.utc)
    if created.tzinfo is None:
        raise ValueError("Batch creation time must include a timezone")
    created = created.astimezone(timezone.utc).replace(microsecond=0)
    batch = {
        "schema_version": BATCH_SCHEMA_VERSION,
        "environment": "staging",
        "project_ref": STAGING_PROJECT_REF,
        "database_read_role": "authenticated_operator",
        "run_id": str(uuid.UUID(run_id)),
        "created_at": created.isoformat(),
        "expires_at": (created + BATCH_TTL).isoformat(),
        "limits": limits,
        "source_registry_sha256": source_registry_digest(),
        "rows": rows,
    }
    return batch, batch_digest(batch)


def proposal_projection(rows: list[dict]) -> list[dict]:
    """Human review projection; importer uses the exact row nested in each item."""
    projected = []
    for item in rows:
        row = item["row"]
        projected.append({
            "source": row["source"],
            "title": row["title"],
            "description": row["description"],
            "url": row["url"],
            "author": row["author"],
            "image_url": row["image_url"],
            "published_at": row["published_at"],
            "publication_date_unknown": item["publication_date_unknown"],
            "category": item["category_slug"],
            "category_id": row["category_id"],
            "topic_group": item["topic_group"],
            "language": item["language"],
            "content_hash": row["content_hash"],
            "title_hash": row["title_hash"],
        })
    return projected


def resolve_report_path(path_text: str | Path, reports_dir: Path) -> Path:
    reports = reports_dir.resolve(strict=True)
    path = Path(path_text)
    if not path.is_absolute():
        path = Path.cwd() / path
    try:
        mode = path.lstat().st_mode
    except OSError:
        raise ApprovedBatchError("approved_report_invalid", "report_file_unavailable") from None
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise ApprovedBatchError("approved_report_invalid", "report_must_be_regular_non_symlink_file")
    resolved = path.resolve(strict=True)
    if resolved.parent != reports or resolved.suffix.lower() != ".json":
        raise ApprovedBatchError("approved_report_invalid", "report_must_be_json_directly_under_reports")
    if resolved.stat().st_size > MAX_BATCH_FILE_BYTES:
        raise ApprovedBatchError("approved_report_invalid", "report_exceeds_size_limit")
    return resolved


def read_approved_report(path_text: str | Path, reports_dir: Path, *,
                         expected_run_id: str, expected_digest: str,
                         expected_limits: dict) -> tuple[dict, dict]:
    path = resolve_report_path(path_text, reports_dir)
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as report_file:
            metadata = os.fstat(report_file.fileno())
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_BATCH_FILE_BYTES:
                raise ApprovedBatchError("approved_report_invalid", "report_file_type_or_size_changed")
            raw_report = report_file.read(MAX_BATCH_FILE_BYTES + 1)
        if len(raw_report) > MAX_BATCH_FILE_BYTES:
            raise ApprovedBatchError("approved_report_invalid", "report_exceeds_size_limit")
        report = json.loads(raw_report.decode("utf-8"))
    except ApprovedBatchError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ApprovedBatchError("approved_report_invalid", "report_is_not_valid_json") from None
    if not isinstance(report, dict):
        raise ApprovedBatchError("approved_report_invalid", "report_root_must_be_object")
    batch = report.get("approved_batch")
    stated_digest = report.get("batch_sha256")
    if not isinstance(batch, dict) or not isinstance(stated_digest, str):
        raise ApprovedBatchError("approved_batch_missing", "report_has_no_immutable_approved_batch")
    if batch.get("schema_version") != BATCH_SCHEMA_VERSION:
        raise ApprovedBatchError("approved_batch_invalid", "unsupported_batch_schema")
    if batch.get("database_read_role") != "authenticated_operator":
        raise ApprovedBatchError("approved_batch_invalid", "preflight_must_use_authenticated_rls_role")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_digest or ""):
        raise ApprovedBatchError("approved_digest_invalid", "explicit_sha256_approval_is_required")
    try:
        computed_digest = batch_digest(batch)
    except (TypeError, ValueError, UnicodeError):
        raise ApprovedBatchError("approved_batch_invalid", "batch_is_not_canonical_json") from None
    if computed_digest != stated_digest or computed_digest != expected_digest:
        raise ApprovedBatchError("approved_digest_mismatch", "batch_digest_does_not_match_explicit_approval")
    if report.get("environment") != "staging" or report.get("dry_run") is not True:
        raise ApprovedBatchError("approved_report_invalid", "only_staging_dry_run_reports_are_importable")
    if report.get("total_sources") != len(SOURCES):
        raise ApprovedBatchError("approved_report_invalid", "source_registry_count_does_not_match")
    if report.get("run_id") != batch.get("run_id") or report.get("run_id") != expected_run_id:
        raise ApprovedBatchError("approved_run_id_mismatch", "confirmation_id_does_not_match_batch")
    if report.get("limits") != expected_limits or batch.get("limits") != expected_limits:
        raise ApprovedBatchError("approved_limits_mismatch", "confirmation_limits_do_not_match_batch")
    try:
        projection = proposal_projection(batch.get("rows", []))
    except (KeyError, TypeError):
        raise ApprovedBatchError("approved_batch_invalid", "stored_review_projection_is_malformed") from None
    if report.get("proposed") != projection:
        raise ApprovedBatchError("approved_report_modified", "review_projection_does_not_match_approved_rows")
    db_write = report.get("database_write")
    totals = report.get("totals")
    if (not isinstance(db_write, dict) or db_write.get("attempted") is not False
            or not isinstance(totals, dict) or totals.get("inserted") != 0):
        raise ApprovedBatchError("approved_report_invalid", "preparation_report_must_prove_zero_writes")
    return report, batch


def _parse_utc(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def validate_approved_batch(batch: dict, *, expected_run_id: str, expected_digest: str,
                            confirmed_project_ref: str, expected_limits: dict,
                            category_ids: dict[str, str], now: datetime | None = None) -> list[dict]:
    """Validate the complete immutable snapshot before the first database write."""
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if batch_digest(batch) != expected_digest:
        raise ApprovedBatchError("approved_digest_mismatch", "batch_digest_changed_before_import")
    required = {"schema_version", "environment", "project_ref", "database_read_role", "run_id", "created_at",
                "expires_at", "limits", "source_registry_sha256", "rows"}
    if set(batch) != required or batch.get("schema_version") != BATCH_SCHEMA_VERSION:
        raise ApprovedBatchError("approved_batch_invalid", "unsupported_batch_schema")
    if batch.get("environment") != "staging" or batch.get("project_ref") != STAGING_PROJECT_REF:
        raise ApprovedBatchError("wrong_project", "batch_is_not_bound_to_the_authorized_staging_project")
    if batch.get("database_read_role") != "authenticated_operator":
        raise ApprovedBatchError("approved_batch_invalid", "preflight_must_use_authenticated_rls_role")
    if confirmed_project_ref != STAGING_PROJECT_REF:
        raise ApprovedBatchError("wrong_project", "explicit_project_confirmation_is_not_staging")
    try:
        run_id = str(uuid.UUID(batch.get("run_id", "")))
        approved_run_id = str(uuid.UUID(expected_run_id))
    except (ValueError, TypeError, AttributeError):
        raise ApprovedBatchError("approved_run_id_invalid", "run_id_must_be_a_uuid") from None
    if run_id != approved_run_id:
        raise ApprovedBatchError("approved_run_id_mismatch", "confirmation_id_does_not_match_batch")
    if batch.get("limits") != expected_limits:
        raise ApprovedBatchError("approved_limits_mismatch", "confirmation_limits_do_not_match_batch")
    limits = batch.get("limits")
    if (not isinstance(limits, dict)
            or type(limits.get("per_source")) is not int or not 1 <= limits["per_source"] <= MAX_PER_SOURCE
            or type(limits.get("global")) is not int or not 1 <= limits["global"] <= MAX_GLOBAL_ROWS
            or type(limits.get("max_age_hours")) is not int or not 1 <= limits["max_age_hours"] <= MAX_AGE_HOURS):
        raise ApprovedBatchError("approved_limits_invalid", "limits_exceed_staging_safety_bounds")
    created = _parse_utc(batch.get("created_at"))
    expires = _parse_utc(batch.get("expires_at"))
    if not created or not expires or expires <= created or expires - created > BATCH_TTL:
        raise ApprovedBatchError("approved_batch_invalid", "batch_expiration_window_is_invalid")
    if created > current + timedelta(minutes=5):
        raise ApprovedBatchError("approved_batch_invalid", "batch_creation_time_is_in_the_future")
    if expires <= current:
        raise ApprovedBatchError("approved_batch_expired", "approval_snapshot_has_expired")
    if batch.get("source_registry_sha256") != source_registry_digest():
        raise ApprovedBatchError("source_registry_changed", "current_source_allowlist_differs_from_snapshot")
    rows = batch.get("rows")
    if (not isinstance(rows, list) or not rows
            or len(rows) > expected_limits.get("global", 0)):
        raise ApprovedBatchError("approved_batch_invalid", "row_count_is_empty_or_exceeds_global_limit",
                                 rejected_rows=len(rows) if isinstance(rows, list) else 0)

    sources = {source.source_id: source for source in SOURCES}
    slugs = set(category_ids)
    seen_urls: set[str] = set()
    seen_hashes: set[str] = set()
    source_counts: dict[str, int] = {}
    normalized_rows = []
    seen_articles: list[dict] = []
    rejected = 0
    for item in rows:
        if not isinstance(item, dict) or set(item) != APPROVED_ROW_FIELDS:
            rejected += 1
            continue
        source = sources.get(item.get("source_id"))
        row = item.get("row")
        if not source or not source.enabled or not isinstance(row, dict) or set(row) != DATABASE_ROW_FIELDS:
            rejected += 1
            continue
        source_counts[item["source_id"]] = source_counts.get(item["source_id"], 0) + 1
        if source_counts[item["source_id"]] > limits["per_source"]:
            rejected += 1
            continue
        if (item.get("publication_date_unknown") is not False
                or item.get("category_slug") not in slugs
                or row.get("category_id") != category_ids.get(item.get("category_slug"))
                or row.get("source") != source.name):
            rejected += 1
            continue
        title, description = row.get("title"), row.get("description")
        if (not isinstance(title, str) or not title.strip() or len(title) > 500
                or (description is not None and (not isinstance(description, str) or len(description) > 20_000))
                or (row.get("author") is not None and (not isinstance(row["author"], str) or len(row["author"]) > 1000))):
            rejected += 1
            continue
        url = row.get("url")
        if not isinstance(url, str) or not article_url_allowed(url, source):
            rejected += 1
            continue
        published = _parse_utc(row.get("published_at"))
        if not published or published > current + timedelta(minutes=10):
            rejected += 1
            continue
        if (current - published).total_seconds() > expected_limits.get("max_age_hours", 0) * 3600:
            rejected += 1
            continue
        normalized = normalize_entry({
            "title": title, "description": description, "url": url,
            "author": row.get("author"), "image_url": row.get("image_url"),
            "published_raw": published.isoformat(),
        }, source, slugs, current)
        topic_group = classify({"title": title, "description": description}, source, slugs)[1]
        language = ("my" if any("\u1000" <= char <= "\u109f" for char in title + (description or ""))
                    else source.language)
        expected_row = ({
            "category_id": category_ids[item["category_slug"]], "source": source.name,
            "title": normalized["title"], "description": normalized["description"],
            "url": normalized["url"], "image_url": normalized["image_url"],
            "author": normalized["author"], "published_at": normalized["published_at"],
            "content_hash": normalized["content_hash"], "title_hash": normalized["title_hash"],
        } if normalized else None)
        if (not expected_row or expected_row != row
                or normalized["category_slug"] != item["category_slug"]
                or topic_group != item.get("topic_group") or language != item.get("language")):
            rejected += 1
            continue
        if url in seen_urls or row["content_hash"] in seen_hashes:
            rejected += 1
            continue
        article = {"title": title, "description": description, "published_at": published.isoformat()}
        if any(similar_story(article, old) for old in seen_articles):
            rejected += 1
            continue
        seen_urls.add(url)
        seen_hashes.add(row["content_hash"])
        seen_articles.append(article)
        normalized_rows.append({"source_id": source.source_id, "category_slug": item["category_slug"],
                                "row": row, "article": article})
    if rejected:
        raise ApprovedBatchError("approved_rows_rejected", "one_or_more_snapshot_rows_failed_policy_validation",
                                 rejected_rows=rejected)
    return normalized_rows
