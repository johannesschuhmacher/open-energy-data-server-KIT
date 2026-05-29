# SPDX-FileCopyrightText: OpenAI
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import logging
import tempfile
import unittest
from unittest.mock import Mock

import pandas as pd
from crawler.entsoe_fms import EntsoeFMSCrawler


class _FakeFmsResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _FakeFmsSession:
    def __init__(self) -> None:
        self.posts: list[dict] = []

    def post(self, url: str, json: dict, timeout: int) -> _FakeFmsResponse:
        self.posts.append({"url": url, "json": json, "timeout": timeout})
        if len(self.posts) == 1:
            return _FakeFmsResponse(
                {"contentItemList": [{"name": "2026_04_file.csv", "fileId": "file-1"}]}
            )
        return _FakeFmsResponse({"contentItemList": []})


class _FakeSqlResult:
    def __init__(self, rows: list[tuple[bool]]):
        self.rows = rows

    def fetchone(self) -> tuple[bool]:
        return self.rows.pop(0)


class _FakeSqlConnection:
    def __init__(self) -> None:
        self.table_exists_results = [(False,), (True,)]

    def __enter__(self) -> "_FakeSqlConnection":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None

    def execute(self, query) -> _FakeSqlResult:
        return _FakeSqlResult(self.table_exists_results)


class _FakeSqlEngine:
    def __init__(self) -> None:
        self.connection = _FakeSqlConnection()

    def connect(self) -> _FakeSqlConnection:
        return self.connection


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

    def test_list_metadata_authenticates_when_session_is_missing(self) -> None:
        crawler = object.__new__(EntsoeFMSCrawler)
        crawler.session = None
        crawler.logger = logging.getLogger("test_entsoe_fms_package_refresh")
        fake_session = _FakeFmsSession()

        def authenticate() -> None:
            crawler.session = fake_session

        crawler._authenticate = authenticate

        metadata = crawler._list_metadata(
            "EnergyPrices_12.1.D_r3",
            pd.Timestamp("2026-04-01"),
            pd.Timestamp("2026-05-01"),
        )

        self.assertEqual(metadata, [{"name": "2026_04_file.csv", "fileId": "file-1"}])
        self.assertEqual(len(fake_session.posts), 2)
        self.assertEqual(fake_session.posts[0]["json"]["path"], "/TP_export/EnergyPrices_12.1.D_r3/")

    def test_backfill_metadata_errors_are_not_swallowed(self) -> None:
        crawler = object.__new__(EntsoeFMSCrawler)
        crawler.logger = logging.getLogger("test_entsoe_fms_package_refresh")
        crawler._list_metadata = Mock(side_effect=RuntimeError("metadata unavailable"))

        with self.assertRaisesRegex(RuntimeError, "Backward update failed while listing metadata"):
            crawler._load_backfill_metadata("EnergyPrices_12.1.D_r3")

    def test_backfill_creates_missing_table_before_insert(self) -> None:
        crawler = object.__new__(EntsoeFMSCrawler)
        crawler.engine = _FakeSqlEngine()
        crawler.logger = logging.getLogger("test_entsoe_fms_package_refresh")
        inserted_batches = []

        def download_file(file_id: str, target: str) -> None:
            pd.DataFrame(
                [
                    {
                        "InstanceCode": "1",
                        "DateTime(UTC)": "2026-04-01T00:00:00Z",
                        "ResolutionCode": "PT60M",
                        "AreaCode": "10Y1001A1001A83F",
                        "AreaDisplayName": "Germany",
                        "AreaTypeCode": "BZN",
                        "MapCode": "DE",
                        "ContractType": "A01",
                        "Sequence": "1",
                        "Price[Currency/MWh]": 42.0,
                        "Currency": "EUR",
                        "UpdateTime(UTC)": "2026-04-01T00:30:00Z",
                    }
                ]
            ).to_csv(target, sep="\t", index=False)

        crawler._download_file = download_file
        crawler._create_table_with_unique_constraint = Mock()
        crawler._insert_dataframe = lambda table_name, frame: inserted_batches.append((table_name, frame.copy()))

        with tempfile.TemporaryDirectory() as tmpdir:
            crawler._update_data_file(
                "EnergyPrices_12.1.D_r3",
                tmpdir,
                file_identifier="2026_04",
                logic_type="%Y_%m",
                metadata_entries=[
                    {"name": "2026_04_EnergyPrices_12.1.D_r3.csv", "fileId": "file-1"}
                ],
            )

        crawler._create_table_with_unique_constraint.assert_called_once_with("EnergyPrices")
        self.assertEqual(len(inserted_batches), 1)
        table_name, inserted = inserted_batches[0]
        self.assertEqual(table_name, "EnergyPrices")
        self.assertEqual(len(inserted), 1)


if __name__ == "__main__":
    unittest.main()
