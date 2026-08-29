from __future__ import annotations

import csv
import hashlib
import json
import unittest
from pathlib import Path

import numpy as np

from src.ml.dataset_builder import COMPLETED_SHA256, ONGOING_SHA256
from src.ml.refine_logistic import (
    LEGACY_MINIMAL_STATIC_NUMERIC,
    MODERN_SELECTED_TRAJECTORY,
    REGIME_FEATURE_SETS,
    candidate_model_name,
    fit_logistic_variant,
    project_cluster_intervals,
)
from src.ml.robustness_audit import FULL_V1_FEATURES, STATIC_AT_T_FEATURES, TRAJECTORY_FEATURES


ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = ROOT / "data/ml/schedule_extension_3m"
REFINEMENT_DIR = DATASET_DIR / "evaluation/refinement"


def sample_row(cost: str, target: str) -> dict[str, str]:
    return {
        "sector": "POWER",
        "original_cost": cost,
        "target_effective_schedule_ext_3m": target,
    }


class LogisticRefinementUnitTests(unittest.TestCase):
    def test_feature_sets_are_manual_regime_specific_subsets(self) -> None:
        self.assertEqual(REGIME_FEATURE_SETS["LEGACY"]["trajectory_only"], TRAJECTORY_FEATURES)
        self.assertEqual(
            REGIME_FEATURE_SETS["LEGACY"]["trajectory_plus_minimal_static"],
            TRAJECTORY_FEATURES + LEGACY_MINIMAL_STATIC_NUMERIC,
        )
        self.assertEqual(REGIME_FEATURE_SETS["MODERN"]["static_only"], STATIC_AT_T_FEATURES)
        self.assertEqual(
            REGIME_FEATURE_SETS["MODERN"]["static_plus_selected_trajectory"],
            STATIC_AT_T_FEATURES + MODERN_SELECTED_TRAJECTORY,
        )
        self.assertEqual(REGIME_FEATURE_SETS["LEGACY"]["full_v1"], FULL_V1_FEATURES)
        self.assertEqual(REGIME_FEATURE_SETS["MODERN"]["full_v1"], FULL_V1_FEATURES)
        self.assertLess(len(MODERN_SELECTED_TRAJECTORY), len(TRAJECTORY_FEATURES))
        self.assertTrue(set(MODERN_SELECTED_TRAJECTORY).issubset(TRAJECTORY_FEATURES))
        self.assertTrue(set(LEGACY_MINIMAL_STATIC_NUMERIC).issubset(STATIC_AT_T_FEATURES))

    def test_balanced_and_unweighted_are_explicit_separate_fits(self) -> None:
        training = [
            sample_row("10", "0"), sample_row("20", "0"), sample_row("30", "0"),
            sample_row("40", "0"), sample_row("80", "1"),
        ]
        evaluation = [sample_row("25", "0"), sample_row("70", "1")]
        unweighted, _, unweighted_model = fit_logistic_variant(
            training, evaluation, ["sector", "original_cost"], None
        )
        balanced, _, balanced_model = fit_logistic_variant(
            training, evaluation, ["sector", "original_cost"], "balanced"
        )
        self.assertIsNone(unweighted_model.class_weight)
        self.assertEqual(balanced_model.class_weight, "balanced")
        self.assertFalse(np.array_equal(unweighted, balanced))
        self.assertNotEqual(
            candidate_model_name("static_only", "unweighted"),
            candidate_model_name("static_only", "balanced"),
        )

    def test_project_cluster_bootstrap_is_deterministic(self) -> None:
        rows = [
            {
                "project_code": code,
                "actual_label": actual,
                "predicted_probability": score,
                "predicted_label": int(score >= 0.5),
            }
            for code, actual, score in (
                ("A", 0, 0.1), ("A", 1, 0.7), ("B", 0, 0.2),
                ("B", 0, 0.4), ("C", 1, 0.8), ("C", 1, 0.9),
            )
        ]
        first = project_cluster_intervals(rows, 30, seed=9)
        second = project_cluster_intervals(rows, 30, seed=9)
        self.assertEqual(first, second)


class GeneratedLogisticRefinementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = json.loads(
            (REFINEMENT_DIR / "configuration_manifest.json").read_text(encoding="utf-8")
        )

    def test_manifest_enforces_scope_embargo_and_reconciliation(self) -> None:
        validation = self.manifest["validation"]
        self.assertEqual(validation["evaluated_fold_count"], 17)
        self.assertEqual(validation["embargo_violations"], 0)
        self.assertFalse(validation["random_split_created"])
        self.assertFalse(validation["calibration_fitted"])
        self.assertEqual(validation["nonlinear_models_implemented"], [])
        self.assertLessEqual(
            validation["accepted_full_v1_score_reconciliation_max_absolute_difference"], 1e-12
        )
        self.assertEqual(self.manifest["skipped_folds"], [])

    def test_generated_population_and_candidate_counts_are_exact(self) -> None:
        generated = self.manifest["generated_files"]
        self.assertEqual(generated["candidate_model_comparison.csv"]["rows"], 12)
        self.assertEqual(generated["fold_metrics.csv"]["rows"], 136)
        self.assertEqual(generated["regime_aggregates.csv"]["rows"], 16)
        self.assertEqual(generated["predictions.csv"]["rows"], 201512)
        self.assertEqual(generated["cluster_bootstrap_cis.csv"]["rows"], 112)
        self.assertEqual(self.manifest["bootstrap"]["iterations"], 1000)

    def test_every_candidate_uses_identical_accepted_folds(self) -> None:
        with (REFINEMENT_DIR / "fold_metrics.csv").open(
            "r", encoding="utf-8-sig", newline=""
        ) as handle:
            rows = list(csv.DictReader(handle))
        by_fold: dict[tuple[str, str], list[dict[str, str]]] = {}
        for row in rows:
            by_fold.setdefault((row["regime"], row["evaluation_month"]), []).append(row)
            self.assertLess(row["maximum_training_label_window_end"], row["evaluation_month"])
        self.assertEqual(len(by_fold), 17)
        for fold_rows in by_fold.values():
            self.assertEqual(len(fold_rows), 8)
            self.assertEqual(len({row["training_rows"] for row in fold_rows}), 1)
            self.assertEqual(len({row["evaluation_rows"] for row in fold_rows}), 1)
            self.assertEqual(len({row["evaluation_positives"] for row in fold_rows}), 1)

    def test_weighting_and_calibration_findings_are_reported_not_silently_selected(self) -> None:
        self.assertEqual(self.manifest["winners"]["LEGACY"]["weighting"], "balanced")
        self.assertEqual(self.manifest["winners"]["MODERN"]["weighting"], "unweighted")
        self.assertIn("LEGACY", self.manifest["class_weight_effects"])
        findings = self.manifest["calibration_findings"]
        self.assertFalse(findings["calibration_fitted"])
        self.assertGreater(findings["modern_underprediction_absolute_gap_reduction"], 0)
        self.assertEqual(findings["modern_winner_underpredicting_fold_count"], 5)
        self.assertEqual(findings["modern_winner_evaluated_fold_count"], 5)

    def test_february_2025_remains_in_legacy_stability_results(self) -> None:
        legacy_winner = self.manifest["winners"]["LEGACY"]["model"]
        result = next(
            row for row in self.manifest["aggregate_results"]
            if row["regime"] == "LEGACY" and row["model"] == legacy_winner
        )
        self.assertIsNotNone(result["feb_2025_ap"])
        self.assertLess(result["feb_2025_ap"], result["average_precision"])
        self.assertGreater(result["pooled_ap_without_feb_2025"], result["average_precision"])

    def test_canonical_hashes_remain_unchanged(self) -> None:
        def digest(path: Path) -> str:
            return hashlib.sha256(path.read_bytes()).hexdigest().upper()

        self.assertEqual(digest(ROOT / "data/processed/projects_monthly.csv"), ONGOING_SHA256)
        self.assertEqual(digest(ROOT / "data/processed/projects_completed.csv"), COMPLETED_SHA256)


if __name__ == "__main__":
    unittest.main()
