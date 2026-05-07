# ENTSO-E Live Availability Map for OEDS

## Goal

Build a near-live European map of power plant availability for the next 24 hours.
The map should show plant-level status as `green`, `yellow`, or `red` and support
separate `planned` and `forced` outage layers.

Current decisions for this use case:

- default map layer: `combined`
- hourly aggregation rule: conservative `minimum available capacity within the hour`
- assets without exact plant coordinates: show aggregated at the country center
  with `location_tag = unknown`

## What ENTSO-E actually provides

The relevant ENTSO-E Transparency Platform source is
`UnavailabilityOfProductionAndGenerationUnits_15.1.A_B_C_D_r3`.
It is published as a monthly CSV extract in the File Library, not as a ready-made
hourly time series. The data therefore has to be discretized into time buckets
inside OEDS.

Verified source facts:

- The outage extract is event-based and contains `StartOutage(UTC)`,
  `EndOutage(UTC)`, `StartTimeSeries(UTC)`, `EndTimeSeries(UTC)`,
  `Status`, `Type`, `AssetCode`, `AssetType`, `ProductionType`,
  `AvailableCapacity[MW]`, `Reason`, `VersionPublicationTimestamp(UTC)`,
  and `UpdateTime(UTC)`.
- `Status` is currently `Active`, `Cancelled`, or `Withdrawn`.
- `Type` is currently `Forced` or `Planned`.
- Planned maintenance is business type `A53`; unplanned outage is business type
  `A54`.
- `AssetCode` is an EIC resource-object code in practice. ENTSO-E defines EIC
  object type `W` for resource objects such as production, consumption, and
  storage assets.
- The publication thresholds matter: generation-unit outages cover units of
  `100 MW+`; production-unit outages cover `200 MW+` if they are not already
  disclosed on generation-unit level. Smaller units will therefore not appear
  consistently in this map.
- The current combined 15.1 extract exposes `AvailableCapacity[MW]`, but not
  `InstalledCapacity[MW]`. For traffic-light logic, OEDS should therefore use
  `entsoe_fms.InstalledGenerationCapacityPerProductionUnit` as the primary
  denominator source and only fall back to other sources where the outage asset
  cannot be matched cleanly.

Related ENTSO-E sources needed for the denominator and asset master data:

- `InstalledGenerationCapacityPerProductionUnit_14.1.B_r3`
- `ProductionAndGenerationUnits_r3`
- EIC allocated code lists for optional enrichment

## What OEDS already has

Existing OEDS assets that are directly useful:

- `entsoe_fms.UnavailabilityOfProductionAndGenerationUnits`
- `entsoe_fms.InstalledGenerationCapacityPerProductionUnit`
- `entsoe_fms.powersystemdata`

`powersystemdata` is already populated from the OPSD/PyPSA plant list and carries
`eic_code`, `name`, `country`, `capacity`, `lon`, and `lat`. In this repo, the
coordinate mapping happens in `save_power_system_data()` in
`crawler/entsoe_crawler.py` and `crawler/entsoe_fms.py`. I did not find a map
rendering module in this repository; the repo currently provides the data side,
not the frontend layer.

## Recommended OEDS schema

Create a new derived schema named `entsoe_availability_map`.

This schema should not duplicate the raw ENTSO-E crawler tables. It should add:

1. A small curated override table for manual asset mapping corrections.
2. A country-center reference table for fallback display positions.
3. Canonical views on top of `entsoe_fms`.
4. One plant-level next-24h availability view for exact locations.
5. One aggregated next-24h availability view for unknown locations.

### 1. Curated table: `asset_mapping_override`

Purpose:

- fix coordinates where `powersystemdata` does not match the outage asset EIC
- override installed capacity if ENTSO-E and OPSD disagree
- keep a manual audit trail for problematic assets

Key:

- `asset_code`

Important columns:

- `override_asset_name`
- `override_installed_capacity_mw`
- `override_lon`
- `override_lat`
- `override_geom`
- `override_country`
- `override_production_type`
- `mapping_confidence`
- `note`
- `updated_at`

### 2. Reference table: `country_display_point`

Purpose:

- provide one fallback display point per country
- support aggregated display of assets without exact plant coordinates

Key:

- `country_key`

Important columns:

- `country_name`
- `lon`
- `lat`
- `geom`

`country_key` should match the country grouping used by the final map layer. In
practice this should be normalized to the same country identifier used in
`powersystemdata` or your frontend country overlay.

### 3. Canonical view: `v_outage_event_latest`

Purpose:

- collapse versioned outage rows to the latest state
- keep only currently active rows
- normalize the layer dimension to `planned` / `forced`

Key logic:

- source: `entsoe_fms.UnavailabilityOfProductionAndGenerationUnits`
- latest version per `InstanceCode + AssetCode + StartTimeSeries + EndTimeSeries`
- keep `Status = 'Active'`
- use `StartTimeSeries(UTC)` / `EndTimeSeries(UTC)` for time-step overlap
  because the available capacity is attached to the time-series segment, not
  only to the coarse outage envelope

### 4. Canonical view: `v_asset_reference`

Purpose:

- produce one asset master record per outage asset
- attach geometry, installed capacity, and display metadata

Join priority:

1. `asset_mapping_override`
2. `entsoe_fms.ProductionAndGenerationUnits`
3. `entsoe_fms.InstalledGenerationCapacityPerProductionUnit` as the primary
   installed-capacity source
4. `entsoe_fms.powersystemdata`

Important output columns:

- `asset_code`
- `asset_name`
- `asset_type`
- `production_type`
- `installed_capacity_mw`
- `capacity_source`
- `country`
- `lon`
- `lat`
- `geom`
- `mapping_confidence`
- `is_mappable`
- `country_key`
- `location_tag`
- `display_mode`

Recommended semantics:

- `location_tag = exact` for plant-level coordinates
- `location_tag = unknown` if the asset has no exact plant coordinates
- `display_mode = plant` for exact plant markers
- `display_mode = country_centroid` for fallback aggregation only

### 5. Live view: `v_availability_next_24h`

Purpose:

- expose one row per `asset + hour + layer` for assets with exact locations
- give the frontend a direct plant-marker payload

Granularity:

- hourly for now
- horizon: `date_trunc('hour', now())` through `+23 hours`

Recommended row grain:

- `snapshot_utc`
- `asset_code`
- `layer` in `planned`, `forced`, `combined`

Frontend default:

- default selected layer should be `combined`

Important output columns:

- `snapshot_utc`
- `asset_code`
- `asset_name`
- `asset_type`
- `production_type`
- `country`
- `area_code`
- `area_display_name`
- `layer`
- `installed_capacity_mw`
- `available_capacity_mw`
- `unavailable_capacity_mw`
- `availability_ratio`
- `status_color`
- `active_outage_count`
- `reason`
- `lon`
- `lat`
- `geom`
- `location_tag`
- `display_mode`

Frontend usage:

- use this view for exact plant markers
- filter to `location_tag = exact`

### 6. Live view: `v_availability_country_unknown_agg_next_24h`

Purpose:

- aggregate all assets without exact plant coordinates by country and hour
- place one fallback marker per country center
- preserve visibility of otherwise lost outage information

Recommended row grain:

- `snapshot_utc`
- `country_key`
- `layer`

Important output columns:

- `snapshot_utc`
- `country_key`
- `country_name`
- `layer`
- `asset_count`
- `installed_capacity_mw`
- `available_capacity_mw`
- `unavailable_capacity_mw`
- `availability_ratio`
- `status_color`
- `lon`
- `lat`
- `geom`
- `location_tag`

Frontend usage:

- use this view for fallback markers only
- all rows should carry `location_tag = unknown`
- tooltip should explain that the marker is an aggregate at country-center level,
  not an exact plant position

## Traffic-light logic

Recommended default logic:

- `green`: `available_capacity_mw >= installed_capacity_mw - tolerance`
- `yellow`: `0 < available_capacity_mw < installed_capacity_mw - tolerance`
- `red`: `available_capacity_mw <= 0`
- `unknown`: installed capacity missing, geometry missing, or denominator not
  trustworthy enough

Recommended tolerance:

- `max(1 MW, 1% of installed capacity)`

This avoids false `yellow` states caused by rounding differences between ENTSO-E
and fallback denominators.

Important distinction:

- `status_color` describes availability
- `location_tag` describes spatial certainty

So an aggregated country-center marker can still be `red`, `yellow`, or `green`
while carrying `location_tag = unknown`.

## Hourly discretization logic

Because ENTSO-E publishes intervals, OEDS should derive the next 24 hours like
this:

1. Generate an hourly time grid.
2. For each asset and hour, find all active outage rows whose
   `StartTimeSeries(UTC)` / `EndTimeSeries(UTC)` overlaps the hour bucket.
3. For `planned` and `forced`, compute the minimum available capacity across all
   overlapping rows in that layer for the hour.
4. For `combined`, compute the minimum available capacity across all overlapping
   rows regardless of layer.
5. If no outage overlaps the hour, set `available_capacity_mw = installed_capacity_mw`.

Using the minimum available capacity is the chosen rule for this use case. It is
conservative and works well for a live traffic-light map. A plant therefore turns
yellow or red for an hour if any active outage slice within that hour reduces the
available capacity to that level.

## Refresh strategy

For a near-live map, the current `entsoe_fms` scheduler frequency of every 3 hours
is too coarse. ENTSO-E publishes outage changes with an `H+1` expectation, so the
derived layer should refresh at least hourly.

Recommended operations model:

- run `entsoe_fms` hourly
- refresh the derived availability view or materialized view after each crawler run
- expose the result via PostgREST

If frontend latency is more important than storage minimization:

- use a materialized view for `v_availability_next_24h`
- use a materialized view for `v_availability_country_unknown_agg_next_24h`
- refresh it after each crawler run

If always-fresh SQL is more important than compute cost:

- use a normal view

## Recommended implementation note for OEDS

`InstalledGenerationCapacityPerProductionUnit` is the primary installed-capacity
source for this design and should be used first. `ProductionAndGenerationUnits_r3`
is still recommended as an additional asset master source because the outage
extract mixes production and generation assets and not every outage asset will
necessarily match the production-unit table one-to-one.

## Sources

Official ENTSO-E sources used for this schema design:

- File Library Guide:
  https://transparencyplatform.zendesk.com/hc/en-us/articles/35960137882129
- Unavailability of Production and Generation Units [15.1.A/B/C/D]:
  https://transparencyplatform.zendesk.com/hc/en-us/articles/16652173943828-Unavailability-of-Production-and-Generation-Units-15-1-A-15-1-B-15-1-C-15-1-D-
- 15.1 extract columns:
  https://transparencyplatform.zendesk.com/hc/en-us/articles/32492060810513-UnavailabilityOfProductionAndGenerationUnits-15-1-A-B-C-D-r3
- Installed Capacity Per Production Unit [14.1.B]:
  https://transparencyplatform.zendesk.com/hc/en-us/articles/16648452972180-Installed-Capacity-Per-Production-Unit-14-1-B
- ProductionAndGenerationUnits_r3:
  https://transparencyplatform.zendesk.com/hc/en-us/articles/36496214610449
- BusinessType code list:
  https://transparencyplatform.zendesk.com/hc/en-us/articles/15857010932500
- ENTSO-E EIC overview:
  https://www.entsoe.eu/data/energy-identification-codes-eic/
- ENTSO-E EIC reference manual:
  https://www.entsoe.eu/Documents/EDI/Library/EIC_Reference_Manual_Release_5_4.pdf

## Open questions

1. Which country identifier should be canonical for fallback aggregation:
   ISO code, OPSD country name, or ENTSO-E area/map code?
