from __future__ import annotations

import csv
import hashlib
import json
import unittest
from pathlib import Path

from src.ml.dataset_builder import COMPLETED_SHA256, ONGOING_SHA256
from src.ml.robustness_audit import (
    FEATURE_FAMILIES,
    FULL_V1_FEATURES,
    _bootstrap_metric_samples,
)


ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = ROOT / "data/ml/schedule_extension_3m"
EVALUATION_DIR = DATASET_DIR / "evaluation"
ROBUSTNESS_DIR = EVALUATION_DIR / "robustness"


class RobustnessAuditUnitTests(unittest.TestCase):
    def test_full_feature_family_exactly_reproduces_manifest_order(self) -> None:
        manifest = json.loads((DATASET_DIR / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(FULL_V1_FEATURES, manifest["feature_columns"])
        self.assertEqual(FEATURE_FAMILIES["full_v1"], manifest["feature_columns"])
        self.assertTrue(
            set(FEATURE_FAMILIES["numeric_only_full_v1"]).isdisjoint(
                {"sector", "agency", "state"}
            )
        )

    def test_project_cluster_bootstrap_is_deterministic(self) -> None:
        rows = [
            {
                "project_code": code,
                "actual_label": actual,
                "predicted_probability_or_score": score,
                "predicted_label": int(score >= 0.5),
            }
            for code, actual, score in (
                ("A", 0, 0.1), ("A", 1, 0.7), ("B", 0, 0.2),
                ("B", 0, 0.4), ("C", 1, 0.8), ("C", 1, 0.9),
            )
        ]
        first = _bootstrap_metric_samples(rows, "project_code", 30, seed=7)
        second = _bootstrap_metric_samples(rows, "project_code", 30, seed=7)
        self.assertEqual(first, second)


class GeneratedRobustnessAuditRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = json.loads(
            (ROBUSTNESS_DIR / "robustness_manifest.json").read_text(encoding="utf-8")
        )

    def test_manifest_reconciles_accepted_full_v1_evaluation(self) -> None:
        self.assertFalse(self.manifest["target_labels_rebuilt"])
        self.assertFalse(self.manifest["target_defect_found"])
        self.assertEqual(self.manifest["advanced_models_implemented"], [])
        self.assertLessEqual(
            self.manifest["full_v1_score_reconciliation_max_absolute_difference"], 1e-12
        )
        self.assertEqual(self.manifest["bootstrap"]["iterations"], 1000)

    def test_aggregation_views_are_explicit_and_brier_reconciles(self) -> None:
        with (ROBUSTNESS_DIR / "aggregation_comparison.csv").open(
            "r", encoding="utf-8-sig", newline=""
        ) as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 24)
        brier = [row for row in rows if row["metric"] == "brier_score"]
        for row in brier:
            self.assertAlmostEqual(
                float(row["micro_concatenated_oof"]),
                float(row["evaluation_row_weighted_fold_mean"]),
            )
        logistic_ap = next(
            row for row in rows
            if row["regime"] == "LEGACY"
            and row["model"] == "logistic_l2_unweighted"
            and row["metric"] == "average_precision"
        )
        self.assertNotAlmostEqual(
            float(logistic_ap["micro_concatenated_oof"]),
            float(logistic_ap["macro_fold_mean"]),
        )

    def test_ablation_uses_identical_regime_origins_and_row_counts(self) -> None:
        with (ROBUSTNESS_DIR / "feature_family_fold_metrics.csv").open(
            "r", encoding="utf-8-sig", newline=""
        ) as handle:
            rows = list(csv.DictReader(handle))
        by_fold: dict[tuple[str, str], list[dict[str, str]]] = {}
        for row in rows:
            by_fold.setdefault((row["regime"], row["evaluation_month"]), []).append(row)
        self.assertEqual(len(by_fold), 17)
        for fold_rows in by_fold.values():
            self.assertEqual({row["feature_family"] for row in fold_rows}, set(FEATURE_FAMILIES))
            self.assertEqual(len({row["training_rows"] for row in fold_rows}), 1)
            self.assertEqual(len({row["evaluation_rows"] for row in fold_rows}), 1)
            self.assertEqual(len({row["positives"] for row in fold_rows}), 1)

    def test_confidence_intervals_use_cluster_and_month_resampling(self) -> None:
        with (ROBUSTNESS_DIR / "cluster_and_block_confidence_intervals.csv").open(
            "r", encoding="utf-8-sig", newline=""
        ) as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(
            {row["method"] for row in rows},
            {"PROJECT_CLUSTER_BOOTSTRAP", "EVALUATION_MONTH_BLOCK_BOOTSTRAP"},
        )
        self.assertTrue(all(int(row["iterations"]) == 1000 for row in rows))
        self.assertTrue(all(float(row["ci_lower"]) <= float(row["ci_upper"]) for row in rows))

    def test_canonical_hashes_remain_unchanged(self) -> None:
        def digest(path: Path) -> str:
            return hashlib.sha256(path.read_bytes()).hexdigest().upper()

        self.assertEqual(digest(ROOT / "data/processed/projects_monthly.csv"), ONGOING_SHA256)
        self.assertEqual(digest(ROOT / "data/processed/projects_completed.csv"), COMPLETED_SHA256)


if __name__ == "__main__":
    unittest.main()
