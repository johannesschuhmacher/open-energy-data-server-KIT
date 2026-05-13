# SPDX-FileCopyrightText: OEDS Contributors
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import sys
import types
import unittest

dotenv_stub = types.ModuleType("dotenv")
dotenv_stub.load_dotenv = lambda *args, **kwargs: None
sys.modules.setdefault("dotenv", dotenv_stub)

from crawler_core import BaseCrawler, resolve_database_uri  # noqa: E402
from oeds_gapfill import GAPFILL_METHODS, SeriesFillConfig  # noqa: E402


class PublicFacadeTest(unittest.TestCase):
    def test_crawler_core_exports_runtime_helpers(self) -> None:
        self.assertTrue(callable(resolve_database_uri))
        self.assertTrue(issubclass(BaseCrawler, object))

    def test_oeds_gapfill_exports_core_types(self) -> None:
        self.assertIn("linear", GAPFILL_METHODS)
        config = SeriesFillConfig(
            table_name="Example",
            time_column="DateTime",
            value_columns=("Value",),
            groupby_columns=("Area",),
        )

        self.assertEqual(config.method, "donor_refined")


if __name__ == "__main__":
    unittest.main()
