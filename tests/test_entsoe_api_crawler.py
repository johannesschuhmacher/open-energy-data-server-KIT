# SPDX-FileCopyrightText: OpenAI
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import unittest
from unittest.mock import patch

import pandas as pd
from crawler.entsoe_api import (
    DATASET_DAY_AHEAD_PRICES,
    DATASET_EXAA_PRICES,
    EntsoeApiCrawler,
)


class EntsoeApiCrawlerTransformTest(unittest.TestCase):
    def test_price_series_to_frame_normalizes_to_utc_delivery_intervals(self) -> None:
        index = pd.date_range(
            "2026-01-01 00:00",
            periods=2,
            freq="15min",
            tz="Europe/Berlin",
        )
        series = pd.Series([12.5, 13.75], index=index)

        frame = EntsoeApiCrawler._price_series_to_frame(
            series,
            market_area="DE_LU",
            sequence=2,
            source_market="EXAA",
        )

        self.assertEqual(len(frame), 2)
        self.assertEqual(frame["market_area"].tolist(), ["DE_LU", "DE_LU"])
        self.assertEqual(frame["sequence"].tolist(), [2, 2])
        self.assertEqual(frame["source_market"].tolist(), ["EXAA", "EXAA"])
        self.assertEqual(frame["price_eur_mwh"].tolist(), [12.5, 13.75])
        self.assertEqual(str(frame["delivery_start_utc"].iloc[0]), "2025-12-31 23:00:00+00:00")
        self.assertEqual(str(frame["delivery_end_utc"].iloc[1]), "2025-12-31 23:30:00+00:00")

    def test_wide_forecast_to_frame_melts_columns(self) -> None:
        index = pd.date_range(
            "2026-01-01 00:00",
            periods=2,
            freq="h",
            tz="Europe/Berlin",
        )
        source = pd.DataFrame(
            {
                "Forecasted Load": [50000.0, 51000.0],
                "Actual Load": [49900.0, None],
            },
            index=index,
        )

        frame = EntsoeApiCrawler._wide_forecast_to_frame(
            source,
            market_area="DE_LU",
            process_type="A01",
            value_column="load_mw",
            label_column="metric",
        )

        self.assertEqual(len(frame), 3)
        self.assertEqual(set(frame["metric"]), {"Forecasted Load", "Actual Load"})
        self.assertEqual(frame["market_area"].unique().tolist(), ["DE_LU"])
        self.assertEqual(frame["process_type"].unique().tolist(), ["A01"])
        self.assertEqual(str(frame["delivery_start_utc"].min()), "2025-12-31 23:00:00+00:00")

    def test_enabled_datasets_can_be_restricted(self) -> None:
        crawler = object.__new__(EntsoeApiCrawler)
        crawler.config = {
            "target_datasets": [
                DATASET_DAY_AHEAD_PRICES,
                DATASET_EXAA_PRICES,
            ]
        }

        self.assertEqual(
            crawler._enabled_datasets(),
            {DATASET_DAY_AHEAD_PRICES, DATASET_EXAA_PRICES},
        )

    def test_enabled_datasets_rejects_unknown_values(self) -> None:
        crawler = object.__new__(EntsoeApiCrawler)
        crawler.config = {"target_datasets": ["unknown"]}

        with self.assertRaises(ValueError):
            crawler._enabled_datasets()

    def test_api_key_accepts_entsoe_api_alias(self) -> None:
        crawler = object.__new__(EntsoeApiCrawler)
        crawler.config = {}

        with patch.dict("os.environ", {"ENTSOE_API": "token-from-alias"}, clear=True):
            self.assertEqual(crawler._api_key(), "token-from-alias")


if __name__ == "__main__":
    unittest.main()
