# Crawler Documentation

This section contains crawler-specific operational documentation.

The generic scheduler and development model are documented in
[crawler_config.md](../crawler_config.md) and
[crawler_development.md](../crawler_development.md). The pages in this folder
describe what a specific crawler does, how it is configured, which tables it
writes, and which downstream dashboards or scripts depend on it.

## Recommended structure

For each crawler, create one file at:

`docs/source/crawlers/<crawler_name>.md`

Use the same section order for every crawler page:

1. Purpose
2. Source system and authentication
3. How to run it manually
4. Scheduler configuration
5. Output schema and tables
6. Downstream dependencies
7. Operational notes

This keeps the documentation readable for operators and makes crawler pages easy to compare.

## Documentation status

Currently documented crawlers:

- [entsoe_fms](./entsoe_fms.md)
- [entsog](./entsog.md)
- [weather_forecast](./weather_forecast.md)
- [energy_forecast_crawler](./energy_forecast_crawler.md)
- [smard](./smard.md)
- [mastr](./mastr.md)
- [eurostat_crawler](./eurostat_crawler.md)
- [epex_spot](./epex_spot.md)

Recommended next candidates:

- `ninja`
- `dwd_cdc`
- `open_meteo`
