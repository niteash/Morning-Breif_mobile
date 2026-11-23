"""Run a one-shot RSS dry-run against the guarded staging configuration."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

from dotenv import dotenv_values

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.news.approved_batch import STAGING_PROJECT_REF, batch_digest, resolve_report_path
from run_staging import ROOT, child_environment


def _save_fresh_dry_run(report: dict) -> tuple[Path, Path] | None:
    """Persist a verified read-only proposal report without replacing prior reports."""
    if (report.get("environment") != "staging" or report.get("dry_run") is not True
            or report.get("totals", {}).get("inserted") != 0
            or report.get("database_write", {}).get("attempted") is not False):
        return None
    batch = report.get("approved_batch")
    if (not isinstance(batch, dict) or batch.get("project_ref") != STAGING_PROJECT_REF
            or report.get("batch_sha256") != batch_digest(batch)):
        return None
    try:
        report_id = uuid.UUID(report.get("run_id", ""))
    except (ValueError, TypeError, AttributeError):
        return None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_dir = ROOT / "backend/reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / f"rss_staging_dry_run_{stamp}_{report_id}.json"
    markdown_path = json_path.with_suffix(".md")
    try:
        _create_read_only_file(json_path, json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        category_rows = "\n".join(
            f"| {slug} | {counts.get('proposed', 0)} | {counts.get('eligible', 0)} |"
            for slug, counts in report.get("category_counts", {}).items())
        _create_read_only_file(markdown_path,
            f"# Fresh staging RSS dry run — {stamp}\n\n"
            f"Run ID: `{report_id}`. No database writes were performed.\n\n"
            f"Batch SHA-256: `{report['batch_sha256']}`\n\n"
            f"Approval expires: `{batch['expires_at']}`\n\n"
            f"Sources checked: {report.get('total_sources', 0)}; "
            f"parseable: {report.get('successful_sources', 0)}; "
            f"proposed: {len(report.get('proposed', []))}; "
            f"eligible: {report.get('totals', {}).get('eligible', 0)}.\n\n"
            "| Category | Proposed | Eligible |\n|---|---:|---:|\n"
            f"{category_rows}\n\n"
            "Review the exact rows in the JSON sidecar. The SHA-256 digest binds those stored rows to the explicit import command.\n")
    except FileExistsError:
        return None
    return json_path, markdown_path


def _create_read_only_file(path: Path, contents: str) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as report_file:
            report_file.write(contents)
            report_file.flush()
            os.fsync(report_file.fileno())
        os.chmod(path, 0o400)
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        try:
            path.unlink()
        except OSError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--write", action="store_true")
    parser.add_argument("--confirm-staging-project", default="")
    parser.add_argument("--approved-report", default="")
    parser.add_argument("--confirm-approved-run-id", default="")
    parser.add_argument("--approve-batch-sha256", default="")
    parser.add_argument("--limit-per-feed", type=int, default=20)
    parser.add_argument("--max-inserts", type=int, default=100)
    parser.add_argument("--max-age-hours", type=int, default=24)
    parser.add_argument("--retry-failed-sources", action="store_true")
    args = parser.parse_args()
    if args.write and args.confirm_staging_project != "wwtntxknfjagdjdgiaxu":
        parser.error("Confirm the staging project ID explicitly before a write run")
    if args.write and (not args.approved_report or not args.confirm_approved_run_id
                       or not args.approve_batch_sha256):
        parser.error("Write mode requires the reviewed batch report, exact run ID and explicit SHA-256 approval")
    if args.dry_run and (args.approved_report or args.confirm_approved_run_id or args.approve_batch_sha256):
        parser.error("Approved report arguments are valid only in write mode")
    report_path = None
    if args.write:
        reports_dir = (ROOT / "backend/reports").resolve()
        try:
            report_path = resolve_report_path(args.approved_report, reports_dir)
        except Exception:
            parser.error("The reviewed report must be a regular JSON file directly under backend/reports")
    values = dotenv_values(ROOT / "backend/.env.staging", interpolate=False)
    try:
        env = child_environment(values, "backend")
    except ValueError:
        print("Staging environment validation failed.", file=sys.stderr)
        return 1
    env["MANUAL_INGESTION_WRITE"] = "true" if args.write else "false"
    command = [sys.executable, "-m", "app.services.news.cli", "--environment", "staging",
               "--write" if args.write else "--dry-run", "--limit-per-feed", str(args.limit_per_feed),
               "--max-inserts", str(args.max_inserts), "--max-age-hours", str(args.max_age_hours)]
    if report_path:
        command.extend(["--approved-report", str(report_path),
                        "--confirm-approved-run-id", args.confirm_approved_run_id,
                        "--approve-batch-sha256", args.approve_batch_sha256])
    if args.retry_failed_sources:
        command.append("--retry-failed-sources")
    if args.write:
        command.extend(["--confirm-staging-project", args.confirm_staging_project])
    result = subprocess.run(command, cwd=ROOT / "backend", env=env, capture_output=True, text=True)
    try:
        report = json.loads(result.stdout)
        if not isinstance(report, dict):
            report = None
    except (json.JSONDecodeError, TypeError):
        report = None
    json_path = markdown_path = None
    if report is not None:
        totals = report.get("totals", {})
        database_write = report.get("database_write", {})
        if (report.get("environment") != "staging"
                or report.get("dry_run") is not (not args.write)
                or (not args.write and (totals.get("inserted") != 0
                                        or database_write.get("attempted") is not False))
                or (args.write and (report.get("approved_run_id") != args.confirm_approved_run_id
                                    or report.get("batch_sha256") != args.approve_batch_sha256
                                    or totals.get("inserted", 0) > args.max_inserts
                                    or database_write.get("rows_attempted", 0) > args.max_inserts))):
            print("RSS staging run failed: stage=report_validation category=safety_assertion_failed "
                  "database_write_attempted=unknown rows_committed=unknown", file=sys.stderr)
            return 1
        try:
            report_id = uuid.UUID(report.get("run_id", ""))
        except (ValueError, TypeError, AttributeError):
            print("RSS staging run failed: stage=report_validation category=invalid_run_id "
                  "database_write_attempted=unknown rows_committed=unknown", file=sys.stderr)
            return 1
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        report_dir = ROOT / "backend/reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        json_path = report_dir / f"rss_staging_{'write' if args.write else 'dry_run'}_{stamp}_{report_id}.json"
        try:
            _create_read_only_file(json_path, json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        except FileExistsError:
            print("RSS staging run failed: stage=report_persistence category=report_path_collision "
                  "database_write_attempted=unknown rows_committed=unknown", file=sys.stderr)
            return 1
        markdown_path = json_path.with_suffix(".md")
    if result.returncode:
        try:
            failure = json.loads(result.stderr)
            if not isinstance(failure, dict):
                failure = {}
        except (json.JSONDecodeError, TypeError):
            failure = {}
        if (not failure and report is not None
                and report.get("database_write", {}).get("write_failures", 0)):
            write_result = report["database_write"]
            failure = {"stage": "database_write", "error_category": "partial_database_write_failure",
                       "validation_condition": "one_or_more_row_writes_failed",
                       "database_write_attempted": write_result.get("attempted", False),
                       "rows_attempted": write_result.get("rows_attempted", 0),
                       "rows_committed": write_result.get("rows_committed", 0),
                       "write_failures": write_result.get("write_failures", 0),
                       "rows_with_unknown_commit_status": write_result.get("rows_with_unknown_commit_status", 0)}
        safe_fields = ("stage", "error_category", "validation_condition",
                       "database_write_attempted", "rows_attempted", "rows_committed",
                       "write_failures", "rows_with_unknown_commit_status", "error_type",
                       "database_error_code", "rejected_rows")
        public_failure = {key: failure[key] for key in safe_fields if key in failure}
        if not public_failure:
            public_failure = {"stage": "runner", "error_category": "runner_failure",
                              "database_write_attempted": "unknown", "rows_committed": "unknown"}
        print("RSS staging run failed: " + json.dumps(public_failure, ensure_ascii=False, sort_keys=True),
              file=sys.stderr)
        if json_path:
            print(f"Outcome report: {json_path.relative_to(ROOT)}", file=sys.stderr)
        return result.returncode
    if report is None or json_path is None or markdown_path is None:
        print("RSS staging run failed: stage=report_validation category=invalid_report "
              "database_write_attempted=unknown rows_committed=unknown", file=sys.stderr)
        return 1
    totals = report.get("totals", {})
    table_rows = []
    for item in report.get("sources", []):
        candidate = item.get("candidate_url") or item.get("url") or "—"
        current = item.get("url") or ""
        replacement = current if current and current != candidate else "—"
        table_rows.append("| {source} | {url} | {status} | {parsed_result} | {enabled} | {failure} | {replacement} | {entries} | {evaluated} | {recent} | {undated} | {rejected} | {duplicates} | {eligible} | {proposed} |".format(
            source=item.get("source", ""), url=candidate, status=item.get("http_status") or "—",
            parsed_result=item.get("feed_parse_result", "—"), enabled="yes" if item.get("enabled") else "no",
            failure=item.get("failure_category") or "—", replacement=replacement,
            entries=item.get("parsed", 0), evaluated=item.get("evaluated", 0),
            recent=item.get("valid_recent", 0), undated=item.get("valid_undated", 0),
            duplicates=item.get("duplicates", 0), rejected=item.get("rejected", 0),
            eligible=item.get("eligible", 0), proposed=item.get("proposed", 0)))
    markdown_path = json_path.with_suffix(".md")
    if args.write:
        source_rows = "\n".join(
            f"| {item.get('source', '')} | {item.get('category', '')} | {item.get('inserted', 0)} | "
            f"{item.get('skipped', 0)} | {item.get('rejected', 0)} | {item.get('failed', 0)} |"
            for item in report.get("sources", []))
        category_rows = "\n".join(
            f"| {slug} | {counts.get('inserted', 0)} | {counts.get('skipped', 0)} | "
            f"{counts.get('rejected', 0)} | {counts.get('failed', 0)} |"
            for slug, counts in report.get("category_counts", {}).items())
        markdown = (
            f"# Approved staging RSS import — {stamp}\n\n"
            f"Approved run: `{report.get('approved_run_id')}`. Batch SHA-256: `{report.get('batch_sha256')}`.\n\n"
            f"Inserted: {totals.get('inserted', 0)}; skipped duplicates: {totals.get('skipped', 0)}; "
            f"rejected: {totals.get('rejected', 0)}; failed: {totals.get('failed', 0)}; "
            f"rows committed: {database_write.get('rows_committed', 0)}; "
            f"unknown commit status: {database_write.get('rows_with_unknown_commit_status', 0)}.\n\n"
            "| Source | Category | Inserted | Skipped | Rejected | Failed |\n|---|---|---:|---:|---:|---:|\n"
            f"{source_rows}\n\n## Category totals\n\n"
            "| Category | Inserted | Skipped | Rejected | Failed |\n|---|---:|---:|---:|---:|\n"
            f"{category_rows}\n"
        )
    else:
        markdown = (
            f"# RSS staging dry run — {stamp}\n\n"
            f"Environment: staging. Batch SHA-256: `{report.get('batch_sha256')}`. "
            f"Approval expires: `{report.get('expires_at')}`. No database writes were performed.\n\n"
            f"Sources: {report.get('successful_sources', 0)} parseable; "
            f"{report.get('failed_or_disabled_sources', 0)} failed or disabled of {report.get('total_sources', 0)}. "
            f"Parsed: {totals.get('parsed', 0)}; evaluated (per-feed cap): {totals.get('evaluated', 0)}; "
            f"valid within {report.get('limits', {}).get('max_age_hours', 24)}h: {totals.get('valid_recent', 0)}; "
            f"undated: {totals.get('valid_undated', 0)}; rejected: {totals.get('rejected', 0)}; "
            f"duplicates: {totals.get('duplicates', 0)}; eligible: {totals.get('eligible', 0)}; "
            f"proposals: {len(report.get('proposed', []))}; over cap: {totals.get('over_global_limit', 0)}.\n\n"
            f"| Source | Candidate URL | HTTP | Parse | Enabled | Failure category | Verified replacement URL | Parsed | Evaluated | Valid ≤{report.get('limits', {}).get('max_age_hours', 24)}h | Undated | Rejected | Duplicates | Eligible | Proposed |\n"
            "|---|---|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|\n"
            + "\n".join(table_rows)
            + "\n\n## Category totals\n\n"
            + f"| Category | Valid ≤{report.get('limits', {}).get('max_age_hours', 24)}h | Undated | Rejected | Duplicates | Eligible | Proposed |\n"
            + "|---|---:|---:|---:|---:|---:|---:|\n"
            + "\n".join("| {slug} | {valid_recent} | {valid_undated} | {rejected} | {duplicates} | {eligible} | {proposed} |".format(
                slug=slug, **counts) for slug, counts in report.get("category_counts", {}).items())
            + "\n\nThe JSON sidecar contains the immutable database rows, source/category mapping and approval-bound metadata.\n"
        )
    _create_read_only_file(markdown_path, markdown)
    if args.write:
        print("RSS staging approved import: inserted={inserted}, skipped={skipped}, rejected={rejected}, failed={failed}".format(
            inserted=totals.get("inserted", 0), skipped=totals.get("skipped", 0),
            rejected=totals.get("rejected", 0), failed=totals.get("failed", 0)))
    else:
        print("RSS staging dry-run: sources={sources}, successful={success}, failed_or_disabled={failed}, "
              "parsed={parsed}, valid={valid}, duplicates={duplicates}, proposed={proposed}".format(
                  sources=report.get("total_sources", 0), success=report.get("successful_sources", 0),
                  failed=report.get("failed_or_disabled_sources", 0), parsed=totals.get("parsed", 0),
                  valid=totals.get("valid", 0), duplicates=totals.get("duplicates", 0),
                  proposed=len(report.get("proposed", []))))
    print(f"Detailed report: {json_path.relative_to(ROOT)}")
    print(f"Source table: {markdown_path.relative_to(ROOT)}")
    if not args.write:
        print("No database writes were performed.")
        print("Batch SHA-256: " + report["batch_sha256"])
        print("Approval expires: " + report["approved_batch"]["expires_at"])
        print("Exact import command (not executed):")
        command_lines = [
            ".venv/bin/python backend/scripts/staging_news.py \\",
            "  --write \\",
            "  --confirm-staging-project " + STAGING_PROJECT_REF + " \\",
            "  --approved-report " + str(json_path.relative_to(ROOT)) + " \\",
            "  --confirm-approved-run-id " + report["run_id"] + " \\",
            "  --approve-batch-sha256 " + report["batch_sha256"] + " \\",
            "  --limit-per-feed " + str(args.limit_per_feed) + " \\",
            "  --max-inserts " + str(args.max_inserts) + " \\",
            "  --max-age-hours " + str(args.max_age_hours),
        ]
        print("\n".join(command_lines))
    if report.get("database_write", {}).get("write_failures", 0):
        print("RSS staging write completed with database row failures; do not retry automatically. "
              f"See {json_path.relative_to(ROOT)} for committed and uncertain row counts.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
