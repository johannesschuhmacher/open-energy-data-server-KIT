# SPDX-FileCopyrightText: OpenAI
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

GapfillMethod = Literal["linear", "previous_period", "seasonal_linear"]

METADATA_COLUMNS = (
    "gapfill_run_id",
    "gapfill_method",
    "gapfill_created_row",
    "gapfill_filled_columns",
    "gapfill_updated_at",
)


@dataclass(frozen=True)
class SeriesFillConfig:
    table_name: str
    time_column: str
    value_columns: tuple[str, ...]
    groupby_columns: tuple[str, ...]
    method: GapfillMethod = "linear"
    resolution: pd.Timedelta | None = None
    period: pd.Timedelta = pd.Timedelta(hours=24)
    max_gap_periods: int = 24
    min_points: int = 3


@dataclass(frozen=True)
class GroupMetric:
    table_name: str
    value_column: str
    group_key: str
    method: str
    source_rows: int
    output_rows: int
    expected_rows: int
    created_gap_rows: int
    missing_before: int
    missing_after: int
    filled_values: int
    start_time: pd.Timestamp | None
    end_time: pd.Timestamp | None
    status: str
    error_message: str | None = None


@dataclass(frozen=True)
class TableFillResult:
    dataframe: pd.DataFrame
    metrics: list[GroupMetric]


def slugify_column(name: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z]+", "_", name).strip("_").lower()
    return slug or "value"


def group_key_from_values(groupby_columns: tuple[str, ...], values: dict[str, object]) -> str:
    if not groupby_columns:
        return "__all__"
    tokens = []
    for column in groupby_columns:
        value = values.get(column)
        if pd.isna(value):
            value = "<null>"
        tokens.append(f"{column}={value}")
    return "|".join(tokens)


def infer_frequency(index: pd.DatetimeIndex) -> pd.Timedelta | None:
    clean_index = pd.DatetimeIndex(pd.Series(index).dropna().sort_values().unique())
    if len(clean_index) < 2:
        return None

    diffs = clean_index.to_series().diff().dropna()
    diffs = diffs[diffs > pd.Timedelta(0)]
    if diffs.empty:
        return None

    median = diffs.median()
    if median <= pd.Timedelta(0) or pd.isna(median):
        return None

    seconds = max(1, int(round(median.total_seconds())))
    return pd.Timedelta(seconds=seconds)


def fill_table(
    dataframe: pd.DataFrame,
    config: SeriesFillConfig,
    run_id: str,
    run_timestamp: pd.Timestamp | None = None,
) -> TableFillResult:
    if dataframe.empty:
        return TableFillResult(dataframe=_empty_output(dataframe), metrics=[])

    _validate_columns(dataframe, config)
    run_timestamp = run_timestamp or pd.Timestamp.now(tz="UTC")

    prepared = dataframe.copy()
    prepared[config.time_column] = pd.to_datetime(prepared[config.time_column], utc=True, errors="coerce")
    prepared = prepared.dropna(subset=[config.time_column])

    if prepared.empty:
        return TableFillResult(dataframe=_empty_output(dataframe), metrics=[])

    if config.groupby_columns:
        grouped = prepared.groupby(list(config.groupby_columns), dropna=False, sort=False)
        group_items = grouped
    else:
        group_items = [((), prepared)]

    outputs: list[pd.DataFrame] = []
    metrics: list[GroupMetric] = []

    for group_values_raw, group_df in group_items:
        group_values = _normalise_group_values(config.groupby_columns, group_values_raw, group_df)
        group_result = fill_group(group_df, config, run_id, run_timestamp, group_values)
        outputs.append(group_result.dataframe)
        metrics.extend(group_result.metrics)

    if not outputs:
        return TableFillResult(dataframe=_empty_output(dataframe), metrics=metrics)

    output = pd.concat(outputs, ignore_index=True)
    output = output.sort_values([*config.groupby_columns, config.time_column], kind="stable").reset_index(drop=True)
    return TableFillResult(dataframe=output, metrics=metrics)


def fill_group(
    dataframe: pd.DataFrame,
    config: SeriesFillConfig,
    run_id: str,
    run_timestamp: pd.Timestamp,
    group_values: dict[str, object],
) -> TableFillResult:
    group_key = group_key_from_values(config.groupby_columns, group_values)
    group_df = dataframe.copy()
    group_df = group_df.sort_values(config.time_column, kind="stable")
    group_df = group_df.drop_duplicates(subset=[config.time_column], keep="last")

    source_rows = len(group_df)
    if source_rows < config.min_points:
        output = _with_metadata(group_df, config, run_id, run_timestamp, False, [])
        metrics = [
            _metric(
                config=config,
                value_column=value_column,
                group_key=group_key,
                method=config.method,
                source_rows=source_rows,
                output_rows=len(output),
                expected_rows=len(output),
                created_gap_rows=0,
                missing_before=int(group_df[value_column].isna().sum()),
                missing_after=int(group_df[value_column].isna().sum()),
                filled_values=0,
                start_time=_timestamp_or_none(group_df[config.time_column].min()),
                end_time=_timestamp_or_none(group_df[config.time_column].max()),
                status="skipped_insufficient_points",
            )
            for value_column in config.value_columns
        ]
        return TableFillResult(dataframe=output, metrics=metrics)

    indexed = group_df.set_index(config.time_column).sort_index()
    frequency = config.resolution or infer_frequency(pd.DatetimeIndex(indexed.index))
    if frequency is None:
        output = _with_metadata(group_df, config, run_id, run_timestamp, False, [])
        metrics = [
            _metric(
                config=config,
                value_column=value_column,
                group_key=group_key,
                method=config.method,
                source_rows=source_rows,
                output_rows=len(output),
                expected_rows=len(output),
                created_gap_rows=0,
                missing_before=int(group_df[value_column].isna().sum()),
                missing_after=int(group_df[value_column].isna().sum()),
                filled_values=0,
                start_time=_timestamp_or_none(group_df[config.time_column].min()),
                end_time=_timestamp_or_none(group_df[config.time_column].max()),
                status="skipped_no_frequency",
            )
            for value_column in config.value_columns
        ]
        return TableFillResult(dataframe=output, metrics=metrics)

    full_index = pd.date_range(indexed.index.min(), indexed.index.max(), freq=frequency)
    expanded = indexed.reindex(full_index)
    created_mask = ~expanded.index.isin(indexed.index)

    for column, value in group_values.items():
        expanded[column] = value

    for column in expanded.columns:
        if column in config.value_columns or column in config.groupby_columns:
            continue
        if column.startswith("gapfill_"):
            continue
        if pd.api.types.is_datetime64_any_dtype(expanded[column]):
            continue
        expanded[column] = expanded[column].ffill().bfill()

    filled_columns_by_row: dict[pd.Timestamp, list[str]] = {timestamp: [] for timestamp in expanded.index}
    metrics: list[GroupMetric] = []

    for value_column in config.value_columns:
        series = pd.to_numeric(expanded[value_column], errors="coerce")
        missing_before_mask = series.isna()
        missing_before = int(missing_before_mask.sum())

        candidate = _build_fill_candidate(series, config.method, config.period)
        eligible_mask = _eligible_missing_mask(missing_before_mask, config.max_gap_periods)
        filled_mask = missing_before_mask & eligible_mask & candidate.notna()

        expanded.loc[filled_mask, value_column] = candidate.loc[filled_mask]
        for timestamp in expanded.index[filled_mask]:
            filled_columns_by_row[timestamp].append(value_column)

        missing_after = int(pd.to_numeric(expanded[value_column], errors="coerce").isna().sum())
        metrics.append(
            _metric(
                config=config,
                value_column=value_column,
                group_key=group_key,
                method=config.method,
                source_rows=source_rows,
                output_rows=len(expanded),
                expected_rows=len(full_index),
                created_gap_rows=int(created_mask.sum()),
                missing_before=missing_before,
                missing_after=missing_after,
                filled_values=int(filled_mask.sum()),
                start_time=_timestamp_or_none(full_index.min()),
                end_time=_timestamp_or_none(full_index.max()),
                status="ok",
            )
        )

    output = expanded.reset_index(names=config.time_column)
    output["gapfill_run_id"] = run_id
    output["gapfill_method"] = config.method
    output["gapfill_created_row"] = created_mask
    output["gapfill_filled_columns"] = [
        ",".join(filled_columns_by_row.get(timestamp, [])) for timestamp in expanded.index
    ]
    output["gapfill_updated_at"] = run_timestamp

    return TableFillResult(dataframe=output, metrics=metrics)


def _validate_columns(dataframe: pd.DataFrame, config: SeriesFillConfig) -> None:
    required = {config.time_column, *config.value_columns, *config.groupby_columns}
    missing = sorted(required - set(dataframe.columns))
    if missing:
        raise ValueError(f"Missing columns for {config.table_name}: {missing}")


def _normalise_group_values(
    groupby_columns: tuple[str, ...],
    raw_values: object,
    group_df: pd.DataFrame,
) -> dict[str, object]:
    if not groupby_columns:
        return {}

    if len(groupby_columns) == 1:
        values = raw_values if isinstance(raw_values, tuple) else (raw_values,)
    elif isinstance(raw_values, tuple):
        values = raw_values
    else:
        values = tuple(group_df.iloc[0][column] for column in groupby_columns)

    return dict(zip(groupby_columns, values, strict=True))


def _build_fill_candidate(
    series: pd.Series,
    method: GapfillMethod,
    period: pd.Timedelta,
) -> pd.Series:
    linear = series.interpolate(method="time", limit_area="inside")
    if method == "linear":
        return linear

    previous_period = _previous_period_candidate(series, period)
    if method == "previous_period":
        return previous_period.combine_first(linear)

    if method == "seasonal_linear":
        both = previous_period.notna() & linear.notna()
        candidate = previous_period.combine_first(linear)
        candidate.loc[both] = 0.7 * previous_period.loc[both] + 0.3 * linear.loc[both]
        return candidate

    raise ValueError(f"Unsupported gapfill method: {method}")


def _previous_period_candidate(series: pd.Series, period: pd.Timedelta) -> pd.Series:
    candidate = pd.Series(np.nan, index=series.index, dtype="float64")
    missing_index = series.index[series.isna()]
    values = series.dropna()
    if values.empty:
        return candidate

    for timestamp in missing_index:
        donor_timestamp = timestamp - period
        if donor_timestamp in values.index:
            candidate.loc[timestamp] = values.loc[donor_timestamp]
    return candidate


def _eligible_missing_mask(missing_mask: pd.Series, max_gap_periods: int) -> pd.Series:
    if max_gap_periods <= 0:
        return pd.Series(False, index=missing_mask.index)

    eligible = pd.Series(False, index=missing_mask.index)
    positions = np.flatnonzero(missing_mask.to_numpy())
    if len(positions) == 0:
        return eligible

    start = positions[0]
    previous = positions[0]
    for position in positions[1:]:
        if position != previous + 1:
            _mark_gap_if_eligible(eligible, start, previous, max_gap_periods)
            start = position
        previous = position
    _mark_gap_if_eligible(eligible, start, previous, max_gap_periods)
    return eligible


def _mark_gap_if_eligible(eligible: pd.Series, start: int, end: int, max_gap_periods: int) -> None:
    length = end - start + 1
    if length <= max_gap_periods:
        eligible.iloc[start : end + 1] = True


def _with_metadata(
    dataframe: pd.DataFrame,
    config: SeriesFillConfig,
    run_id: str,
    run_timestamp: pd.Timestamp,
    created_row: bool,
    filled_columns: list[str],
) -> pd.DataFrame:
    output = dataframe.copy()
    output["gapfill_run_id"] = run_id
    output["gapfill_method"] = config.method
    output["gapfill_created_row"] = created_row
    output["gapfill_filled_columns"] = ",".join(filled_columns)
    output["gapfill_updated_at"] = run_timestamp
    return output


def _metric(
    *,
    config: SeriesFillConfig,
    value_column: str,
    group_key: str,
    method: str,
    source_rows: int,
    output_rows: int,
    expected_rows: int,
    created_gap_rows: int,
    missing_before: int,
    missing_after: int,
    filled_values: int,
    start_time: pd.Timestamp | None,
    end_time: pd.Timestamp | None,
    status: str,
    error_message: str | None = None,
) -> GroupMetric:
    return GroupMetric(
        table_name=config.table_name,
        value_column=value_column,
        group_key=group_key,
        method=method,
        source_rows=int(source_rows),
        output_rows=int(output_rows),
        expected_rows=int(expected_rows),
        created_gap_rows=int(created_gap_rows),
        missing_before=int(missing_before),
        missing_after=int(missing_after),
        filled_values=int(filled_values),
        start_time=start_time,
        end_time=end_time,
        status=status,
        error_message=error_message,
    )


def _timestamp_or_none(value: object) -> pd.Timestamp | None:
    if value is None or pd.isna(value):
        return None
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        return timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC")


def _empty_output(dataframe: pd.DataFrame) -> pd.DataFrame:
    output = dataframe.copy()
    for column in METADATA_COLUMNS:
        if column not in output.columns:
            output[column] = None
    return output


def serialise_metric(metric: GroupMetric) -> dict[str, object]:
    row = metric.__dict__.copy()
    for key in ("start_time", "end_time"):
        value = row[key]
        if value is not None and not (isinstance(value, float) and math.isnan(value)):
            row[key] = pd.Timestamp(value).isoformat()
    return row
