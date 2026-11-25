"""Tests for the immutable staging RSS batch wrapper."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import uuid

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import staging_news  # noqa: E402

from app.services.news.approved_batch import batch_digest, build_approved_batch, proposal_projection
from app.services.news.rss_registry import SOURCES
from app.services.news.rss_processing import normalize_entry


def make_report():
    now = datetime.now(timezone.utc).replace(microsecond=0)
    source = next(item for item in SOURCES if item.source_id == "techcrunch")
    normalized = normalize_entry({
        "title": "OpenAI announces a new AI technology service",
        "description": "A technology company announced its latest AI service.",
        "url": "https://techcrunch.com/story", "author": "Reporter",
        "image_url": None, "published_raw": now.isoformat(),
    }, source, {"technology", "business", "football", "myanmar", "world"}, now)
    row = {
        "category_id": "category-tech", "source": source.name,
        "title": normalized["title"], "description": "A technology company announced its latest AI service.",
        "url": normalized["url"], "image_url": None, "author": "Reporter",
        "published_at": normalized["published_at"],
        "content_hash": normalized["content_hash"], "title_hash": normalized["title_hash"],
    }
    rows = [{"source_id": source.source_id, "category_slug": "technology",
             "topic_group": normalized["topic_group"], "language": normalized["language"],
             "publication_date_unknown": False, "row": row}]
    limits = {"per_source": 20, "global": 100, "max_age_hours": 24}
    run_id = str(uuid.uuid4())
    batch, digest = build_approved_batch(run_id=run_id, rows=rows, limits=limits, created_at=now)
    return {
        "environment": "staging", "dry_run": True, "total_sources": 23,
        "run_id": run_id, "limits": limits, "totals": {"inserted": 0, "proposed": 1},
        "database_write": {"attempted": False, "rows_attempted": 0, "rows_committed": 0,
                            "write_failures": 0, "rows_with_unknown_commit_status": 0},
        "category_counts": {"technology": {"proposed": 1, "eligible": 1}},
        "sources": [], "proposed": proposal_projection(rows),
        "approved_batch": batch, "batch_sha256": digest,
    }


def test_dry_run_persistence_is_create_only_and_records_digest_and_expiry(tmp_path, monkeypatch):
    monkeypatch.setattr(staging_news, "ROOT", tmp_path)
    report = make_report()
    saved, markdown = staging_news._save_fresh_dry_run(report)
    assert json.loads(saved.read_text(encoding="utf-8"))["batch_sha256"] == report["batch_sha256"]
    assert saved.stat().st_mode & 0o777 == 0o400
    assert report["batch_sha256"] in markdown.read_text(encoding="utf-8")
    assert report["approved_batch"]["expires_at"] in markdown.read_text(encoding="utf-8")
    assert staging_news._save_fresh_dry_run(report) is None


def test_fresh_report_persistence_rejects_a_modified_batch_or_one_that_could_write(tmp_path, monkeypatch):
    monkeypatch.setattr(staging_news, "ROOT", tmp_path)
    report = make_report()
    report["approved_batch"]["rows"][0]["row"]["title"] = "tampered"
    assert staging_news._save_fresh_dry_run(report) is None
    report = make_report()
    report["database_write"]["attempted"] = True
    assert staging_news._save_fresh_dry_run(report) is None
    assert not (tmp_path / "backend" / "reports").exists()


def test_approved_write_uses_only_the_saved_snapshot_without_refetching(tmp_path, monkeypatch, capsys):
    root = tmp_path
    reports = root / "backend" / "reports"
    reports.mkdir(parents=True)
    approved = make_report()
    report_path = reports / "approved.json"
    report_path.write_text(json.dumps(approved), encoding="utf-8")
    monkeypatch.setattr(staging_news, "ROOT", root)
    monkeypatch.setattr(staging_news, "dotenv_values", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(staging_news, "child_environment", lambda *_args, **_kwargs: {"MANUAL_INGESTION_WRITE": "true"})
    monkeypatch.setattr(sys, "argv", ["staging_news.py", "--write",
        "--confirm-staging-project", "wwtntxknfjagdjdgiaxu",
        "--approved-report", str(report_path),
        "--confirm-approved-run-id", approved["run_id"],
        "--approve-batch-sha256", approved["batch_sha256"]])
    calls = []
    outcome = {
        "run_id": str(uuid.uuid4()), "approved_run_id": approved["run_id"],
        "batch_sha256": approved["batch_sha256"], "environment": "staging", "dry_run": False,
        "totals": {"inserted": 1, "skipped": 0, "rejected": 0, "failed": 0},
        "database_write": {"attempted": True, "rows_attempted": 1, "rows_committed": 1,
                           "write_failures": 0, "rows_with_unknown_commit_status": 0},
        "sources": [], "category_counts": {},
    }
    def run(command, *, cwd, env, capture_output, text):
        calls.append((command, env))
        return SimpleNamespace(returncode=0, stdout=json.dumps(outcome), stderr="")
    monkeypatch.setattr(staging_news.subprocess, "run", run)
    assert staging_news.main() == 0
    assert len(calls) == 1
    command, env = calls[0]
    assert "--write" in command and "--dry-run" not in command
    assert "--approve-batch-sha256" in command and approved["batch_sha256"] in command
    assert "--confirm-approved-run-id" in command and approved["run_id"] in command
    assert env["MANUAL_INGESTION_WRITE"] == "true"
    output = capsys.readouterr().out
    assert "RSS staging approved import: inserted=1" in output
    assert "approved" in output


def test_write_refuses_report_outside_designated_directory_before_subprocess(tmp_path, monkeypatch):
    root = tmp_path
    reports = root / "backend" / "reports"; reports.mkdir(parents=True)
    outside = root / "outside.json"; outside.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(staging_news, "ROOT", root)
    monkeypatch.setattr(staging_news, "dotenv_values", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(staging_news, "child_environment", lambda *_args, **_kwargs: {})
    called = []
    monkeypatch.setattr(staging_news.subprocess, "run", lambda *args, **kwargs: called.append(args))
    monkeypatch.setattr(sys, "argv", ["staging_news.py", "--write",
        "--confirm-staging-project", "wwtntxknfjagdjdgiaxu", "--approved-report", str(outside),
        "--confirm-approved-run-id", str(uuid.uuid4()), "--approve-batch-sha256", "0" * 64])
    with pytest.raises(SystemExit):
        staging_news.main()
    assert called == []


def test_partial_import_report_records_commits_and_uncertainty(tmp_path, monkeypatch, capsys):
    root = tmp_path
    reports = root / "backend" / "reports"; reports.mkdir(parents=True)
    approved = make_report()
    report_path = reports / "approved.json"; report_path.write_text(json.dumps(approved), encoding="utf-8")
    monkeypatch.setattr(staging_news, "ROOT", root)
    monkeypatch.setattr(staging_news, "dotenv_values", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(staging_news, "child_environment", lambda *_args, **_kwargs: {"MANUAL_INGESTION_WRITE": "true"})
    monkeypatch.setattr(sys, "argv", ["staging_news.py", "--write",
        "--confirm-staging-project", "wwtntxknfjagdjdgiaxu", "--approved-report", str(report_path),
        "--confirm-approved-run-id", approved["run_id"], "--approve-batch-sha256", approved["batch_sha256"]])
    outcome = {
        "run_id": str(uuid.uuid4()), "approved_run_id": approved["run_id"],
        "batch_sha256": approved["batch_sha256"], "environment": "staging", "dry_run": False,
        "totals": {"inserted": 1, "skipped": 0, "rejected": 0, "failed": 2},
        "database_write": {"attempted": True, "rows_attempted": 3, "rows_committed": 1,
                           "write_failures": 2, "rows_with_unknown_commit_status": 2},
        "sources": [], "category_counts": {},
    }
    monkeypatch.setattr(staging_news.subprocess, "run", lambda *_args, **_kwargs:
        SimpleNamespace(returncode=2, stdout=json.dumps(outcome), stderr=""))
    assert staging_news.main() == 2
    error = capsys.readouterr().err
    assert '"rows_committed": 1' in error
    assert '"rows_with_unknown_commit_status": 2' in error
    saved = next(reports.glob("rss_staging_write_*.json"))
    assert saved.stat().st_mode & 0o777 == 0o400
    assert json.loads(saved.read_text(encoding="utf-8"))["database_write"]["rows_committed"] == 1
