# SPDX-FileCopyrightText: OpenAI
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import os

from dotenv import load_dotenv


def get_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_local_crawler_env(repo_root: Path | None = None) -> Path | None:
    root = repo_root or get_repo_root()
    env_path = root / "crawler" / ".env"
    if not env_path.exists():
        return None

    load_dotenv(dotenv_path=env_path, override=False)
    return env_path


def resolve_database_uri(database_uri: str) -> str:
    if not isinstance(database_uri, str) or not database_uri.strip():
        return database_uri

    host_override = os.getenv("OEDS_DB_HOST", "").strip()
    port_override = os.getenv("OEDS_DB_PORT", "").strip()

    if not host_override and not port_override:
        return database_uri

    split = urlsplit(database_uri)
    if not split.scheme or not split.netloc:
        return database_uri

    username = split.username or ""
    password = split.password
    hostname = split.hostname or ""
    port = split.port

    resolved_host = host_override or hostname
    resolved_port = int(port_override) if port_override else port

    if ":" in resolved_host and not resolved_host.startswith("["):
        host_token = f"[{resolved_host}]"
    else:
        host_token = resolved_host

    auth_token = ""
    if username:
        auth_token = username
        if password is not None:
            auth_token += f":{password}"
        auth_token += "@"

    netloc = auth_token + host_token
    if resolved_port is not None:
        netloc += f":{resolved_port}"

    return urlunsplit((split.scheme, netloc, split.path, split.query, split.fragment))
