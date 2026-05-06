# SPDX-FileCopyrightText: OpenAI
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
from scripts.lib.gapfiller.core import SeriesFillConfig, fill_table

if TYPE_CHECKING:
    from scripts.lib.gapfiller.config import GapfillJobConfig
    from sqlalchemy import Engine


@dataclass(frozen=True)
class SelfTestResult:
    test_name: str
    status: str
    expected_filled: int
    actual_filled: int
    missing_after: int
    message: str


def run_self_tests() -> tuple[str, list[SelfTestResult], pd.DataFrame]:
    run_id = str(uuid.uuid4())
    checked_at = pd.Timestamp.now(tz="UTC")
    results: list[SelfTestResult] = []
    series_outputs: list[pd.DataFrame] = []

    for test_name, dataframe, config, expected_filled in _test_cases():
        fill_result = fill_table(dataframe, config, run_id, checked_at)
        actual_filled = sum(metric.filled_values for metric in fill_result.metrics)
        missing_after = sum(metric.missing_after for metric in fill_result.metrics)
        status = "passed" if actual_filled == expected_filled and missing_after == 0 else "failed"
        message = "" if status == "passed" else f"expected {expected_filled} fills, got {actual_filled}, missing_after={missing_after}"
        results.append(
            SelfTestResult(
                test_name=test_name,
                status=status,
                expected_filled=expected_filled,
                actual_filled=actual_filled,
                missing_after=missing_after,
                message=message,
            )
        )
        series_outputs.append(_series_for_dashboard(test_name, dataframe, fill_result.dataframe, checked_at))

    series_df = pd.concat(series_outputs, ignore_index=True) if series_outputs else pd.DataFrame()
    return run_id, results, series_df


def write_self_test_results(engine: Engine, job: GapfillJobConfig) -> list[SelfTestResult]:
    from scripts.lib.gapfiller.db import ensure_control_tables, qualified
    from sqlalchemy import text

    ensure_control_tables(engine, job.target_schema)
    run_id, results, series_df = run_self_tests()
    checked_at = pd.Timestamp.now(tz="UTC")

    result_rows = [
        {
            "run_id": run_id,
            "test_name": result.test_name,
            "status": result.status,
            "expected_filled": result.expected_filled,
            "actual_filled": result.actual_filled,
            "missing_after": result.missing_after,
            "message": result.message,
            "checked_at": checked_at.to_pydatetime(),
        }
        for result in results
    ]

    with engine.begin() as conn:
        conn.execute(text(f"DELETE FROM {qualified(job.target_schema, 'gapfill_test_results')}"))
        conn.execute(text(f"DELETE FROM {qualified(job.target_schema, 'gapfill_test_series')}"))
        pd.DataFrame(result_rows).to_sql(
            "gapfill_test_results",
            con=conn,
            schema=job.target_schema,
            if_exists="append",
            index=False,
        )
        if not series_df.empty:
            series_df["run_id"] = run_id
            series_df["checked_at"] = checked_at.to_pydatetime()
            series_df.to_sql(
                "gapfill_test_series",
                con=conn,
                schema=job.target_schema,
                if_exists="append",
                index=False,
            )

    return results


def _test_cases() -> list[tuple[str, pd.DataFrame, SeriesFillConfig, int]]:
    return [
        _linear_value_gap_case(),
        _missing_timestamp_case(),
        _seasonal_case(),
    ]


def _linear_value_gap_case() -> tuple[str, pd.DataFrame, SeriesFillConfig, int]:
    index = pd.date_range("2026-01-01", periods=12, freq="h", tz="UTC")
    values = np.arange(12, dtype=float)
    values[4:7] = np.nan
    dataframe = pd.DataFrame({
        "DateTime": index,
        "Value": values,
        "Area": "DE",
    })
    config = SeriesFillConfig(
        table_name="SelfTestLinear",
        time_column="DateTime",
        value_columns=("Value",),
        groupby_columns=("Area",),
        method="linear",
        max_gap_periods=6,
    )
    return "linear_value_gap", dataframe, config, 3


def _missing_timestamp_case() -> tuple[str, pd.DataFrame, SeriesFillConfig, int]:
    index = pd.date_range("2026-01-02", periods=12, freq="h", tz="UTC")
    dataframe = pd.DataFrame({
        "DateTime": index.delete([5, 6]),
        "Value": np.delete(np.arange(12, dtype=float), [5, 6]),
        "Area": "DE",
    })
    config = SeriesFillConfig(
        table_name="SelfTestMissingTimestamp",
        time_column="DateTime",
        value_columns=("Value",),
        groupby_columns=("Area",),
        method="linear",
        max_gap_periods=6,
    )
    return "missing_timestamp_gap", dataframe, config, 2


def _seasonal_case() -> tuple[str, pd.DataFrame, SeriesFillConfig, int]:
    index = pd.date_range("2026-01-01", periods=72, freq="h", tz="UTC")
    values = 100 + 10 * np.sin(np.arange(72) * 2 * np.pi / 24)
    values[48:51] = np.nan
    dataframe = pd.DataFrame({
        "DateTime": index,
        "Value": values,
        "Area": "DE",
    })
    config = SeriesFillConfig(
        table_name="SelfTestSeasonal",
        time_column="DateTime",
        value_columns=("Value",),
        groupby_columns=("Area",),
        method="donor_refined",
        period=pd.Timedelta(hours=24),
        candidate_periods=(pd.Timedelta(hours=24), pd.Timedelta(days=7)),
        donor_context_periods=4,
        max_gap_periods=6,
    )
    return "donor_refined_seasonal_gap", dataframe, config, 3


def _series_for_dashboard(
    test_name: str,
    original: pd.DataFrame,
    filled: pd.DataFrame,
    checked_at: pd.Timestamp,
) -> pd.DataFrame:
    original_series = original[["DateTime", "Value"]].copy()
    original_series["series_name"] = "source"
    original_series["is_original"] = True
    original_series["was_filled"] = False

    filled_series = filled[["DateTime", "Value", "gapfill_filled_columns"]].copy()
    filled_series["series_name"] = "gapfilled"
    filled_series["is_original"] = False
    filled_series["was_filled"] = filled_series["gapfill_filled_columns"].astype(str).str.contains("Value", regex=False)
    filled_series = filled_series.drop(columns=["gapfill_filled_columns"])

    output = pd.concat([original_series, filled_series], ignore_index=True)
    output = output.rename(columns={"DateTime": "time", "Value": "value"})
    output["test_name"] = test_name
    output["checked_at"] = checked_at.to_pydatetime()
    return output[["test_name", "time", "series_name", "value", "is_original", "was_filled", "checked_at"]]
