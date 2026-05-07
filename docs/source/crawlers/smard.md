# `smard`

## Purpose

`crawler.smard` downloads German electricity market data from the SMARD portal
of the Bundesnetzagentur and stores it in the `smard` schema.

The crawler currently targets:

- quarter-hourly generation and consumption series for Germany
- quarter-hourly price series exposed by SMARD

It is useful when you want open-license German market data without depending on
the ENTSO-E Transparency Platform for the same basic indicators.

## Source system and authentication

- Source system: SMARD
- Upstream site: `https://www.smard.de/`
- Authentication: none
- License declared in the crawler metadata: `CC-BY-4.0`

## How to run it manually

From the repository root:

```shell
python -m crawler.smard
```

## Scheduler configuration

The crawler is configured under the `smard` key in `CRAWLER_CONFIG.yml`.

Important options:

- `enable`
- `schema_name`
- `schedule`
- `database_uri`
- `default_start_date`
- `post_run_scripts`

Current default entry:

```yaml
smard:
  enable: true
  schema_name: "smard"
  schedule: "0 4 * * *"
  post_run_scripts:
    - "scripts/gapfill_smard.py"
```

## Output schema and tables

The crawler writes to schema `smard`.

Base tables:

- `smard`
- `prices`

`smard` stores quarter-hourly generation, consumption, and similar commodity
series keyed by `timestamp` and `commodity_id`.

`prices` stores quarter-hourly price series keyed by the same timestamp and
commodity concept.

## Downstream dependencies

The repository currently does not provision a dedicated SMARD-only dashboard.
The schema is primarily useful for:

- ad-hoc SQL analysis
- notebook-based comparisons with ENTSO-E data
- downstream scripts such as `scripts/gapfill_smard.py`

## Operational notes

- The crawler derives its incremental start point from the latest timestamp
  already stored for each commodity.
- `default_start_date` can be used to control the initial backfill window for a
  fresh schema or for targeted smoke tests.
- SMARD exposes separate commodity identifiers for prices and quantity series.
- The crawler writes naive UTC timestamps to PostgreSQL, while upstream SMARD
  timestamps are parsed as UTC during ingestion.
