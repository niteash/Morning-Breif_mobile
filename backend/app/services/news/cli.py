"""Staging-only RSS audit. No scheduler, AI provider, push or trial service is called."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

from .approved_batch import (
    ApprovedBatchError,
    STAGING_PROJECT_REF,
    read_approved_report,
)
from .manual_ingestion import IngestionDiagnosticError, import_approved_batch, run_manual_ingestion

STAGING_URL = "https://wwtntxknfjagdjdgiaxu.supabase.co"
STAGING_REF = STAGING_PROJECT_REF
REPORTS_DIR = Path(__file__).resolve().parents[3] / "reports"


class StagingPreflightError(Exception):
    def __init__(self, stage: str, category: str, condition: str):
        self.stage, self.category, self.condition = stage, category, condition


def _emit_failure(*, stage: str, category: str, condition: str,
                  write_attempted: bool = False, rows_attempted: int = 0,
                  rows_committed: int = 0, write_failures: int = 0,
                  uncertain_rows: int = 0, error_type: str | None = None,
                  database_error_code: str | None = None,
                  metadata: dict | None = None) -> None:
    payload = {"environment": "staging", "stage": stage,
               "error_category": category, "validation_condition": condition,
               "database_write_attempted": bool(write_attempted),
               "rows_attempted": int(rows_attempted), "rows_committed": int(rows_committed),
               "write_failures": int(write_failures),
               "rows_with_unknown_commit_status": int(uncertain_rows)}
    if error_type:
        payload["error_type"] = error_type
    if database_error_code:
        payload["database_error_code"] = database_error_code
    if metadata:
        payload.update(metadata)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True), file=sys.stderr)


def _read_approved_report(path_text: str, run_id: str, expected_digest: str,
                          limit_per_feed: int, max_inserts: int,
                          max_age_hours: int) -> tuple[dict, dict]:
    try:
        return read_approved_report(
            path_text, REPORTS_DIR, expected_run_id=run_id,
            expected_digest=expected_digest,
            expected_limits={"per_source": limit_per_feed, "global": max_inserts,
                             "max_age_hours": max_age_hours},
        )
    except ApprovedBatchError as error:
        raise StagingPreflightError("approval_report_validation", error.category,
                                    error.condition) from None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", choices=["staging"], required=True)
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
    parser.add_argument("--retry-failed-sources", action="store_true",
                        help="explicitly retry feeds still in their health cooldown")
    args = parser.parse_args(argv)
    try:
        if os.getenv("APP_ENV") != "staging" or os.getenv("SUPABASE_URL", "").rstrip("/") != STAGING_URL:
            raise StagingPreflightError("environment_guard", "wrong_staging_target",
                                        "only_authorized_staging_project_is_allowed")
        if os.getenv("SCHEDULER_ENABLED", "false").lower() != "false" or os.getenv("NEWS_INGESTION_ENABLED", "false").lower() != "false":
            raise StagingPreflightError("environment_guard", "background_ingestion_enabled",
                                        "scheduler_and_automatic_ingestion_must_be_disabled")
        if (os.getenv("PUSH_DELIVERY_ENABLED", "false").lower() != "false"
                or os.getenv("ACCOUNT_DELETION_ENABLED", "false").lower() != "false"
                or os.getenv("ACCOUNT_DELETION_WORKER_ENABLED", "false").lower() != "false"
                or os.getenv("TRIAL_STAGING_ACCOUNT_ENABLED", "false").lower() != "false"):
            raise StagingPreflightError("environment_guard", "unrelated_worker_enabled",
                                        "push_account_deletion_and_trial_workers_must_be_disabled")
        if any(os.getenv(name, "") for name in ("GEMINI_API_KEY", "AZURE_SPEECH_KEY", "FIREBASE_SERVICE_ACCOUNT_PATH", "INGESTION_OPERATOR_IDS")):
            raise StagingPreflightError("environment_guard", "provider_or_operator_secret_present",
                                        "providers_and_operator_secrets_must_be_blank")
        if args.write and (os.getenv("MANUAL_INGESTION_WRITE") != "true" or args.confirm_staging_project != STAGING_REF):
            raise StagingPreflightError("environment_guard", "write_guard_rejected",
                                        "single_run_enablement_and_exact_staging_confirmation_required")
        if args.write and (not args.approved_report or not args.confirm_approved_run_id
                           or not args.approve_batch_sha256):
            raise StagingPreflightError("approval_report_validation", "approved_report_required",
                                        "write_requires_report_run_id_and_explicit_batch_digest")
        if args.dry_run and (args.approved_report or args.confirm_approved_run_id
                             or args.approve_batch_sha256):
            raise StagingPreflightError("approval_report_validation", "unexpected_approval_arguments",
                                        "approved_report_arguments_only_allowed_in_write_mode")
        approved_batch = (_read_approved_report(args.approved_report, args.confirm_approved_run_id,
                                                args.approve_batch_sha256,
                                                args.limit_per_feed, args.max_inserts,
                                                args.max_age_hours)[1]
                          if args.write else None)
    except StagingPreflightError as error:
        _emit_failure(stage=error.stage, category=error.category, condition=error.condition)
        return 1

    progress = {}
    try:
        if args.write:
            report = asyncio.run(import_approved_batch(
                batch=approved_batch,
                expected_digest=args.approve_batch_sha256,
                expected_run_id=args.confirm_approved_run_id,
                confirmed_project_ref=args.confirm_staging_project,
                limits={"per_source": args.limit_per_feed, "global": args.max_inserts,
                        "max_age_hours": args.max_age_hours},
                _progress=progress,
            ))
        else:
            report = asyncio.run(run_manual_ingestion(limit_per_feed=args.limit_per_feed,
                                                      max_inserts=args.max_inserts,
                                                      retry_failed_sources=args.retry_failed_sources,
                                                      max_age_hours=args.max_age_hours,
                                                      _progress=progress))
    except IngestionDiagnosticError as error:
        _emit_failure(stage=error.stage, category=error.category, condition=error.condition,
                      write_attempted=progress.get("database_write_attempted", False),
                      rows_attempted=progress.get("rows_attempted", 0),
                      rows_committed=progress.get("rows_committed", 0),
                      write_failures=progress.get("write_failures", 0),
                      uncertain_rows=progress.get("uncertain_rows", 0),
                      error_type=error.error_type, database_error_code=error.database_error_code,
                      metadata=error.metadata)
        return 1
    except Exception as error:
        # Emit type and stage only. Exception text may include URLs, SQL, or credentials.
        stage = progress.get("stage", "pipeline")
        _emit_failure(stage=stage, category="unexpected_failure",
                      condition="ingestion_failed_without_safe_classification",
                      write_attempted=progress.get("database_write_attempted", False),
                      rows_attempted=progress.get("rows_attempted", 0),
                      rows_committed=progress.get("rows_committed", 0),
                      write_failures=progress.get("write_failures", 0),
                      uncertain_rows=progress.get("uncertain_rows", 0),
                      error_type=type(error).__name__)
        return 1
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 2 if report.get("database_write", {}).get("write_failures", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
