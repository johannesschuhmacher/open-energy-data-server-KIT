# SPDX-FileCopyrightText: Johannes Schuhmacher, Andre Meyer, Haoshen Zhang
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from cron_converter import Cron
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, EVENT_TYPE_CREATED, EVENT_TYPE_MODIFIED, EVENT_TYPE_MOVED
import signal 
from threading import Thread, Event 
import yaml
import os
import sys
import logging
from datetime import datetime
import time
from crawler.common.base_crawler import BaseCrawler
from crawler.common.local_env import apply_email_env_overrides
from inspect import isclass
from pathlib import Path
from copy import deepcopy
import traceback

from crawler.common.runtime_env import load_local_crawler_env

CONFIG_FILENAME = "CRAWLER_CONFIG.yml"
configChanged = False


# WATCHDOG
class ConfigEventHandler(FileSystemEventHandler):
    def on_any_event(self, event):
        if event.event_type in (EVENT_TYPE_CREATED, EVENT_TYPE_MODIFIED, EVENT_TYPE_MOVED):
            logging.debug(f"Event {event.event_type} occurred on {event.src_path}")
            global configChanged
            configChanged = True
            logging.info("Registered config change. Restarting scheduler...")


class SchedulerThread(Thread):
    def __init__(self):
        super().__init__()
        self.stop_event = Event()
        config = load_config()
        logging.debug(f"Configuration loaded: {config}")
        self.scheduled_crawlers = get_scheduled_crawlers(config)

    def stop(self):
        """外部调用此方法来停止线程"""
        logging.info("Stopping scheduler thread...")
        self.stop_event.set()

    def run(self):
        
        while not self.stop_event.is_set():
            # Sort by next schedule
            self.scheduled_crawlers.sort()
            
            if self.scheduled_crawlers:
                next_run_time = self.scheduled_crawlers[0].get_next_schedule()
                crawlers_next_up = [c.crawler_name for c in self.scheduled_crawlers if c.get_next_schedule() == next_run_time]
                
                logging.info(f"Next crawlers to run: {', '.join(crawlers_next_up)} at {next_run_time}")

                seconds_till_nextrun = (next_run_time - datetime.now()).total_seconds()
            else:
                logging.info("No crawlers scheduled to run. Waiting for configuration changes.")
                seconds_till_nextrun = 4 * 60 * 60  # Wait 4 hours

            # Check for config changes or stop signal while waiting
            while seconds_till_nextrun > 0:
                wait_time = min(60, seconds_till_nextrun)
                
                if self.stop_event.wait(wait_time): 
                    logging.info("Scheduler received stop signal while waiting.")
                    return

                global configChanged
                if configChanged:
                    return
                
                seconds_till_nextrun -= wait_time

            # Execution Phase
            if self.stop_event.is_set(): return

            for crawler in self.scheduled_crawlers:
                # Check if the crawler should run now (allowing a small time buffer)
                if (crawler.get_next_schedule(next_run_time) - next_run_time).total_seconds() <= 0.01:
                    logging.info(f"Triggering crawler: {crawler.crawler_name} at {datetime.now()}")
                    start_crawler_thread(crawler)



def get_crawler_config_with_defaults(default_config, crawler_config):
    """
    Recursively merges the default configuration with the crawler-specific configuration.
    """
    merged_crawler_config = deepcopy(default_config)
    for k, v in crawler_config.items():
        if k not in merged_crawler_config:
            merged_crawler_config[k] = v
        elif isinstance(v, dict):
            merged_crawler_config[k] = get_crawler_config_with_defaults(merged_crawler_config[k], v)
        else:
            merged_crawler_config[k] = v

    return merged_crawler_config


def load_config():
    if not os.path.isfile(CONFIG_FILENAME):
        logging.error(f"Configuration file {CONFIG_FILENAME} not found.")
        sys.exit(1)

    with open(CONFIG_FILENAME) as file:
        config = yaml.safe_load(file)
    config = apply_email_env_overrides(config)

    for crawler_name in config:
        if crawler_name == 'default':
            continue

        # Merge with defaults
        config[crawler_name] = get_crawler_config_with_defaults(config['default'], config[crawler_name])

        # Convert cron expression to Cron object
        try:
            config[crawler_name]['schedule'] = Cron(config[crawler_name]['schedule'])
        except TypeError as e:
            logging.error(f"{e} in {CONFIG_FILENAME}, crawler {crawler_name}: '{config[crawler_name]['schedule']}'")
            config[crawler_name]['enable'] = False

    return config


def start_crawler_thread(crawler):
    def thread_func(crawler):
        # Visual separation for better readability
        print(f"\n>>>>>>> [START] {crawler.crawler_name} <<<<<<<")
        start_time = time.time()
        
        try:
            crawler.run()
        except Exception as e:
            print(f"\n❌ [ERROR] {crawler.crawler_name} crashed!")
            logging.error(f"Details: {e}")
            if logging.root.level == logging.DEBUG:
                traceback.print_exc()
            return
        
        # Post-run scripts
        post_run_scripts = crawler.get('post_run_scripts')
        if post_run_scripts:
            print(f"   [SCRIPT] Executing {len(post_run_scripts)} post-run scripts...")
            for script in post_run_scripts:
                logging.info(f"   -> Running: {script}")
                os.system(f'python {script}')

        duration = time.time() - start_time
        print(f"<<<<<<< [FINISH] {crawler.crawler_name} (Took {duration:.2f}s) >>>>>>>\n")

    Thread(target=thread_func, args=[crawler]).start()


def get_scheduled_crawlers(config):
    # Ensure crawler directory is in path (optional if using correct imports in files)
    crawler_path = os.path.join(os.getcwd(), 'crawler')
    if crawler_path not in sys.path:
        sys.path.append(crawler_path)

    available_crawlers = [Path(m).stem for m in os.listdir('crawler') if os.path.isfile(os.path.join('crawler', m)) and m.endswith('.py') and not m.startswith('__')]
    
    logging.info(f"Scanning 'crawler' directory...")
    
    scheduled_crawlers = []
    failed_imports = []

    # Import and Initialize
    for crawler_name in available_crawlers:
        try:
            crawler_module = __import__(f'crawler.{crawler_name}')
        except Exception as e:
            # Catch import errors (e.g. missing libraries)
            failed_imports.append((crawler_name, str(e)))
            continue
            
        crawler_module = getattr(crawler_module, crawler_name)
        
        class_found = False
        for module_element_name in dir(crawler_module):
            crawlerClass = getattr(crawler_module, module_element_name)

            # Strict check: Must be subclass of BaseCrawler
            if isclass(crawlerClass) and issubclass(crawlerClass, BaseCrawler) and crawlerClass.__name__ != BaseCrawler.__name__:
                try:
                    # Try to initialize with config
                    crawler = crawlerClass(crawler_name, config[crawler_name])
                    scheduled_crawlers.append(crawler)
                    class_found = True
                    break # Found the class, stop searching this module
                except KeyError:
                    # Config missing in YAML
                    logging.warning(f"  [SKIP] {crawler_name}: Missing config in YAML")
                except Exception as e:
                    logging.error(f"  [FAIL] {crawler_name}: Init error - {e}")
                    if logging.root.level == logging.DEBUG: traceback.print_exception(e)

    # --- Print Summary Report ---
    print("\n" + "-"*20 + " CRAWLER LOAD REPORT " + "-"*20)
    
    if failed_imports:
        pass
    
    # Filter only enabled crawlers
    enabled_crawlers = [c for c in scheduled_crawlers if c.get('enable')]
    disabled_crawlers = [c for c in scheduled_crawlers if not c.get('enable')]

    print(f"\n✅ LOADED & ENABLED ({len(enabled_crawlers)}):")
    loaded_names = [c.crawler_name for c in enabled_crawlers]
    for i in range(0, len(loaded_names), 4):
        print("   " + ", ".join(loaded_names[i:i+4]))

    if disabled_crawlers:
        print(f"\n⚠️  LOADED BUT DISABLED ({len(disabled_crawlers)}):")
        disabled_names = [c.crawler_name for c in disabled_crawlers]
        for i in range(0, len(disabled_names), 4):
            print("   " + ", ".join(disabled_names[i:i+4]))
            
    print("-"*61 + "\n")

    return enabled_crawlers


def main():
    load_local_crawler_env()

    # Improved logging configuration
    log_format = '[%(asctime)s] %(levelname)-8s %(message)s'
    date_format = '%H:%M:%S'
    
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=date_format,
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    
    print("\n" + "="*50)
    print("       OEDS CRAWLER SCHEDULER (PRODUCTION)")
    print("="*50 + "\n")

    # Watch for changes in CONFIG FILE
    event_handler = ConfigEventHandler()
    observer = Observer()
    observer.schedule(event_handler, CONFIG_FILENAME)
    observer.start()

    global scheduler_thread
    scheduler_thread = None

    def signal_handler(signum, frame):
        print("\n\n🛑 Received exit signal. Shutting down gracefully...")
        if scheduler_thread and scheduler_thread.is_alive():
            scheduler_thread.stop() 
            scheduler_thread.join(timeout=5) 
        observer.stop()
        observer.join()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler) # docker stop / kill

    try:
        while True:
            scheduler_thread = SchedulerThread()
            scheduler_thread.start()
            
            while scheduler_thread.is_alive():
                scheduler_thread.join(1) 

            global configChanged
            if configChanged:
                logging.info("Configuration changed, reloading crawlers...")
                configChanged = False
            else:
                break
                
    except Exception as e:
        logging.error(f"Unexpected error in main loop: {e}")
    finally:
        if observer.is_alive():
            observer.stop()
            observer.join()


if __name__ == "__main__":
    main()
