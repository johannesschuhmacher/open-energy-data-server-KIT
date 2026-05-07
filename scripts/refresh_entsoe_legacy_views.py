# SPDX-FileCopyrightText: OpenAI
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from pathlib import Path
import logging

from sqlalchemy import create_engine

from crawler.common.runtime_env import resolve_database_uri

try:
    import yaml
except ImportError:  # pragma: no cover - optional dependency in scheduler containers
    yaml = None


ROOT = Path(__file__).resolve().parents[1]
SQL_FILE = ROOT / "scripts" / "lib" / "entsoe_legacy_views.sql"
CONFIG_FILE = ROOT / "CRAWLER_CONFIG.yml"

VIEW_DEFINITIONS = {
    "query_load": '''
        CREATE OR REPLACE VIEW entsoe.query_load AS
        SELECT
            "DateTime(UTC)" AS index,
            entsoe.normalize_area_name("AreaDisplayName") AS country,
            "TotalLoad[MW]"::double precision AS actual_load
        FROM entsoe_fms."ActualTotalLoad"
        WHERE "TotalLoad[MW]" IS NOT NULL
    ''',
    "query_load_forecast": '''
        CREATE OR REPLACE VIEW entsoe.query_load_forecast AS
        SELECT
            "DateTime(UTC)" AS index,
            entsoe.normalize_area_name("AreaDisplayName") AS country,
            "TotalLoad[MW]"::double precision AS forecasted_load
        FROM entsoe_fms."DayAheadTotalLoadForecast"
        WHERE "TotalLoad[MW]" IS NOT NULL
    ''',
    "query_day_ahead_prices": '''
        CREATE OR REPLACE VIEW entsoe.query_day_ahead_prices AS
        SELECT
            "DateTime(UTC)" AS index,
            entsoe.normalize_area_name("AreaDisplayName") AS country,
            avg("Price[Currency/MWh]"::double precision) AS "0"
        FROM entsoe_fms."EnergyPrices"
        WHERE "Price[Currency/MWh]" IS NOT NULL
          AND "AreaTypeCode" = 'BZN'
          AND (trim(coalesce("Sequence", '')) = '' OR "Sequence" = '1')
        GROUP BY 1, 2
    ''',
    "query_generation_forecast": '''
        CREATE OR REPLACE VIEW entsoe.query_generation_forecast AS
        SELECT
            "DateTime(UTC)" AS index,
            entsoe.normalize_area_name("AreaDisplayName") AS country,
            ("GenerationForecast[MW]"::double precision * 10.0) AS actual_aggregated,
            "ScheduledConsumption[MW]"::double precision AS actual_consumption
        FROM entsoe_fms."DayAheadAggregatedGeneration"
        WHERE "GenerationForecast[MW]" IS NOT NULL
           OR "ScheduledConsumption[MW]" IS NOT NULL
    ''',
    "query_wind_and_solar_forecast": '''
        CREATE OR REPLACE VIEW entsoe.query_wind_and_solar_forecast AS
        SELECT
            "DateTime(UTC)" AS index,
            entsoe.normalize_area_name("AreaDisplayName") AS country,
            sum(CASE WHEN "ProductionType" = 'Solar' THEN coalesce("DayAheadGenerationForecast[MW]"::double precision, 0.0) ELSE 0.0 END) AS solar,
            sum(CASE WHEN "ProductionType" = 'Wind Onshore' THEN coalesce("DayAheadGenerationForecast[MW]"::double precision, 0.0) ELSE 0.0 END) AS wind_onshore,
            sum(CASE WHEN "ProductionType" = 'Wind Offshore' THEN coalesce("DayAheadGenerationForecast[MW]"::double precision, 0.0) ELSE 0.0 END) AS wind_offshore
        FROM entsoe_fms."GenerationForecastsForWindAndSolar"
        GROUP BY 1, 2
    ''',
    "query_generation": '''
        CREATE OR REPLACE VIEW entsoe.query_generation AS
        SELECT
            "DateTime(UTC)" AS index,
            entsoe.normalize_area_name("AreaDisplayName") AS country,
            sum(CASE WHEN "ProductionType" = 'Biomass' THEN coalesce("ActualGenerationOutput[MW]"::double precision, 0.0) ELSE 0.0 END) AS biomass,
            sum(CASE WHEN "ProductionType" = 'Fossil Hard coal' THEN coalesce("ActualGenerationOutput[MW]"::double precision, 0.0) ELSE 0.0 END) AS fossil_hard_coal,
            sum(CASE WHEN "ProductionType" = 'Geothermal' THEN coalesce("ActualGenerationOutput[MW]"::double precision, 0.0) ELSE 0.0 END) AS geothermal,
            sum(CASE WHEN "ProductionType" = 'Nuclear' THEN coalesce("ActualGenerationOutput[MW]"::double precision, 0.0) ELSE 0.0 END) AS nuclear,
            sum(CASE WHEN "ProductionType" = 'Fossil Brown coal/Lignite' THEN coalesce("ActualGenerationOutput[MW]"::double precision, 0.0) ELSE 0.0 END) AS "fossil_brown_coal/lignite",
            sum(CASE WHEN "ProductionType" = 'Fossil Coal-derived gas' THEN coalesce("ActualGenerationOutput[MW]"::double precision, 0.0) ELSE 0.0 END) AS "fossil_coal-derived_gas",
            sum(CASE WHEN "ProductionType" = 'Hydro Run-of-river and poundage' THEN coalesce("ActualGenerationOutput[MW]"::double precision, 0.0) ELSE 0.0 END) AS "hydro_run-of-river_and_poundage",
            sum(CASE WHEN "ProductionType" = 'Waste' THEN coalesce("ActualGenerationOutput[MW]"::double precision, 0.0) ELSE 0.0 END) AS waste,
            sum(CASE WHEN "ProductionType" = 'Hydro Pumped Storage' THEN coalesce("ActualGenerationOutput[MW]"::double precision, 0.0) ELSE 0.0 END) AS hydro_pumped_storage,
            sum(CASE WHEN "ProductionType" = 'Solar' THEN coalesce("ActualGenerationOutput[MW]"::double precision, 0.0) ELSE 0.0 END) AS solar,
            sum(CASE WHEN "ProductionType" = 'Wind Offshore' THEN coalesce("ActualGenerationOutput[MW]"::double precision, 0.0) ELSE 0.0 END) AS wind_offshore,
            sum(CASE WHEN "ProductionType" = 'Wind Onshore' THEN coalesce("ActualGenerationOutput[MW]"::double precision, 0.0) ELSE 0.0 END) AS wind_onshore,
            sum(CASE WHEN "ProductionType" = 'Other renewable' THEN coalesce("ActualGenerationOutput[MW]"::double precision, 0.0) ELSE 0.0 END) AS other_renewable,
            sum(CASE WHEN "ProductionType" = 'Hydro Water Reservoir' THEN coalesce("ActualGenerationOutput[MW]"::double precision, 0.0) ELSE 0.0 END) AS hydro_water_reservoir,
            sum(CASE WHEN "ProductionType" = 'Fossil Gas' THEN coalesce("ActualGenerationOutput[MW]"::double precision, 0.0) ELSE 0.0 END) AS fossil_gas
        FROM entsoe_fms."AggregatedGenerationPerType"
        GROUP BY 1, 2
    ''',
    "query_installed_generation_capacity": '''
        CREATE OR REPLACE VIEW entsoe.query_installed_generation_capacity AS
        SELECT
            make_timestamp("Year"::int, 1, 1, 0, 0, 0) AS index,
            entsoe.normalize_area_name("AreaDisplayName") AS country,
            sum(CASE WHEN "ProductionType" = 'Biomass' THEN coalesce("AggregatedInstalledCapacity[MW]"::double precision, 0.0) ELSE 0.0 END) AS biomass,
            sum(CASE WHEN "ProductionType" = 'Fossil Hard coal' THEN coalesce("AggregatedInstalledCapacity[MW]"::double precision, 0.0) ELSE 0.0 END) AS fossil_hard_coal,
            sum(CASE WHEN "ProductionType" = 'Geothermal' THEN coalesce("AggregatedInstalledCapacity[MW]"::double precision, 0.0) ELSE 0.0 END) AS geothermal,
            sum(CASE WHEN "ProductionType" = 'Nuclear' THEN coalesce("AggregatedInstalledCapacity[MW]"::double precision, 0.0) ELSE 0.0 END) AS nuclear,
            sum(CASE WHEN "ProductionType" = 'Fossil Brown coal/Lignite' THEN coalesce("AggregatedInstalledCapacity[MW]"::double precision, 0.0) ELSE 0.0 END) AS "fossil_brown_coal/lignite",
            sum(CASE WHEN "ProductionType" = 'Fossil Coal-derived gas' THEN coalesce("AggregatedInstalledCapacity[MW]"::double precision, 0.0) ELSE 0.0 END) AS "fossil_coal-derived_gas",
            sum(CASE WHEN "ProductionType" = 'Hydro Run-of-river and poundage' THEN coalesce("AggregatedInstalledCapacity[MW]"::double precision, 0.0) ELSE 0.0 END) AS "hydro_run-of-river_and_poundage",
            sum(CASE WHEN "ProductionType" = 'Waste' THEN coalesce("AggregatedInstalledCapacity[MW]"::double precision, 0.0) ELSE 0.0 END) AS waste,
            sum(CASE WHEN "ProductionType" = 'Solar' THEN coalesce("AggregatedInstalledCapacity[MW]"::double precision, 0.0) ELSE 0.0 END) AS solar,
            sum(CASE WHEN "ProductionType" = 'Wind Offshore' THEN coalesce("AggregatedInstalledCapacity[MW]"::double precision, 0.0) ELSE 0.0 END) AS wind_offshore,
            sum(CASE WHEN "ProductionType" = 'Wind Onshore' THEN coalesce("AggregatedInstalledCapacity[MW]"::double precision, 0.0) ELSE 0.0 END) AS wind_onshore,
            sum(CASE WHEN "ProductionType" = 'Other renewable' THEN coalesce("AggregatedInstalledCapacity[MW]"::double precision, 0.0) ELSE 0.0 END) AS other_renewable,
            sum(CASE WHEN "ProductionType" = 'Hydro Water Reservoir' THEN coalesce("AggregatedInstalledCapacity[MW]"::double precision, 0.0) ELSE 0.0 END) AS hydro_water_reservoir,
            sum(CASE WHEN "ProductionType" = 'Fossil Gas' THEN coalesce("AggregatedInstalledCapacity[MW]"::double precision, 0.0) ELSE 0.0 END) AS fossil_gas
        FROM entsoe_fms."InstalledGenerationCapacityAggregated"
        GROUP BY 1, 2
    ''',
    "powersystemdata": '''
        CREATE OR REPLACE VIEW entsoe.powersystemdata AS
        SELECT
            source_id,
            name,
            fuel_type AS energy_source,
            technology,
            set_type,
            entsoe.normalize_country_name(country) AS country,
            capacity,
            efficiency,
            date_in,
            date_retrofit,
            date_out,
            lat,
            lon,
            duration,
            volume_mm3,
            dam_height_m,
            storage_capacity_mwh,
            eic_code,
            project_id
        FROM entsoe_fms.powersystemdata
    ''',
}

EMPTY_VIEW_DEFINITIONS = {
    "query_load": '''
        CREATE OR REPLACE VIEW entsoe.query_load AS
        SELECT null::timestamp AS index, null::text AS country, null::double precision AS actual_load
        WHERE false
    ''',
    "query_load_forecast": '''
        CREATE OR REPLACE VIEW entsoe.query_load_forecast AS
        SELECT null::timestamp AS index, null::text AS country, null::double precision AS forecasted_load
        WHERE false
    ''',
    "query_day_ahead_prices": '''
        CREATE OR REPLACE VIEW entsoe.query_day_ahead_prices AS
        SELECT null::timestamp AS index, null::text AS country, null::double precision AS "0"
        WHERE false
    ''',
    "query_generation_forecast": '''
        CREATE OR REPLACE VIEW entsoe.query_generation_forecast AS
        SELECT null::timestamp AS index, null::text AS country, null::double precision AS actual_aggregated, null::double precision AS actual_consumption
        WHERE false
    ''',
    "query_wind_and_solar_forecast": '''
        CREATE OR REPLACE VIEW entsoe.query_wind_and_solar_forecast AS
        SELECT null::timestamp AS index, null::text AS country, null::double precision AS solar, null::double precision AS wind_onshore, null::double precision AS wind_offshore
        WHERE false
    ''',
    "query_generation": '''
        CREATE OR REPLACE VIEW entsoe.query_generation AS
        SELECT
            null::timestamp AS index,
            null::text AS country,
            null::double precision AS biomass,
            null::double precision AS fossil_hard_coal,
            null::double precision AS geothermal,
            null::double precision AS nuclear,
            null::double precision AS "fossil_brown_coal/lignite",
            null::double precision AS "fossil_coal-derived_gas",
            null::double precision AS "hydro_run-of-river_and_poundage",
            null::double precision AS waste,
            null::double precision AS hydro_pumped_storage,
            null::double precision AS solar,
            null::double precision AS wind_offshore,
            null::double precision AS wind_onshore,
            null::double precision AS other_renewable,
            null::double precision AS hydro_water_reservoir,
            null::double precision AS fossil_gas
        WHERE false
    ''',
    "query_installed_generation_capacity": '''
        CREATE OR REPLACE VIEW entsoe.query_installed_generation_capacity AS
        SELECT
            null::timestamp AS index,
            null::text AS country,
            null::double precision AS biomass,
            null::double precision AS fossil_hard_coal,
            null::double precision AS geothermal,
            null::double precision AS nuclear,
            null::double precision AS "fossil_brown_coal/lignite",
            null::double precision AS "fossil_coal-derived_gas",
            null::double precision AS "hydro_run-of-river_and_poundage",
            null::double precision AS waste,
            null::double precision AS solar,
            null::double precision AS wind_offshore,
            null::double precision AS wind_onshore,
            null::double precision AS other_renewable,
            null::double precision AS hydro_water_reservoir,
            null::double precision AS fossil_gas
        WHERE false
    ''',
    "powersystemdata": '''
        CREATE OR REPLACE VIEW entsoe.powersystemdata AS
        SELECT
            null::text AS source_id,
            null::text AS name,
            null::text AS energy_source,
            null::text AS technology,
            null::text AS set_type,
            null::text AS country,
            null::double precision AS capacity,
            null::double precision AS efficiency,
            null::date AS date_in,
            null::date AS date_retrofit,
            null::date AS date_out,
            null::double precision AS lat,
            null::double precision AS lon,
            null::double precision AS duration,
            null::double precision AS volume_mm3,
            null::double precision AS dam_height_m,
            null::double precision AS storage_capacity_mwh,
            null::text AS eic_code,
            null::text AS project_id
        WHERE false
    ''',
    "areas": '''
        CREATE OR REPLACE VIEW entsoe.areas AS
        SELECT null::text AS name, null::text AS meaning
        WHERE false
    ''',
}

AREAS_SOURCE_TABLES = (
    'ActualTotalLoad',
    'DayAheadTotalLoadForecast',
    'EnergyPrices',
    'AggregatedGenerationPerType',
    'InstalledGenerationCapacityAggregated',
)

VIEW_TABLE_REQUIREMENTS = {
    "query_load": {"ActualTotalLoad"},
    "query_load_forecast": {"DayAheadTotalLoadForecast"},
    "query_day_ahead_prices": {"EnergyPrices"},
    "query_generation_forecast": {"DayAheadAggregatedGeneration"},
    "query_wind_and_solar_forecast": {"GenerationForecastsForWindAndSolar"},
    "query_generation": {"AggregatedGenerationPerType"},
    "query_installed_generation_capacity": {"InstalledGenerationCapacityAggregated"},
    "powersystemdata": {"powersystemdata"},
}


def load_database_uri() -> str:
    default_uri = "postgresql://opendata:opendata@localhost:6432/opendata?options=--search_path="

    if yaml is not None:
        with CONFIG_FILE.open(encoding="utf-8") as handle:
            config = yaml.safe_load(handle)

        default_uri = config["default"]["database_uri"]
        crawler_uri = config.get("entsoe_fms", {}).get("database_uri", default_uri)
        return f"{resolve_database_uri(crawler_uri)}entsoe_fms"

    current_section = None
    crawler_uri = None
    parsed_default_uri = None

    for raw_line in CONFIG_FILE.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line and not raw_line.startswith(" "):
            current_section = raw_line.split(":", 1)[0].strip()
            continue

        stripped = raw_line.strip()
        if not stripped.startswith("database_uri:"):
            continue

        value = stripped.split(":", 1)[1].strip().strip('"').strip("'")
        if current_section == "default":
            parsed_default_uri = value
        elif current_section == "entsoe_fms":
            crawler_uri = value

    default_uri = parsed_default_uri or default_uri
    crawler_uri = crawler_uri or default_uri
    return f"{resolve_database_uri(crawler_uri)}entsoe_fms"


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s %(message)s",
    )

    sql = SQL_FILE.read_text(encoding="utf-8")
    engine = create_engine(load_database_uri())

    logging.info("Refreshing ENTSO-E legacy compatibility views...")
    with engine.begin() as conn:
        conn.exec_driver_sql(sql)
        existing_tables = {
            row[0]
            for row in conn.exec_driver_sql(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'entsoe_fms'
                """
            )
        }

        area_sources = [
            f'SELECT DISTINCT "AreaDisplayName" AS area_label FROM entsoe_fms."{table_name}"'
            for table_name in AREAS_SOURCE_TABLES
            if table_name in existing_tables
        ]
        if area_sources:
            conn.exec_driver_sql(
                """
                CREATE OR REPLACE VIEW entsoe.areas AS
                WITH source_areas AS (
                """
                + "\nUNION\n".join(area_sources)
                + """
                )
                SELECT
                    entsoe.normalize_area_name(area_label) AS name,
                    area_label AS meaning
                FROM source_areas
                WHERE area_label IS NOT NULL
                ORDER BY 1
                """
            )
        else:
            conn.exec_driver_sql(EMPTY_VIEW_DEFINITIONS["areas"])

        for view_name, requirements in VIEW_TABLE_REQUIREMENTS.items():
            statement = VIEW_DEFINITIONS[view_name] if requirements.issubset(existing_tables) else EMPTY_VIEW_DEFINITIONS[view_name]
            conn.exec_driver_sql(statement)

        conn.exec_driver_sql("NOTIFY pgrst, 'reload schema'")
    logging.info("ENTSO-E legacy compatibility views refreshed.")


if __name__ == "__main__":
    main()
