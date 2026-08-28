import json
import csv
import unittest
from pathlib import Path


class GeneratedQualityRegressionTests(unittest.TestCase):
    def test_expected_monthly_counts_and_nonproject_removal(self):
        root = Path(__file__).resolve().parents[1]
        expected = {
            "2026_04": {"clean_rows": 1981, "pages": [55, 162], "table_pages": 108},
            "2026_05": {"clean_rows": 1987, "pages": [54, 162], "table_pages": 109},
            "2026_06": {"clean_rows": 1847, "pages": [59, 159], "table_pages": 101},
            "2026_07": {"clean_rows": 1775, "pages": [55, 152], "table_pages": 98},
        }
        for token, values in expected.items():
            path = root / "data" / "validation" / f"manifest_{token}.json"
            self.assertTrue(path.exists(), f"Run extraction first: missing {path}")
            manifest = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["clean_rows"], values["clean_rows"])
            self.assertEqual([manifest["table6_start_page"], manifest["table6_end_page"]], values["pages"])
            self.assertEqual(len(manifest["pages_processed"]), values["table_pages"])
            self.assertEqual(manifest["missing_project_codes"], 0)
            self.assertEqual(manifest["duplicate_project_codes"], 0)
            self.assertEqual(manifest["rejected_rows"], 1 if token in {"2026_04", "2026_05"} else 0)
            self.assertEqual(manifest["serial_gaps"], [])
            self.assertEqual(manifest["serial_duplicates"], [])
            self.assertEqual(manifest["removed_nonproject_rows"]["total"], 31)
            self.assertGreater(manifest["removed_nonproject_rows"]["ministry_heading"], 0)
            self.assertGreater(manifest["removed_nonproject_rows"]["sector_heading"], 0)

    def test_cross_field_warning_counts_are_stable(self):
        root = Path(__file__).resolve().parents[1]
        expected = {
            "2026_04": {
                "ZERO_EXPENDITURE_POSITIVE_PROGRESS": 247,
                "EXPENDITURE_WITH_ZERO_PROGRESS": 41,
                "FULL_PROGRESS_STILL_ONGOING": 97,
                "PHYSICAL_PROGRESS_ABOVE_100": 0,
                "NEGATIVE_EXPENDITURE": 0,
                "EXTREME_EXPENDITURE_COST_MISMATCH": 1,
                "REVISED_COST_BELOW_ORIGINAL": 335,
                "COMPLETION_DATE_BEFORE_START_DATE": 1,
                "PROGRESS_REPORTED_BEFORE_START": 1,
            },
            "2026_05": {
                "ZERO_EXPENDITURE_POSITIVE_PROGRESS": 250,
                "EXPENDITURE_WITH_ZERO_PROGRESS": 55,
                "FULL_PROGRESS_STILL_ONGOING": 106,
                "PHYSICAL_PROGRESS_ABOVE_100": 0,
                "NEGATIVE_EXPENDITURE": 0,
                "EXTREME_EXPENDITURE_COST_MISMATCH": 4,
                "REVISED_COST_BELOW_ORIGINAL": 340,
                "COMPLETION_DATE_BEFORE_START_DATE": 1,
                "PROGRESS_REPORTED_BEFORE_START": 0,
            },
            "2026_06": {
                "ZERO_EXPENDITURE_POSITIVE_PROGRESS": 226,
                "EXPENDITURE_WITH_ZERO_PROGRESS": 57,
                "FULL_PROGRESS_STILL_ONGOING": 70,
                "PHYSICAL_PROGRESS_ABOVE_100": 0,
                "NEGATIVE_EXPENDITURE": 0,
                "EXTREME_EXPENDITURE_COST_MISMATCH": 4,
                "REVISED_COST_BELOW_ORIGINAL": 316,
                "COMPLETION_DATE_BEFORE_START_DATE": 2,
                "PROGRESS_REPORTED_BEFORE_START": 0,
            },
            "2026_07": {
                "ZERO_EXPENDITURE_POSITIVE_PROGRESS": 113,
                "EXPENDITURE_WITH_ZERO_PROGRESS": 59,
                "FULL_PROGRESS_STILL_ONGOING": 61,
                "PHYSICAL_PROGRESS_ABOVE_100": 0,
                "NEGATIVE_EXPENDITURE": 0,
                "EXTREME_EXPENDITURE_COST_MISMATCH": 2,
                "REVISED_COST_BELOW_ORIGINAL": 316,
                "COMPLETION_DATE_BEFORE_START_DATE": 3,
                "PROGRESS_REPORTED_BEFORE_START": 0,
            },
        }
        for token, counts in expected.items():
            manifest = json.loads((root / "data" / "validation" / f"manifest_{token}.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["warnings_by_rule"], counts)

    def test_combined_project_month_key_is_unique(self):
        root = Path(__file__).resolve().parents[1]
        path = root / "data" / "validation" / "combined_summary.json"
        self.assertTrue(path.exists(), f"Run extraction first: missing {path}")
        summary = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(summary["rows"], 46568)
        self.assertEqual(summary["unique_projects"], 4412)
        self.assertEqual(
            summary["report_months"],
            [
                "2024-01",
                "2024-02",
                "2024-03",
                "2024-06",
                "2024-07",
                "2024-08",
                "2024-09",
                "2024-10",
                "2024-11",
                "2024-12",
                *[f"2025-{month:02d}" for month in range(1, 13)],
                *[f"2026-{month:02d}" for month in range(1, 8)],
            ],
        )
        self.assertEqual(summary["projects_with_at_least_3_observations"], 4220)
        self.assertEqual(summary["projects_with_at_least_6_observations"], 3796)
        self.assertEqual(summary["projects_with_at_least_10_observations"], 2385)
        self.assertEqual(summary["projects_with_at_least_12_observations"], 2186)
        self.assertEqual(summary["projects_with_at_least_16_observations"], 1253)
        self.assertEqual(summary["projects_with_at_least_18_observations"], 0)
        self.assertEqual(summary["projects_with_at_least_19_observations"], 0)
        self.assertEqual(summary["projects_present_in_all_months"], 0)
        self.assertEqual(summary["duplicate_project_month_keys"], 0)
        self.assertEqual(summary["duplicate_project_month_rows"], 0)

    def test_april_may_identifier_population_and_boundaries(self):
        root = Path(__file__).resolve().parents[1]
        expected = {
            "2026_04": ("55", "1981"),
            "2026_05": ("54", "1987"),
        }
        for token, (first_page, last_serial) in expected.items():
            path = root / "data" / "cleaned" / f"projects_{token}.csv"
            with path.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows[0]["project_code"], "612786")
            self.assertEqual(rows[0]["legacy_ocms_code"], "N04000106")
            self.assertEqual(rows[0]["source_page"], first_page)
            self.assertEqual(rows[-1]["project_code"], "613787")
            self.assertEqual(rows[-1]["pmgid"], "6135")
            self.assertEqual(rows[-1]["source_serial_number"], last_serial)

    def test_known_zero_expenditure_positive_progress_records_are_flagged(self):
        root = Path(__file__).resolve().parents[1]
        expected = {
            "2026_06": {"618364", "618365", "618366", "618413"},
            "2026_07": {"618364", "618365", "618366"},
        }
        for token, codes in expected.items():
            warning_path = root / "data" / "validation" / f"warnings_{token}.csv"
            with warning_path.open(encoding="utf-8-sig", newline="") as stream:
                flagged = {
                    row["project_code"]
                    for row in csv.DictReader(stream)
                    if row["rule"] == "ZERO_EXPENDITURE_POSITIVE_PROGRESS"
                }
            self.assertTrue(codes <= flagged)

    def test_qc_metrics_are_separate_from_clean_dataset(self):
        root = Path(__file__).resolve().parents[1]
        clean_path = root / "data" / "cleaned" / "projects_2026_06.csv"
        qc_path = root / "data" / "validation" / "qc_metrics_2026_06.csv"
        with clean_path.open(encoding="utf-8-sig", newline="") as stream:
            clean_fields = next(csv.reader(stream))
        with qc_path.open(encoding="utf-8-sig", newline="") as stream:
            qc_fields = next(csv.reader(stream))
        self.assertNotIn("financial_progress", clean_fields)
        self.assertNotIn("physical_financial_gap", clean_fields)
        self.assertIn("financial_progress", qc_fields)
        self.assertIn("physical_financial_gap", qc_fields)


if __name__ == "__main__":
    unittest.main()
