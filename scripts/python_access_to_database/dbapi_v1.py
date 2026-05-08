#<!--SPDX-FileCopyrightText: Johannes Schuhmacher-->

#<!--SPDX-License-Identifier: AGPL-3.0-or-later-->

"""
Small API for flexible TimescaleDB and PostgreSQL queries.

The module supports an optional SSH tunnel so local scripts can behave like a
database IDE with port forwarding. If no tunnel variables are configured, it
connects directly to the database.

Required packages:
    - pandas
    - sqlalchemy
    - python-dotenv
    - psycopg[binary] or psycopg2-binary
    - sshtunnel (only when SSH tunneling is needed)

Example `.env` for SSH tunneling:
    # SSH access
    DB_SSH_HOST=example-host
    DB_SSH_PORT=22
    DB_SSH_USER=opendata
    DB_SSH_PASS=secret
    # or DB_SSH_KEY=/path/to/private/key
    DB_REMOTE_PORT=5432

    # Database credentials
    DB_DIALECT=postgresql+psycopg
    DB_USER=opendata
    DB_PASS=opendata
    DB_NAME=opendata
    DB_HOST=localhost
    DB_PORT=6432
"""

from __future__ import annotations

import atexit
import contextlib
import os
import textwrap
from typing import Any, Iterable, Mapping

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

load_dotenv()

try:
    from sshtunnel import SSHTunnelForwarder  # type: ignore
except ImportError:  # pragma: no cover
    SSHTunnelForwarder = None


def _start_tunnel():
    """Start an SSH tunnel when DB_SSH_HOST is configured."""
    ssh_host = os.getenv("DB_SSH_HOST")
    if not ssh_host:
        return None

    if SSHTunnelForwarder is None:
        raise RuntimeError("sshtunnel is required when DB_SSH_HOST is set")

    ssh_port = int(os.getenv("DB_SSH_PORT", "22"))
    ssh_user = os.getenv("DB_SSH_USER")
    ssh_pass = os.getenv("DB_SSH_PASS")
    ssh_key = os.getenv("DB_SSH_KEY")
    remote_bind_port = int(os.getenv("DB_REMOTE_PORT", "5432"))
    local_bind_port = int(os.getenv("DB_PORT", "6432"))

    tunnel = SSHTunnelForwarder(
        (ssh_host, ssh_port),
        ssh_username=ssh_user,
        ssh_password=ssh_pass if ssh_key is None else None,
        ssh_pkey=ssh_key,
        remote_bind_address=("localhost", remote_bind_port),
        local_bind_address=("localhost", local_bind_port),
        mute_exceptions=True,
    )
    tunnel.start()
    atexit.register(tunnel.stop)
    return tunnel


_TUNNEL = _start_tunnel()


def _build_engine() -> Engine:
    load_dotenv()

    dialect = os.getenv("DB_DIALECT", "postgresql+psycopg")
    uri = (
        f"{dialect}://{os.getenv('DB_USER')}:{os.getenv('DB_PASS')}"
        f"@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '6432')}"
        f"/{os.getenv('DB_NAME')}"
    )
    return create_engine(
        uri,
        future=True,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5},
    )


_ENGINE: Engine = _build_engine()
_INSP = inspect(_ENGINE)


def list_schemas() -> list[str]:
    """Return all non-system schemas."""
    system = {"information_schema", "pg_catalog"}
    return [schema for schema in _INSP.get_schema_names() if schema not in system]


def list_tables(schema: str) -> list[str]:
    """Return all tables for a schema."""
    return _INSP.get_table_names(schema=schema)


def list_columns(table: str, *, schema: str) -> list[str]:
    """Return all column names for a table."""
    return [column["name"] for column in _INSP.get_columns(table, schema=schema)]


def fetch_df(
    schema: str,
    table: str,
    columns: Iterable[str] | None = None,
    where: str | None = None,
    params: Mapping[str, Any] | None = None,
    limit: int | None = None,
) -> pd.DataFrame:
    """Run a flexible SELECT query and return a DataFrame.

    Example:
        df = fetch_df(
            "entsoe_fms",
            "ActualTotalLoad",
            ['"DateTime(UTC)"', '"TotalLoad[MW]"'],
            '"AreaDisplayName" = :bz AND "DateTime(UTC)" >= :t0',
            {"bz": "Germany (DE)", "t0": "2024-01-01"},
            limit=1000,
        )
    """
    cols = ", ".join(columns) if columns else "*"
    sql = text(
        textwrap.dedent(
            f"""
            SELECT {cols}
            FROM "{schema}"."{table}"
            {('WHERE ' + where) if where else ''}
            {f'LIMIT {limit}' if limit else ''}
            """
        )
    )
    with _ENGINE.begin() as conn:
        return pd.read_sql(sql, conn, params=params)


def interactive_demo():  # pragma: no cover
    """Run a minimal interactive schema explorer."""
    print("\n=== SCHEMAS ===")
    schemas = list_schemas()
    for index, schema in enumerate(schemas, start=1):
        print(f"{index:2d}. {schema}")
    schema_index = int(input("Choose schema [number]: ")) - 1
    schema = schemas[schema_index]

    print(f"\n=== TABLES in {schema} ===")
    tables = list_tables(schema)
    for index, table in enumerate(tables, start=1):
        print(f"{index:2d}. {table}")
    table_index = int(input("Choose table [number]: ")) - 1
    table = tables[table_index]

    columns = list_columns(table, schema=schema)
    print(f"\nColumns: {', '.join(columns)}")
    selected = input("Comma-separated columns (leave empty for all): ").split(",")
    selected_columns = [column.strip() for column in selected if column.strip()] or None

    where = input("WHERE clause (without 'WHERE', leave empty for all rows): ").strip() or None
    limit = input("Limit (leave empty for no limit): ").strip()
    limit_value = int(limit) if limit else None

    df = fetch_df(schema, table, selected_columns, where, limit=limit_value)
    print(df.head())
    print(f"\nLoaded {len(df):,} rows.")


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        interactive_demo()
