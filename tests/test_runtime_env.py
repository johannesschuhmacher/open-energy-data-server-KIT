# SPDX-FileCopyrightText: OpenAI
#
# SPDX-License-Identifier: AGPL-3.0-or-later

import os
import sys
import types
import unittest
from unittest.mock import patch

dotenv_stub = types.ModuleType("dotenv")
dotenv_stub.load_dotenv = lambda *args, **kwargs: None
sys.modules.setdefault("dotenv", dotenv_stub)

from crawler_core.runtime_env import resolve_database_uri  # noqa: E402


class ResolveDatabaseUriTest(unittest.TestCase):
    def test_returns_original_uri_without_overrides(self):
        uri = "postgresql://opendata:opendata@localhost:6432/opendata?options=--search_path="

        with patch.dict(os.environ, {}, clear=False):
            self.assertEqual(resolve_database_uri(uri), uri)

    def test_overrides_password_without_changing_host_or_port(self):
        uri = "postgresql://opendata:opendata@localhost:6432/opendata?options=--search_path="

        with patch.dict(os.environ, {"OEDS_DB_PASSWORD": "pa:ss@word/1"}, clear=False):
            self.assertEqual(
                resolve_database_uri(uri),
                "postgresql://opendata:pa%3Ass%40word%2F1@localhost:6432/opendata?options=--search_path=",
            )

    def test_overrides_host_port_and_password_together(self):
        uri = "postgresql://opendata:opendata@localhost:6432/opendata?options=--search_path="

        with patch.dict(
            os.environ,
            {
                "OEDS_DB_HOST": "open-data",
                "OEDS_DB_PORT": "5432",
                "OEDS_DB_PASSWORD": "new secret",
            },
            clear=False,
        ):
            self.assertEqual(
                resolve_database_uri(uri),
                "postgresql://opendata:new%20secret@open-data:5432/opendata?options=--search_path=",
            )


if __name__ == "__main__":
    unittest.main()
