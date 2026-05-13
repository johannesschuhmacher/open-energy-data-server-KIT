# SPDX-FileCopyrightText: OpenAI
#
# SPDX-License-Identifier: AGPL-3.0-or-later

import logging
from pathlib import Path

import yaml
from crawler_core.runtime_env import resolve_database_uri
from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parents[1]
SQL_FILE = ROOT / "scripts" / "lib" / "entsoe_availability_map.sql"
CONFIG_FILE = ROOT / "CRAWLER_CONFIG.yml"


def load_database_uri() -> str:
    with CONFIG_FILE.open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle)

    default_uri = config["default"]["database_uri"]
    crawler_uri = config.get("entsoe_fms", {}).get("database_uri", default_uri)
    return f"{resolve_database_uri(crawler_uri)}entsoe_fms"


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s %(message)s",
    )

    sql = SQL_FILE.read_text(encoding="utf-8")
    engine = create_engine(load_database_uri())

    logging.info("Refreshing ENTSO-E availability map objects...")
    with engine.begin() as conn:
        conn.exec_driver_sql(sql)
    logging.info("ENTSO-E availability map objects refreshed.")


if __name__ == "__main__":
    main()
