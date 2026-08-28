import json
import unittest
from pathlib import Path


class MLReadinessAuditRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.audit = cls.root / "data" / "validation" / "audit"

    def load(self, name):
        path = self.audit / name
        self.assertTrue(path.exists(), f"Run the ML-readiness audit first: missing {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def test_coverage_and_identifier_eras(self):
        coverage = self.load("coverage_summary.json")
        self.assertEqual(coverage["dataset"]["project_month_rows"], 46568)
        self.assertEqual(coverage["dataset"]["unique_source_project_codes"], 4412)
        self.assertEqual(coverage["dataset"]["missing_project_codes"], 0)
        self.assertEqual(coverage["dataset"]["duplicate_project_month_keys"], 0)
        self.assertEqual(
            coverage["identifier_eras"]["six_digit_id_era"]["projects_present_in_every_era_month"],
            552,
        )
        self.assertEqual(
            coverage["identifier_eras"]["legacy_id_era"]["projects_present_in_every_era_month"],
            1253,
        )
        june = next(row for row in coverage["monthly"] if row["report_month"] == "2025-06")
        july = next(row for row in coverage["monthly"] if row["report_month"] == "2025-07")
        self.assertIsNone(june["project_codes_disappearing_before_next_same_era_month"])
        self.assertIsNone(july["new_project_codes_vs_previous_same_era_month"])

    def test_structural_missingness_and_event_counts(self):
        missing = self.load("field_missingness.json")
        self.assertEqual(missing["overall"]["fields"]["ministry"]["structurally_absent"], 27967)
        self.assertEqual(missing["overall"]["fields"]["start_date"]["structurally_absent"], 28758)
        self.assertEqual(missing["overall"]["fields"]["physical_progress"]["structurally_absent"], 5596)
        self.assertEqual(missing["overall"]["fields"]["project_code"]["source_missing"], 0)
        events = self.load("event_audit.json")
        self.assertEqual(events["revised_cost"]["overall"]["upward_changes"], 224)
        self.assertEqual(events["revised_cost"]["overall"]["downward_changes"], 115)
        self.assertEqual(events["revised_completion_date"]["overall"]["upward_changes"], 2737)
        self.assertEqual(events["physical_progress"]["adjacent_changes"]["reported_decreases_or_corrections"], 674)
        self.assertEqual(events["cumulative_expenditure"]["adjacent_changes"]["positive_to_zero_resets"], 20)

    def test_horizon_eligibility_and_manifest_are_read_only(self):
        horizons = self.load("horizon_eligibility.json")
        legacy = horizons["eras"]["legacy_id_era"]["horizons_months"]
        modern = horizons["eras"]["six_digit_id_era"]["horizons_months"]
        self.assertEqual(legacy["3"]["complete_project_history_observations"], 16478)
        self.assertEqual(legacy["6"]["complete_project_history_observations"], 11014)
        self.assertEqual(modern["12"]["complete_project_history_observations"], 552)
        manifest = self.load("audit_manifest.json")
        self.assertFalse(manifest["canonical_files_written"])
        self.assertFalse(manifest["identifier_crosswalk_integrated"])
        self.assertFalse(manifest["completed_projects_extracted"])
        self.assertEqual(
            manifest["source_combined_sha256"],
            "FE115E5FE71CC70552669FC4E0ACC2699B14CFE7545A319EEAEAF577E4DB95C3",
        )


if __name__ == "__main__":
    unittest.main()
