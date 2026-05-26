# SPDX-FileCopyrightText: OEDS Contributors
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import logging
import unittest
from unittest.mock import patch

import pandas as pd
from crawler.entsoe_fms import EntsoeFMSCrawler
from sqlalchemy.exc import IntegrityError


class EntsoeFMSInsertTest(unittest.TestCase):
    def make_crawler(self) -> EntsoeFMSCrawler:
        crawler = EntsoeFMSCrawler.__new__(EntsoeFMSCrawler)
        crawler.engine = object()
        crawler.logger = logging.getLogger("test_entsoe_fms_insert")
        crawler.upserted_batches = []

        def capture_upsert(table_name: str, frame: pd.DataFrame) -> None:
            crawler.upserted_batches.append((table_name, frame.copy()))

        crawler._upsert_dataframe = capture_upsert
        return crawler

    def make_actual_total_load_frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "DateTime(UTC)": pd.Timestamp("2026-05-26T10:00:00Z"),
                    "ResolutionCode": "PT60M",
                    "AreaDisplayName": "Austria (AT)",
                    "AreaTypeCode": "BZN/CTA/CTY",
                    "Value": 123.0,
                }
            ]
        )

    def test_insert_dataframe_upserts_when_pandas_wraps_integrity_error(self) -> None:
        crawler = self.make_crawler()

        def raise_wrapped_integrity_error(*args, **kwargs) -> None:
            raise pd.errors.DatabaseError("wrapped duplicate key") from IntegrityError(
                "INSERT",
                {},
                RuntimeError("duplicate key"),
            )

        with patch.object(pd.DataFrame, "to_sql", raise_wrapped_integrity_error):
            crawler._insert_dataframe("ActualTotalLoad", self.make_actual_total_load_frame())

        self.assertEqual(len(crawler.upserted_batches), 1)
        table_name, upserted_frame = crawler.upserted_batches[0]
        self.assertEqual(table_name, "ActualTotalLoad")
        self.assertEqual(len(upserted_frame), 1)

    def test_insert_dataframe_reraises_non_integrity_database_errors(self) -> None:
        crawler = self.make_crawler()

        with patch.object(pd.DataFrame, "to_sql", side_effect=pd.errors.DatabaseError("connection lost")):
            with self.assertRaises(pd.errors.DatabaseError):
                crawler._insert_dataframe("ActualTotalLoad", self.make_actual_total_load_frame())

        self.assertEqual(crawler.upserted_batches, [])


if __name__ == "__main__":
    unittest.main()
