#!/usr/bin/env bash
set -euo pipefail

readonly_password="${OEDS_READONLY_PASSWORD:-readonly}"
readonly_password_sql="${readonly_password//\'/\'\'}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_catalog.pg_roles
    WHERE rolname = 'readonly'
  ) THEN
    CREATE ROLE readonly
      WITH LOGIN
      PASSWORD '${readonly_password_sql}'
      NOSUPERUSER
      INHERIT
      NOCREATEDB
      NOCREATEROLE
      NOREPLICATION
      VALID UNTIL 'infinity';
  ELSE
    ALTER ROLE readonly
      WITH LOGIN
      PASSWORD '${readonly_password_sql}'
      VALID UNTIL 'infinity';
  END IF;
END
\$\$;
SQL
