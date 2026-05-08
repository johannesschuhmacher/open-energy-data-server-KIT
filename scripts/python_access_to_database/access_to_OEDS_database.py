#<!--SPDX-FileCopyrightText: Johannes Schuhmacher-->

#<!--SPDX-License-Identifier: AGPL-3.0-or-later-->

import dbapi_v1 as db

# 1) Which schemas are available?
# print(db.list_schemas())  # ['entsoe', 'entsoe_fms', ...]

# 2) Which tables exist in 'entsoe_fms'?
# print(db.list_tables("entsoe_fms"))

# 3) Which columns does a table expose?
# print(db.list_columns("AggregatedGenerationPerType", schema="entsoe_fms"))

# 4) Fetch data
df = db.fetch_df(
    schema="entsoe_fms",
    table="AggregatedGenerationPerType",
    columns=[
        '"DateTime(UTC)"',
        '"AreaDisplayName"',
        '"ProductionType"',
        '"ActualGenerationOutput[MW]"',
    ],
    where='"ProductionType" = :pt AND "DateTime(UTC)" >= :t0 AND "DateTime(UTC)" <= :t1',
    params={
        "pt": "Solar",
        "t0": "2024-01-01 00:00:00 +00:00",
        "t1": "2024-12-31 23:00:00+00:00",
    },
    limit=1000,
)
df.head()

# Rough benchmark: ~6 million mixed string/float cells took ~45 seconds to load
# into a Pandas DataFrame on the original test machine.
