from __future__ import annotations

import csv
import hashlib
import json
import unittest
from collections import defaultdict
from pathlib import Path

import numpy as np

from src.ml.dataset_builder import COMPLETED_SHA256, ONGOING_SHA256
from src.ml.evaluate_baselines import EVALUATION_ORIGINS, PROHIBITED_FEATURES
from src.ml.explain_locked_models import (
    CONTRIBUTION_SPACE,
    EXPLANATION_PROHIBITED_FEATURES,
    deterministic_ranks,
    fit_logistic_contributions,
)
from src.ml.operational_policy import LOCKED_FEATURES, LOCKED_MODELS


ROOT = Path(__file__).resolve().parents[1]
EXPLANATION_DIR = ROOT / "data/ml/schedule_extension_3m/evaluation/explainability"


def read_csv(name: str) -> list[dict[str, str]]:
    with (EXPLANATION_DIR / name).open(
        "r", encoding="utf-8-sig", newline=""
    ) as handle:
        return list(csv.DictReader(handle))


class ExplainabilityUnitTests(unittest.TestCase):
    def test_logistic_contributions_reconcile_exact_raw_score(self) -> None:
        training = [
            {"sector": "POWER", "original_cost": "10", "target_effective_schedule_ext_3m": "0"},
            {"sector": "POWER", "original_cost": "20", "target_effective_schedule_ext_3m": "0"},
            {"sector": "RAIL", "original_cost": "40", "target_effective_schedule_ext_3m": "1"},
            {"sector": "ROAD", "original_cost": "80", "target_effective_schedule_ext_3m": "1"},
        ]
        scoring = [
            {"sector": "POWER", "original_cost": "15"},
            {"sector": "OTHER", "original_cost": ""},
        ]
        (
            probability,
            raw_score,
            intercept,
            encoded_names,
            source_names,
            encodings,
            contributions,
            _,
        ) = fit_logistic_contributions(training, scoring, ["sector", "original_cost"])
        np.testing.assert_allclose(intercept + contributions.sum(axis=1), raw_score, atol=1e-12)
        np.testing.assert_allclose(1 / (1 + np.exp(-raw_score)), probability, atol=1e-12)
        self.assertEqual(
            encoded_names,
            ["sector__train_frequency", "original_cost__standardized", "original_cost__missing"],
        )
        self.assertEqual(source_names, ["sector", "original_cost", "original_cost"])
        self.assertEqual(encodings, ["TRAIN_FREQUENCY", "TRAIN_STANDARDIZED", "MISSING_INDICATOR"])

    def test_ranks_are_deterministic_and_scoped_to_given_population(self) -> None:
        rows = [{"project_code": code} for code in ("B", "A", "C")]
        ranks, percentiles = deterministic_ranks(np.asarray([0.8, 0.8, 0.2]), rows)
        np.testing.assert_array_equal(ranks, np.asarray([2, 1, 3]))
        np.testing.assert_allclose(percentiles, np.asarray([2 / 3, 1.0, 1 / 3]))


class GeneratedExplainabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            (EXPLANATION_DIR / "explainability_manifest.json").read_text(encoding="utf-8")
        )
        cls.risk = read_csv("risk_rankings.csv")
        cls.global_rows = read_csv("global_feature_contributions.csv")
        cls.stability = read_csv("fold_explanation_stability.csv")

    def test_locked_models_regimes_and_all_accepted_folds_are_used(self) -> None:
        self.assertEqual(self.manifest["locked_models"], LOCKED_MODELS)
        self.assertEqual(self.manifest["locked_features"], LOCKED_FEATURES)
        self.assertEqual(self.manifest["target"], "target_effective_schedule_ext_3m")
        fold_keys = {
            (row["regime"], row["evaluation_month"])
            for row in self.manifest["fold_audits"]
        }
        expected = {
            (regime, month)
            for regime, months in EVALUATION_ORIGINS.items()
            for month in months
        }
        self.assertEqual(fold_keys, expected)
        for row in self.risk:
            self.assertEqual(row["model_identifier"], LOCKED_MODELS[row["regime"]])

    def test_generated_reconciliation_and_scope_audits_pass(self) -> None:
        validation = self.manifest["validation"]
        self.assertEqual(validation["main_embargo_violations"], 0)
        self.assertEqual(validation["explained_fold_count"], 17)
        self.assertEqual(validation["explained_project_month_rows"], 25189)
        self.assertLessEqual(
            validation["maximum_legacy_shap_reconciliation_error"],
            validation["reconciliation_tolerance"],
        )
        self.assertLessEqual(
            validation["maximum_modern_logit_reconciliation_error"],
            validation["reconciliation_tolerance"],
        )
        self.assertLessEqual(
            validation["maximum_locked_score_reconciliation_error"],
            validation["reconciliation_tolerance"],
        )
        self.assertEqual(validation["other_model_families_trained"], [])
        self.assertEqual(validation["secondary_targets_explained"], [])

    def test_ranks_and_percentiles_are_complete_within_month_only(self) -> None:
        groups: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
        for row in self.risk:
            groups[(row["regime"], row["report_month"], row["model_identifier"])].append(row)
        self.assertEqual(len(groups), 17)
        for rows in groups.values():
            population = len(rows)
            self.assertEqual({int(row["month_population"]) for row in rows}, {population})
            self.assertEqual({int(row["risk_rank_within_month"]) for row in rows}, set(range(1, population + 1)))
            for row in rows:
                expected = (population - int(row["risk_rank_within_month"]) + 1) / population
                self.assertAlmostEqual(float(row["risk_percentile_within_month"]), expected, places=14)

    def test_prohibited_features_and_metadata_are_separate(self) -> None:
        validation = self.manifest["validation"]
        self.assertEqual(validation["prohibited_feature_intersection"], [])
        self.assertEqual(validation["metadata_columns_used_as_model_features"], [])
        self.assertEqual(validation["project_code_role"], "METADATA_ONLY")
        self.assertFalse(validation["project_name_used_as_feature"])
        self.assertFalse(validation["completed_project_data_used_as_feature"])
        self.assertEqual(validation["future_target_event_fields_used_as_features"], [])
        global_features = {row["source_feature_name"] for row in self.global_rows}
        self.assertFalse(global_features & EXPLANATION_PROHIBITED_FEATURES)
        self.assertFalse(global_features & PROHIBITED_FEATURES)
        self.assertNotIn("project_code", global_features)

    def test_calibration_is_recorded_separately_from_contributions(self) -> None:
        self.assertFalse(
            self.manifest["validation"]["calibration_parameters_used_as_feature_contributions"]
        )
        active = [row for row in self.risk if row["calibration_active"] == "True"]
        inactive = [row for row in self.risk if row["calibration_active"] == "False"]
        self.assertTrue(active)
        self.assertTrue(inactive)
        self.assertEqual({row["regime"] for row in active}, {"MODERN"})
        self.assertEqual({row["report_month"] for row in active}, {"2026-04"})
        self.assertTrue(all(row["calibrated_probability"] != "" for row in active))
        self.assertTrue(all(row["calibrated_probability"] == "" for row in inactive))
        self.assertEqual(self.manifest["methods"]["contribution_space"], CONTRIBUTION_SPACE)

    def test_complete_vectors_have_deterministic_order_and_approved_features(self) -> None:
        regime_position = {"LEGACY": 0, "MODERN": 1}
        month_position = {
            (regime, month): index
            for regime, months in EVALUATION_ORIGINS.items()
            for index, month in enumerate(months)
        }
        previous = None
        observed_features: dict[str, set[str]] = defaultdict(set)
        row_count = 0
        with (EXPLANATION_DIR / "local_explanations.csv").open(
            "r", encoding="utf-8-sig", newline=""
        ) as handle:
            for row in csv.DictReader(handle):
                key = (
                    regime_position[row["regime"]],
                    month_position[(row["regime"], row["report_month"])],
                    row["project_code"],
                    int(row["contribution_rank"]),
                )
                if previous is not None:
                    self.assertLessEqual(previous, key)
                previous = key
                observed_features[row["regime"]].add(row["source_feature_name"])
                self.assertEqual(row["contribution_space"], CONTRIBUTION_SPACE)
                row_count += 1
        self.assertEqual(observed_features["LEGACY"], set(LOCKED_FEATURES["LEGACY"]))
        self.assertEqual(observed_features["MODERN"], set(LOCKED_FEATURES["MODERN"]))
        self.assertEqual(row_count, 996894)

    def test_global_and_fold_stability_outputs_are_complete(self) -> None:
        self.assertEqual(len(self.global_rows), 61)
        self.assertEqual(len(self.stability), 557)
        for regime in ("LEGACY", "MODERN"):
            ranks = sorted(
                int(row["feature_rank"])
                for row in self.global_rows
                if row["regime"] == regime
            )
            self.assertEqual(ranks, list(range(1, len(LOCKED_FEATURES[regime]) + 1)))
        comparison = self.manifest["legacy_shap_vs_previous_importance"]
        self.assertEqual(comparison["top_10_overlap_count"], 10)
        self.assertGreater(comparison["rank_spearman"], 0.9)
        self.assertIn("legacy_february_2025_top_10", self.manifest["explicit_fold_inspection"])
        self.assertEqual(
            set(self.manifest["explicit_fold_inspection"]["modern_top_10_by_fold"]),
            set(EVALUATION_ORIGINS["MODERN"]),
        )

    def test_generated_artifact_counts_are_frozen(self) -> None:
        generated = self.manifest["generated_files"]
        self.assertEqual(generated["local_explanations.csv"]["rows"], 996894)
        self.assertEqual(generated["top_contributors.csv"]["rows"], 250570)
        self.assertEqual(generated["global_feature_contributions.csv"]["rows"], 61)
        self.assertEqual(generated["fold_explanation_stability.csv"]["rows"], 557)
        self.assertEqual(generated["risk_rankings.csv"]["rows"], 25189)

    def test_canonical_hashes_remain_unchanged(self) -> None:
        def digest(path: Path) -> str:
            return hashlib.sha256(path.read_bytes()).hexdigest().upper()

        self.assertEqual(digest(ROOT / "data/processed/projects_monthly.csv"), ONGOING_SHA256)
        self.assertEqual(digest(ROOT / "data/processed/projects_completed.csv"), COMPLETED_SHA256)


if __name__ == "__main__":
    unittest.main()
