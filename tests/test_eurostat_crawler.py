# SPDX-FileCopyrightText: OpenAI
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import unittest

from crawler.eurostat_crawler import (
    DEFAULT_TABLE_NAME,
    LEGACY_DATASET_ID,
    EurostatCrawler,
)


class EurostatCrawlerNamingTest(unittest.TestCase):
    def test_legacy_dataset_keeps_existing_table_name(self) -> None:
        crawler = object.__new__(EurostatCrawler)
        crawler.config = {}
        crawler.dataset_id = LEGACY_DATASET_ID

        self.assertEqual(crawler._resolve_table_name(), DEFAULT_TABLE_NAME)

    def test_non_legacy_dataset_uses_dataset_specific_table_name(self) -> None:
        crawler = object.__new__(EurostatCrawler)
        crawler.config = {}
        crawler.dataset_id = "nrg_bal_sd"

        self.assertEqual(crawler._resolve_table_name(), "eurostat_nrg_bal_sd")

    def test_explicit_table_name_override_is_sanitized(self) -> None:
        crawler = object.__new__(EurostatCrawler)
        crawler.config = {"table_name": "Eurostat Custom-Table"}
        crawler.dataset_id = LEGACY_DATASET_ID

        self.assertEqual(crawler._resolve_table_name(), "eurostat_custom_table")


if __name__ == "__main__":
    unittest.main()
