import csv
import json
import unittest
from collections import Counter
from pathlib import Path


class Generated2024Q2AcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]

    def _manifest(self, token):
        return json.loads(
            (self.root / "data" / "validation" / f"manifest_{token}.json").read_text(encoding="utf-8")
        )

    def _rows(self, path):
        with path.open(encoding="utf-8-sig", newline="") as stream:
            return list(csv.DictReader(stream))

    def test_april_may_are_uncoded_and_excluded_from_canonical_cleaned(self):
        for token, expected_rows, last_serial in (("2024_04", 1838, 1838), ("2024_05", 1812, 1817)):
            canonical = self.root / "data" / "cleaned" / f"projects_{token}.csv"
            uncoded = self.root / "data" / "cleaned_uncoded" / f"projects_{token}.csv"
            self.assertFalse(canonical.exists())
            self.assertTrue(uncoded.exists())
            rows = self._rows(uncoded)
            self.assertEqual(len(rows), expected_rows)
            self.assertTrue(all(not row["project_code"] for row in rows))
            self.assertTrue(all(not row["agency"] for row in rows))
            self.assertTrue(all(not row["ministry"] for row in rows))
            self.assertTrue(all(not row["start_date"] for row in rows))
            self.assertTrue(all(not row["physical_progress"] for row in rows))
            self.assertEqual(int(rows[-1]["source_serial_number"]), last_serial)
            manifest = self._manifest(token)
            self.assertFalse(manifest["canonical_integration_eligible"])
            self.assertEqual(manifest["layout_versions"], ["legacy-annexure-xviii-six-column-v1"])
            self.assertEqual(manifest["missing_project_codes"], expected_rows)
            self.assertEqual(manifest["structurally_missing_project_codes"], expected_rows)

    def test_april_and_may_boundaries_and_may_source_defects(self):
        april = self._rows(self.root / "data" / "cleaned_uncoded" / "projects_2024_04.csv")
        may = self._rows(self.root / "data" / "cleaned_uncoded" / "projects_2024_05.csv")
        self.assertEqual((april[0]["source_serial_number"], april[0]["source_page"]), ("1", "462"))
        self.assertEqual((april[-1]["source_serial_number"], april[-1]["source_page"]), ("1838", "571"))
        self.assertEqual((may[0]["source_serial_number"], may[0]["source_page"]), ("1", "462"))
        self.assertEqual((may[-1]["source_serial_number"], may[-1]["source_page"]), ("1817", "570"))
        may_serials = {int(row["source_serial_number"]) for row in may}
        self.assertEqual(
            [serial for serial in range(1, 1818) if serial not in may_serials],
            [175, 919, 920, 1353, 1785],
        )
        rejected = self._rows(self.root / "data" / "validation" / "rejected_2024_05.csv")
        self.assertEqual(
            Counter(row["reason"] for row in rejected),
            Counter(
                {
                    "unclassified_non_project_row": 26,
                    "empty_table_row": 2,
                    "source_omitted_serial_project_row": 2,
                    "multiple_source_projects_merged_in_one_detected_row": 1,
                    "serial_project_cell_bleed": 1,
                }
            ),
        )

    def test_june_is_coded_complete_and_integrated(self):
        rows = self._rows(self.root / "data" / "cleaned" / "projects_2024_06.csv")
        self.assertEqual(len(rows), 1810)
        self.assertEqual([int(row["source_serial_number"]) for row in rows], list(range(1, 1811)))
        self.assertEqual(len({row["project_code"] for row in rows}), 1810)
        self.assertTrue(all(row["project_code"] for row in rows))
        self.assertEqual(
            (rows[0]["project_code"], rows[0]["source_page"]),
            ("N04000073", "35"),
        )
        self.assertEqual(
            (rows[-1]["project_code"], rows[-1]["source_page"]),
            ("N30000049", "304"),
        )
        by_serial = {int(row["source_serial_number"]): row for row in rows}
        self.assertEqual(by_serial[66]["project_code"], "N24002124")
        self.assertEqual(by_serial[67]["project_code"], "N24002125")
        self.assertEqual(by_serial[68]["project_code"], "N24002126")
        self.assertEqual(by_serial[71]["project_code"], "N24002141")
        self.assertEqual(by_serial[72]["project_code"], "N24002142")
        manifest = self._manifest("2024_06")
        self.assertTrue(manifest["canonical_integration_eligible"])
        self.assertEqual(manifest["layout_versions"], ["legacy-all-ongoing-nine-column-v1"])
        self.assertEqual(manifest["serial_gaps"], [])
        self.assertEqual(manifest["missing_project_codes"], 0)
        self.assertEqual(manifest["duplicate_project_codes"], 0)

    def test_combined_includes_june_and_excludes_uncoded_months(self):
        summary = json.loads(
            (self.root / "data" / "validation" / "combined_summary.json").read_text(encoding="utf-8")
        )
        self.assertEqual(summary["report_months"][0], "2023-01")
        self.assertNotIn("2023-12", summary["report_months"])
        self.assertIn("2024-06", summary["report_months"])
        self.assertNotIn("2024-04", summary["report_months"])
        self.assertNotIn("2024-05", summary["report_months"])
        self.assertEqual(summary["rows_by_month"]["2024-06"], 1810)
        self.assertEqual(summary["duplicate_project_month_keys"], 0)


if __name__ == "__main__":
    unittest.main()
