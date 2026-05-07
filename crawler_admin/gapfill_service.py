from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import pandas as pd
from scripts.lib.gapfiller.core import GAPFILL_METHODS
from scripts.lib.gapfiller.selftest import (
    HoldoutTestResult,
    SelfTestResult,
    list_holdout_datasets,
    list_self_test_cases,
    run_holdout_test,
    run_self_tests,
)


@dataclass(frozen=True)
class GapfillSelfTestCatalogItem:
    name: str
    description: str
    fault_type: str
    method: str
    expected_filled: int
    source_rows: int
    value_columns: str
    period_label: str
    candidate_periods_label: str


@dataclass(frozen=True)
class GapfillHoldoutDatasetItem:
    name: str
    label: str
    description: str
    method: str
    row_count: int
    max_gap_length: int
    recommended_gap_start: int
    recommended_gap_length: int
    period_label: str
    candidate_periods_label: str


@dataclass(frozen=True)
class GapfillErrorMetric:
    label: str
    value: str


@dataclass(frozen=True)
class GapfillChartMarker:
    cx: str
    cy: str
    label: str


@dataclass(frozen=True)
class GapfillChart:
    test_name: str
    truth_segments: list[str]
    source_segments: list[str]
    gapfilled_segments: list[str]
    filled_markers: list[GapfillChartMarker]
    start_label: str
    end_label: str
    y_min_label: str
    y_max_label: str
    filled_count: int

    @property
    def has_data(self) -> bool:
        return bool(self.truth_segments or self.source_segments or self.gapfilled_segments)


@dataclass(frozen=True)
class GapfillSelfTestView:
    run_id: str
    checked_at: str
    selected_names: list[str]
    results: list[SelfTestResult]
    charts: list[GapfillChart]
    passed_count: int
    failed_count: int
    series_rows: int

    @property
    def all_passed(self) -> bool:
        return self.failed_count == 0 and bool(self.results)


@dataclass(frozen=True)
class GapfillHoldoutView:
    run_id: str
    checked_at: str
    result: HoldoutTestResult
    charts: list[GapfillChart]
    error_metrics: list[GapfillErrorMetric]
    series_rows: int

    @property
    def passed(self) -> bool:
        return self.result.status == "passed"


def build_gapfill_selftest_catalog() -> list[GapfillSelfTestCatalogItem]:
    catalog = []
    for test_case in list_self_test_cases():
        catalog.append(
            GapfillSelfTestCatalogItem(
                name=test_case.name,
                description=test_case.description,
                fault_type=test_case.fault_type,
                method=test_case.method,
                expected_filled=test_case.expected_filled,
                source_rows=test_case.source_rows,
                value_columns=", ".join(test_case.config.value_columns),
                period_label=_format_timedelta(test_case.config.period),
                candidate_periods_label=_format_candidate_periods(test_case.config.candidate_periods),
            )
        )
    return catalog


def build_gapfill_holdout_catalog() -> list[GapfillHoldoutDatasetItem]:
    catalog = []
    for dataset in list_holdout_datasets():
        catalog.append(
            GapfillHoldoutDatasetItem(
                name=dataset.name,
                label=dataset.label,
                description=dataset.description,
                method=dataset.method,
                row_count=dataset.row_count,
                max_gap_length=dataset.max_gap_length,
                recommended_gap_start=dataset.recommended_gap_start,
                recommended_gap_length=dataset.recommended_gap_length,
                period_label=_format_timedelta(dataset.config.period),
                candidate_periods_label=_format_candidate_periods(dataset.config.candidate_periods),
            )
        )
    return catalog


def build_gapfill_selftest_view(selected_names: Sequence[str] | None = None) -> GapfillSelfTestView:
    run_id, results, series = run_self_tests(selected_names)
    charts = _build_charts(series)
    passed_count = sum(1 for result in results if result.status == "passed")
    failed_count = sum(1 for result in results if result.status != "passed")
    return GapfillSelfTestView(
        run_id=run_id,
        checked_at=_extract_checked_at(series),
        selected_names=[result.test_name for result in results],
        results=results,
        charts=charts,
        passed_count=passed_count,
        failed_count=failed_count,
        series_rows=len(series),
    )


def build_gapfill_holdout_view(
    dataset_name: str,
    gap_length_periods: int,
    *,
    gap_start_index: int | None = None,
    fault_type: str = "value_gap",
    method: str | None = None,
) -> GapfillHoldoutView:
    run_id, result, series = run_holdout_test(
        dataset_name,
        gap_length_periods,
        gap_start_index=gap_start_index,
        fault_type=fault_type,
        method=method,
    )
    return GapfillHoldoutView(
        run_id=run_id,
        checked_at=_extract_checked_at(series),
        result=result,
        charts=_build_charts(series),
        error_metrics=_build_error_metrics(result),
        series_rows=len(series),
    )


def gapfill_method_options() -> list[str]:
    return list(GAPFILL_METHODS)


def _build_error_metrics(result: HoldoutTestResult) -> list[GapfillErrorMetric]:
    return [
        GapfillErrorMetric("MAE", _format_optional_number(result.mean_absolute_error)),
        GapfillErrorMetric("RMSE", _format_optional_number(result.root_mean_squared_error)),
        GapfillErrorMetric("Max abs.", _format_optional_number(result.max_absolute_error)),
        GapfillErrorMetric("MAPE", _format_optional_number(result.mean_absolute_percentage_error, suffix="%")),
        GapfillErrorMetric("Compared", f"{result.compared_points} / {result.expected_points}"),
        GapfillErrorMetric("Filled", str(result.actual_filled)),
    ]


def _build_charts(series: pd.DataFrame) -> list[GapfillChart]:
    if series.empty:
        return []

    charts = []
    ordered_names = list(dict.fromkeys(series["test_name"].astype(str).tolist()))
    for test_name in ordered_names:
        test_frame = series[series["test_name"] == test_name].copy()
        test_frame["time"] = pd.to_datetime(test_frame["time"], utc=True)
        finite_values = test_frame["value"].dropna().astype(float)
        if finite_values.empty:
            continue

        start_time = test_frame["time"].min()
        end_time = test_frame["time"].max()
        y_min = float(finite_values.min())
        y_max = float(finite_values.max())
        y_span = y_max - y_min
        if math.isclose(y_span, 0.0):
            y_span = 1.0

        truth_frame = test_frame[test_frame["series_name"] == "truth"]
        source_frame = test_frame[test_frame["series_name"] == "source"]
        gapfilled_frame = test_frame[test_frame["series_name"] == "gapfilled"]
        filled_frame = gapfilled_frame[gapfilled_frame["was_filled"].astype(bool)]

        charts.append(
            GapfillChart(
                test_name=test_name,
                truth_segments=_build_segments(truth_frame, start_time, end_time, y_min, y_span),
                source_segments=_build_segments(source_frame, start_time, end_time, y_min, y_span),
                gapfilled_segments=_build_segments(gapfilled_frame, start_time, end_time, y_min, y_span),
                filled_markers=_build_markers(filled_frame, start_time, end_time, y_min, y_span),
                start_label=_format_timestamp(start_time),
                end_label=_format_timestamp(end_time),
                y_min_label=_format_number(y_min),
                y_max_label=_format_number(y_max),
                filled_count=len(filled_frame),
            )
        )

    return charts


def _build_segments(
    frame: pd.DataFrame,
    start_time: pd.Timestamp,
    end_time: pd.Timestamp,
    y_min: float,
    y_span: float,
) -> list[str]:
    segments: list[str] = []
    current_points: list[str] = []

    for _, row in frame.sort_values("time").iterrows():
        value = row["value"]
        if pd.isna(value):
            if len(current_points) > 1:
                segments.append(" ".join(current_points))
            current_points = []
            continue
        current_points.append(_point_string(pd.Timestamp(row["time"]), float(value), start_time, end_time, y_min, y_span))

    if len(current_points) > 1:
        segments.append(" ".join(current_points))

    return segments


def _build_markers(
    frame: pd.DataFrame,
    start_time: pd.Timestamp,
    end_time: pd.Timestamp,
    y_min: float,
    y_span: float,
) -> list[GapfillChartMarker]:
    markers = []
    for _, row in frame.sort_values("time").iterrows():
        value = row["value"]
        if pd.isna(value):
            continue
        timestamp = pd.Timestamp(row["time"])
        x, y = _point(timestamp, float(value), start_time, end_time, y_min, y_span)
        markers.append(
            GapfillChartMarker(
                cx=f"{x:.2f}",
                cy=f"{y:.2f}",
                label=f"{_format_timestamp(timestamp)}: {_format_number(float(value))}",
            )
        )
    return markers


def _point_string(
    timestamp: pd.Timestamp,
    value: float,
    start_time: pd.Timestamp,
    end_time: pd.Timestamp,
    y_min: float,
    y_span: float,
) -> str:
    x, y = _point(timestamp, value, start_time, end_time, y_min, y_span)
    return f"{x:.2f},{y:.2f}"


def _point(
    timestamp: pd.Timestamp,
    value: float,
    start_time: pd.Timestamp,
    end_time: pd.Timestamp,
    y_min: float,
    y_span: float,
) -> tuple[float, float]:
    total_seconds = max((end_time - start_time).total_seconds(), 1.0)
    elapsed_seconds = max((timestamp - start_time).total_seconds(), 0.0)
    x = min(max(elapsed_seconds / total_seconds * 100.0, 0.0), 100.0)
    y = 38.0 - ((value - y_min) / y_span * 34.0)
    return x, min(max(y, 4.0), 38.0)


def _extract_checked_at(series: pd.DataFrame) -> str:
    if series.empty or "checked_at" not in series:
        return ""
    value = pd.to_datetime(series["checked_at"].iloc[0], utc=True)
    return _format_timestamp(value)


def _format_candidate_periods(periods: tuple[pd.Timedelta, ...] | None) -> str:
    if not periods:
        return "-"
    return ", ".join(_format_timedelta(period) for period in periods)


def _format_timedelta(value: pd.Timedelta) -> str:
    seconds = int(value.total_seconds())
    if seconds % 86400 == 0:
        return f"{seconds // 86400}d"
    if seconds % 3600 == 0:
        return f"{seconds // 3600}h"
    if seconds % 60 == 0:
        return f"{seconds // 60}min"
    return f"{seconds}s"


def _format_timestamp(value: pd.Timestamp) -> str:
    return value.strftime("%Y-%m-%d %H:%M UTC")


def _format_optional_number(value: float | None, *, suffix: str = "") -> str:
    if value is None:
        return "n/a"
    return f"{_format_number(value)}{suffix}"


def _format_number(value: float) -> str:
    if math.isclose(value, round(value), abs_tol=0.0001):
        return str(int(round(value)))
    return f"{value:.2f}".rstrip("0").rstrip(".")
