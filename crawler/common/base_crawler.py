# SPDX-FileCopyrightText: Florian Maurer, Johannes Schuhmacher, Andre Meyer
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from datetime import date, datetime
from sqlalchemy import create_engine, text
from abc import ABC, abstractmethod
import logging
from logging.handlers import SMTPHandler
import os

from crawler.common.runtime_env import resolve_database_uri


class BaseCrawler(ABC):
    # crawler name is the the name which is specified in the config file, so its the basename of the python file
    # config are the corresonding configuration parameters for the crawler
    # the scheduler will pass poth parameters to the crawler when it is initialized
    def __init__(self, crawler_name: str, config: dict):
        self.config = config
        self.engine = create_engine(self.get_db_uri())
        self.crawler_name = crawler_name
        self.create_schema(self.get('schema_name'))

        self.logger = logging.getLogger(self.crawler_name)

        log_file_name = f'logs/{self.crawler_name}.log'
        if not os.path.isfile(log_file_name):
            os.makedirs(os.path.dirname(log_file_name), exist_ok=True)

        fileHandler = logging.FileHandler(log_file_name)
        if logging.root.handlers: # if basicConfig was called before, use the same formatter
            fileHandler.setFormatter(logging.root.handlers[0].formatter) # use the same formatter as defined in basic config in server.py
        self.logger.addHandler(fileHandler)

        try:
            subject = self.config['email']['subject'].replace(':crawler_name', self.crawler_name)
            username = self.config['email']['username']
            password = self.config['email']['password']
            credentials = (username, password) if username or password else None
            smtp_handler = SMTPHandler(
                mailhost=self.config['email']['mailhost'],
                fromaddr=self.config['email']['fromaddr'],
                toaddrs=self.config['email']['toaddrs'],
                subject=subject,
                credentials=credentials,
            )
            smtp_handler.setLevel(logging.CRITICAL)
            if logging.root.handlers:
                smtp_handler.setFormatter(logging.root.handlers[0].formatter) # use the same formatter as defined in basic config in server.py
            self.logger.addHandler(smtp_handler)
        except KeyError as e:
            self.logger.warning(f"can't configure Email logging: Missing field {e}")

    def get_db_uri(self):
        return resolve_database_uri(self.get('database_uri')) + self.get('schema_name')

    def __lt__(self, other):
        if not isinstance(other, BaseCrawler):
            raise NotImplementedError("Comparison is only supported between BaseCrawler instances.")
        ref_time = datetime.now()
        return self.get_next_schedule(ref_time) < other.get_next_schedule(ref_time)

    def get(self, key: str):
        keys = key.split('.')

        conf = self.config
        for k in keys:
            if type(conf) == dict and k in conf:
                conf = conf[k]
            else:
                raise KeyError(f"Key '{key}' not found in crawler configuration.")
        return conf

    def get_next_schedule(self, ref_time=None):
        if not ref_time:
            ref_time = datetime.now()
        return self.config['schedule'].schedule(ref_time).next()

    # This method is the only method that will be executed by the scheduler
    # so all the setup an the code to crawl the data needs to executed in
    # in this method in order for the crawler to work
    @abstractmethod
    def run(self):
        raise NotImplementedError("Run method not implemented. Override this method in your crawler and be sure that all the setup is done in this method as well.")

    def create_schema(self, schema_name: str) -> str:
        create_schema_only(self.engine, schema_name)

    def set_metadata(self, metadata_info: dict[str, str]) -> None:
        set_metadata_only(self.engine, metadata_info)


def create_schema_only(engine, schema_name: str) -> None:
    with engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))


def set_metadata_only(engine, metadata_info: dict[str, str]):
    for key in ["concave_hull_geometry", "temporal_start", "temporal_end", "contact"]:
        if key not in metadata_info.keys():
            metadata_info[key] = None
    if "data_date" not in metadata_info.keys():
        metadata_info["data_date"] = date.today()
    with engine.begin() as conn:
        conn.execute(
            text("""
            INSERT INTO public.metadata
            (schema_name, data_date, data_source, license, description, contact, concave_hull_geometry, temporal_start, temporal_end)
            VALUES
            (:schema_name, :data_date, :data_source, :license, :description, :contact, :concave_hull_geometry, :temporal_start, :temporal_end)
            ON CONFLICT (schema_name) DO UPDATE SET
                data_date = EXCLUDED.data_date,
                data_source = EXCLUDED.data_source,
                license = EXCLUDED.license,
                description = EXCLUDED.description,
                contact = EXCLUDED.contact,
                concave_hull_geometry = EXCLUDED.concave_hull_geometry,
                temporal_start = EXCLUDED.temporal_start,
                temporal_end = EXCLUDED.temporal_end
            """),
            metadata_info,
        )
        conn.execute(
            text("""
            UPDATE public.metadata
            SET tables = (SELECT COUNT(*) FROM pg_class JOIN pg_namespace ON pg_namespace.oid = pg_class.relnamespace WHERE nspname = :schema_name AND pg_class.relkind = 'r'),
                size = (SELECT SUM(pg_total_relation_size(pg_class.oid)) FROM pg_class JOIN pg_namespace ON pg_namespace.oid = pg_class.relnamespace WHERE nspname = :schema_name AND pg_class.relkind = 'r'),
                crawl_date = NOW()
            WHERE schema_name = :schema_name
            """),
            {"schema_name": metadata_info["schema_name"]},
        )
        conn.execute(
            text("""
            NOTIFY pgrst, 'reload schema';
            """)
        )
