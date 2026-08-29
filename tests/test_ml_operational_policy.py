from __future__ import annotations

import csv
import hashlib
import json
import math
import unittest
from pathlib import Path

import numpy as np

from src.ml.dataset_builder import (
    COMPLETED_SHA256,
    ONGOING_SHA256,
    training_reference_is_embargo_safe,
)
from src.ml.operational_policy import (
    LOCKED_MODELS,
    SELECTED_MINIMUM,
    apply_platt,
    fit_platt,
    select_precision_threshold,
    select_recall_threshold,
)


ROOT = Path(__file__).resolve().parents[1]
POLICY_DIR = ROOT / "data/ml/schedule_extension_3m/evaluation/operational_policy"


def read_csv(name: str) -> list[dict[str, str]]:
    with (POLICY_DIR / name).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


class OperationalPolicyUnitTests(unittest.TestCase):
    def test_strict_embargo_rejects_equality_for_main_and_nested_boundaries(self) -> None:
        # The same helper enforces T+3<E for an outer E and T'+3<T for nested OOF T.
        self.assertFalse(training_reference_is_embargo_safe("2025-08", "2025-11", 3))
        self.assertTrue(training_reference_is_embargo_safe("2025-08", "2025-12", 3))
        self.assertFalse(training_reference_is_embargo_safe("2025-07", "2025-10", 3))
        self.assertTrue(training_reference_is_embargo_safe("2025-07", "2025-11", 3))

    def test_locked_model_families_and_selected_minimum_are_explicit(self) -> None:
        self.assertEqual(LOCKED_MODELS["LEGACY"], "catboost_full_v1__unweighted")
        self.assertEqual(LOCKED_MODELS["MODERN"], "logistic_static_only__unweighted")
        self.assertEqual(SELECTED_MINIMUM["minimum_rows"], 1000)
        self.assertEqual(SELECTED_MINIMUM["minimum_months"], 2)
        self.assertEqual(SELECTED_MINIMUM["minimum_per_class"], 100)

    def test_platt_fit_consumes_one_dimensional_raw_logits(self) -> None:
        logits = np.asarray([-3.0, -1.5, -0.5, 0.5, 1.5, 3.0])
        labels = np.asarray([0, 0, 0, 1, 1, 1])
        slope, intercept, _ = fit_platt(logits, labels)
        calibrated = apply_platt(logits, slope, intercept)
        self.assertGreater(slope, 0.0)
        self.assertTrue(np.all(np.diff(calibrated) > 0.0))
        with self.assertRaisesRegex(ValueError, "one-dimensional raw logits"):
            fit_platt(logits.reshape(-1, 1), labels)

    def test_threshold_selection_is_history_only_and_deterministic(self) -> None:
        scores = np.asarray([0.1, 0.2, 0.4, 0.8, 0.9])
        labels = np.asarray([0, 1, 0, 1, 1])
        first_recall = select_recall_threshold(scores, labels, 2 / 3)
        second_recall = select_recall_threshold(scores, labels, 2 / 3)
        first_precision = select_precision_threshold(scores, labels, 0.5)
        second_precision = select_precision_threshold(scores, labels, 0.5)
        self.assertEqual(first_recall, second_recall)
        self.assertEqual(first_precision, second_precision)
        self.assertEqual(first_recall[0], 0.8)
        self.assertEqual(first_precision[0], 0.1)


class GeneratedOperationalPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            (POLICY_DIR / "configuration_manifest.json").read_text(encoding="utf-8")
        )
        cls.calibration = read_csv("fold_calibration_metrics.csv")
        cls.pools = read_csv("calibration_pools_audit.csv")
        cls.policy_rows = read_csv("threshold_policy_fold_metrics.csv")
        cls.caps = read_csv("cap_sensitivity.csv")
        cls.predictions = read_csv("predictions.csv")
        cls.freeze = json.loads(
            (POLICY_DIR / "threshold_freeze_audit.json").read_text(encoding="utf-8")
        )
        cls.nested = json.loads(
            (POLICY_DIR / "nested_oof_audit.json").read_text(encoding="utf-8")
        )

    def test_manifest_records_zero_leakage_and_closed_scope(self) -> None:
        validation = self.manifest["validation"]
        self.assertEqual(validation["main_embargo_violations"], 0)
        self.assertEqual(validation["nested_embargo_violations"], 0)
        self.assertEqual(validation["evaluation_leakage_rows"], 0)
        self.assertEqual(validation["in_sample_threshold_fallbacks"], 0)
        self.assertFalse(validation["random_split_created"])
        self.assertEqual(validation["other_model_families_implemented"], [])
        self.assertEqual(validation["secondary_targets_implemented"], [])
        self.assertLessEqual(
            validation["locked_score_reconciliation_max_absolute_difference"], 1e-12
        )

    def test_main_and_nested_audits_preserve_strict_temporal_order(self) -> None:
        for row in self.pools:
            self.assertLess(row["maximum_main_training_label_window_end"], row["evaluation_month"])
            for month in filter(None, row["pool_months"].split(";")):
                self.assertLess(month, row["evaluation_month"])
        generated = [row for row in self.nested if row["status"] == "GENERATED"]
        self.assertTrue(generated)
        for row in generated:
            self.assertLess(row["maximum_subtraining_label_window_end"], row["target_month"])
            self.assertLess(row["subtraining_month_max"], row["target_month"])

    def test_unavailable_folds_have_no_in_sample_threshold_fallback(self) -> None:
        unavailable = [row for row in self.policy_rows if row["threshold_status"] == "UNAVAILABLE"]
        self.assertTrue(unavailable)
        for row in unavailable:
            self.assertEqual(row["selected_threshold"], "")
            self.assertEqual(row["alert_count"], "")
            self.assertEqual(row["tp"], "")
            self.assertEqual(row["precision"], "")

    def test_modern_early_folds_are_inactive_and_only_m5_is_calibrated(self) -> None:
        modern = [row for row in self.calibration if row["regime"] == "MODERN"]
        self.assertEqual([row["evaluation_month"] for row in modern], [
            "2025-12", "2026-01", "2026-02", "2026-03", "2026-04"
        ])
        self.assertEqual([row["calibration_active"] for row in modern], [
            "False", "False", "False", "False", "True"
        ])
        m4, m5 = modern[-2:]
        self.assertEqual((m4["pool_rows"], m4["pool_month_count"]), ("772", "1"))
        self.assertEqual((m5["pool_rows"], m5["pool_month_count"]), ("2110", "2"))
        self.assertLess(float(m5["operational_brier_score"]), float(m5["raw_brier_score"]))
        self.assertLess(float(m5["operational_ece_10bin"]), float(m5["raw_ece_10bin"]))
        self.assertAlmostEqual(
            float(m5["operational_average_precision"]),
            float(m5["raw_average_precision"]),
            places=12,
        )

    def test_modern_platt_uses_raw_logits_and_legacy_scores_remain_raw(self) -> None:
        active_pool = next(
            row for row in self.pools
            if row["regime"] == "MODERN" and row["calibration_active"] == "True"
        )
        self.assertEqual(active_pool["platt_input"], "RAW_DECISION_LOGIT")
        for row in self.predictions:
            raw_from_logit = 1.0 / (1.0 + math.exp(-float(row["raw_logit"])))
            self.assertAlmostEqual(raw_from_logit, float(row["raw_probability"]), places=12)
            if row["identifier_regime"] == "LEGACY":
                self.assertEqual(row["calibration_active"], "False")
                self.assertAlmostEqual(
                    float(row["raw_probability"]),
                    float(row["operational_probability"]),
                    places=15,
                )

    def test_thresholds_are_persisted_frozen_before_evaluation_scoring(self) -> None:
        frozen = {}
        for fold in self.freeze:
            self.assertTrue(fold["frozen_before_evaluation_scoring"])
            for policy in fold["policies"]:
                frozen[(fold["regime"], fold["evaluation_month"], policy["policy"], policy["candidate_value"])] = policy
        for row in self.policy_rows:
            key = (
                row["regime"], row["evaluation_month"], row["policy"],
                float(row["candidate_value"]),
            )
            self.assertEqual(row["threshold_frozen_before_evaluation"], "True")
            self.assertEqual(row["threshold_status"], frozen[key]["threshold_status"])
            if row["threshold_status"] == "AVAILABLE":
                self.assertAlmostEqual(
                    float(row["selected_threshold"]), float(frozen[key]["threshold"]), places=14
                )

    def test_cap_rows_report_override_counts_and_recall_shortfall(self) -> None:
        available = [row for row in self.caps if row["threshold_status"] == "AVAILABLE"]
        activated = [row for row in available if row["alert_cap_triggered"] == "True"]
        self.assertTrue(activated)
        for row in available:
            self.assertLessEqual(int(row["capped_alert_count"]), int(row["original_alert_count"]))
            self.assertEqual(
                int(row["suppressed_alerts"]),
                int(row["original_alert_count"]) - int(row["capped_alert_count"]),
            )
            expected = max(
                0.0,
                float(row["target_recall"]) - float(row["achieved_recall_after_cap"]),
            )
            self.assertAlmostEqual(float(row["recall_shortfall"]), expected, places=14)

    def test_generated_shape_and_bootstrap_are_deterministic_contracts(self) -> None:
        generated = self.manifest["generated_files"]
        self.assertEqual(generated["fold_calibration_metrics.csv"]["rows"], 17)
        self.assertEqual(generated["threshold_policy_fold_metrics.csv"]["rows"], 119)
        self.assertEqual(generated["policy_aggregate_metrics.csv"]["rows"], 14)
        self.assertEqual(generated["cap_sensitivity.csv"]["rows"], 204)
        self.assertEqual(generated["top_k_metrics.csv"]["rows"], 63)
        self.assertEqual(generated["predictions.csv"]["rows"], 25189)
        self.assertEqual(self.manifest["bootstrap"]["iterations"], 1000)

    def test_canonical_hashes_remain_unchanged(self) -> None:
        def digest(path: Path) -> str:
            return hashlib.sha256(path.read_bytes()).hexdigest().upper()

        self.assertEqual(digest(ROOT / "data/processed/projects_monthly.csv"), ONGOING_SHA256)
        self.assertEqual(digest(ROOT / "data/processed/projects_completed.csv"), COMPLETED_SHA256)


if __name__ == "__main__":
    unittest.main()
