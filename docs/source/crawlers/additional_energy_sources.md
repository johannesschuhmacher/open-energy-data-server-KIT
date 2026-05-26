# Additional Energy Source Crawlers

This page summarizes the access model for the additional energy-sector sources
that have scheduler-compatible crawler modules in `crawler/`. All entries are
disabled by default in `CRAWLER_CONFIG.yml`; enable them only after reviewing
the upstream terms and configuring the required credentials.

| Source | Crawler | Group | Access required | Test status |
|---|---|---|---|---|
| [regelleistung.net Datacenter](https://www.regelleistung.net/en-us/Data/Where-can-I-find-what-data) | `regelleistung` | 1: public/free/no account | Public tender file API for data-center downloads | Test import completed |
| [Trading Hub Europe XML interface](https://www.tradinghub.eu/Portals/0/DLC%20Datenformate/2024/240101_THE_XML_Interface_V1.1_en.pdf?ver=B38fHTVUA-mqEK7BVy-dWA%3D%3D) | `tradinghub` | 1: public/free/no account | Public XML interface; User-Agent required | Test import completed |
| [OpenStreetMap / Overpass](https://operations.osmfoundation.org/policies/api/) | `osm_power` | 1: public/free/no account | Public read access; heavy use should move to extracts or a dedicated Overpass instance | Small-bbox test import completed |
| [DWD Climate Data Center](https://www.dwd.de/EN/ourservices/cdc/cdc_ueberblick-klimadaten_en.html) | `dwd_cdc` | 1: public/free/no account | Public DWD Open Data HTTP download | Test import completed |
| [Open-Meteo DWD API](https://open-meteo.com/en/docs/dwd-api) | `open_meteo` | 1: public/free/no account | No key for non-commercial fair use; API key required for commercial plans | Test import completed |
| [Netztransparenz WebAPI](https://www.netztransparenz.de/xspproxy/api/staticfiles/ntp-relaunch/dokumente/web-api/dokumentation-webserviceapi-netztransparenz_v1.21.pdf) | `netztransparenz` | 2: public/free/account | OAuth2 client credentials | Test import completed; the documented `Trafficlight` endpoint returned 404 and is not part of the default run |
| [GIE AGSI/ALSI](https://www.gie.eu/transparency-platform/GIE_API_documentation_v007.pdf) | `gie_agsi_alsi` | 2: public/free/account | Free GIE API account and `x-key` API key | Test import completed |
| [Copernicus Climate Data Store](https://cds.climate.copernicus.eu/en/how-to-api) | `copernicus_cds` | 2: public/free/account | CDS account, Personal Access Token, `cdsapi`, and accepted dataset terms | Small ERA5 test download completed |
| [U.S. EIA Open Data API](https://www.eia.gov/opendata/documentation.php) | `eia` | 2: public/free/account | Free EIA API key; `DEMO_KEY` is only for limited tests | Test import completed |
| [PRISMA Capacity Platform API](https://help.prisma-capacity.eu/solutions/shipper-hub-prisma-api-business-information) | `prisma_capacity` | 3: paid/subscription | PRISMA API package subscription and test/production credentials | Prepared only; not tested against a paid API package |

## Operational Notes

- Credential-gated crawlers create their tables and write an `access_status`
  row even when credentials are missing. This lets Grafana show what is still
  needed without failing the scheduler.
- Public crawlers use a descriptive User-Agent and conservative defaults.
  Increase bounding boxes, date windows, or file counts only after checking the
  upstream usage policy.
- Generic API importers (`prisma_capacity`, `copernicus_cds`, `eia`) are
  intentionally configurable because the concrete dataset or package depends on
  the operator account and intended use.
