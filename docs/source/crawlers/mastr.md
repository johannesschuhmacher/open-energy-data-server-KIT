# `mastr`

## Purpose

`crawler.mastr` imports the German Marktstammdatenregister full export into the
`mastr` schema.

This crawler is intended for:

- asset and registration reference data
- operator and unit master data
- enrichment of operational time-series datasets with plant metadata

Unlike the time-series focused crawlers, `mastr` mainly provides slowly
changing reference tables.

## Source system and authentication

- Source system: Marktstammdatenregister full export
- Upstream landing page: `https://www.marktstammdatenregister.de/MaStR/Datendownload`
- Export base URL: `https://download.marktstammdatenregister.de/Gesamtdatenexport`
- Authentication: none
- License declared in the crawler metadata: `DL-DE/BY-2-0`

## How to run it manually

From the repository root:

```shell
python -m crawler.mastr
```

The first run can be expensive because the crawler downloads the current full
export ZIP and rewrites large tables when the XML structure changes.

## Scheduler configuration

The crawler is configured under the `mastr` key in `CRAWLER_CONFIG.yml`.

Important options:

- `enable`
- `schema_name`
- `database_uri`
- `base_download_url`

Current default entry:

```yaml
mastr:
  enable: false
  schema_name: "mastr"
  base_download_url: "https://download.marktstammdatenregister.de/Gesamtdatenexport"
```

## Output schema and tables

The crawler writes to schema `mastr`.

It creates one table per XML file contained in the MaStR full export archive.
The exact set of tables therefore follows the upstream export structure and may
change over time.

Operationally important characteristics:

- primary keys are inferred from known MaStR identifier fields
- tables are replaced when new columns appear in the upstream export
- this schema is best treated as reference data, not as a narrow fact table

## Downstream dependencies

There is currently no provisioned MaStR dashboard in the repository.

The schema is most useful as an enrichment layer for:

- generation and outage data
- asset lookups by unit or registry identifier
- geospatial and inventory-style analyses

## Operational notes

- The crawler scrapes the MaStR download page to discover the current export
  ZIP URL before downloading the archive.
- A full import can create many tables and consume significant memory and disk.
- Because upstream XML structure can change, this crawler is more sensitive to
  schema drift than the simpler CSV-based crawlers.
