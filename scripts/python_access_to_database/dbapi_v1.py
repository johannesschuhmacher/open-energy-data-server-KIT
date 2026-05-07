#<!--SPDX-FileCopyrightText: Johannes Schuhmacher-->

#<!--SPDX-License-Identifier: AGPL-3.0-or-later-->

"""
Mini‑API für flexible Datenabfragen aus Timescale/PostgreSQL.

Ergänzt um **optionalen SSH‑Tunnel** – damit verhält sich das Skript wie DataGrip,
welches im Hintergrund einen Port‑Forward öffnet. Läuft kein Tunnel (und keine
passenden Umgebungsvariablen), wird wie bisher direkt verbunden.

Benötigt:
    - pandas
    - sqlalchemy
    - python‑dotenv (dotenv)
    - psycopg[binary]   # oder psycopg2‑binary
    - sshtunnel         # nur wenn SSH‑Tunnel gewünscht

.env‑Beispiel für SSH:
    # SSH‑Zugang
    DB_SSH_HOST=2a00:1398:5:800::ac16:c67d
    DB_SSH_PORT=22             # optional, default 22
    DB_SSH_USER=opendata
    DB_SSH_PASS=opendata       # oder DB_SSH_KEY=/Pfad/zum/key
    DB_REMOTE_PORT=5432        # Zielport auf dem Server

    # Datenbank‑Creds
    DB_DIALECT=postgresql+psycopg   # oder postgresql+psycopg2
    DB_USER=opendata
    DB_PASS=opendata
    DB_NAME=opendata
    DB_HOST=localhost          # **immer localhost**, wir tunneln
    DB_PORT=6432               # lokaler Forward‑Port
"""

from __future__ import annotations

import os
import textwrap
import contextlib
import atexit
from typing import Iterable, Mapping, Any

import pandas as pd
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from dotenv import load_dotenv
load_dotenv()

print("DBG  · DB_SSH_HOST =", os.getenv("DB_SSH_HOST"))
print("DBG  · DB_PORT     =", os.getenv("DB_PORT"))
print("DBG  · DB_REMOTE_PORT =", os.getenv("DB_REMOTE_PORT"))

# sshtunnel ist nur nötig, wenn ein Tunnel gewünscht ist
try:
    from sshtunnel import SSHTunnelForwarder  # type: ignore
except ImportError:  # pragma: no cover
    SSHTunnelForwarder = None

# ---------------------------------------------------------------------------
# 1 · SSH‑Tunnel (optional)
# ---------------------------------------------------------------------------

def _start_tunnel():
    """Öffnet einen SSH‑Tunnel, falls DB_SSH_HOST gesetzt ist.

    Gibt den gestarteten SSHTunnelForwarder zurück oder *None*, wenn kein
    Tunnel benötigt wird.
    """
    ssh_host = os.getenv("DB_SSH_HOST")
    if not ssh_host:
        return None  # Direktverbindung

    if SSHTunnelForwarder is None:
        raise RuntimeError("sshtunnel nicht installiert, SSH‑Tunnel aber verlangt")

    ssh_port = int(os.getenv("DB_SSH_PORT", "22"))
    ssh_user = os.getenv("DB_SSH_USER")
    ssh_pass = os.getenv("DB_SSH_PASS")
    ssh_key = os.getenv("DB_SSH_KEY")
    remote_bind_port = int(os.getenv("DB_REMOTE_PORT", "5432"))
    local_bind_port = int(os.getenv("DB_PORT", "6432"))  # forward nach außen

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

    # Sauberes Aufräumen beim Programmende.
    atexit.register(tunnel.stop)
    return tunnel

_TUNNEL = _start_tunnel()  # startet nur, wenn benötigt

# ---------------------------------------------------------------------------
# 2 · Engine & Inspector
# ---------------------------------------------------------------------------

def _build_engine() -> Engine:
    load_dotenv()

    DIALECT = os.getenv("DB_DIALECT", "postgresql+psycopg")
    uri = (
        f"{DIALECT}://{os.getenv('DB_USER')}:{os.getenv('DB_PASS')}"
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

# ---------------------------------------------------------------------------
# 3 · Metadaten‑Helfer
# ---------------------------------------------------------------------------

def list_schemas() -> list[str]:
    """Alle nicht‑System‑Schemata."""
    system = {"information_schema", "pg_catalog"}
    return [s for s in _INSP.get_schema_names() if s not in system]


def list_tables(schema: str) -> list[str]:
    return _INSP.get_table_names(schema=schema)


def list_columns(table: str, *, schema: str) -> list[str]:
    return [c["name"] for c in _INSP.get_columns(table, schema=schema)]

# ---------------------------------------------------------------------------
# 4 · Generisches Abfrage‑Interface
# ---------------------------------------------------------------------------

def fetch_df(
    schema: str,
    table: str,
    columns: Iterable[str] | None = None,
    where: str | None = None,
    params: Mapping[str, Any] | None = None,
    limit: int | None = None,
) -> pd.DataFrame:
    """Flexibles SELECT → DataFrame.

    Beispiel:
        df = fetch_df(
            "entsoe_fms", "ActualTotalLoad",
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
            FROM \"{schema}\".\"{table}\"
            {('WHERE ' + where) if where else ''}
            {f'LIMIT {limit}' if limit else ''}
            """
        )
    )
    with _ENGINE.begin() as conn:
        return pd.read_sql(sql, conn, params=params)

# ---------------------------------------------------------------------------
# 5 · CLI‑ähnliche Demo
# ---------------------------------------------------------------------------

def interactive_demo():  # pragma: no cover
    print("\n=== SCHEMAS ===")
    for i, sch in enumerate(list_schemas(), 1):
        print(f"{i:2d}. {sch}")
    s_idx = int(input("Schema wählen [Nr]: ")) - 1
    schema = list_schemas()[s_idx]

    print(f"\n=== TABLES in {schema} ===")
    tables = list_tables(schema)
    for i, t in enumerate(tables, 1):
        print(f"{i:2d}. {t}")
    t_idx = int(input("Tabelle wählen [Nr]: ")) - 1
    table = tables[t_idx]

    cols = list_columns(table, schema=schema)
    print(f"\nSpalten: {', '.join(cols)}")
    sel = input("Gewünschte Spalten kommagetrennt (leer = alle): ").split(",")
    sel_cols = [c.strip() for c in sel if c.strip()] or None

    where = input("WHERE‑Klausel (ohne 'WHERE', leer = alle Zeilen): ").strip() or None
    limit = input("Limit (leer = kein Limit): ").strip()
    limit = int(limit) if limit else None

    df = fetch_df(schema, table, sel_cols, where, limit=limit)
    print(df.head())
    print(f"\n→ {len(df):,} Zeilen geladen.")


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        interactive_demo()
