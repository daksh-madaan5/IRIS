import json
import unittest
from pathlib import Path


class LongitudinalValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        path = root / "data" / "validation" / "longitudinal_summary_2026_01_07.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        cls.data = data
        cls.transitions = {
            f"{item['earlier_month']}->{item['later_month']}": item
            for item in data["adjacent_month_transitions"]
        }

    def test_combined_key_and_month_coverage(self):
        self.assertEqual(self.data["rows"], 13181)
        self.assertEqual(self.data["report_months"], [f"2026-{month:02d}" for month in range(1, 8)])
        self.assertEqual(self.data["unique_projects"], 2127)
        self.assertEqual(self.data["projects_with_at_least_3_observations"], 2031)
        self.assertEqual(self.data["projects_with_at_least_6_observations"], 1726)
        self.assertEqual(self.data["projects_present_in_all_months"], 1367)
        self.assertEqual(self.data["duplicate_project_month_keys"], 0)

    def test_project_membership_transitions(self):
        expected = {
            "2026-01->2026-02": (1678, 24, 270),
            "2026-02->2026-03": (1919, 29, 22),
            "2026-03->2026-04": (1924, 17, 57),
            "2026-04->2026-05": (1951, 30, 36),
            "2026-05->2026-06": (1825, 162, 22),
            "2026-06->2026-07": (1732, 115, 43),
        }
        for pair, (both, earlier_only, later_only) in expected.items():
            item = self.transitions[pair]
            self.assertEqual((item["projects_in_both"], item["earlier_only"], item["later_only"]), (both, earlier_only, later_only))

    def test_expenditure_state_transitions(self):
        expected = {
            "2026-01->2026-02": {"negative_to_positive": 1, "positive_to_positive": 1417, "positive_to_zero": 4, "zero_to_positive": 24, "zero_to_zero": 232},
            "2026-02->2026-03": {"positive_to_positive": 1612, "positive_to_zero": 1, "zero_to_positive": 18, "zero_to_zero": 288},
            "2026-03->2026-04": {"positive_to_positive": 1633, "zero_to_positive": 7, "zero_to_zero": 284},
            "2026-04->2026-05": {"positive_to_positive": 1650, "zero_to_positive": 10, "zero_to_zero": 291},
            "2026-05->2026-06": {"positive_to_positive": 1548, "positive_to_zero": 6, "zero_to_positive": 26, "zero_to_zero": 245},
            "2026-06->2026-07": {"positive_to_positive": 1488, "positive_to_zero": 2, "zero_to_positive": 118, "zero_to_zero": 124},
        }
        for pair, counts in expected.items():
            self.assertEqual(self.transitions[pair]["expenditure_state_transitions"], counts)

    def test_numeric_transition_counts_reconcile_to_common_projects(self):
        for item in self.transitions.values():
            for counts in item["numeric_field_changes"].values():
                self.assertEqual(sum(counts.values()), item["projects_in_both"])

    def test_longitudinal_warning_counts_are_stable(self):
        self.assertEqual(
            self.data["longitudinal_warning_counts"],
            {
                "agency_changed": 844,
                "cumulative_expenditure_decreased": 265,
                "ministry_changed": 0,
                "physical_progress_decreased": 179,
                "positive_to_zero_expenditure": 13,
                "project_name_changed": 166,
                "revised_cost_decreased": 64,
                "sector_changed": 0,
                "state_changed": 28,
                "total": 1559,
            },
        )
    def test_whitespace_normalization_in_diagnostics(self):
        from src.build_dataset.monthly import _pair_summary
        earlier = "2024-07"
        later = "2024-08"
        rows = {
            earlier: [
                {"project_code": "1", "project_name": "A", "agency": "A", "ministry": "A", "sector": "COAL", "state": "BIHAR", "revised_cost": "", "cumulative_expenditure": "", "physical_progress": ""},
            ],
            later: [
                {"project_code": "1", "project_name": "A", "agency": "A", "ministry": "A", "sector": "COAL ", "state": " BIHAR ", "revised_cost": "", "cumulative_expenditure": "", "physical_progress": ""},
            ]
        }
        summary = _pair_summary(earlier, later, rows)
        self.assertEqual(summary["identity_field_change_counts"]["sector"], 0)
        self.assertEqual(summary["identity_field_change_counts"]["state"], 0)
        self.assertEqual(summary["identity_field_change_counts"]["sector_exact"], 1)
        self.assertEqual(summary["identity_field_change_counts"]["state_exact"], 1)
        self.assertEqual(rows[later][0]["sector"], "COAL ")
        self.assertEqual(rows[later][0]["state"], " BIHAR ")

    def test_calendar_gap_is_not_an_adjacent_month_transition(self):
        from src.build_dataset.monthly import _are_consecutive_months

        self.assertTrue(_are_consecutive_months("2023-10", "2023-11"))
        self.assertTrue(_are_consecutive_months("2023-12", "2024-01"))
        self.assertFalse(_are_consecutive_months("2023-11", "2024-01"))


if __name__ == "__main__":
    unittest.main()
