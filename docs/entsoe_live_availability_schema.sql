-- Proposed OEDS schema for a live ENTSO-E power plant availability map.
-- This script is intentionally additive: raw ENTSO-E data stays in entsoe_fms.
-- Chosen semantics:
--   - default frontend layer: combined
--   - hourly aggregation: minimum available capacity within the hour
-- Primary installed-capacity source:
--   - entsoe_fms."InstalledGenerationCapacityPerProductionUnit"
-- Fallback spatial semantics:
--   - assets without exact coordinates are aggregated by country centroid
--   - aggregated rows carry location_tag = 'unknown'

CREATE SCHEMA IF NOT EXISTS entsoe_availability_map;

CREATE TABLE IF NOT EXISTS entsoe_availability_map.asset_mapping_override (
    asset_code text PRIMARY KEY,
    override_asset_name text,
    override_installed_capacity_mw double precision,
    override_lon double precision,
    override_lat double precision,
    override_geom geometry(Point, 4326),
    override_country text,
    override_production_type text,
    mapping_confidence text NOT NULL DEFAULT 'manual',
    note text,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (
        mapping_confidence IN (
            'manual',
            'opsd_eic',
            'entsoe_unit',
            'fallback_capacity_only',
            'unmatched'
        )
    )
);

CREATE TABLE IF NOT EXISTS entsoe_availability_map.country_display_point (
    country_key text PRIMARY KEY,
    country_name text NOT NULL,
    lon double precision NOT NULL,
    lat double precision NOT NULL,
    geom geometry(Point, 4326) NOT NULL
);

CREATE OR REPLACE VIEW entsoe_availability_map.v_outage_event_latest AS
WITH ranked AS (
    SELECT
        o.*,
        row_number() OVER (
            PARTITION BY
                o."InstanceCode",
                o."AssetCode",
                o."StartTimeSeries(UTC)",
                o."EndTimeSeries(UTC)"
            ORDER BY
                o."Version" DESC,
                o."UpdateTime(UTC)" DESC
        ) AS version_rank
    FROM entsoe_fms."UnavailabilityOfProductionAndGenerationUnits" o
),
latest AS (
    SELECT *
    FROM ranked
    WHERE version_rank = 1
      AND "Status" = 'Active'
      AND COALESCE("EndTimeSeries(UTC)", "EndOutage(UTC)") > now()
)
SELECT
    "InstanceCode" AS instance_code,
    "Version" AS version,
    "OldVersion" AS old_version,
    "Status" AS status,
    lower("Type") AS layer,
    "AreaCode" AS area_code,
    "AreaDisplayName" AS area_display_name,
    "AreaTypeCode" AS area_type_code,
    "AreaMapCode" AS area_map_code,
    "AssetCode" AS asset_code,
    "AssetName" AS asset_name,
    "AssetType" AS asset_type,
    "ProductionType" AS production_type,
    "AvailableCapacity[MW]"::double precision AS available_capacity_mw,
    "Reason" AS reason,
    "ReasonText" AS reason_text,
    "StartOutage(UTC)" AS start_outage_utc,
    "EndOutage(UTC)" AS end_outage_utc,
    "StartTimeSeries(UTC)" AS start_timeseries_utc,
    "EndTimeSeries(UTC)" AS end_timeseries_utc,
    "VersionPublicationTimestamp(UTC)" AS version_publication_timestamp_utc,
    "UpdateTime(UTC)" AS update_time_utc
FROM latest;

CREATE OR REPLACE VIEW entsoe_availability_map.v_asset_reference AS
WITH outage_assets AS (
    SELECT DISTINCT
        o.asset_code,
        o.asset_name,
        o.asset_type,
        o.production_type,
        o.area_code,
        o.area_display_name,
        o.area_type_code,
        o.area_map_code,
        o.update_time_utc
    FROM entsoe_availability_map.v_outage_event_latest o
),
prod_unit_latest AS (
    SELECT DISTINCT ON ("ProductionUnitCode")
        "ProductionUnitCode" AS production_unit_code,
        "ProductionUnitName" AS production_unit_name,
        "ProductionType" AS production_type,
        "InstalledCapacity(MW)"::double precision AS installed_capacity_mw,
        "AreaCode" AS area_code,
        "AreaDisplayName" AS area_display_name,
        "AreaTypeCode" AS area_type_code,
        "UpdateTime(UTC)" AS update_time_utc
    FROM entsoe_fms."InstalledGenerationCapacityPerProductionUnit"
    ORDER BY
        "ProductionUnitCode",
        COALESCE("ValidTo", "ValidFrom") DESC,
        "UpdateTime(UTC)" DESC
)
SELECT
    a.asset_code,
    COALESCE(m.override_asset_name, a.asset_name, p.name, pu.production_unit_name) AS asset_name,
    a.asset_type,
    COALESCE(m.override_production_type, a.production_type, pu.production_type, p.energy_source) AS production_type,
    COALESCE(
        m.override_installed_capacity_mw,
        CASE
            WHEN a.asset_type = 'Production Unit' THEN pu.installed_capacity_mw
            ELSE NULL
        END,
        p.capacity
    ) AS installed_capacity_mw,
    CASE
        WHEN m.override_installed_capacity_mw IS NOT NULL THEN 'manual'
        WHEN a.asset_type = 'Production Unit' AND pu.installed_capacity_mw IS NOT NULL THEN 'entsoe_unit'
        WHEN p.capacity IS NOT NULL THEN 'opsd_eic'
        ELSE 'fallback_capacity_only'
    END AS capacity_source,
    COALESCE(m.override_country, p.country, a.area_map_code) AS country,
    COALESCE(m.override_lon, p.lon) AS lon,
    COALESCE(m.override_lat, p.lat) AS lat,
    COALESCE(
        m.override_geom,
        CASE
            WHEN p.lon IS NOT NULL AND p.lat IS NOT NULL
                THEN ST_SetSRID(ST_MakePoint(p.lon, p.lat), 4326)
            ELSE NULL
        END
    ) AS geom,
    CASE
        WHEN m.asset_code IS NOT NULL THEN m.mapping_confidence
        WHEN p.eic_code IS NOT NULL THEN 'opsd_eic'
        WHEN a.asset_type = 'Production Unit' AND pu.production_unit_code IS NOT NULL THEN 'entsoe_unit'
        ELSE 'unmatched'
    END AS mapping_confidence,
    COALESCE(m.override_country, p.country, a.area_map_code) AS country_key,
    (COALESCE(m.override_lon, p.lon) IS NOT NULL AND COALESCE(m.override_lat, p.lat) IS NOT NULL) AS is_mappable,
    CASE
        WHEN COALESCE(m.override_lon, p.lon) IS NOT NULL AND COALESCE(m.override_lat, p.lat) IS NOT NULL THEN 'exact'
        ELSE 'unknown'
    END AS location_tag,
    CASE
        WHEN COALESCE(m.override_lon, p.lon) IS NOT NULL AND COALESCE(m.override_lat, p.lat) IS NOT NULL THEN 'plant'
        ELSE 'country_centroid'
    END AS display_mode,
    a.area_code,
    a.area_display_name,
    a.area_type_code,
    a.area_map_code,
    a.update_time_utc AS last_seen_update_time_utc
FROM outage_assets a
LEFT JOIN entsoe_availability_map.asset_mapping_override m
    ON m.asset_code = a.asset_code
LEFT JOIN entsoe_fms.powersystemdata p
    ON p.eic_code = a.asset_code
LEFT JOIN prod_unit_latest pu
    ON pu.production_unit_code = a.asset_code;

CREATE OR REPLACE VIEW entsoe_availability_map.v_availability_next_24h AS
WITH hours AS (
    SELECT
        generate_series(
            date_trunc('hour', now()),
            date_trunc('hour', now()) + interval '23 hours',
            interval '1 hour'
        ) AS snapshot_utc
),
asset_hours AS (
    SELECT
        h.snapshot_utc,
        a.*
    FROM hours h
    CROSS JOIN entsoe_availability_map.v_asset_reference a
),
hourly_overlap AS (
    SELECT
        ah.snapshot_utc,
        ah.asset_code,
        ah.asset_name,
        ah.asset_type,
        ah.production_type,
        ah.installed_capacity_mw,
        ah.capacity_source,
        ah.country,
        ah.lon,
        ah.lat,
        ah.geom,
        ah.mapping_confidence,
        ah.country_key,
        ah.is_mappable,
        ah.location_tag,
        ah.display_mode,
        ah.area_code,
        ah.area_display_name,
        ah.area_type_code,
        ah.area_map_code,
        MIN(o.available_capacity_mw) FILTER (WHERE o.layer = 'planned') AS planned_available_capacity_mw,
        MIN(o.available_capacity_mw) FILTER (WHERE o.layer = 'forced') AS forced_available_capacity_mw,
        MIN(o.available_capacity_mw) AS combined_available_capacity_mw,
        COUNT(*) FILTER (WHERE o.layer = 'planned') AS planned_outage_count,
        COUNT(*) FILTER (WHERE o.layer = 'forced') AS forced_outage_count,
        string_agg(DISTINCT o.reason, '; ') FILTER (WHERE o.reason IS NOT NULL) AS reasons
    FROM asset_hours ah
    LEFT JOIN entsoe_availability_map.v_outage_event_latest o
        ON o.asset_code = ah.asset_code
       AND tstzrange(o.start_timeseries_utc, o.end_timeseries_utc, '[)')
           && tstzrange(ah.snapshot_utc, ah.snapshot_utc + interval '1 hour', '[)')
    GROUP BY
        ah.snapshot_utc,
        ah.asset_code,
        ah.asset_name,
        ah.asset_type,
        ah.production_type,
        ah.installed_capacity_mw,
        ah.capacity_source,
        ah.country,
        ah.lon,
        ah.lat,
        ah.geom,
        ah.mapping_confidence,
        ah.country_key,
        ah.is_mappable,
        ah.location_tag,
        ah.display_mode,
        ah.area_code,
        ah.area_display_name,
        ah.area_type_code,
        ah.area_map_code
),
layered AS (
    SELECT
        snapshot_utc,
        asset_code,
        asset_name,
        asset_type,
        production_type,
        installed_capacity_mw,
        capacity_source,
        country,
        lon,
        lat,
        geom,
        mapping_confidence,
        country_key,
        is_mappable,
        location_tag,
        display_mode,
        area_code,
        area_display_name,
        area_type_code,
        area_map_code,
        'planned'::text AS layer,
        planned_outage_count AS active_outage_count,
        COALESCE(planned_available_capacity_mw, installed_capacity_mw) AS available_capacity_mw,
        reasons
    FROM hourly_overlap

    UNION ALL

    SELECT
        snapshot_utc,
        asset_code,
        asset_name,
        asset_type,
        production_type,
        installed_capacity_mw,
        capacity_source,
        country,
        lon,
        lat,
        geom,
        mapping_confidence,
        country_key,
        is_mappable,
        location_tag,
        display_mode,
        area_code,
        area_display_name,
        area_type_code,
        area_map_code,
        'forced'::text AS layer,
        forced_outage_count AS active_outage_count,
        COALESCE(forced_available_capacity_mw, installed_capacity_mw) AS available_capacity_mw,
        reasons
    FROM hourly_overlap

    UNION ALL

    SELECT
        snapshot_utc,
        asset_code,
        asset_name,
        asset_type,
        production_type,
        installed_capacity_mw,
        capacity_source,
        country,
        lon,
        lat,
        geom,
        mapping_confidence,
        country_key,
        is_mappable,
        location_tag,
        display_mode,
        area_code,
        area_display_name,
        area_type_code,
        area_map_code,
        'combined'::text AS layer,
        planned_outage_count + forced_outage_count AS active_outage_count,
        COALESCE(combined_available_capacity_mw, installed_capacity_mw) AS available_capacity_mw,
        reasons
    FROM hourly_overlap
)
SELECT
    snapshot_utc,
    asset_code,
    asset_name,
    asset_type,
    production_type,
    installed_capacity_mw,
    available_capacity_mw,
    GREATEST(installed_capacity_mw - COALESCE(available_capacity_mw, 0), 0) AS unavailable_capacity_mw,
    CASE
        WHEN installed_capacity_mw IS NULL OR installed_capacity_mw <= 0 THEN NULL
        ELSE available_capacity_mw / installed_capacity_mw
    END AS availability_ratio,
    CASE
        WHEN installed_capacity_mw IS NULL OR installed_capacity_mw <= 0 THEN 'unknown'
        WHEN available_capacity_mw IS NULL THEN 'unknown'
        WHEN available_capacity_mw <= 0 THEN 'red'
        WHEN available_capacity_mw < installed_capacity_mw - GREATEST(1.0, installed_capacity_mw * 0.01) THEN 'yellow'
        ELSE 'green'
    END AS status_color,
    layer,
    active_outage_count,
    reasons AS reason,
    capacity_source,
    country,
    lon,
    lat,
    geom,
    mapping_confidence,
    country_key,
    is_mappable,
    location_tag,
    display_mode,
    area_code,
    area_display_name,
    area_type_code,
    area_map_code
FROM layered;

CREATE OR REPLACE VIEW entsoe_availability_map.v_availability_country_unknown_agg_next_24h AS
SELECT
    v.snapshot_utc,
    v.layer,
    v.country_key,
    c.country_name,
    COUNT(DISTINCT v.asset_code) AS asset_count,
    SUM(v.installed_capacity_mw) AS installed_capacity_mw,
    SUM(v.available_capacity_mw) AS available_capacity_mw,
    SUM(v.unavailable_capacity_mw) AS unavailable_capacity_mw,
    CASE
        WHEN SUM(v.installed_capacity_mw) IS NULL OR SUM(v.installed_capacity_mw) <= 0 THEN NULL
        ELSE SUM(v.available_capacity_mw) / SUM(v.installed_capacity_mw)
    END AS availability_ratio,
    CASE
        WHEN SUM(v.installed_capacity_mw) IS NULL OR SUM(v.installed_capacity_mw) <= 0 THEN 'unknown'
        WHEN SUM(v.available_capacity_mw) <= 0 THEN 'red'
        WHEN SUM(v.available_capacity_mw) < SUM(v.installed_capacity_mw) - GREATEST(1.0, SUM(v.installed_capacity_mw) * 0.01) THEN 'yellow'
        ELSE 'green'
    END AS status_color,
    c.lon,
    c.lat,
    c.geom,
    'unknown'::text AS location_tag,
    'country_centroid_aggregate'::text AS display_mode
FROM entsoe_availability_map.v_availability_next_24h v
LEFT JOIN entsoe_availability_map.country_display_point c
    ON c.country_key = v.country_key
WHERE v.location_tag = 'unknown'
GROUP BY
    v.snapshot_utc,
    v.layer,
    v.country_key,
    c.country_name,
    c.lon,
    c.lat,
    c.geom;
