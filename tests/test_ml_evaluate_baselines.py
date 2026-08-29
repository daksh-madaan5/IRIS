from __future__ import annotations

import csv
import hashlib
import json
import unittest
from pathlib import Path

import numpy as np

from src.ml.dataset_builder import COMPLETED_SHA256, ONGOING_SHA256
from src.ml.evaluate_baselines import (
    EVALUATION_ORIGINS,
    FoldPreprocessor,
    PROHIBITED_FEATURES,
    bootstrap_intervals,
    fit_logistic_scores,
    lagged_rule_predictions,
    select_training_rows,
)


ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = ROOT / "data/ml/schedule_extension_3m"
EVALUATION_DIR = DATASET_DIR / "evaluation"


def sample_row(
    month: str,
    regime: str = "LEGACY",
    segment: str = "SEGMENT_1",
    code: str = "N00000001",
    prior_extensions: str = "0",
) -> dict[str, str]:
    return {
        "project_code": code,
        "report_month": month,
        "identifier_regime": regime,
        "continuous_segment": segment,
        "target_window_end_month": month,
        "target_effective_schedule_ext_3m": "0",
        "sector": "POWER",
        "agency": "AGENCY A",
        "state": "STATE A",
        "original_cost": "100",
        "n_prior_schedule_extensions": prior_extensions,
    }


class BaselineEvaluatorUnitTests(unittest.TestCase):
    def test_embargo_is_strict_and_excludes_equal_window_end(self) -> None:
        rows = [sample_row("2023-03"), sample_row("2023-04"), sample_row("2023-05")]
        selected = select_training_rows(rows, "LEGACY", "2023-07")
        self.assertEqual([row["report_month"] for row in selected], ["2023-03"])

    def test_preprocessing_is_fit_on_training_only(self) -> None:
        features = ["sector", "original_cost"]
        training = [
            {"sector": "A", "original_cost": "10"},
            {"sector": "A", "original_cost": "20"},
            {"sector": "B", "original_cost": ""},
        ]
        evaluation = [{"sector": "UNSEEN", "original_cost": "1000000"}]
        processor = FoldPreprocessor(features).fit(training)
        original_mean = processor.numeric_mean["original_cost"]
        matrix = processor.transform(evaluation)
        self.assertEqual(original_mean, 15.0)
        self.assertEqual(processor.category_frequency["sector"], {"A": 2 / 3, "B": 1 / 3})
        self.assertEqual(matrix[0, 0], 0.0)
        self.assertEqual(processor.numeric_mean["original_cost"], original_mean)

    def test_manifest_drives_features_and_prohibits_metadata(self) -> None:
        manifest = json.loads((DATASET_DIR / "manifest.json").read_text(encoding="utf-8"))
        self.assertTrue(set(manifest["feature_columns"]).isdisjoint(PROHIBITED_FEATURES))
        self.assertIn("baseline_completion_date", PROHIBITED_FEATURES)
        self.assertIn("extension_type", PROHIBITED_FEATURES)

    def test_training_selection_separates_regimes(self) -> None:
        rows = [
            sample_row("2025-07", "MODERN", "SEGMENT_4", "600001"),
            sample_row("2025-01", "LEGACY", "SEGMENT_3"),
        ]
        selected = select_training_rows(rows, "MODERN", "2025-12")
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["identifier_regime"], "MODERN")

    def test_bootstrap_is_deterministic_for_fixed_seed(self) -> None:
        y = np.asarray([0, 0, 0, 1, 1], dtype=int)
        score = np.asarray([0.1, 0.2, 0.4, 0.6, 0.9], dtype=float)
        predicted = (score >= 0.5).astype(int)
        first = bootstrap_intervals(y, score, predicted, seed=42, iterations=25)
        second = bootstrap_intervals(y, score, predicted, seed=42, iterations=25)
        self.assertEqual(first, second)

    def test_logistic_evaluation_is_deterministic(self) -> None:
        training = [
            {**sample_row("2023-01", code="A"), "target_effective_schedule_ext_3m": "0", "original_cost": "10"},
            {**sample_row("2023-01", code="B"), "target_effective_schedule_ext_3m": "0", "original_cost": "20"},
            {**sample_row("2023-02", code="C"), "target_effective_schedule_ext_3m": "1", "original_cost": "80"},
            {**sample_row("2023-02", code="D"), "target_effective_schedule_ext_3m": "1", "original_cost": "100"},
        ]
        evaluation = [
            {**sample_row("2023-07", code="E"), "original_cost": "15"},
            {**sample_row("2023-07", code="F"), "original_cost": "90"},
        ]
        first, _, _ = fit_logistic_scores(training, evaluation, ["sector", "original_cost"])
        second, _, _ = fit_logistic_scores(training, evaluation, ["sector", "original_cost"])
        np.testing.assert_array_equal(first, second)

    def test_lagged_rule_uses_latest_prior_transition_not_future(self) -> None:
        rows = [
            sample_row("2024-06", segment="SEGMENT_3", prior_extensions="1"),
            sample_row("2024-07", segment="SEGMENT_3", prior_extensions="2"),
            sample_row("2024-08", segment="SEGMENT_3", prior_extensions="99"),
        ]
        prediction, covered = lagged_rule_predictions([rows[1]], rows)
        self.assertEqual(prediction.tolist(), [1])
        self.assertEqual(covered.tolist(), [1])
        rows[2]["n_prior_schedule_extensions"] = "0"
        prediction_after_future_change, _ = lagged_rule_predictions([rows[1]], rows)
        self.assertEqual(prediction_after_future_change.tolist(), [1])


class GeneratedBaselineEvaluationRegressionTests(unittest.TestCase):
    def test_evaluation_manifest_has_requested_folds_and_no_leakage(self) -> None:
        manifest = json.loads((EVALUATION_DIR / "evaluation_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["evaluated_origins"], EVALUATION_ORIGINS)
        self.assertEqual(manifest["validation"]["skipped_fold_count"], 0)
        self.assertEqual(manifest["validation"]["prohibited_feature_intersection"], [])
        self.assertEqual(manifest["validation"]["embargo_violations"], 0)
        self.assertFalse(manifest["validation"]["random_split_created"])
        self.assertEqual(manifest["configuration"]["bootstrap"]["iterations"], 1000)
        self.assertIsNone(manifest["configuration"]["logistic_regression"]["class_weight"])

        aggregate = {
            (row["regime"], row["model"]): row for row in manifest["aggregate_results"]
        }
        self.assertAlmostEqual(
            aggregate[("LEGACY", "logistic_l2_unweighted")]["average_precision"],
            0.29059411548598246,
        )
        self.assertAlmostEqual(
            aggregate[("MODERN", "logistic_l2_unweighted")]["average_precision"],
            0.7091363989429846,
        )
        self.assertEqual(manifest["generated_files"]["fold_metrics.csv"]["rows"], 68)
        self.assertEqual(manifest["generated_files"]["predictions.csv"]["rows"], 100756)

    def test_fold_training_windows_end_before_evaluation(self) -> None:
        with (EVALUATION_DIR / "fold_metrics.csv").open(
            "r", encoding="utf-8-sig", newline=""
        ) as handle:
            for row in csv.DictReader(handle):
                self.assertLess(row["training_month_max"], row["evaluation_month"])
        audits = json.loads(
            (EVALUATION_DIR / "preprocessing_fit_audit.json").read_text(encoding="utf-8")
        )
        for audit in audits:
            self.assertLess(audit["maximum_training_label_window_end"], audit["evaluation_month"])
            self.assertGreater(audit["fit_row_count"], 0)
            self.assertEqual(audit["input_feature_count"], 36)

    def test_predictions_are_regime_separated_and_precision_na_is_preserved(self) -> None:
        with (EVALUATION_DIR / "predictions.csv").open(
            "r", encoding="utf-8-sig", newline=""
        ) as handle:
            for row in csv.DictReader(handle):
                if row["identifier_regime"] == "LEGACY":
                    self.assertIn(row["report_month"], EVALUATION_ORIGINS["LEGACY"])
                else:
                    self.assertEqual(row["identifier_regime"], "MODERN")
                    self.assertIn(row["report_month"], EVALUATION_ORIGINS["MODERN"])
        with (EVALUATION_DIR / "regime_aggregate_metrics.csv").open(
            "r", encoding="utf-8-sig", newline=""
        ) as handle:
            metrics = list(csv.DictReader(handle))
        always = [row for row in metrics if row["model"] == "always_negative"]
        self.assertEqual(len(always), 2)
        self.assertTrue(all(row["precision"] == "" for row in always))
        self.assertTrue(all(row["f1"] == "0" for row in always))

    def test_canonical_hashes_remain_unchanged(self) -> None:
        def digest(path: Path) -> str:
            return hashlib.sha256(path.read_bytes()).hexdigest().upper()

        self.assertEqual(digest(ROOT / "data/processed/projects_monthly.csv"), ONGOING_SHA256)
        self.assertEqual(digest(ROOT / "data/processed/projects_completed.csv"), COMPLETED_SHA256)


if __name__ == "__main__":
    unittest.main()
