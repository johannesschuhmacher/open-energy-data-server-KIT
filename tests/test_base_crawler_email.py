# SPDX-FileCopyrightText: OEDS Contributors
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import logging
import tempfile
import unittest
from logging.handlers import RotatingFileHandler, SMTPHandler
from pathlib import Path

from crawler.common.base_crawler import BaseCrawler, RateLimitedSMTPHandler


class CountingSMTPHandler(RateLimitedSMTPHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sent_records = 0

    def _emit_smtp(self, record):
        self.sent_records += 1


class DummyCrawler(BaseCrawler):
    def create_schema(self, schema_name: str) -> str:
        return schema_name

    def run(self):
        return None


def make_record() -> logging.LogRecord:
    return logging.LogRecord(
        name="test-crawler",
        level=logging.CRITICAL,
        pathname=__file__,
        lineno=1,
        msg="Crawler run FAILED",
        args=(),
        exc_info=None,
    )


class EmailAlertLimitTest(unittest.TestCase):
    def test_smtp_handler_rate_limit_persists_across_instances(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "email_alert_state.json"
            first_handler = CountingSMTPHandler(
                mailhost="smtp.example.test",
                fromaddr="from@example.test",
                toaddrs=["to@example.test"],
                subject="Critical",
                rate_limit_seconds=3600,
                rate_limit_key="entsoe_fms:Critical",
                state_file=state_file,
            )
            second_handler = CountingSMTPHandler(
                mailhost="smtp.example.test",
                fromaddr="from@example.test",
                toaddrs=["to@example.test"],
                subject="Critical",
                rate_limit_seconds=3600,
                rate_limit_key="entsoe_fms:Critical",
                state_file=state_file,
            )

            first_handler.emit(make_record())
            first_handler.emit(make_record())
            second_handler.emit(make_record())

            self.assertEqual(first_handler.sent_records, 1)
            self.assertEqual(second_handler.sent_records, 0)

    def test_base_crawler_does_not_add_duplicate_handlers(self) -> None:
        logger = logging.getLogger("dedupe_test_crawler")
        previous_handlers = list(logger.handlers)
        for handler in previous_handlers:
            logger.removeHandler(handler)

        config = {
            "database_uri": "sqlite:///",
            "schema_name": ":memory:",
            "schedule": "0 * * * *",
            "email": {
                "mailhost": "smtp.example.test",
                "fromaddr": "from@example.test",
                "toaddrs": ["to@example.test"],
                "subject": "OEDS Crawler :crawler_name Critical Error Notification",
                "username": "",
                "password": "",
                "rate_limit_minutes": 60,
            },
            "logging": {
                "max_bytes": 12345,
                "backup_count": 2,
            },
        }

        try:
            legacy_handler = SMTPHandler(
                mailhost="smtp.example.test",
                fromaddr="from@example.test",
                toaddrs=["to@example.test"],
                subject="OEDS Crawler dedupe_test_crawler Critical Error Notification",
            )
            logger.addHandler(legacy_handler)

            DummyCrawler("dedupe_test_crawler", config)
            DummyCrawler("dedupe_test_crawler", config)

            file_handlers = [
                handler
                for handler in logger.handlers
                if isinstance(handler, logging.FileHandler)
            ]
            smtp_handlers = [
                handler
                for handler in logger.handlers
                if isinstance(handler, RateLimitedSMTPHandler)
            ]

            self.assertEqual(len(file_handlers), 1)
            self.assertEqual(len(smtp_handlers), 1)
            self.assertIsInstance(file_handlers[0], RotatingFileHandler)
            self.assertEqual(file_handlers[0].maxBytes, 12345)
            self.assertEqual(file_handlers[0].backupCount, 2)
            self.assertNotIn(legacy_handler, logger.handlers)
        finally:
            for handler in list(logger.handlers):
                logger.removeHandler(handler)
                handler.close()
            for handler in previous_handlers:
                logger.addHandler(handler)


if __name__ == "__main__":
    unittest.main()
