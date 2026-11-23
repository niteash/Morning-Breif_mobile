"""Immutable staging batch integrity, policy, retry and idempotency tests."""
import asyncio
from datetime import datetime, timedelta, timezone
import json
import threading
from types import SimpleNamespace
from unittest.mock import Mock
import uuid

import pytest

from app.services.news import approved_batch, manual_ingestion
from app.services.news.approved_batch import (
    ApprovedBatchError,
    batch_digest,
    build_approved_batch,
    proposal_projection,
    read_approved_report,
    validate_approved_batch,
)
from app.services.news.rss_registry import SOURCES
from app.services.news.rss_processing import normalize_entry

NOW = datetime.now(timezone.utc).replace(microsecond=0)
LIMITS = {"per_source": 20, "global": 100, "max_age_hours": 24}
CATEGORIES = {"technology": "cat-tech", "business": "cat-business", "football": "cat-football",
              "myanmar": "cat-myanmar", "world": "cat-world"}
TECH = next(source for source in SOURCES if source.source_id == "techcrunch")


def make_item(*, url="https://techcrunch.com/story", title="OpenAI unveils a new AI technology system",
              published_at=None):
    published_at = published_at or NOW.isoformat()
    normalized = normalize_entry({
        "title": title, "description": "The technology company announced an AI product.",
        "url": url, "published_raw": published_at, "author": "Reporter", "image_url": None,
    }, TECH, set(CATEGORIES), NOW)
    assert normalized
    row = {
        "category_id": CATEGORIES[normalized["category_slug"]],
        "source": normalized["source"], "title": normalized["title"],
        "description": "The technology company announced an AI product.",
        "url": normalized["url"], "image_url": normalized["image_url"],
        "author": normalized["author"], "published_at": normalized["published_at"],
        "content_hash": normalized["content_hash"], "title_hash": normalized["title_hash"],
    }
    return {
        "source_id": TECH.source_id, "category_slug": normalized["category_slug"],
        "topic_group": normalized["topic_group"], "language": normalized["language"],
        "publication_date_unknown": False, "row": row,
    }


def make_report(rows=None, *, created_at=None, limits=None):
    rows = rows if rows is not None else [make_item()]
    limits = limits or dict(LIMITS)
    run_id = str(uuid.uuid4())
    batch, digest = build_approved_batch(run_id=run_id, rows=rows, limits=limits,
                                        created_at=created_at or NOW)
    report = {
        "environment": "staging", "dry_run": True, "total_sources": len(SOURCES),
        "run_id": run_id, "limits": limits, "totals": {"inserted": 0},
        "database_write": {"attempted": False, "rows_attempted": 0, "rows_committed": 0},
        "proposed": proposal_projection(rows), "approved_batch": batch,
        "batch_sha256": digest,
    }
    return report


def batch_from(report):
    return report["approved_batch"], report["batch_sha256"]


def test_canonical_batch_digest_is_stable_and_binds_every_exact_row_field():
    report = make_report()
    batch, digest = batch_from(report)
    reordered = dict(reversed(list(batch.items())))
    assert batch_digest(reordered) == digest
    modified = json.loads(json.dumps(batch))
    modified["rows"][0]["row"]["description"] += " changed"
    assert batch_digest(modified) != digest


def test_report_approval_requires_the_independently_confirmed_digest_and_run_id(tmp_path):
    report = make_report()
    path = tmp_path / "approved.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    loaded, batch = read_approved_report(path, tmp_path, expected_run_id=report["run_id"],
        expected_digest=report["batch_sha256"], expected_limits=LIMITS)
    assert loaded["run_id"] == batch["run_id"]
    with pytest.raises(ApprovedBatchError, match="batch_digest_does_not_match_explicit_approval"):
        read_approved_report(path, tmp_path, expected_run_id=report["run_id"],
            expected_digest="0" * 64, expected_limits=LIMITS)
    with pytest.raises(ApprovedBatchError, match="confirmation_id_does_not_match_batch"):
        read_approved_report(path, tmp_path, expected_run_id=str(uuid.uuid4()),
            expected_digest=report["batch_sha256"], expected_limits=LIMITS)


def test_service_role_preflight_snapshot_is_not_approvable(tmp_path):
    report = make_report()
    report["approved_batch"]["schema_version"] = 1
    report["approved_batch"].pop("database_read_role")
    report["batch_sha256"] = batch_digest(report["approved_batch"])
    path = tmp_path / "old-service-role-report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ApprovedBatchError, match="unsupported_batch_schema"):
        read_approved_report(path, tmp_path, expected_run_id=report["run_id"],
            expected_digest=report["batch_sha256"], expected_limits=LIMITS)


def test_cli_import_uses_only_saved_batch_and_requires_explicit_digest(tmp_path, monkeypatch, capsys):
    from app.services.news import cli
    report = make_report()
    path = tmp_path / "approved.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    monkeypatch.setattr(cli, "REPORTS_DIR", tmp_path)
    for key, value in {
        "APP_ENV": "staging", "SUPABASE_URL": cli.STAGING_URL,
        "GEMINI_API_KEY": "", "AZURE_SPEECH_KEY": "", "FIREBASE_SERVICE_ACCOUNT_PATH": "",
        "INGESTION_OPERATOR_IDS": "", "SCHEDULER_ENABLED": "false", "NEWS_INGESTION_ENABLED": "false",
        "PUSH_DELIVERY_ENABLED": "false", "ACCOUNT_DELETION_ENABLED": "false",
        "ACCOUNT_DELETION_WORKER_ENABLED": "false", "TRIAL_STAGING_ACCOUNT_ENABLED": "false",
        "MANUAL_INGESTION_WRITE": "true",
    }.items():
        monkeypatch.setenv(key, value)
    captured = {}
    async def importer(**kwargs):
        captured.update(kwargs)
        return {
            "run_id": str(uuid.uuid4()), "approved_run_id": report["run_id"],
            "environment": "staging", "dry_run": False, "batch_sha256": report["batch_sha256"],
            "totals": {"inserted": 1, "skipped": 0, "rejected": 0, "failed": 0},
            "database_write": {"attempted": True, "rows_attempted": 1, "rows_committed": 1,
                                "write_failures": 0, "rows_with_unknown_commit_status": 0},
            "sources": [], "category_counts": {},
        }
    monkeypatch.setattr(cli, "import_approved_batch", importer)
    monkeypatch.setattr(cli, "run_manual_ingestion", Mock(side_effect=AssertionError("write must not fetch feeds")))
    assert cli.main([
        "--environment", "staging", "--write", "--confirm-staging-project", cli.STAGING_REF,
        "--approved-report", str(path), "--confirm-approved-run-id", report["run_id"],
        "--approve-batch-sha256", report["batch_sha256"],
    ]) == 0
    assert captured["batch"] == report["approved_batch"]
    assert captured["expected_digest"] == report["batch_sha256"]
    assert capsys.readouterr().out.startswith("{")


def test_rehashing_a_modified_snapshot_does_not_reuse_the_user_approved_digest(tmp_path):
    report = make_report()
    approved_digest = report["batch_sha256"]
    report["approved_batch"]["rows"][0]["row"]["title"] = "modified headline"
    report["batch_sha256"] = batch_digest(report["approved_batch"])
    report["proposed"] = proposal_projection(report["approved_batch"]["rows"])
    path = tmp_path / "changed.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ApprovedBatchError, match="batch_digest_does_not_match_explicit_approval"):
        read_approved_report(path, tmp_path, expected_run_id=report["run_id"],
            expected_digest=approved_digest, expected_limits=LIMITS)


def test_paths_are_restricted_to_regular_json_files_directly_under_reports(tmp_path):
    report = make_report()
    path = tmp_path / "batch.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    outside = tmp_path.parent / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    with pytest.raises(ApprovedBatchError):
        read_approved_report(outside, tmp_path, expected_run_id=report["run_id"],
            expected_digest=report["batch_sha256"], expected_limits=LIMITS)
    link = tmp_path / "link.json"
    link.symlink_to(path)
    with pytest.raises(ApprovedBatchError):
        read_approved_report(link, tmp_path, expected_run_id=report["run_id"],
            expected_digest=report["batch_sha256"], expected_limits=LIMITS)


@pytest.mark.parametrize("mutation,category", [
    (lambda b: b.update(project_ref="kobsywjfynjvhcarbqxo"), "wrong_project"),
    (lambda b: b.update(rows=[]), "approved_batch_invalid"),
    (lambda b: b["rows"][0].update(source_id="unregistered"), "approved_rows_rejected"),
    (lambda b: b["rows"][0].update(category_slug="unsupported"), "approved_rows_rejected"),
    (lambda b: b["rows"][0]["row"].update(url="https://outside.example/story"), "approved_rows_rejected"),
    (lambda b: b["rows"][0]["row"].update(content_hash="0" * 64), "approved_rows_rejected"),
    (lambda b: b["rows"][0]["row"].update(published_at=(NOW-timedelta(hours=25)).isoformat()), "approved_rows_rejected"),
])
def test_policy_rejects_wrong_target_source_category_url_hash_and_stale_publication(mutation, category):
    report = make_report()
    batch, digest = batch_from(report)
    changed = json.loads(json.dumps(batch))
    mutation(changed)
    digest = batch_digest(changed)
    with pytest.raises(ApprovedBatchError) as failure:
        validate_approved_batch(changed, expected_run_id=changed["run_id"], expected_digest=digest,
            confirmed_project_ref=approved_batch.STAGING_PROJECT_REF, expected_limits=LIMITS,
            category_ids=CATEGORIES, now=NOW)
    assert failure.value.category == category


def test_expired_batch_and_modified_source_registry_fail_closed(monkeypatch):
    created = NOW - timedelta(hours=2)
    report = make_report(created_at=created)
    batch, digest = batch_from(report)
    with pytest.raises(ApprovedBatchError, match="approval_snapshot_has_expired"):
        validate_approved_batch(batch, expected_run_id=batch["run_id"], expected_digest=digest,
            confirmed_project_ref=approved_batch.STAGING_PROJECT_REF, expected_limits=LIMITS,
            category_ids=CATEGORIES, now=NOW)
    fresh = make_report()
    batch, digest = batch_from(fresh)
    monkeypatch.setattr(approved_batch, "SOURCES", SOURCES[:-1])
    with pytest.raises(ApprovedBatchError, match="current_source_allowlist_differs_from_snapshot"):
        validate_approved_batch(batch, expected_run_id=batch["run_id"], expected_digest=digest,
            confirmed_project_ref=approved_batch.STAGING_PROJECT_REF, expected_limits=LIMITS,
            category_ids=CATEGORIES, now=NOW)


def test_internal_duplicate_and_per_feed_over_limit_are_rejected_before_writes():
    duplicate_report = make_report([make_item(), make_item()])
    batch, digest = batch_from(duplicate_report)
    with pytest.raises(ApprovedBatchError, match="one_or_more_snapshot_rows_failed_policy_validation"):
        validate_approved_batch(batch, expected_run_id=batch["run_id"], expected_digest=digest,
            confirmed_project_ref=approved_batch.STAGING_PROJECT_REF, expected_limits=LIMITS,
            category_ids=CATEGORIES, now=NOW)
    narrow_limits = {"per_source": 1, "global": 100, "max_age_hours": 24}
    over_limit = make_report([make_item(url="https://techcrunch.com/one"),
                              make_item(url="https://techcrunch.com/two")], limits=narrow_limits)
    batch, digest = batch_from(over_limit)
    with pytest.raises(ApprovedBatchError):
        validate_approved_batch(batch, expected_run_id=batch["run_id"], expected_digest=digest,
            confirmed_project_ref=approved_batch.STAGING_PROJECT_REF, expected_limits=narrow_limits,
            category_ids=CATEGORIES, now=NOW)


class AtomicFakeDB:
    def __init__(self):
        self.saved = {}
        self.calls = 0
        self.lock = threading.Lock()
        self.fail_on_call = None

    def table(self, _name):
        return self

    def upsert(self, row, *, on_conflict, ignore_duplicates):
        assert on_conflict == "content_hash" and ignore_duplicates is True
        return FakeInsert(self, row)


class FakeInsert:
    def __init__(self, db, row):
        self.db, self.row = db, row

    def execute(self):
        with self.db.lock:
            self.db.calls += 1
            if self.db.calls == self.db.fail_on_call:
                error = RuntimeError("dsn=password=fixture"); error.code = "08006"
                raise error
            key = self.row["content_hash"]
            if key in self.db.saved:
                return SimpleNamespace(data=[])
            self.db.saved[key] = self.row
            return SimpleNamespace(data=[{"id": "fixture"}])


def configure_import(monkeypatch, db, existing=None):
    monkeypatch.setenv("MANUAL_INGESTION_WRITE", "true")
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("SUPABASE_URL", "https://wwtntxknfjagdjdgiaxu.supabase.co")
    monkeypatch.setenv("RSS_IMPORT_ACCESS_TOKEN", "fixture-authenticated-operator-jwt")
    monkeypatch.setenv("RSS_IMPORT_RLS_POLICY_VERIFIED", "true")
    monkeypatch.setattr(manual_ingestion, "_load_reference_data",
                        lambda _client: (CATEGORIES, list(existing if existing is not None else db.saved.values())))
    monkeypatch.setattr(manual_ingestion, "create_supabase_client",
                        lambda token: db if token == "fixture-authenticated-operator-jwt" else None)


def run_import(report, *, project=approved_batch.STAGING_PROJECT_REF, run_id=None):
    batch, digest = batch_from(report)
    return asyncio.run(manual_ingestion.import_approved_batch(
        batch=batch, expected_digest=digest, expected_run_id=run_id or report["run_id"],
        confirmed_project_ref=project, limits=report["limits"],
    ))


def test_import_never_refetches_live_rss_and_writes_only_snapshot_rows(monkeypatch):
    report = make_report()
    db = AtomicFakeDB()
    configure_import(monkeypatch, db)
    monkeypatch.setattr(manual_ingestion, "fetch_feed", Mock(side_effect=AssertionError("no RSS fetch in import")))
    result = run_import(report)
    assert result["totals"]["inserted"] == 1
    assert list(db.saved.values()) == [report["approved_batch"]["rows"][0]["row"]]


def test_wrong_explicit_project_and_missing_write_enablement_do_not_query_or_write(monkeypatch):
    report = make_report()
    batch, digest = batch_from(report)
    loader = Mock(side_effect=AssertionError("preflight must stop before DB access"))
    monkeypatch.setattr(manual_ingestion, "_load_reference_data", loader)
    monkeypatch.setenv("MANUAL_INGESTION_WRITE", "false")
    with pytest.raises(manual_ingestion.IngestionDiagnosticError, match="single_run_write_enablement_missing"):
        run_import(report)
    monkeypatch.setenv("MANUAL_INGESTION_WRITE", "true")
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("SUPABASE_URL", "https://wwtntxknfjagdjdgiaxu.supabase.co")
    with pytest.raises(manual_ingestion.IngestionDiagnosticError, match="explicit_project_confirmation_is_not_staging"):
        asyncio.run(manual_ingestion.import_approved_batch(batch=batch, expected_digest=digest,
            expected_run_id=report["run_id"], confirmed_project_ref="kobsywjfynjvhcarbqxo",
            limits=LIMITS))
    loader.assert_not_called()


def test_import_requires_authenticated_rls_operator_before_any_reference_query(monkeypatch):
    report = make_report()
    loader = Mock(side_effect=AssertionError("auth preflight must precede DB access"))
    monkeypatch.setattr(manual_ingestion, "_load_reference_data", loader)
    monkeypatch.setenv("MANUAL_INGESTION_WRITE", "true")
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("SUPABASE_URL", "https://wwtntxknfjagdjdgiaxu.supabase.co")
    monkeypatch.delenv("RSS_IMPORT_ACCESS_TOKEN", raising=False)
    with pytest.raises(manual_ingestion.IngestionDiagnosticError,
                       match="authenticated_operator_access_token_missing"):
        run_import(report)
    loader.assert_not_called()


def test_import_requires_reviewed_staging_rls_policy_before_any_reference_query(monkeypatch):
    report = make_report()
    loader = Mock(side_effect=AssertionError("RLS policy preflight must precede DB access"))
    monkeypatch.setattr(manual_ingestion, "_load_reference_data", loader)
    monkeypatch.setenv("MANUAL_INGESTION_WRITE", "true")
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("SUPABASE_URL", "https://wwtntxknfjagdjdgiaxu.supabase.co")
    monkeypatch.setenv("RSS_IMPORT_ACCESS_TOKEN", "fixture-authenticated-operator-jwt")
    monkeypatch.delenv("RSS_IMPORT_RLS_POLICY_VERIFIED", raising=False)
    with pytest.raises(manual_ingestion.IngestionDiagnosticError,
                       match="staging_operator_insert_policy_must_be_reviewed_and_verified"):
        run_import(report)
    loader.assert_not_called()


def test_existing_duplicate_is_skipped_and_approval_replay_is_idempotent(monkeypatch):
    report = make_report()
    db = AtomicFakeDB()
    configure_import(monkeypatch, db)
    first = run_import(report)
    assert first["totals"]["inserted"] == 1
    second = run_import(report)
    assert second["totals"]["inserted"] == 0
    assert second["totals"]["skipped"] == 1
    assert len(db.saved) == 1 and db.calls == 1


def test_partial_failure_is_reported_and_same_approval_can_safely_retry(monkeypatch, caplog):
    report = make_report([make_item(url="https://techcrunch.com/one"),
                          make_item(url="https://techcrunch.com/two", title="TechCrunch reports a second new AI software system")])
    db = AtomicFakeDB(); db.fail_on_call = 2
    configure_import(monkeypatch, db)
    first = run_import(report)
    assert first["totals"]["inserted"] == 1
    assert first["totals"]["failed"] == 1
    assert first["database_write"]["rows_with_unknown_commit_status"] == 1
    assert "password=fixture" not in caplog.text
    db.fail_on_call = None
    second = run_import(report)
    assert second["totals"]["inserted"] == 1
    assert second["totals"]["skipped"] == 1
    assert len(db.saved) == 2


def test_concurrent_imports_are_atomic_on_existing_content_hash_constraint(monkeypatch):
    report = make_report()
    db = AtomicFakeDB()
    configure_import(monkeypatch, db, existing=[])
    async def concurrent():
        batch, digest = batch_from(report)
        args = dict(batch=batch, expected_digest=digest, expected_run_id=report["run_id"],
                    confirmed_project_ref=approved_batch.STAGING_PROJECT_REF, limits=LIMITS)
        return await asyncio.gather(manual_ingestion.import_approved_batch(**args),
                                    manual_ingestion.import_approved_batch(**args))
    results = asyncio.run(concurrent())
    assert sorted(item["totals"]["inserted"] for item in results) == [0, 1]
    assert len(db.saved) == 1


def test_direct_live_feed_write_api_is_disabled():
    with pytest.raises(manual_ingestion.IngestionDiagnosticError, match="live_feed_write_mode_is_disabled"):
        asyncio.run(manual_ingestion.run_manual_ingestion(write=True))
