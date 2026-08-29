from __future__ import annotations

import csv
import hashlib
import json
import unittest
from pathlib import Path

import numpy as np

from src.ml.challenger_catboost import (
    CATEGORICAL_MISSING_SENTINEL,
    CATBOOST_FEATURE_SETS,
    audit_fold_categories,
    catboost_model_name,
    fit_catboost_variant,
    paired_cluster_bootstrap,
    prepare_catboost_df,
)
from src.ml.dataset_builder import COMPLETED_SHA256, ONGOING_SHA256
from src.ml.evaluate_baselines import PROHIBITED_FEATURES
from src.ml.robustness_audit import FULL_V1_FEATURES, STATIC_AT_T_FEATURES, TRAJECTORY_FEATURES


ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = ROOT / "data/ml/schedule_extension_3m"
CATBOOST_DIR = DATASET_DIR / "evaluation/catboost"
REFINEMENT_DIR = DATASET_DIR / "evaluation/refinement"


def sample_row(sector: str, cost: str, exp_delta: str, target: str, code: str = "P1", month: str = "2024-06") -> dict[str, str]:
    return {
        "project_code": code,
        "report_month": month,
        "sector": sector,
        "agency": "NHAI",
        "state": "DELHI",
        "original_cost": cost,
        "exp_delta_3m": exp_delta,
        "target_effective_schedule_ext_3m": target,
    }


class CatBoostChallengerUnitTests(unittest.TestCase):
    def test_feature_sets_are_manual_regime_specific_subsets(self) -> None:
        self.assertEqual(CATBOOST_FEATURE_SETS["LEGACY"]["trajectory_only"], TRAJECTORY_FEATURES)
        self.assertEqual(CATBOOST_FEATURE_SETS["LEGACY"]["full_v1"], FULL_V1_FEATURES)
        self.assertEqual(CATBOOST_FEATURE_SETS["MODERN"]["static_only"], STATIC_AT_T_FEATURES)
        self.assertEqual(CATBOOST_FEATURE_SETS["MODERN"]["full_v1"], FULL_V1_FEATURES)
        for regime, fsets in CATBOOST_FEATURE_SETS.items():
            for fset_name, cols in fsets.items():
                intersection = set(cols) & PROHIBITED_FEATURES
                self.assertEqual(intersection, set(), f"Prohibited leakage in {regime} {fset_name}")

    def test_catboost_data_preparation_and_sentinel(self) -> None:
        rows = [
            sample_row("POWER", "100.5", "10.2", "0"),
            sample_row("", "", "", "1"),  # missing sector, cost, exp_delta
        ]
        feature_columns = ["sector", "original_cost", "exp_delta_3m"]
        df, cat_cols = prepare_catboost_df(rows, feature_columns)
        self.assertEqual(cat_cols, ["sector"])
        self.assertEqual(df["sector"].tolist(), ["POWER", CATEGORICAL_MISSING_SENTINEL])
        self.assertEqual(df["original_cost"].iloc[0], 100.5)
        self.assertTrue(np.isnan(df["original_cost"].iloc[1]))
        self.assertEqual(df["exp_delta_3m"].iloc[0], 10.2)
        self.assertTrue(np.isnan(df["exp_delta_3m"].iloc[1]))

    def test_audit_fold_categories(self) -> None:
        train_rows = [sample_row("POWER", "10", "1", "0"), sample_row("RAILWAYS", "20", "2", "1")]
        eval_rows = [sample_row("POWER", "15", "1", "0"), sample_row("COAL", "25", "3", "1")]
        audit = audit_fold_categories(train_rows, eval_rows, ["sector", "original_cost"])
        self.assertIn("sector", audit)
        self.assertEqual(audit["sector"]["training_distinct_count"], 2)
        self.assertEqual(audit["sector"]["evaluation_distinct_count"], 2)
        self.assertEqual(audit["sector"]["unseen_in_training_count"], 1)
        self.assertEqual(audit["sector"]["unseen_categories"], ["COAL"])

    def test_unweighted_and_balanced_catboost_variants(self) -> None:
        training = [
            sample_row("POWER", "10", "1", "0"),
            sample_row("POWER", "20", "2", "0"),
            sample_row("RAILWAYS", "30", "3", "0"),
            sample_row("RAILWAYS", "40", "4", "0"),
            sample_row("ROAD", "80", "15", "1"),
        ]
        evaluation = [
            sample_row("POWER", "25", "2", "0"),
            sample_row("ROAD", "70", "12", "1"),
        ]
        unweighted_preds, _, _ = fit_catboost_variant(
            training, evaluation, ["sector", "original_cost", "exp_delta_3m"], None
        )
        balanced_preds, _, _ = fit_catboost_variant(
            training, evaluation, ["sector", "original_cost", "exp_delta_3m"], "Balanced"
        )
        self.assertEqual(len(unweighted_preds), 2)
        self.assertEqual(len(balanced_preds), 2)
        self.assertTrue(np.all((unweighted_preds >= 0) & (unweighted_preds <= 1)))
        self.assertTrue(np.all((balanced_preds >= 0) & (balanced_preds <= 1)))
        self.assertFalse(np.allclose(unweighted_preds, balanced_preds))
        self.assertNotEqual(
            catboost_model_name("trajectory_only", "unweighted"),
            catboost_model_name("trajectory_only", "balanced"),
        )

    def test_deterministic_execution_within_tolerance(self) -> None:
        training = [
            sample_row("POWER", "10", "1", "0"),
            sample_row("RAILWAYS", "20", "2", "0"),
            sample_row("ROAD", "80", "15", "1"),
        ]
        evaluation = [sample_row("POWER", "25", "2", "0")]
        first, _, _ = fit_catboost_variant(training, evaluation, ["original_cost", "exp_delta_3m"], None)
        second, _, _ = fit_catboost_variant(training, evaluation, ["original_cost", "exp_delta_3m"], None)
        self.assertTrue(np.allclose(first, second, atol=1e-5))

    def test_paired_cluster_bootstrap_behavior(self) -> None:
        cb_rows = [
            {"project_code": "A", "report_month": "2024-06", "actual_label": 0, "predicted_probability": 0.2, "predicted_label": 0},
            {"project_code": "A", "report_month": "2024-07", "actual_label": 1, "predicted_probability": 0.8, "predicted_label": 1},
            {"project_code": "B", "report_month": "2024-06", "actual_label": 0, "predicted_probability": 0.3, "predicted_label": 0},
            {"project_code": "B", "report_month": "2024-07", "actual_label": 1, "predicted_probability": 0.9, "predicted_label": 1},
        ]
        log_rows = [
            {"project_code": "A", "report_month": "2024-06", "actual_label": 0, "predicted_probability": 0.1, "predicted_label": 0},
            {"project_code": "A", "report_month": "2024-07", "actual_label": 1, "predicted_probability": 0.7, "predicted_label": 1},
            {"project_code": "B", "report_month": "2024-06", "actual_label": 0, "predicted_probability": 0.4, "predicted_label": 0},
            {"project_code": "B", "report_month": "2024-07", "actual_label": 1, "predicted_probability": 0.6, "predicted_label": 1},
        ]
        res = paired_cluster_bootstrap(cb_rows, log_rows, iterations=20, seed=42)
        self.assertIn("average_precision", res)
        self.assertIn("delta_point", res["average_precision"])
        self.assertIn("delta_ci_lower", res["average_precision"])
        self.assertIn("delta_ci_upper", res["average_precision"])


class GeneratedCatBoostChallengerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        manifest_path = CATBOOST_DIR / "configuration_manifest.json"
        if not manifest_path.exists():
            raise unittest.SkipTest("CatBoost evaluation artifacts have not been generated yet.")
        cls.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    def test_manifest_enforces_scope_embargo_and_regimes(self) -> None:
        validation = self.manifest["validation"]
        self.assertEqual(validation["evaluated_fold_count"], 17)
        self.assertEqual(validation["embargo_violations"], 0)
        self.assertFalse(validation["random_split_created"])
        self.assertFalse(validation["row_shuffle_performed"])
        self.assertFalse(validation["calibration_fitted"])
        self.assertEqual(validation["other_nonlinear_models_implemented"], [])
        self.assertEqual(self.manifest["skipped_folds"], [])

    def test_generated_artifact_counts_and_iterations(self) -> None:
        generated = self.manifest["generated_files"]
        self.assertIn("candidate_model_comparison.csv", generated)
        self.assertIn("fold_metrics.csv", generated)
        self.assertIn("regime_aggregates.csv", generated)
        self.assertIn("predictions.csv", generated)
        self.assertIn("cluster_bootstrap_cis.csv", generated)
        self.assertIn("paired_logistic_comparison.csv", generated)
        self.assertIn("feature_importance.csv", generated)
        self.assertIn("preprocessing_fit_audit.json", generated)
        self.assertEqual(self.manifest["bootstrap"]["iterations"], 1000)

    def test_every_candidate_uses_identical_accepted_origins(self) -> None:
        with (CATBOOST_DIR / "fold_metrics.csv").open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        by_fold: dict[tuple[str, str], list[dict[str, str]]] = {}
        for row in rows:
            by_fold.setdefault((row["regime"], row["evaluation_month"]), []).append(row)
            self.assertLess(row["maximum_training_label_window_end"], row["evaluation_month"])
        self.assertEqual(len(by_fold), 17)
        for fold_rows in by_fold.values():
            self.assertEqual(len({row["training_rows"] for row in fold_rows}), 1)
            self.assertEqual(len({row["evaluation_rows"] for row in fold_rows}), 1)
            self.assertEqual(len({row["evaluation_positives"] for row in fold_rows}), 1)

    def test_paired_row_alignment_with_logistic_benchmark(self) -> None:
        with (CATBOOST_DIR / "predictions.csv").open("r", encoding="utf-8-sig", newline="") as handle:
            cb_rows = [r for r in csv.DictReader(handle) if r["model"].startswith("catboost_")]
        with (REFINEMENT_DIR / "predictions.csv").open("r", encoding="utf-8-sig", newline="") as handle:
            log_rows = list(csv.DictReader(handle))

        cb_models = sorted({r["model"] for r in cb_rows})
        for regime in ("LEGACY", "MODERN"):
            log_sub = [
                r for r in log_rows
                if r["identifier_regime"] == regime
                and r["model"] == ("logistic_trajectory_only__balanced" if regime == "LEGACY" else "logistic_static_only__unweighted")
            ]
            for model_name in [m for m in cb_models if (m.endswith("__balanced") or m.endswith("__unweighted"))]:
                cb_sub = [r for r in cb_rows if r["identifier_regime"] == regime and r["model"] == model_name]
                if not cb_sub:
                    continue
                self.assertEqual(len(cb_sub), len(log_sub), f"Row count mismatch in {regime} for {model_name}")
                for cb_r, log_r in zip(cb_sub, log_sub):
                    self.assertEqual(cb_r["project_code"], log_r["project_code"])
                    self.assertEqual(cb_r["report_month"], log_r["report_month"])
                    self.assertEqual(cb_r["actual_label"], log_r["actual_label"])

    def test_february_2025_is_retained_and_evaluated(self) -> None:
        legacy_rows = [r for r in self.manifest["aggregate_results"] if r["regime"] == "LEGACY" and r["model"].startswith("catboost_")]
        for row in legacy_rows:
            self.assertIsNotNone(row["feb_2025_ap"])
            self.assertIsNotNone(row["pooled_ap_without_feb_2025"])

    def test_canonical_hashes_remain_unchanged(self) -> None:
        def digest(path: Path) -> str:
            return hashlib.sha256(path.read_bytes()).hexdigest().upper()

        self.assertEqual(digest(ROOT / "data/processed/projects_monthly.csv"), ONGOING_SHA256)
        self.assertEqual(digest(ROOT / "data/processed/projects_completed.csv"), COMPLETED_SHA256)


if __name__ == "__main__":
    unittest.main()
