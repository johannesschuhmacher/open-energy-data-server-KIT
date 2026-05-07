# SPDX-FileCopyrightText: OpenAI
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import unittest

import pandas as pd
from crawler.entsoe_fms import EntsoeFMSCrawler


class EntsoeFMSPackageRefreshTest(unittest.TestCase):
    def test_one_month_window_starts_at_current_month(self) -> None:
        end_time = pd.Timestamp("2026-05-07T12:15:00", tz="Europe/Berlin")

        start_time = EntsoeFMSCrawler.calculate_package_window_start(end_time, 1)

        self.assertEqual(start_time, pd.Timestamp("2026-05-01T00:00:00", tz="Europe/Berlin"))

    def test_three_month_window_includes_current_and_two_previous_months(self) -> None:
        end_time = pd.Timestamp("2026-05-07T12:15:00", tz="Europe/Berlin")

        start_time = EntsoeFMSCrawler.calculate_package_window_start(end_time, 3)

        self.assertEqual(start_time, pd.Timestamp("2026-03-01T00:00:00", tz="Europe/Berlin"))

    def test_full_package_upsert_keeps_rows_older_than_global_update_watermark(self) -> None:
        crawler = object.__new__(EntsoeFMSCrawler)
        dataframe = pd.DataFrame(
            {
                "DateTime(UTC)": pd.to_datetime(
                    ["2026-05-01T00:00:00Z", "2026-05-01T01:00:00Z"]
                ),
                "ResolutionCode": ["PT60M", "PT60M"],
                "AreaDisplayName": ["Germany", "Germany"],
                "AreaTypeCode": ["CTY", "CTY"],
                "TotalLoad[MW]": [50000.0, 51000.0],
                "UpdateTime(UTC)": pd.to_datetime(
                    ["2026-05-01T00:20:00Z", "2026-05-01T01:20:00Z"]
                ),
            }
        )

        inserts, upserts = crawler._split_package_refresh_chunk("ActualTotalLoad", dataframe)

        self.assertTrue(inserts.empty)
        self.assertEqual(len(upserts), 2)
        self.assertEqual(upserts["TotalLoad[MW]"].tolist(), [50000.0, 51000.0])


if __name__ == "__main__":
    unittest.main()
