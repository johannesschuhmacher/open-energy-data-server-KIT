# SPDX-FileCopyrightText: OpenAI
#
# SPDX-License-Identifier: AGPL-3.0-or-later

# ruff: noqa: E402

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import replace
from pathlib import Path

from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = ROOT / "CRAWLER_CONFIG.yml"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crawler.common.runtime_env import load_local_crawler_env  # noqa: E402
from scripts.lib.gapfiller.config import (
    ENTSOE_FMS_TABLES,
    load_job_from_crawler_config,
    select_tables,
)  # noqa: E402
from scripts.lib.gapfiller.core import GAPFILL_METHODS  # noqa: E402
from scripts.lib.gapfiller.db import run_gapfill_job  # noqa: E402
from scripts.lib.gapfiller.selftest import write_self_test_results  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fill gaps in configured OEDS time-series tables.",
    )
    parser.add_argument(
        "--job",
        default="entsoe_fms",
        help="Crawler job name in CRAWLER_CONFIG.yml. Defaults to entsoe_fms.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=CONFIG_FILE,
        help="Path to CRAWLER_CONFIG.yml.",
    )
    parser.add_argument(
        "--tables",
        default=None,
        help="Comma-separated table names. Defaults to the job gapfill.tables config.",
    )
    parser.add_argument(
        "--target-schema",
        default=None,
        help="Override the configured gapfilled target schema.",
    )
    parser.add_argument(
        "--method",
        choices=GAPFILL_METHODS,
        default=None,
        help="Override the configured filling method.",
    )
    parser.add_argument(
        "--max-gap-periods",
        type=int,
        default=None,
        help="Override the maximum contiguous gap length to fill.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Process and record metrics without replacing target data.",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run synthetic gapfiller self-tests and write their results for the dashboard.",
    )
    parser.add_argument(
        "--list-tables",
        action="store_true",
        help="List built-in time-series table configs and exit.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="[%(asctime)s] %(levelname)s %(message)s",
    )
    logger = logging.getLogger("gapfill_timeseries")

    if args.list_tables:
        for table in ENTSOE_FMS_TABLES:
            print(f"{table.table_name}: {', '.join(table.value_columns)}")
        return 0

    load_local_crawler_env(ROOT)
    table_names = _split_tables(args.tables)
    job = load_job_from_crawler_config(args.config, job_name=args.job, table_names=table_names)
    job = _apply_overrides(job, args)

    engine = create_engine(job.database_uri)

    if args.self_test:
        results = write_self_test_results(engine, job)
        for result in results:
            logger.info(
                "self-test %s: %s (%s/%s filled, missing_after=%s)",
                result.test_name,
                result.status,
                result.actual_filled,
                result.expected_filled,
                result.missing_after,
            )
        return 0 if all(result.status == "passed" for result in results) else 1

    summary = run_gapfill_job(engine, job, dry_run=args.dry_run, logger=logger)
    logger.info(
        "Gapfill %s: tables=%s processed, %s skipped, %s failed; rows_written=%s; values_filled=%s",
        summary.status,
        summary.tables_processed,
        summary.tables_skipped,
        summary.tables_failed,
        summary.rows_written,
        summary.values_filled,
    )
    return 0 if summary.status in {"success", "skipped"} else 1


def _apply_overrides(job, args: argparse.Namespace):
    tables = list(job.tables)
    if args.method is not None or args.max_gap_periods is not None:
        method = args.method or tables[0].method
        max_gap_periods = args.max_gap_periods if args.max_gap_periods is not None else tables[0].max_gap_periods
        tables = select_tables([table.table_name for table in tables], method=method, max_gap_periods=max_gap_periods)

    target_schema = args.target_schema or job.target_schema
    return replace(job, tables=tuple(tables), target_schema=target_schema)


def _split_tables(raw_tables: str | None) -> list[str] | None:
    if not raw_tables:
        return None
    return [table.strip() for table in raw_tables.split(",") if table.strip()]


if __name__ == "__main__":
    raise SystemExit(main())
