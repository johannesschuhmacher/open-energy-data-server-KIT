# Grafana dashboard inventory

This inventory captures the current crawler-to-dashboard mapping, the available
data surface for non-ENTSOE crawlers, and the main dashboard gaps to address
next.

## Current dashboard coverage

| Crawler / domain | Existing dashboards | Current state |
| --- | --- | --- |
| `entsoe_fms` | `entsoe.json`, `ENTSOE_FMS.json`, `ENTSOE_Country_Comparator*.json`, `ENTSOE_Cross_Border_Price_Spread_Cockpit*.json`, `ENTSOE_Forecast_Accuracy_Lab*.json`, `ENTSOE_Hydro_*.json`, `ENTSOE_Negative_Prices_*.json`, `ENTSOE_Stress_Cockpit*.json`, `ENTSOE_Transfer_Capacity_Adequacy_Projects.json`, `OEDS_Gapfilling_Quality.json` | Rich special-dashboard suite already exists. A stricter signature basic dashboard is still worth adding as the default first screen. |
| `weather_forecast` | `weather.json`, `Energy_Weather_Dashboard.json` | Good base coverage. One dashboard is operational/weather-centric, the other is energy coupling. |
| `smard` | `smard.json` | Exists, but very thin and currently not a real SMARD signature dashboard. |
| `entsog` | `entsog.json` | Exists, but is still closer to an exploratory monitor than a stable gas operations cockpit. |
| `netztransparenz` | `Netztransparenz_WebAPI.json` | Minimal 4-panel access and data-shape dashboard. |
| `regelleistung` | `Regelleistung_Datacenter.json` | Minimal 4-panel access and tender-data dashboard. |
| `gie_agsi_alsi` | `GIE_AGSI_ALSI.json` | Minimal 4-panel storage/LNG inventory dashboard. |
| `tradinghub` | `Trading_Hub_Europe.json` | Minimal 4-panel report-values dashboard. |
| `prisma_capacity` | `PRISMA_Capacity_API.json` | Minimal raw-import dashboard; mostly ingestion observability. |
| `osm_power` | `OpenStreetMap_Power.json` | Minimal inventory/map dashboard; good first step for infrastructure data. |
| `dwd_cdc` | `DWD_Climate_Data_Center.json` | Minimal monthly climate dashboard. |
| `copernicus_cds` | `Copernicus_CDS.json` | Minimal request/download/statistics dashboard. |
| `open_meteo` | `Open_Meteo.json` | Minimal forecast-ingestion dashboard. |
| `eia` | `EIA_Open_Data.json` | Minimal raw/value dashboard. |
| `eurostat_crawler` | none | Missing signature basic dashboard. |
| `ninja` | none | Missing signature basic dashboard. |
| `mastr` | none | Missing signature basic dashboard. |
| `energy_forecast_crawler` | `energy_forecast.json` | Forecast cockpit exists; a stricter signature basic dashboard can still be added later. |
| `power_system_data` | none | New reference layer for plant coordinates and EIC-to-location mapping used by ENTSO-E maps. |
| `epex_spot` | none | Missing signature basic dashboard. |
| `shared` | `OEDS_Datenschutz.json`, `GloHydroRes_Hydro_Plants_Reservoirs.json` | Cross-crawler / non-crawler dashboards. |

## Non-ENTSOE data inventory

### `eurostat_crawler`

- Table: `eurostat.eurostat`
- Main dimensions: `freq`, `geo\\TIME_PERIOD`, `plant_tec`, `siec`, `unit`,
  `year`
- Value field: `capacity`
- Assessment: usable for annual structural views, but only one dataset is
  loaded at the moment (`nrg_inf_epcrw` in `CRAWLER_CONFIG.yml`).

### `smard`

- Table: `smard.smard`
  - `timestamp`, `commodity_id`, `commodity_name`, `mwh`,
    `download_timestamp`
- Table: `smard.prices`
  - `timestamp`, `commodity_id`, `price`
- Current commodity scope in code:
  - price
  - realized load
  - biomass
  - hydro
  - wind offshore
  - wind onshore
  - photovoltaics
  - other renewables
  - lignite
  - gas
  - pumped storage
  - other conventional
  - hard coal

### `ninja`

- Table: `ninja.capacity_wind_on`
- Table: `ninja.capacity_wind_off`
- Table: `ninja.capacity_solar_merra2`
- Assessment: time-series capacity-factor style data imported from the
  Europe-wide Renewables.ninja files. The crawler currently exposes raw source
  tables without an additional curated summary layer.

### `mastr`

- Data model is dynamic.
- Table names are derived from the XML filenames inside the MaStR full export.
- Primary keys are inferred from fields such as `MastrNummer`,
  `EinheitMastrNummer`, `EegMastrNummer`, `KwkMastrNummer`,
  `NetzanschlusspunktMastrNummer`, `Id`, or `GenMastrNummer`.
- Assessment: huge raw registry surface, but no curated semantic layer yet. A
  useful dashboard should start from a selected subset instead of the entire
  raw export.

### `entsog`

- Reference tables:
  - `entsog.operators`
  - `entsog.connectionpoints`
  - `entsog.balancingzones`
  - `entsog.operatorpointdirections`
  - `entsog.interconnections`
  - `entsog.aggregateinterconnections`
- Operational tables:
  - `entsog.physical_flow`
  - `entsog.allocation`
  - `entsog.firm_technical`
- Time fields: `periodfrom`, `periodto`
- Assessment: solid gas-network basis already exists, but the current
  dashboard does not present the operational model clearly enough.

### `energy_forecast_crawler`

- Table: `energy_forecast.predictions_48h`
- Primary key: `prediction_start`
- Value layout:
  - 192 quarter-hour price forecast columns named `p_h_XX_m_YY`
  - 192 matching origin columns named `o_h_XX_m_YY`
- Assessment: useful forecast input, but awkward for Grafana because the
  crawler stores the horizon in a wide table.

### `power_system_data`

- Table: `power_system_data.powersystemdata`
  - Plant names, fuel types, countries, capacities, lifecycle years, and
    `lat`/`lon` coordinates from PyPSA powerplantmatching.
- Table: `power_system_data.eic_geo_location`
  - EIC codes mapped to plant coordinates for ENTSO-E generation-unit maps.
- Assessment: primarily a reference layer for ENTSO-E spatial dashboards.

### `epex_spot`

- Table: `epex_spot.intraday_auction_prices_volumes`
  - auction product rows with `auction_name`, delivery timestamps, `metric`,
    `value`, `market_area`
- Table: `epex_spot.continuous_trades`
  - trade-level rows with execution time, delivery window, side, price,
    volume, product, area
- Table: `epex_spot.continuous_indices`
  - published indices with price and index volume
- Table: `epex_spot.continuous_statistics`
  - delivery-window statistics such as low/high/last/weighted-average price
    and buy/sell volume

### `weather_forecast`

- Table: `weather.locations`
  - location metadata with country, region, type, lat/lon, weight
- Table: `weather.hourly_forecast`
  - weather and derived energy features such as temperature, apparent
    temperature, wind speed, shortwave/direct/diffuse radiation,
    precipitation, humidity, cloud cover, heating/cooling degree signals, and
    weather indices
- Table: `weather.entsoe_country_aliases`
  - mapping between country codes and ENTSOE display names

### `netztransparenz`

- Table: `netztransparenz.endpoint_runs`
  - endpoint-level fetch history with status code, requested window, and row
    count
- Table: `netztransparenz.raw_rows`
  - raw payload rows as JSON
- Table: `netztransparenz.normalized_values`
  - normalized values with `endpoint_id`, `label`, `area`, `category`,
    `data_type`, `direction`, timestamps, `unit`, `value`, `status`

### `regelleistung`

- Table: `regelleistung.tender_files`
  - discovered files with product, market, file type, date-range metadata
- Table: `regelleistung.file_rows`
  - raw workbook rows as JSON
- Table: `regelleistung.numeric_values`
  - normalized numeric values with `delivery_date`, `product_type`, `market`,
    `measure`, `unit`, `value`

### `gie_agsi_alsi`

- Table: `gie_agsi_alsi.daily_inventory`
- Key fields:
  - `platform`, `scope`, `name`, `code`
  - `gas_day_start`
  - `gas_in_storage`, `working_gas_volume`, `full_pct`
  - `injection`, `withdrawal`, `injection_capacity`,
    `withdrawal_capacity`, `status`

### `tradinghub`

- Table: `tradinghub.report_rows`
  - raw report rows as JSON
- Table: `tradinghub.report_values`
  - normalized values with `report_id`, `gas_day`, `dimension`, `measure`,
    `unit`, `value`, `status`

### `prisma_capacity`

- Table: `prisma_capacity.raw_resources`
- Key fields:
  - `resource_id`, `source_url`, `fetched_at`, `row_number`, `payload_json`
- Assessment: raw ingestion only. A better dashboard needs a normalized fact
  layer first.

### `osm_power`

- Table: `osm_power.power_features`
- Key fields:
  - `osm_id`, `osm_type`, `name`, `operator`, `power`, `voltage`
  - `latitude`, `longitude`
  - `tags_json`, `source`, `fetched_at`

### `dwd_cdc`

- Table: `dwd_cdc.regional_monthly`
- Key fields:
  - `region`, `variable`, `year`, `month`, `period_start`, `unit`, `value`
  - `source_created_at`, `source_url`, `fetched_at`

### `copernicus_cds`

- Table: `copernicus_cds.requests`
  - request lifecycle with dataset, request JSON, target path, status, error
- Table: `copernicus_cds.downloaded_files`
  - downloaded file records with request ID and file size
- Table: `copernicus_cds.variable_statistics`
  - variable-level min/mean/max/observation counts per request

### `open_meteo`

- Table: `open_meteo.locations`
  - location metadata
- Table: `open_meteo.hourly_forecast`
  - normalized long-format forecast rows with `location_id`, `valid_time`,
    `variable`, `value`, `unit`, `fetched_at`

### `eia`

- Table: `eia.api_rows`
  - raw API rows with `request_id`, `period`, `payload_json`
- Table: `eia.numeric_values`
  - normalized long-format values with `request_id`, `period`, `dimension`,
    `measure`, `unit`, `value`

## Recommended improvements

### General

- Add one signature basic dashboard per crawler. The current small dashboards
  mostly show access state and row counts, but not data freshness, coverage,
  and the main business signal.
- Standardize the basic layout:
  - freshness / last successful fetch
  - total rows or entities
  - coverage by key dimension
  - one recent time series panel
  - one latest snapshot / top-N table
- Prefer source-owned dashboards over cross-schema coupling in the basic
  dashboard. Use cross-crawler comparisons only in special dashboards.
- Make helper views explicit. Several dashboards depend on views such as
  `latest_values`, `location_summary`, `regional_summary`, `resource_summary`,
  and `access_status`. Those dependencies should be documented or bootstrapped
  centrally.

### Crawler-specific

- `smard`: replace the current 2-panel file with a real SMARD baseline:
  price, realized load, generation stack, commodity coverage, and freshness.
- `entsog`: refocus the existing monitor around network semantics:
  point/operator filters, physical flow vs allocation vs firm technical
  capacity, and recent ingestion freshness.
- `weather_forecast`: split "raw forecast operations" and "energy relevance"
  more clearly; keep `Energy_Weather_Dashboard` as a special dashboard.
- `netztransparenz`: add endpoint freshness, failure history, area/category
  coverage, and a clearer latest-values grid.
- `regelleistung`: add market/product filters, delivery-day trend panels, and
  recent tender coverage by product and market.
- `gie_agsi_alsi`: add country/platform segmentation, latest fill levels, net
  injection/withdrawal trends, and outlier highlighting.
- `tradinghub`: add report family filters, gas-day trend views, and a stable
  "latest per report and measure" section.
- `prisma_capacity`: the current dashboard mainly confirms raw ingestion; a
  real basic dashboard needs normalized subscription-specific facts first.
- `osm_power`: add breakdowns by `power` tag, operator, voltage class, and
  change/fetch history.
- `dwd_cdc`: add variable selectors, region comparison, anomaly vs long-term
  average, and temporal completeness indicators.
- `copernicus_cds`: add request durations, failure reasons, dataset-specific
  throughput, and file volume trends.
- `open_meteo`: add location/variable selectors, forecast horizon completeness,
  and last-refresh age.
- `eia`: add request-level filters, measure coverage, and recent value growth
  by route.
- `eurostat_crawler`: a basic dashboard should focus on country, fuel,
  technology, and annual trend slices for the configured dataset.
- `ninja`: a basic dashboard should show country coverage, time range, and
  capacity-factor distributions for onshore wind, offshore wind, and solar.
- `mastr`: start with a curated summary layer first; a raw-table dashboard
  would be too noisy.
- `energy_forecast_crawler`: the forecast horizon dashboard exists; a
  long-format view would still make future panels simpler.
- `epex_spot`: build one baseline around auction prices, continuous statistics,
  and trade volume/freshness, with a separate special dashboard for micro-level
  trade analysis.

## Dashboard folder structure

The repo now uses one top-level dashboard folder per crawler plus `shared/`:

```text
data/provisioning/grafana/dashboards/
  copernicus_cds/
  dwd_cdc/
  eia/
  energy_forecast_crawler/
  entsoe_fms/
  entsog/
  epex_spot/
  eurostat_crawler/
  gie_agsi_alsi/
  mastr/
  netztransparenz/
  ninja/
  open_meteo/
  osm_power/
  prisma_capacity/
  regelleistung/
  shared/
  smard/
  tradinghub/
  weather_forecast/
```

Planned convention for the new required baseline dashboards:

- `dashboards/<crawler>/Signature_Basic.json`
- additional deep-dive dashboards stay in the same crawler folder
