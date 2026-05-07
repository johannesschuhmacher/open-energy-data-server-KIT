#<!--SPDX-FileCopyrightText: Johannes Schuhmacher-->

#<!--SPDX-License-Identifier: AGPL-3.0-or-later-->

import dbapi_v1 as db   # Name der Datei

# 1) Welche Schemata?
#print(db.list_schemas())           # ['entsoe', 'entsoe_fms', ...]

# 2) Tabellen in 'entsoe_fms'
#print(db.list_tables('entsoe_fms'))

# 3) Spalten anzeigen
#print(db.list_columns('AggregatedGenerationPerType', 'entsoe_fms'))

# 4) Daten
df = db.fetch_df(
        schema='entsoe_fms',
        table='AggregatedGenerationPerType',
        columns=['"DateTime(UTC)"', '"AreaDisplayName"','"ProductionType"','"ActualGenerationOutput[MW]"'],
        where='"ProductionType" = :pt AND "DateTime(UTC)" >= :t0 AND "DateTime(UTC)" <= :t1',
        params={'pt': "Solar", 't0': '2024-01-01 00:00:00 +00:00', 't1': '2024-12-31 23:00:00+00:00'},
        limit=1000,
)
df.head()

# 6 Million cells, mixed string and float took 45 sec to load into # Pandas DataFrame

