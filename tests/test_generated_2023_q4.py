import csv
import hashlib
import json
import unittest
from pathlib import Path


class Generated2023Q4AcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]

    def _rows(self, token):
        path = self.root / "data" / "cleaned" / f"projects_{token}.csv"
        with path.open(encoding="utf-8-sig", newline="") as stream:
            return list(csv.DictReader(stream))

    def _manifest(self, token):
        return json.loads(
            (self.root / "data" / "validation" / f"manifest_{token}.json").read_text(encoding="utf-8")
        )

    def test_monthly_structure_and_parse_acceptance(self):
        cases = {
            "2023_10": (1788, 92, 215, 107),
            "2023_11": (1831, 417, 541, 3),
        }
        for token, (count, first_page, last_page, agency_headings) in cases.items():
            with self.subTest(token=token):
                rows = self._rows(token)
                manifest = self._manifest(token)
                self.assertEqual(len(rows), count)
                self.assertEqual(len({row["project_code"] for row in rows}), count)
                self.assertTrue(all(row["project_code"] for row in rows))
                self.assertTrue(all(not row["physical_progress"] for row in rows))
                self.assertTrue(all(not row["physical_progress_raw"] for row in rows))
                self.assertEqual(manifest["layout_versions"], ["legacy-detail-ongoing-nine-column-milestones-v1"])
                self.assertEqual((manifest["table6_start_page"], manifest["table6_end_page"]), (first_page, last_page))
                self.assertEqual(manifest["serial_gaps"], [])
                self.assertEqual(manifest["serial_duplicates"], [])
                self.assertEqual(manifest["missing_project_codes"], 0)
                self.assertEqual(manifest["duplicate_project_codes"], 0)
                self.assertEqual(manifest["rejected_rows"], 1)
                self.assertEqual(manifest["removed_nonproject_rows"]["agency_heading"], agency_headings)
                for field in ("original_cost", "revised_cost", "cumulative_expenditure"):
                    self.assertEqual(manifest["numeric_parse"][field]["success_rate"], 1.0)
                self.assertEqual(manifest["date_parse"]["success_rate"], 1.0)

    def test_source_boundaries_and_raw_milestones(self):
        oct_rows = self._rows("2023_10")
        nov_rows = self._rows("2023_11")
        self.assertEqual(oct_rows[0]["project_code"], "020100044")
        self.assertEqual(oct_rows[0]["state"], "TAMIL NADU")
        self.assertEqual(oct_rows[-1]["project_code"], "N30000004")
        self.assertEqual(oct_rows[-1]["state"], "UTTARAKHAND")
        self.assertEqual(oct_rows[-1]["source_pages"], "214-215")
        self.assertEqual(nov_rows[-1]["source_serial_number"], "1831")
        self.assertEqual(nov_rows[-1]["state"], "UTTARAKHAND")
        self.assertGreaterEqual(sum("-" in row["source_pages"] for row in oct_rows), 2)
        self.assertGreaterEqual(sum("-" in row["source_pages"] for row in nov_rows), 2)

        raw_path = self.root / "data" / "extracted" / "2023-10" / "raw_table6_rows.jsonl"
        raw_rows = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines()]
        first_project = next(row for row in raw_rows if row["cells"][0] == "1")
        self.assertEqual(first_project["cells"][6], "85/87")

    def test_combined_gap_and_longitudinal_acceptance(self):
        summary = json.loads(
            (self.root / "data" / "validation" / "longitudinal_summary_2023_10_2026_07.json").read_text(encoding="utf-8")
        )
        self.assertEqual(summary["rows"], 50187)
        self.assertEqual(summary["unique_projects"], 4472)
        self.assertEqual(summary["duplicate_project_month_keys"], 0)
        self.assertNotIn("2023-12", summary["report_months"])
        transitions = {
            f"{item['earlier_month']}->{item['later_month']}": item
            for item in summary["adjacent_month_transitions"]
        }
        self.assertNotIn("2023-11->2024-01", transitions)
        oct_nov = transitions["2023-10->2023-11"]
        self.assertEqual((oct_nov["projects_in_both"], oct_nov["earlier_only"], oct_nov["later_only"]), (1773, 15, 58))
        self.assertEqual(oct_nov["longitudinal_warning_counts"]["total"], 47)

        combined = self.root / "data" / "processed" / "projects_monthly.csv"
        digest = hashlib.sha256(combined.read_bytes()).hexdigest().upper()
        self.assertEqual(digest, "A0704D145006CB153FB8D5E07F3AF970103A833214BDC753B09655295428206B")


if __name__ == "__main__":
    unittest.main()
