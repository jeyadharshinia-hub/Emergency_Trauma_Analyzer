import argparse
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


MOCK_MARKERS = (
    "mock mode",
    "mock summary",
    "demo summary",
    "demo report only",
    "use_mock_ai",
    "ui/demo",
    "non-diagnostic output is for ui/demo",
)


def _contains_mock_marker(value) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return False
    return any(marker in text for marker in MOCK_MARKERS)


def _summary_has_mock_markers(summary_json) -> bool:
    if not isinstance(summary_json, dict):
        return False
    for value in summary_json.values():
        if isinstance(value, list):
            if any(_contains_mock_marker(item) for item in value):
                return True
            continue
        if _contains_mock_marker(value):
            return True
    return False


def _needs_backfill(scan) -> bool:
    report = scan.report
    if not report:
        return False
    if str(report.ai_source or "").lower() == "mock":
        return True
    if _contains_mock_marker(report.ai_warning):
        return True
    if _summary_has_mock_markers(report.summary_json or {}):
        return True
    return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill CT/MRI reports that still contain mock/fallback AI summaries."
    )
    parser.add_argument("--dry-run", action="store_true", help="List targets without modifying data.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum number of scans to process.")
    parser.add_argument(
        "--database-url",
        default="",
        help="Optional DATABASE_URL override (for example sqlite:///eta_dev.db).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url

    from app import create_app  # noqa: E402
    from extensions import db  # noqa: E402
    from models.scan import Scan  # noqa: E402
    from routes.scan import reanalyze_scan_live_record  # noqa: E402
    from sqlalchemy.orm import joinedload  # noqa: E402

    app = create_app()

    with app.app_context():
        query = (
            Scan.query.options(joinedload(Scan.report))
            .filter(Scan.scan_type.in_(["ct", "mri"]))
            .order_by(Scan.id.asc())
        )
        scans = query.all()
        targets = [scan for scan in scans if _needs_backfill(scan)]

        if args.limit and args.limit > 0:
            targets = targets[: args.limit]

        print(f"CT/MRI scans found: {len(scans)}")
        print(f"Backfill targets: {len(targets)}")

        if args.dry_run:
            for scan in targets:
                source = scan.report.ai_source if scan.report else "none"
                print(f"[DRY-RUN] scan_id={scan.id} scan_type={scan.scan_type} ai_source={source}")
            return 0

        success = 0
        failed = 0
        for scan in targets:
            try:
                reanalyze_scan_live_record(scan)
                db.session.commit()
                success += 1
                print(f"[OK] scan_id={scan.id} scan_type={scan.scan_type}")
            except Exception as exc:
                db.session.rollback()
                failed += 1
                print(f"[FAIL] scan_id={scan.id} scan_type={scan.scan_type} error={exc}")

        print(f"Completed. success={success} failed={failed}")
        return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
