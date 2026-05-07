# SPDX-FileCopyrightText: Johannes Schuhmacher, Andre Meyer, Haoshen Zhang
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import time
import traceback
from collections import deque
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from inspect import isclass
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Any

import yaml
from crawler.common.base_crawler import BaseCrawler
from crawler.common.local_env import apply_email_env_overrides
from crawler.common.runtime_env import load_local_crawler_env
from cron_converter import Cron
from watchdog.events import (
    EVENT_TYPE_CREATED,
    EVENT_TYPE_MODIFIED,
    EVENT_TYPE_MOVED,
    FileSystemEventHandler,
)
from watchdog.observers import Observer

CONFIG_FILENAME = "CRAWLER_CONFIG.yml"
configChanged = False


@dataclass(frozen=True)
class CrawlerJobConfig:
    crawler_name: str
    job_name: str
    config: dict[str, Any]
    schedule: Cron

    @property
    def job_id(self) -> str:
        return f"{self.crawler_name}:{self.job_name}"

    @property
    def display_name(self) -> str:
        if self.job_name == "default":
            return self.crawler_name
        return self.job_id

    @property
    def enabled(self) -> bool:
        return self.config.get("enable") is True


@dataclass
class ScheduledCrawlerJob:
    crawler_name: str
    job_name: str
    crawler_class: type[BaseCrawler]
    config: dict[str, Any]
    schedule: Cron
    lock_keys: frozenset[str]
    next_run_time: datetime = field(init=False)

    def __post_init__(self) -> None:
        self.advance_after(datetime.now())

    @property
    def job_id(self) -> str:
        return f"{self.crawler_name}:{self.job_name}"

    @property
    def display_name(self) -> str:
        if self.job_name == "default":
            return self.crawler_name
        return self.job_id

    @property
    def run_post_scripts(self) -> bool:
        return self.config.get("run_post_scripts", True) is not False

    def advance_after(self, ref_time: datetime) -> None:
        self.next_run_time = self.schedule.schedule(ref_time).next()

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, ScheduledCrawlerJob):
            raise NotImplementedError("Comparison is only supported between ScheduledCrawlerJob instances.")
        return (self.next_run_time, self.display_name) < (other.next_run_time, other.display_name)


@dataclass(frozen=True)
class QueuedCrawlerJob:
    job: ScheduledCrawlerJob
    scheduled_for: datetime
    enqueued_at: datetime


class CrawlerJobQueue:
    def __init__(self) -> None:
        self._lock = Lock()
        self._pending: deque[QueuedCrawlerJob] = deque()
        self._pending_job_ids: set[str] = set()
        self._active_job_ids: set[str] = set()
        self._active_job_locks: dict[str, frozenset[str]] = {}
        self._active_lock_keys: set[str] = set()

    def enqueue(self, job: ScheduledCrawlerJob, scheduled_for: datetime) -> bool:
        with self._lock:
            if job.job_id in self._pending_job_ids or job.job_id in self._active_job_ids:
                logging.info("Skipping duplicate queued/running job: %s", job.display_name)
                return False

            self._pending.append(
                QueuedCrawlerJob(
                    job=job,
                    scheduled_for=scheduled_for,
                    enqueued_at=datetime.now(),
                )
            )
            self._pending_job_ids.add(job.job_id)
            logging.info("Queued crawler job: %s scheduled for %s", job.display_name, scheduled_for)
            return True

    def pop_ready_jobs(self) -> list[QueuedCrawlerJob]:
        ready: list[QueuedCrawlerJob] = []
        blocked: deque[QueuedCrawlerJob] = deque()

        with self._lock:
            while self._pending:
                queued_job = self._pending.popleft()
                job = queued_job.job

                if job.lock_keys & self._active_lock_keys:
                    blocked.append(queued_job)
                    continue

                self._pending_job_ids.remove(job.job_id)
                self._active_job_ids.add(job.job_id)
                self._active_job_locks[job.job_id] = job.lock_keys
                self._active_lock_keys.update(job.lock_keys)
                ready.append(queued_job)

            self._pending = blocked

        return ready

    def mark_finished(self, job: ScheduledCrawlerJob) -> None:
        with self._lock:
            self._active_job_ids.discard(job.job_id)
            lock_keys = self._active_job_locks.pop(job.job_id, frozenset())
            for lock_key in lock_keys:
                self._active_lock_keys.discard(lock_key)


# WATCHDOG
class ConfigEventHandler(FileSystemEventHandler):
    def on_any_event(self, event):
        if event.event_type in (EVENT_TYPE_CREATED, EVENT_TYPE_MODIFIED, EVENT_TYPE_MOVED):
            logging.debug("Event %s occurred on %s", event.event_type, event.src_path)
            global configChanged
            configChanged = True
            logging.info("Registered config change. Restarting scheduler...")


class SchedulerThread(Thread):
    def __init__(self):
        super().__init__()
        self.stop_event = Event()
        self.job_queue = CrawlerJobQueue()
        config = load_config()
        logging.debug("Configuration loaded: %s", config)
        self.scheduled_jobs = get_scheduled_jobs(config)

    def stop(self):
        logging.info("Stopping scheduler thread...")
        self.stop_event.set()

    def run(self):
        self._dispatch_ready_jobs()

        while not self.stop_event.is_set():
            self.scheduled_jobs.sort()

            if self.scheduled_jobs:
                next_run_time = self.scheduled_jobs[0].next_run_time
                jobs_next_up = [
                    job.display_name
                    for job in self.scheduled_jobs
                    if job.next_run_time == next_run_time
                ]
                logging.info("Next crawler jobs to run: %s at %s", ", ".join(jobs_next_up), next_run_time)
                seconds_till_nextrun = (next_run_time - datetime.now()).total_seconds()
            else:
                logging.info("No crawler jobs scheduled to run. Waiting for configuration changes.")
                seconds_till_nextrun = 4 * 60 * 60

            while seconds_till_nextrun > 0:
                wait_time = min(60, seconds_till_nextrun)

                if self.stop_event.wait(wait_time):
                    logging.info("Scheduler received stop signal while waiting.")
                    return

                global configChanged
                if configChanged:
                    return

                self._dispatch_ready_jobs()
                seconds_till_nextrun -= wait_time

            if self.stop_event.is_set():
                return

            now = datetime.now()
            for job in self.scheduled_jobs:
                if job.next_run_time <= now:
                    scheduled_for = job.next_run_time
                    self.job_queue.enqueue(job, scheduled_for)
                    job.advance_after(now)

            self._dispatch_ready_jobs()

    def _dispatch_ready_jobs(self):
        for queued_job in self.job_queue.pop_ready_jobs():
            logging.info("Dispatching crawler job: %s", queued_job.job.display_name)
            start_crawler_job_thread(queued_job.job, self._on_job_finished)

    def _on_job_finished(self, job: ScheduledCrawlerJob) -> None:
        self.job_queue.mark_finished(job)
        self._dispatch_ready_jobs()


def get_crawler_config_with_defaults(default_config, crawler_config):
    """
    Recursively merge default configuration with crawler-specific configuration.
    """
    merged_crawler_config = deepcopy(default_config)
    for key, value in crawler_config.items():
        if key not in merged_crawler_config:
            merged_crawler_config[key] = value
        elif isinstance(value, dict) and isinstance(merged_crawler_config.get(key), dict):
            merged_crawler_config[key] = get_crawler_config_with_defaults(merged_crawler_config[key], value)
        else:
            merged_crawler_config[key] = value

    return merged_crawler_config


def load_config():
    if not os.path.isfile(CONFIG_FILENAME):
        logging.error("Configuration file %s not found.", CONFIG_FILENAME)
        sys.exit(1)

    with open(CONFIG_FILENAME, encoding="utf-8") as file:
        config = yaml.safe_load(file)

    if not isinstance(config, dict):
        logging.error("Configuration file %s must contain a YAML mapping.", CONFIG_FILENAME)
        sys.exit(1)

    config = apply_email_env_overrides(config)
    default_config = config.get("default", {})
    if not isinstance(default_config, dict):
        logging.error("The 'default' section in %s must be a mapping.", CONFIG_FILENAME)
        default_config = {}

    merged_config: dict[str, Any] = {"default": default_config}
    for crawler_name, crawler_config in config.items():
        if crawler_name == "default":
            continue
        if not isinstance(crawler_config, dict):
            logging.error("Crawler config for %s must be a mapping. Skipping.", crawler_name)
            continue

        crawler_base = {key: value for key, value in crawler_config.items() if key != "jobs"}
        merged_crawler = get_crawler_config_with_defaults(default_config, crawler_base)
        if "jobs" in crawler_config:
            merged_crawler["jobs"] = crawler_config["jobs"]
        merged_config[crawler_name] = merged_crawler

    return merged_config


def expand_crawler_job_configs(crawler_name: str, crawler_config: dict[str, Any]) -> list[CrawlerJobConfig]:
    jobs = crawler_config.get("jobs")
    if isinstance(jobs, dict) and jobs:
        base_config = {key: deepcopy(value) for key, value in crawler_config.items() if key != "jobs"}
        job_configs = []

        for job_name, job_config in jobs.items():
            if not isinstance(job_config, dict):
                logging.error("Job config for %s:%s must be a mapping. Skipping.", crawler_name, job_name)
                continue

            effective_config = get_crawler_config_with_defaults(base_config, job_config)
            effective_config["_scheduler_job_name"] = str(job_name)
            effective_config["_scheduler_job_id"] = f"{crawler_name}:{job_name}"
            parsed_schedule = _parse_job_schedule(crawler_name, str(job_name), effective_config)
            if parsed_schedule is None:
                continue

            job_configs.append(
                CrawlerJobConfig(
                    crawler_name=crawler_name,
                    job_name=str(job_name),
                    config=effective_config,
                    schedule=parsed_schedule,
                )
            )

        return job_configs

    effective_config = deepcopy(crawler_config)
    effective_config.pop("jobs", None)
    effective_config["_scheduler_job_name"] = "default"
    effective_config["_scheduler_job_id"] = f"{crawler_name}:default"
    parsed_schedule = _parse_job_schedule(crawler_name, "default", effective_config)
    if parsed_schedule is None:
        return []

    return [
        CrawlerJobConfig(
            crawler_name=crawler_name,
            job_name="default",
            config=effective_config,
            schedule=parsed_schedule,
        )
    ]


def _parse_job_schedule(crawler_name: str, job_name: str, config: dict[str, Any]) -> Cron | None:
    schedule = config.get("schedule")
    try:
        return Cron(schedule)
    except Exception as exc:
        logging.error("%s in %s, crawler job %s:%s: %r", exc, CONFIG_FILENAME, crawler_name, job_name, schedule)
        config["enable"] = False
        return None


def start_crawler_job_thread(job: ScheduledCrawlerJob, on_finish: Callable[[ScheduledCrawlerJob], None]) -> None:
    def thread_func():
        print(f"\n>>>>>>> [START] {job.display_name} <<<<<<<")
        start_time = time.time()
        success = False

        try:
            crawler = job.crawler_class(job.crawler_name, deepcopy(job.config))
            crawler.run()
            success = True
        except Exception as exc:
            print(f"\n[ERROR] {job.display_name} crashed.")
            logging.error("Details for %s: %s", job.display_name, exc)
            if logging.root.level == logging.DEBUG:
                traceback.print_exc()

        if success and job.run_post_scripts:
            post_run_scripts = job.config.get("post_run_scripts")
            if isinstance(post_run_scripts, list) and post_run_scripts:
                print(f"   [SCRIPT] Executing {len(post_run_scripts)} post-run scripts...")
                for script in post_run_scripts:
                    logging.info("   -> Running for %s: %s", job.display_name, script)
                    completed = subprocess.run([sys.executable, script], check=False)
                    if completed.returncode != 0:
                        logging.error(
                            "Post-run script %s for %s exited with code %s.",
                            script,
                            job.display_name,
                            completed.returncode,
                        )

        duration = time.time() - start_time
        print(f"<<<<<<< [FINISH] {job.display_name} (Took {duration:.2f}s) >>>>>>>\n")
        on_finish(job)

    Thread(target=thread_func, name=f"crawler-job-{job.display_name}").start()


def get_scheduled_jobs(config):
    crawler_path = os.path.join(os.getcwd(), "crawler")
    if crawler_path not in sys.path:
        sys.path.append(crawler_path)

    available_crawlers = [
        Path(module_path).stem
        for module_path in os.listdir("crawler")
        if os.path.isfile(os.path.join("crawler", module_path))
        and module_path.endswith(".py")
        and not module_path.startswith("__")
    ]

    logging.info("Scanning 'crawler' directory...")

    scheduled_jobs: list[ScheduledCrawlerJob] = []
    disabled_jobs: list[str] = []
    failed_imports: list[tuple[str, str]] = []

    for crawler_name in available_crawlers:
        if crawler_name not in config:
            logging.warning("  [SKIP] %s: Missing config in YAML", crawler_name)
            continue

        try:
            crawler_class = _load_crawler_class(crawler_name)
        except Exception as exc:
            failed_imports.append((crawler_name, str(exc)))
            continue

        for job_config in expand_crawler_job_configs(crawler_name, config[crawler_name]):
            if not job_config.enabled:
                disabled_jobs.append(job_config.display_name)
                continue

            scheduled_jobs.append(
                ScheduledCrawlerJob(
                    crawler_name=job_config.crawler_name,
                    job_name=job_config.job_name,
                    crawler_class=crawler_class,
                    config=job_config.config,
                    schedule=job_config.schedule,
                    lock_keys=get_job_lock_keys(job_config.crawler_name, job_config.config, crawler_class),
                )
            )

    print("\n" + "-" * 20 + " CRAWLER JOB LOAD REPORT " + "-" * 20)
    print(f"\nLOADED & ENABLED JOBS ({len(scheduled_jobs)}):")
    loaded_names = [job.display_name for job in scheduled_jobs]
    for index in range(0, len(loaded_names), 4):
        print("   " + ", ".join(loaded_names[index : index + 4]))

    if disabled_jobs:
        print(f"\nLOADED BUT DISABLED JOBS ({len(disabled_jobs)}):")
        for index in range(0, len(disabled_jobs), 4):
            print("   " + ", ".join(disabled_jobs[index : index + 4]))

    if failed_imports:
        logging.warning("Failed crawler imports: %s", ", ".join(name for name, _ in failed_imports))

    print("-" * 65 + "\n")
    return scheduled_jobs


def get_scheduled_crawlers(config):
    """Backward-compatible alias for code that still imports the old helper."""
    return get_scheduled_jobs(config)


def _load_crawler_class(crawler_name: str) -> type[BaseCrawler]:
    crawler_module = __import__(f"crawler.{crawler_name}")
    crawler_module = getattr(crawler_module, crawler_name)

    for module_element_name in dir(crawler_module):
        crawler_class = getattr(crawler_module, module_element_name)
        if (
            isclass(crawler_class)
            and issubclass(crawler_class, BaseCrawler)
            and crawler_class.__name__ != BaseCrawler.__name__
        ):
            return crawler_class

    raise RuntimeError(f"No BaseCrawler subclass found in crawler module '{crawler_name}'.")


def get_job_lock_keys(
    crawler_name: str,
    config: dict[str, Any],
    crawler_class: type[BaseCrawler] | None = None,
) -> frozenset[str]:
    if crawler_name == "entsoe_fms":
        data_item_table_map = getattr(crawler_class, "DATA_ITEM_TABLE_MAP", {}) if crawler_class else {}
        target_data_items = config.get("target_data_items")

        if isinstance(target_data_items, list) and target_data_items:
            return frozenset(
                f"{crawler_name}:{data_item_table_map.get(data_item, data_item)}"
                for data_item in target_data_items
            )

        if isinstance(data_item_table_map, dict) and data_item_table_map:
            return frozenset(f"{crawler_name}:{table_name}" for table_name in data_item_table_map.values())

    return frozenset({f"crawler:{crawler_name}"})


def main():
    load_local_crawler_env()

    log_format = "[%(asctime)s] %(levelname)-8s %(message)s"
    date_format = "%H:%M:%S"

    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=date_format,
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    print("\n" + "=" * 50)
    print("       OEDS CRAWLER SCHEDULER (PRODUCTION)")
    print("=" * 50 + "\n")

    event_handler = ConfigEventHandler()
    observer = Observer()
    observer.schedule(event_handler, CONFIG_FILENAME)
    observer.start()

    global scheduler_thread
    scheduler_thread = None

    def signal_handler(signum, frame):
        print("\n\nReceived exit signal. Shutting down gracefully...")
        if scheduler_thread and scheduler_thread.is_alive():
            scheduler_thread.stop()
            scheduler_thread.join(timeout=5)
        observer.stop()
        observer.join()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        while True:
            scheduler_thread = SchedulerThread()
            scheduler_thread.start()

            while scheduler_thread.is_alive():
                scheduler_thread.join(1)

            global configChanged
            if configChanged:
                logging.info("Configuration changed, reloading crawler jobs...")
                configChanged = False
            else:
                break

    except Exception as exc:
        logging.error("Unexpected error in main loop: %s", exc)
    finally:
        if observer.is_alive():
            observer.stop()
            observer.join()


if __name__ == "__main__":
    main()
