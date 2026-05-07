# SPDX-FileCopyrightText: OpenAI
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import unittest

from crawler_scheduler import (
    CrawlerJobQueue,
    ScheduledCrawlerJob,
    expand_crawler_job_configs,
    get_job_lock_keys,
)
from cron_converter import Cron


class DummyCrawler:
    pass


def make_job(job_name: str, lock_keys: set[str]) -> ScheduledCrawlerJob:
    return ScheduledCrawlerJob(
        crawler_name="dummy",
        job_name=job_name,
        crawler_class=DummyCrawler,
        config={"enable": True},
        schedule=Cron("0 * * * *"),
        lock_keys=frozenset(lock_keys),
    )


class SchedulerJobConfigTest(unittest.TestCase):
    def test_legacy_crawler_config_expands_to_default_job(self) -> None:
        configs = expand_crawler_job_configs(
            "weather_forecast",
            {
                "enable": True,
                "schema_name": "weather",
                "database_uri": "postgresql://example",
                "schedule": "15 */3 * * *",
                "post_run_scripts": ["scripts/example.py"],
            },
        )

        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0].job_name, "default")
        self.assertTrue(configs[0].enabled)
        self.assertEqual(configs[0].config["schema_name"], "weather")
        self.assertEqual(configs[0].config["post_run_scripts"], ["scripts/example.py"])

    def test_multi_job_config_expands_with_inherited_values(self) -> None:
        configs = expand_crawler_job_configs(
            "entsoe_fms",
            {
                "enable": True,
                "schema_name": "entsoe_fms",
                "database_uri": "postgresql://example",
                "post_run_scripts": ["scripts/gapfill_timeseries.py"],
                "jobs": {
                    "latest_hourly": {
                        "enable": True,
                        "schedule": "0 * * * *",
                        "fms_package_window_months": 1,
                    },
                    "revision_sweep_daily": {
                        "enable": True,
                        "schedule": "30 2 * * *",
                        "fms_package_window_months": 3,
                    },
                },
            },
        )

        self.assertEqual([config.job_name for config in configs], ["latest_hourly", "revision_sweep_daily"])
        self.assertEqual(configs[0].config["schema_name"], "entsoe_fms")
        self.assertEqual(configs[0].config["post_run_scripts"], ["scripts/gapfill_timeseries.py"])
        self.assertEqual(configs[0].config["fms_package_window_months"], 1)
        self.assertEqual(configs[1].config["fms_package_window_months"], 3)

    def test_entsoe_lock_keys_are_table_based(self) -> None:
        class DummyEntsoeCrawler:
            DATA_ITEM_TABLE_MAP = {
                "ActualTotalLoad_6.1.A_r3": "ActualTotalLoad",
                "EnergyPrices_12.1.D_r3": "EnergyPrices",
            }

        lock_keys = get_job_lock_keys(
            "entsoe_fms",
            {"target_data_items": ["ActualTotalLoad_6.1.A_r3"]},
            DummyEntsoeCrawler,
        )

        self.assertEqual(lock_keys, frozenset({"entsoe_fms:ActualTotalLoad"}))


class SchedulerJobQueueTest(unittest.TestCase):
    def test_identical_job_is_not_queued_twice(self) -> None:
        queue = CrawlerJobQueue()
        job = make_job("latest_hourly", {"table:a"})

        self.assertTrue(queue.enqueue(job, job.next_run_time))
        self.assertFalse(queue.enqueue(job, job.next_run_time))

        ready = queue.pop_ready_jobs()
        self.assertEqual([queued.job.job_name for queued in ready], ["latest_hourly"])
        self.assertFalse(queue.enqueue(job, job.next_run_time))

        queue.mark_finished(job)
        self.assertTrue(queue.enqueue(job, job.next_run_time))

    def test_conflicting_jobs_wait_for_active_lock(self) -> None:
        queue = CrawlerJobQueue()
        first = make_job("latest_hourly", {"table:a"})
        second = make_job("revision_sweep_daily", {"table:a"})

        queue.enqueue(first, first.next_run_time)
        queue.enqueue(second, second.next_run_time)

        ready = queue.pop_ready_jobs()
        self.assertEqual([queued.job.job_name for queued in ready], ["latest_hourly"])
        self.assertEqual(queue.pop_ready_jobs(), [])

        queue.mark_finished(first)
        ready = queue.pop_ready_jobs()
        self.assertEqual([queued.job.job_name for queued in ready], ["revision_sweep_daily"])

    def test_non_conflicting_jobs_can_start_together(self) -> None:
        queue = CrawlerJobQueue()
        first = make_job("prices", {"table:prices"})
        second = make_job("load", {"table:load"})

        queue.enqueue(first, first.next_run_time)
        queue.enqueue(second, second.next_run_time)

        ready = queue.pop_ready_jobs()
        self.assertEqual({queued.job.job_name for queued in ready}, {"prices", "load"})


if __name__ == "__main__":
    unittest.main()
