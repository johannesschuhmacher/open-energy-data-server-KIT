# SPDX-FileCopyrightText: OpenAI
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import tempfile
import unittest
import warnings
from pathlib import Path

from crawler_admin.config_service import update_gapfill_config_text
from crawler_admin.gapfill_service import build_gapfill_runtime_view
from oeds_gapfill.config import load_job_from_crawler_config


class GapfillConfigTest(unittest.TestCase):
    def test_load_job_preserves_explicit_empty_tables(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "CRAWLER_CONFIG.yml"
            config_path.write_text(
                """
default:
  database_uri: "postgresql://opendata:opendata@localhost:6432/opendata?options=--search_path="
entsoe_fms:
  schema_name: "entsoe_fms"
  gapfill:
    enable: true
    target_schema: "entsoe_fms_gapfilled"
    tables: []
""".strip()
                + "\n",
                encoding="utf-8",
            )

            job = load_job_from_crawler_config(config_path, job_name="entsoe_fms")

        self.assertEqual(job.tables, ())

    def test_load_job_accepts_lowercase_day_durations_without_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "CRAWLER_CONFIG.yml"
            config_path.write_text(
                """
default:
  database_uri: "postgresql://opendata:opendata@localhost:6432/opendata?options=--search_path="
entsoe_fms:
  schema_name: "entsoe_fms"
  gapfill:
    enable: true
    donor_search_radius: "7d"
    lookback: "7d"
""".strip()
                + "\n",
                encoding="utf-8",
            )

            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("error", FutureWarning)
                warnings.simplefilter("error", DeprecationWarning)
                job = load_job_from_crawler_config(config_path, job_name="entsoe_fms")

        self.assertEqual(job.lookback.components.days, 7)
        self.assertTrue(job.tables)
        self.assertEqual(job.tables[0].donor_search_radius.components.days, 7)
        self.assertEqual(caught, [])

    def test_load_job_applies_table_specific_methods(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "CRAWLER_CONFIG.yml"
            config_path.write_text(
                """
default:
  database_uri: "postgresql://opendata:opendata@localhost:6432/opendata?options=--search_path="
entsoe_fms:
  schema_name: "entsoe_fms"
  gapfill:
    enable: true
    method: "donor_refined"
    tables:
      - "ActualTotalLoad"
      - "EnergyPrices"
    table_methods:
      ActualTotalLoad: "linear"
      EnergyPrices: "donor_match"
""".strip()
                + "\n",
                encoding="utf-8",
            )

            job = load_job_from_crawler_config(config_path, job_name="entsoe_fms")

        methods = {table.table_name: table.method for table in job.tables}
        self.assertEqual(methods["ActualTotalLoad"], "linear")
        self.assertEqual(methods["EnergyPrices"], "donor_match")

    def test_update_gapfill_config_text_updates_script_and_tables(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            (repo_root / "CRAWLER_CONFIG.yml").write_text(
                """
default:
  schedule: "0 4 * * *"
entsoe_fms:
  enable: true
  schema_name: "entsoe_fms"
  post_run_scripts:
    - "scripts/refresh_entsoe_availability_map.py"
  gapfill:
    enable: false
    target_schema: "entsoe_fms_gapfilled"
    method: "linear"
    candidate_periods: ["24h"]
    donor_context_periods: 4
    donor_search_radius: "7d"
    refinement_periods: 1
    max_gap_periods: 12
    lookback: "7d"
    fail_on_table_error: false
    tables:
      - "ActualTotalLoad"
""".strip()
                + "\n",
                encoding="utf-8",
            )

            updated = update_gapfill_config_text(
                "entsoe_fms",
                enabled=True,
                script_enabled=True,
                selected_tables=["EnergyPrices", "PhysicalFlows"],
                table_methods={
                    "EnergyPrices": "linear",
                    "PhysicalFlows": "donor_refined",
                },
                target_schema="entsoe_fms_gapfilled",
                method="donor_refined",
                candidate_periods=["24h", "7d"],
                donor_context_periods=6,
                donor_search_radius="28d",
                refinement_periods=3,
                max_gap_periods=24,
                lookback="28d",
                fail_on_table_error=True,
                repo_root=repo_root,
            )

        self.assertIn(
            'post_run_scripts:\n    - "scripts/gapfill_timeseries.py"', updated
        )
        self.assertIn('    - "scripts/refresh_entsoe_availability_map.py"', updated)
        self.assertIn('method: "donor_refined"', updated)
        self.assertIn('      - "EnergyPrices"', updated)
        self.assertIn('      - "PhysicalFlows"', updated)
        self.assertIn("table_methods:", updated)
        self.assertIn('    "EnergyPrices": "linear"', updated)
        self.assertIn('    "PhysicalFlows": "donor_refined"', updated)

    def test_runtime_view_marks_selected_tables(self) -> None:
        view = build_gapfill_runtime_view(
            "entsoe_fms",
            {
                "schema_name": "entsoe_fms",
                "post_run_scripts": ["scripts/gapfill_timeseries.py"],
                "gapfill": {
                    "enable": True,
                    "target_schema": "entsoe_fms_gapfilled",
                    "tables": ["ActualTotalLoad", "EnergyPrices"],
                },
            },
            {
                "schema_name": "entsoe_fms",
                "post_run_scripts": [
                    "scripts/gapfill_timeseries.py",
                    "scripts/refresh_entsoe_availability_map.py",
                ],
                "gapfill": {
                    "enable": True,
                    "target_schema": "entsoe_fms_gapfilled",
                    "method": "donor_refined",
                    "candidate_periods": ["24h", "7d"],
                    "tables": ["ActualTotalLoad", "EnergyPrices"],
                    "table_methods": {
                        "ActualTotalLoad": "linear",
                        "EnergyPrices": "donor_refined",
                    },
                },
            },
        )

        self.assertTrue(view.supported)
        self.assertTrue(view.script_enabled)
        self.assertEqual(view.target_schema, "entsoe_fms_gapfilled")
        self.assertEqual(view.selected_table_count, 2)
        selected_names = {item.table_name for item in view.tables if item.selected}
        self.assertEqual(selected_names, {"ActualTotalLoad", "EnergyPrices"})
        methods = {item.table_name: item.method for item in view.tables}
        self.assertEqual(methods["ActualTotalLoad"], "linear")
        self.assertEqual(methods["EnergyPrices"], "donor_refined")


if __name__ == "__main__":
    unittest.main()
