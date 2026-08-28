import unittest

from src.validation.core import (
    COMPLETION_DATE_BEFORE_START_DATE,
    EXPENDITURE_WITH_ZERO_PROGRESS,
    EXTREME_EXPENDITURE_COST_MISMATCH,
    FULL_PROGRESS_STILL_ONGOING,
    NEGATIVE_EXPENDITURE,
    PHYSICAL_PROGRESS_ABOVE_100,
    PROGRESS_REPORTED_BEFORE_START,
    REVISED_COST_BELOW_ORIGINAL,
    ZERO_EXPENDITURE_POSITIVE_PROGRESS,
    build_quality_control_rows,
    validate_records,
)


def record(**overrides):
    base = {
        "project_code": "612786",
        "report_month": "2026-07",
        "source_file": "sample.pdf",
        "source_page": 55,
        "source_row_number": 1,
        "approval_date": "2023-03",
        "start_date": "2024-01",
        "original_completion_date": "2026-01",
        "revised_completion_date": "2026-09",
        "approval_date_raw": "03/2023",
        "start_date_raw": "01/2024",
        "original_completion_date_raw": "01/2026",
        "revised_completion_date_raw": "09/2026",
        "original_cost": 265.91,
        "revised_cost": 265.91,
        "cumulative_expenditure": 176.38,
        "physical_progress": 80.0,
        "original_cost_raw": "265.91",
        "revised_cost_raw": "265.91",
        "cumulative_expenditure_raw": "176.38",
        "physical_progress_raw": "80",
    }
    base.update(overrides)
    return base


class ValidationTests(unittest.TestCase):
    def test_structurally_absent_project_code_is_counted_without_error_warning(self):
        from src.validation.core import validate_records

        sample = record(project_code=None)
        warnings, duplicates, metrics = validate_records(
            [sample], project_code_structurally_absent=True
        )
        self.assertNotIn("missing_project_code", {warning["rule"] for warning in warnings})
        self.assertEqual(duplicates, [])
        self.assertEqual(metrics["missing_project_codes"], 1)
        self.assertEqual(metrics["structurally_missing_project_codes"], 1)

    @staticmethod
    def rules(row):
        warnings, _, _ = validate_records([row])
        return {item["rule"] for item in warnings}

    def test_duplicate_detection_does_not_drop(self):
        rows = [record(), record(source_page=56)]
        warnings, duplicates, metrics = validate_records(rows)
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(duplicates), 2)
        self.assertEqual(metrics["duplicate_project_codes"], 1)

    def test_progress_range_is_flagged_not_clamped(self):
        rows = [record(physical_progress=101.2, physical_progress_raw="101.2")]
        warnings, _, _ = validate_records(rows)
        self.assertEqual(rows[0]["physical_progress"], 101.2)
        self.assertIn(PHYSICAL_PROGRESS_ABOVE_100, {item["rule"] for item in warnings})

    def test_zero_expenditure_positive_progress_after_start(self):
        row = record(cumulative_expenditure=0.0, cumulative_expenditure_raw="0", physical_progress=87.0, physical_progress_raw="87")
        warnings, _, _ = validate_records([row])
        self.assertIn(ZERO_EXPENDITURE_POSITIVE_PROGRESS, {item["rule"] for item in warnings})
        warning = next(item for item in warnings if item["rule"] == ZERO_EXPENDITURE_POSITIVE_PROGRESS)
        self.assertEqual((warning["severity"], warning["priority"], warning["category"]), ("INFO", "LOW", "UNUSUAL_BUSINESS_STATE"))
        self.assertEqual(row["cumulative_expenditure"], 0.0)
        self.assertEqual(row["physical_progress"], 87.0)

    def test_impossible_and_strong_anomaly_severity(self):
        impossible = record(physical_progress=101.0, physical_progress_raw="101")
        warnings, _, _ = validate_records([impossible])
        above = next(item for item in warnings if item["rule"] == PHYSICAL_PROGRESS_ABOVE_100)
        self.assertEqual((above["severity"], above["priority"], above["category"]), ("ERROR", "HIGH", "STRUCTURAL_OR_IMPOSSIBLE"))
        strong = record(revised_cost=10.0, revised_cost_raw="10", cumulative_expenditure=31.0, cumulative_expenditure_raw="31")
        warnings, _, _ = validate_records([strong])
        mismatch = next(item for item in warnings if item["rule"] == EXTREME_EXPENDITURE_COST_MISMATCH)
        self.assertEqual((mismatch["severity"], mismatch["priority"], mismatch["category"]), ("WARNING", "MEDIUM", "STRONG_PLAUSIBILITY_ANOMALY"))

    def test_positive_progress_before_future_start_is_separate_rule(self):
        row = record(start_date="2026-08", start_date_raw="08/2026", cumulative_expenditure=0.0, cumulative_expenditure_raw="0", physical_progress=10.0, physical_progress_raw="10")
        rules = self.rules(row)
        self.assertIn(PROGRESS_REPORTED_BEFORE_START, rules)
        self.assertNotIn(ZERO_EXPENDITURE_POSITIVE_PROGRESS, rules)

    def test_expenditure_with_zero_progress(self):
        self.assertIn(EXPENDITURE_WITH_ZERO_PROGRESS, self.rules(record(physical_progress=0.0, physical_progress_raw="0")))

    def test_full_and_above_100_progress_are_distinct(self):
        self.assertIn(FULL_PROGRESS_STILL_ONGOING, self.rules(record(physical_progress=100.0, physical_progress_raw="100")))
        above_rules = self.rules(record(physical_progress=100.01, physical_progress_raw="100.01"))
        self.assertIn(PHYSICAL_PROGRESS_ABOVE_100, above_rules)
        self.assertNotIn(FULL_PROGRESS_STILL_ONGOING, above_rules)

    def test_financial_cost_cross_field_rules(self):
        negative = self.rules(record(cumulative_expenditure=-1.0, cumulative_expenditure_raw="-1"))
        self.assertIn(NEGATIVE_EXPENDITURE, negative)
        extreme = self.rules(record(revised_cost=10.0, revised_cost_raw="10", cumulative_expenditure=31.0, cumulative_expenditure_raw="31"))
        self.assertIn(EXTREME_EXPENDITURE_COST_MISMATCH, extreme)
        below = self.rules(record(original_cost=100.0, original_cost_raw="100", revised_cost=90.0, revised_cost_raw="90"))
        self.assertIn(REVISED_COST_BELOW_ORIGINAL, below)

    def test_completion_before_start(self):
        row = record(start_date="2025-01", start_date_raw="01/2025", original_completion_date="2024-12", original_completion_date_raw="12/2024")
        self.assertIn(COMPLETION_DATE_BEFORE_START_DATE, self.rules(row))

    def test_quality_control_metrics_do_not_mutate_record(self):
        row = record(revised_cost=200.0, revised_cost_raw="200", cumulative_expenditure=50.0, cumulative_expenditure_raw="50", physical_progress=40.0, physical_progress_raw="40")
        original_keys = set(row)
        warnings, _, _ = validate_records([row])
        qc = build_quality_control_rows([row], warnings)[0]
        self.assertEqual(qc["financial_progress"], 25.0)
        self.assertEqual(qc["physical_financial_gap"], 15.0)
        self.assertEqual(set(row), original_keys)
        self.assertNotIn("financial_progress", row)


if __name__ == "__main__":
    unittest.main()
