from __future__ import annotations

import csv
import hashlib
import json
import unittest
from pathlib import Path

from src.ml.dataset_builder import (
    COMPLETED_SHA256,
    FEATURE_COLUMNS,
    ONGOING_SHA256,
    add_months,
    build_features,
    classify_target,
    segment_for_month,
    training_reference_is_embargo_safe,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "ml" / "schedule_extension_3m"


def row(month: str, original: str = "2026-01", revised: str = "", **changes: str) -> dict[str, str]:
    value = {
        "project_code": "N00000001",
        "report_month": month,
        "original_completion_date": original,
        "revised_completion_date": revised,
        "approval_date": "2020-01",
        "start_date": "",
        "original_cost": "100",
        "revised_cost": "",
        "cumulative_expenditure": "50",
        "physical_progress": "",
        "sector": "POWER",
        "agency": "SOURCE AGENCY",
        "state": "STATE",
    }
    value.update(changes)
    return value


class DatasetBuilderUnitTests(unittest.TestCase):
    def test_month_arithmetic_and_segments(self) -> None:
        self.assertEqual(add_months("2023-11", 3), "2024-02")
        self.assertEqual(segment_for_month("2023-12"), None)
        self.assertEqual(segment_for_month("2025-07"), ("SEGMENT_4", "MODERN"))

    def test_strict_walk_forward_embargo(self) -> None:
        self.assertFalse(training_reference_is_embargo_safe("2025-01", "2025-04"))
        self.assertTrue(training_reference_is_embargo_safe("2025-01", "2025-05"))

    def test_first_revision_positive_requires_reported_future_value(self) -> None:
        history = [
            row("2025-01"), row("2025-02"), row("2025-03", revised="2026-04"), row("2025-04")
        ]
        decision = classify_target(history[0], {item["report_month"]: item for item in history}, history)
        self.assertTrue(decision.eligible)
        self.assertEqual(decision.label, 1)
        self.assertEqual(decision.extension_type, "FIRST_REVISION")
        self.assertEqual(decision.event_month, "2025-03")

    def test_subsequent_revision_positive(self) -> None:
        history = [
            row("2025-01", revised="2026-03"),
            row("2025-02", revised="2026-03"),
            row("2025-03", revised="2026-06"),
            row("2025-04", revised="2026-06"),
        ]
        decision = classify_target(history[0], {item["report_month"]: item for item in history}, history)
        self.assertEqual((decision.label, decision.extension_type), (1, "SUBSEQUENT_REVISION"))

    def test_null_after_reported_revision_is_not_negative(self) -> None:
        history = [
            row("2025-01", revised="2026-03"), row("2025-02"), row("2025-03"), row("2025-04")
        ]
        decision = classify_target(history[0], {item["report_month"]: item for item in history}, history)
        self.assertFalse(decision.eligible)
        self.assertEqual(decision.reason, "FUTURE_REVISION_PERSISTENCE_AMBIGUOUS")

    def test_prior_revision_then_null_at_t_makes_baseline_ambiguous(self) -> None:
        history = [
            row("2024-12", revised="2026-03"), row("2025-01"), row("2025-02"), row("2025-03"), row("2025-04")
        ]
        by_month = {item["report_month"]: item for item in history}
        decision = classify_target(history[1], by_month, history)
        self.assertFalse(decision.eligible)
        self.assertEqual(decision.reason, "BASELINE_REVISION_PERSISTENCE_AMBIGUOUS")

    def test_disappearance_is_censored(self) -> None:
        history = [row("2025-01"), row("2025-02"), row("2025-04")]
        decision = classify_target(history[0], {item["report_month"]: item for item in history}, history)
        self.assertFalse(decision.eligible)
        self.assertEqual(decision.reason, "PROJECT_DISAPPEARED_OR_MONTH_MISSING")

    def test_structural_boundary_is_ineligible(self) -> None:
        history = [row("2023-10"), row("2023-11"), row("2024-01")]
        decision = classify_target(history[0], {item["report_month"]: item for item in history}, history)
        self.assertFalse(decision.eligible)
        self.assertEqual(decision.reason, "STRUCTURAL_GAP_OR_REGIME_BOUNDARY")

    def test_features_do_not_change_when_future_rows_change(self) -> None:
        current = row("2025-01")
        past = row("2024-12", cumulative_expenditure="40")
        future_a = row("2025-02", revised="2026-05", cumulative_expenditure="60")
        future_b = row("2025-02", revised="2030-01", cumulative_expenditure="999")
        history_a = [past, current, future_a]
        history_b = [past, current, future_b]
        features_a = build_features(current, {item["report_month"]: item for item in history_a}, history_a, "2026-01")
        features_b = build_features(current, {item["report_month"]: item for item in history_b}, history_b, "2026-01")
        self.assertEqual(features_a, features_b)


class GeneratedDatasetRegressionTests(unittest.TestCase):
    def test_canonical_hashes_are_protected(self) -> None:
        def digest(path: Path) -> str:
            return hashlib.sha256(path.read_bytes()).hexdigest().upper()

        self.assertEqual(digest(ROOT / "data/processed/projects_monthly.csv"), ONGOING_SHA256)
        self.assertEqual(digest(ROOT / "data/processed/projects_completed.csv"), COMPLETED_SHA256)

    def test_manifest_and_generated_counts(self) -> None:
        manifest = json.loads((OUTPUT / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["summary"]["LEGACY"]["eligible_rows"], 25406)
        self.assertEqual(manifest["summary"]["LEGACY"]["positive_rows"], 2634)
        self.assertEqual(manifest["summary"]["MODERN"]["eligible_rows"], 11899)
        self.assertEqual(manifest["summary"]["MODERN"]["positive_rows"], 4327)
        self.assertEqual(manifest["validations"]["duplicate_prediction_keys"], 0)
        self.assertEqual(manifest["validations"]["structural_gap_or_regime_crossings"], 0)
        self.assertEqual(manifest["validations"]["completed_project_feature_columns"], [])
        self.assertTrue(set(manifest["metadata_only_leakage_do_not_use"]).isdisjoint(FEATURE_COLUMNS))
        self.assertFalse(manifest["random_split_created"])

    def test_prediction_keys_unique_and_positive_evidence_reproducible(self) -> None:
        with (ROOT / "data/processed/projects_monthly.csv").open(
            "r", encoding="utf-8-sig", newline=""
        ) as handle:
            canonical = {
                (item["project_code"], item["report_month"]): item
                for item in csv.DictReader(handle)
            }
        seen: set[tuple[str, str]] = set()
        for name in ("eligible_legacy.csv", "eligible_modern.csv"):
            with (OUTPUT / name).open("r", encoding="utf-8-sig", newline="") as handle:
                for item in csv.DictReader(handle):
                    key = (item["project_code"], item["report_month"])
                    self.assertNotIn(key, seen)
                    seen.add(key)
                    self.assertEqual(segment_for_month(item["report_month"]), segment_for_month(item["target_window_end_month"]))
                    if item["target_effective_schedule_ext_3m"] == "1":
                        self.assertTrue(item["target_event_month"])
                        source_event = canonical[(item["project_code"], item["target_event_month"])]
                        self.assertEqual(
                            source_event["revised_completion_date"],
                            item["target_event_revised_completion_date"],
                        )
                        self.assertGreater(
                            int(item["target_event_revised_completion_date"].replace("-", "")),
                            int(item["baseline_completion_date"].replace("-", "")),
                        )
                    else:
                        for offset in (1, 2, 3):
                            future_month = add_months(item["report_month"], offset)
                            self.assertIn((item["project_code"], future_month), canonical)

    def test_persistence_audit_expected_material_counts(self) -> None:
        audit = json.loads((OUTPUT / "effective_commitment_persistence_audit.json").read_text(encoding="utf-8"))
        self.assertEqual(audit["revised_completion_date"]["TOTAL"]["projects_affected"], 750)
        self.assertEqual(audit["revised_completion_date"]["TOTAL"]["adjacent_non_null_to_null_transitions"], 798)
        self.assertEqual(audit["revised_cost"]["TOTAL"]["projects_affected"], 89)


if __name__ == "__main__":
    unittest.main()
