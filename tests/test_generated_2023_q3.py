import csv
import hashlib
import json
import unittest
from pathlib import Path


class Generated2023Q3AcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]

    def _rows(self, token):
        with (self.root / "data" / "cleaned" / f"projects_{token}.csv").open(
            encoding="utf-8-sig", newline=""
        ) as stream:
            return list(csv.DictReader(stream))

    def _manifest(self, token):
        return json.loads(
            (self.root / "data" / "validation" / f"manifest_{token}.json").read_text(encoding="utf-8")
        )

    def test_monthly_structure_and_parse_acceptance(self):
        cases = {
            "2023_07": (1646, 108, 218, 84),
            "2023_08": (1762, 118, 237, 81),
            "2023_09": (1763, 89, 207, 74),
        }
        for token, (count, first_page, last_page, warnings) in cases.items():
            with self.subTest(token=token):
                rows = self._rows(token)
                manifest = self._manifest(token)
                self.assertEqual(len(rows), count)
                self.assertEqual(len({row["project_code"] for row in rows}), count)
                self.assertTrue(all(row["project_code"] for row in rows))
                self.assertTrue(all(not row["physical_progress"] for row in rows))
                self.assertEqual(manifest["layout_versions"], ["legacy-detail-ongoing-nine-column-milestones-v1"])
                self.assertEqual((manifest["table6_start_page"], manifest["table6_end_page"]), (first_page, last_page))
                self.assertEqual(manifest["serial_gaps"], [])
                self.assertEqual(manifest["serial_duplicates"], [])
                self.assertEqual(manifest["missing_project_codes"], 0)
                self.assertEqual(manifest["duplicate_project_codes"], 0)
                self.assertEqual(manifest["rejected_rows"], 1)
                self.assertEqual(manifest["warning_count"], warnings)
                self.assertEqual(manifest["date_parse"]["success_rate"], 1.0)
                for field in ("original_cost", "revised_cost", "cumulative_expenditure"):
                    self.assertEqual(manifest["numeric_parse"][field]["success_rate"], 1.0)

    def test_source_boundaries_missing_state_and_raw_milestones(self):
        cases = {
            "2023_07": ("1646", "108-109", "N04000078"),
            "2023_08": ("1762", "118-119", "N04000079"),
            "2023_09": ("1763", "89-90", "N04000077"),
        }
        for token, (last_serial, boundary_pages, boundary_code) in cases.items():
            rows = self._rows(token)
            self.assertEqual(rows[0]["project_code"], "020100044")
            self.assertEqual(rows[-1]["project_code"], "N30000004")
            self.assertEqual(rows[-1]["source_serial_number"], last_serial)
            self.assertGreaterEqual(sum("-" in row["source_pages"] for row in rows), 2)
            boundary = next(row for row in rows if row["project_code"] == boundary_code)
            self.assertEqual(boundary["source_pages"], boundary_pages)

        july = self._rows("2023_07")
        leh = next(row for row in july if row["project_code"] == "N04000078")
        self.assertEqual(leh["original_completion_date_raw"], "9/2021")
        source_missing = next(row for row in july if row["project_code"] == "N28000147")
        self.assertEqual(source_missing["agency"], "CPWD FOR")
        self.assertEqual(source_missing["state"], "")

        raw_path = self.root / "data" / "extracted" / "2023-07" / "raw_table6_rows.jsonl"
        raw_rows = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines()]
        first_project = next(row for row in raw_rows if row["cells"][0] == "1")
        self.assertEqual(first_project["cells"][6], "83/87")

    def test_combined_and_new_transitions(self):
        summary = json.loads(
            (self.root / "data" / "validation" / "longitudinal_summary_2023_07_2026_07.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(summary["rows"], 55358)
        self.assertEqual(summary["unique_projects"], 4574)
        self.assertEqual(summary["duplicate_project_month_keys"], 0)
        self.assertNotIn("2023-12", summary["report_months"])
        transitions = {
            f"{item['earlier_month']}->{item['later_month']}": item
            for item in summary["adjacent_month_transitions"]
        }
        expected = {
            "2023-07->2023-08": (1630, 16, 132, 19),
            "2023-08->2023-09": (1708, 54, 55, 32),
            "2023-09->2023-10": (1728, 35, 60, 36),
        }
        for key, (both, earlier_only, later_only, warnings) in expected.items():
            transition = transitions[key]
            self.assertEqual(
                (transition["projects_in_both"], transition["earlier_only"], transition["later_only"]),
                (both, earlier_only, later_only),
            )
            self.assertEqual(transition["longitudinal_warning_counts"]["total"], warnings)
        self.assertNotIn("2023-11->2024-01", transitions)

        combined = self.root / "data" / "processed" / "projects_monthly.csv"
        self.assertEqual(
            hashlib.sha256(combined.read_bytes()).hexdigest().upper(),
            "9733A05BE6DC63340E713128F7BE3EE1FF77B3F2661287DBAF0580A715F9AD67",
        )


if __name__ == "__main__":
    unittest.main()
