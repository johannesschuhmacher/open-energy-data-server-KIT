# epex_spot

## Purpose

`crawler.epex_spot` imports German EPEX SPOT intraday market data from the
market-data SFTP service into the OEDS PostgreSQL database.

The crawler is configured to cover all currently supported intraday datasets:

- Intraday Continuous end-of-day statistics
- Intraday Continuous indices
- Intraday Continuous transaction ZIP files
- Pan-European intraday auction prices and volumes for IDA1, IDA2, and IDA3

## Source system and authentication

The crawler reads from `sftp.marketdata.epexspot.com` on port `22`.

Required credentials:

- `EPEX_SFTP_USERNAME`
- `EPEX_SFTP_PASSWORD`

Set them as environment variables or in `crawler/.env`. Do not commit real
credentials.

## How to run it manually

Run from the repository root:

```shell
python -m crawler.epex_spot
```

For scheduled OEDS writes, prefer the `database_uri` in `CRAWLER_CONFIG.yml`.
The crawler intentionally prefers that configuration over a local
`EPEX_DATABASE_URI`, so stale local overrides do not redirect scheduled imports.

## Scheduler configuration

The crawler is configured under the `epex_spot` key in `CRAWLER_CONFIG.yml`.

Important options:

- `enable`
- `schema_name`
- `database_uri`
- `schedule`
- `start_date`
- `update_interval_days`
- `include_continuous_statistics`
- `include_continuous_indices`
- `include_intraday_auctions`
- `include_continuous_trades`
- `target_datasets`

`target_datasets` can restrict a run to selected datasets. Valid dataset names
are `continuous_statistics`, `continuous_indices`, `intraday_auctions`, and
`continuous_trades`.

## Output schema and tables

The crawler writes to schema `epex_spot`.

Tables:

- `continuous_statistics`
- `continuous_indices`
- `intraday_auction_prices_volumes`
- `continuous_trades`

All writes use conflict-safe upserts, so repeated scheduled runs can refresh
recent files without duplicating rows.

## Downstream dependencies

No production dashboard is pinned to this schema yet. The data is available for
PostgREST, Grafana, and analysis queries once imported.

## Operational notes

- `start_date: "1970-01-01"` means the first enabled run imports all files
  available from the SFTP paths.
- Later runs recrawl the latest `update_interval_days` and upsert refreshed
  values.
- Continuous transaction ZIP files can be large. The crawler supports them, but
  the first full historical import may take substantially longer than the
  aggregate statistics, indices, and auction files.
