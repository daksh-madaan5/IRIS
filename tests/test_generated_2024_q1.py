import csv
import json
import unittest
from pathlib import Path


class Generated2024Q1AcceptanceTests(unittest.TestCase):
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

    def test_jan_feb_mar_2024_are_coded_and_valid(self):
        cases = (
            ("2024_01", 1821, 1821),
            ("2024_02", 1902, 1902),
            ("2024_03", 1873, 1873),
        )
        for token, expected_rows, last_serial in cases:
            with self.subTest(token=token):
                csv_path = self.root / "data" / "cleaned" / f"projects_{token}.csv"
                self.assertTrue(csv_path.exists(), f"Missing {csv_path}")
                rows = self._rows(csv_path)
                self.assertEqual(len(rows), expected_rows)
                self.assertTrue(all(bool(row["project_code"]) for row in rows))
                self.assertTrue(all(bool(row["project_name"]) for row in rows))
                self.assertTrue(all(bool(row["agency"]) for row in rows))
                self.assertTrue(all(bool(row["sector"]) for row in rows))
                # Structural absence
                self.assertTrue(all(not row["ministry"] for row in rows))
                self.assertTrue(all(not row["start_date"] for row in rows))
                self.assertTrue(all(not row["physical_progress"] for row in rows))
                self.assertEqual(int(rows[0]["source_serial_number"]), 1)
                self.assertEqual(int(rows[-1]["source_serial_number"]), last_serial)

                manifest = self._manifest(token)
                self.assertTrue(manifest["canonical_integration_eligible"])
                self.assertEqual(manifest["layout_versions"], ["legacy-detail-ongoing-nine-column-milestones-v1"])
                self.assertEqual(manifest["clean_rows"], expected_rows)
                self.assertEqual(manifest["missing_project_codes"], 0)
                self.assertEqual(manifest["duplicate_project_codes"], 0)
                self.assertEqual(manifest["serial_gaps"], [])
                self.assertEqual(manifest["serial_duplicates"], [])

    def test_pairwise_coded_overlap(self):
        jan_rows = self._rows(self.root / "data" / "cleaned" / "projects_2024_01.csv")
        feb_rows = self._rows(self.root / "data" / "cleaned" / "projects_2024_02.csv")
        mar_rows = self._rows(self.root / "data" / "cleaned" / "projects_2024_03.csv")
        jun_rows = self._rows(self.root / "data" / "cleaned" / "projects_2024_06.csv")

        jan_codes = {r["project_code"] for r in jan_rows}
        feb_codes = {r["project_code"] for r in feb_rows}
        mar_codes = {r["project_code"] for r in mar_rows}
        jun_codes = {r["project_code"] for r in jun_rows}

        self.assertEqual(len(jan_codes & feb_codes), 1799)
        self.assertEqual(len(feb_codes & mar_codes), 1870)
        self.assertEqual(len(mar_codes & jun_codes), 1753)


if __name__ == "__main__":
    unittest.main()
