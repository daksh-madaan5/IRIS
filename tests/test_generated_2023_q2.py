import csv
import hashlib
import json
import unittest
from pathlib import Path


class Generated2023Q2AcceptanceTests(unittest.TestCase):
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
            "2023_04": (1605, 114, 218, 72),
            "2023_05": (1681, 106, 218, 72),
            "2023_06": (1643, 107, 217, 81),
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
            "2023_04": ("1605", "114-115", "N04000079"),
            "2023_05": ("1681", "106-107", "N04000079"),
            "2023_06": ("1643", "107-108", "N04000078"),
        }
        for token, (last_serial, boundary_pages, boundary_code) in cases.items():
            rows = self._rows(token)
            self.assertEqual(rows[0]["project_code"], "020100044")
            self.assertEqual(rows[-1]["project_code"], "N30000004")
            self.assertEqual(rows[-1]["source_serial_number"], last_serial)
            self.assertGreaterEqual(sum("-" in row["source_pages"] for row in rows), 2)
            boundary = next(row for row in rows if row["project_code"] == boundary_code)
            self.assertEqual(boundary["source_pages"], boundary_pages)

        june = self._rows("2023_06")
        empty_state_1 = next(row for row in june if row["project_code"] == "N42000009")
        self.assertEqual(empty_state_1["agency"], "CPWD")
        self.assertEqual(empty_state_1["state"], "")

        empty_state_2 = next(row for row in june if row["project_code"] == "N28000148")
        self.assertEqual(empty_state_2["agency"], "PATNA METRO")
        self.assertEqual(empty_state_2["state"], "")

        raw_path = self.root / "data" / "extracted" / "2023-04" / "raw_table6_rows.jsonl"
        raw_rows = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines()]
        first_project = next(row for row in raw_rows if row["cells"][0] == "1")
        self.assertEqual(first_project["cells"][6], "83/87")

    def test_combined_and_new_transitions(self):
        summary = json.loads(
            (self.root / "data" / "validation" / "longitudinal_summary_2023_04_2026_07.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(summary["rows"], 60287)
        self.assertEqual(summary["unique_projects"], 4649)
        self.assertEqual(summary["duplicate_project_month_keys"], 0)
        self.assertNotIn("2023-12", summary["report_months"])
        transitions = {
            f"{item['earlier_month']}->{item['later_month']}": item
            for item in summary["adjacent_month_transitions"]
        }
        expected = {
            "2023-04->2023-05": (1594, 11, 87, 172),
            "2023-05->2023-06": (1626, 55, 17, 41),
            "2023-06->2023-07": (1634, 9, 12, 37),
        }
        for key, (both, earlier_only, later_only, warnings) in expected.items():
            transition = transitions[key]
            self.assertEqual(
                (transition["projects_in_both"], transition["earlier_only"], transition["later_only"]),
                (both, earlier_only, later_only),
            )
            self.assertEqual(transition["longitudinal_warning_counts"]["total"], warnings)

        combined = self.root / "data" / "processed" / "projects_monthly.csv"
        self.assertEqual(
            hashlib.sha256(combined.read_bytes()).hexdigest().upper(),
            "2301524D9A7AF597672716FB6D483FBBCCCBCAA9B9A57E0A154AC7E42F4878FA",
        )


if __name__ == "__main__":
    unittest.main()
