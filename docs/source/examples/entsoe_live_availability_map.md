# ENTSO-E Live Availability Map

This example describes how raw ENTSO-E outage data can be turned into a derived
availability layer for plant-level or country-level map views.

## Goal

Build a near-live view for the next 24 hours that shows whether generation
assets are available, partially available, or unavailable.

## Raw source tables

The core raw inputs come from the ENTSO-E FMS crawler:

- `entsoe_fms.UnavailabilityOfProductionAndGenerationUnits`
- `entsoe_fms.InstalledGenerationCapacityPerProductionUnit`
- `entsoe_fms.ProductionAndGenerationUnits`
- `entsoe_fms.powersystemdata`

## Derived schema concept

The proposed derived schema is `entsoe_availability_map`. It adds:

- an override table for manual asset matching corrections
- a country-center table for fallback display positions
- canonical views for latest outage events and asset reference data
- next-24h availability views for exact and aggregated map layers

## Repository assets

The full prototype lives in two repository files:

- SQL objects: `docs/entsoe_live_availability_schema.sql`
- refresh/backfill helper: `scripts/backfill_entsoe_unavailability.py`

## Status

This is a documented example and design reference, not a default schema that is
created on every install. It is useful when you want to build outage maps or
plant availability dashboards on top of OEDS.
