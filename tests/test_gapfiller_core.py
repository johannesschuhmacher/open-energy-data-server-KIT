# SPDX-FileCopyrightText: OpenAI
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd
from scripts.lib.gapfiller.core import SeriesFillConfig, fill_table, infer_frequency
from scripts.lib.gapfiller.selftest import run_self_tests


class GapfillerCoreTest(unittest.TestCase):
    def test_infer_frequency_uses_median_delta(self) -> None:
        index = pd.DatetimeIndex([
            "2026-01-01T00:00:00Z",
            "2026-01-01T01:00:00Z",
            "2026-01-01T02:00:00Z",
            "2026-01-01T05:00:00Z",
        ])

        self.assertEqual(infer_frequency(index), pd.Timedelta(hours=1))

    def test_linear_gap_fill_fills_short_internal_nan_gap(self) -> None:
        dataframe = pd.DataFrame({
            "DateTime": pd.date_range("2026-01-01", periods=8, freq="h", tz="UTC"),
            "Value": [0.0, 1.0, np.nan, np.nan, 4.0, 5.0, 6.0, 7.0],
            "Area": "DE",
        })
        config = SeriesFillConfig(
            table_name="Example",
            time_column="DateTime",
            value_columns=("Value",),
            groupby_columns=("Area",),
            max_gap_periods=4,
        )

        result = fill_table(dataframe, config, "run-1", pd.Timestamp("2026-01-02T00:00:00Z"))

        self.assertEqual(result.metrics[0].filled_values, 2)
        self.assertEqual(result.metrics[0].missing_after, 0)
        filled = result.dataframe.set_index("DateTime")
        self.assertEqual(filled.loc[pd.Timestamp("2026-01-01T02:00:00Z"), "Value"], 2.0)
        self.assertEqual(filled.loc[pd.Timestamp("2026-01-01T03:00:00Z"), "Value"], 3.0)

    def test_missing_timestamps_are_created_and_filled(self) -> None:
        full_index = pd.date_range("2026-01-01", periods=8, freq="h", tz="UTC")
        dataframe = pd.DataFrame({
            "DateTime": full_index.delete([3, 4]),
            "Value": np.delete(np.arange(8, dtype=float), [3, 4]),
            "Area": "DE",
        })
        config = SeriesFillConfig(
            table_name="Example",
            time_column="DateTime",
            value_columns=("Value",),
            groupby_columns=("Area",),
            max_gap_periods=4,
        )

        result = fill_table(dataframe, config, "run-1", pd.Timestamp("2026-01-02T00:00:00Z"))

        self.assertEqual(len(result.dataframe), 8)
        self.assertEqual(result.metrics[0].created_gap_rows, 2)
        self.assertEqual(result.metrics[0].filled_values, 2)
        self.assertEqual(int(result.dataframe["gapfill_created_row"].sum()), 2)

    def test_large_gap_above_limit_is_left_unfilled(self) -> None:
        dataframe = pd.DataFrame({
            "DateTime": pd.date_range("2026-01-01", periods=10, freq="h", tz="UTC"),
            "Value": [0.0, 1.0, np.nan, np.nan, np.nan, np.nan, 6.0, 7.0, 8.0, 9.0],
            "Area": "DE",
        })
        config = SeriesFillConfig(
            table_name="Example",
            time_column="DateTime",
            value_columns=("Value",),
            groupby_columns=("Area",),
            max_gap_periods=3,
        )

        result = fill_table(dataframe, config, "run-1", pd.Timestamp("2026-01-02T00:00:00Z"))

        self.assertEqual(result.metrics[0].filled_values, 0)
        self.assertEqual(result.metrics[0].missing_after, 4)

    def test_multi_value_table_is_filled_in_one_output(self) -> None:
        dataframe = pd.DataFrame({
            "DateTime": pd.date_range("2026-01-01", periods=8, freq="h", tz="UTC"),
            "Generation": [0.0, 1.0, np.nan, 3.0, 4.0, 5.0, 6.0, 7.0],
            "Consumption": [10.0, 11.0, 12.0, 13.0, np.nan, np.nan, 16.0, 17.0],
            "Area": "DE",
        })
        config = SeriesFillConfig(
            table_name="Example",
            time_column="DateTime",
            value_columns=("Generation", "Consumption"),
            groupby_columns=("Area",),
            max_gap_periods=4,
        )

        result = fill_table(dataframe, config, "run-1", pd.Timestamp("2026-01-02T00:00:00Z"))

        metrics = {metric.value_column: metric for metric in result.metrics}
        self.assertEqual(metrics["Generation"].filled_values, 1)
        self.assertEqual(metrics["Consumption"].filled_values, 2)
        self.assertIn("Generation", result.dataframe.columns)
        self.assertIn("Consumption", result.dataframe.columns)

    def test_previous_period_method_uses_donor_from_prior_day(self) -> None:
        index = pd.date_range("2026-01-01", periods=48, freq="h", tz="UTC")
        values = np.arange(48, dtype=float)
        values[30] = np.nan
        dataframe = pd.DataFrame({
            "DateTime": index,
            "Value": values,
            "Area": "DE",
        })
        config = SeriesFillConfig(
            table_name="Example",
            time_column="DateTime",
            value_columns=("Value",),
            groupby_columns=("Area",),
            method="previous_period",
            period=pd.Timedelta(hours=24),
            max_gap_periods=2,
        )

        result = fill_table(dataframe, config, "run-1", pd.Timestamp("2026-01-03T00:00:00Z"))
        filled = result.dataframe.set_index("DateTime")

        self.assertEqual(filled.loc[index[30], "Value"], 6.0)

    def test_builtin_self_tests_pass(self) -> None:
        _, results, series = run_self_tests()

        self.assertTrue(results)
        self.assertTrue(all(result.status == "passed" for result in results))
        self.assertFalse(series.empty)


if __name__ == "__main__":
    unittest.main()
