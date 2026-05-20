# SPDX-FileCopyrightText: OpenAI
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import unittest
from datetime import datetime

from crawler.smard import SmardCrawler
from sqlalchemy import Column, DateTime, Float, MetaData, String, Table
from sqlalchemy.dialects import postgresql


class SmardCrawlerUpsertTest(unittest.TestCase):
    def test_build_upsert_statement_updates_price_on_conflict(self) -> None:
        table = Table(
            "prices",
            MetaData(),
            Column("timestamp", DateTime, primary_key=True),
            Column("commodity_id", String, primary_key=True),
            Column("price", Float),
            schema="smard",
        )
        statement = SmardCrawler._build_upsert_statement(
            table,
            [
                {
                    "timestamp": datetime(2026, 1, 1, 0, 0, 0),
                    "commodity_id": "4169",
                    "price": 12.5,
                }
            ],
            ("price",),
        )

        compiled = str(
            statement.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )

        self.assertIn("ON CONFLICT (timestamp, commodity_id) DO UPDATE", compiled)
        self.assertIn("price = excluded.price", compiled)


if __name__ == "__main__":
    unittest.main()
