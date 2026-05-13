# Crawler Development

New crawlers live in the `crawler/` package and are scheduled through
`CRAWLER_CONFIG.yml`.

## Minimum structure

Each crawler should:

1. inherit from `BaseCrawler`
2. accept the scheduler-provided config in `__init__`
3. implement `run(self)`
4. optionally expose a `main(...)` helper for manual execution

Minimal example:

```python
from crawler_core.base import BaseCrawler


class ExampleCrawler(BaseCrawler):
    def __init__(self, schema_name: str, config: dict):
        super().__init__(schema_name, config)

    def run(self):
        self.logger.info("Starting crawler")
        # crawler logic here
        self.logger.info("Finished crawler")
```

## Manual execution

For local testing, run crawlers from the repository root:

```shell
python -m crawler.example_crawler
```

The scheduler itself can be started with:

```shell
python crawler_scheduler.py
```

## Logging and metadata

- Use `self.logger` for operational logs.
- Use `self.set_metadata(...)` when the crawler writes a dataset that should be
  described in `public.metadata`.
- Use critical logging only for failures that should trigger operator attention.
- Prefer shared helpers from `crawler_core` for new reusable runtime code
  instead of adding more cross-imports directly under `crawler/` or `scripts/`.

## Database and schema design

- Keep raw source data in source-specific schemas such as `entsoe_fms`,
  `weather`, or `energy_forecast`.
- Add derived views or post-run scripts when dashboards need cleaned or
  aggregated tables.
- If fresh installs need helper functions or base objects, add them to
  `docker/initdb/10-init.sql`.

## Documentation expectation

Every crawler that is intended for regular use should get its own page in
`docs/source/crawlers/` with the following structure:

1. Purpose
2. Source system and authentication
3. How to run it manually
4. Scheduler configuration
5. Output schema and tables
6. Downstream dependencies
7. Operational notes
