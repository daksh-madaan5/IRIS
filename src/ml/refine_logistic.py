"""Regime-specific Logistic refinement for the H=3 schedule-extension target.

This module is intentionally limited to transparent, manually declared feature
sets and L2 Logistic Regression.  It reuses the accepted walk-forward origins,
strict ``T + 3 < E`` embargo, and fold-local preprocessing.  It does not tune a
test-fold threshold, fit calibration, pool identifier regimes, or train any
nonlinear model.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import scipy
import sklearn
from sklearn.linear_model import LogisticRegression

from src.ml.dataset_builder import COMPLETED_SHA256, HORIZON, ONGOING_SHA256, sha256
from src.ml.evaluate_baselines import (
    BOOTSTRAP_ITERATIONS,
    EVALUATION_ORIGINS,
    FoldPreprocessor,
    PROHIBITED_FEATURES,
    RANDOM_SEED,
    TARGET,
    _point_metrics,
    lagged_rule_predictions,
    select_training_rows,
)
from src.ml.robustness_audit import FULL_V1_FEATURES, STATIC_AT_T_FEATURES, TRAJECTORY_FEATURES


LEGACY_MINIMAL_STATIC_NUMERIC = [
    "project_age_months",
    "months_to_effective_schedule",
    "schedule_revision_lag_months",
    "expenditure_to_original_cost_ratio",
    "revised_date_is_present",
]

MODERN_SELECTED_TRAJECTORY = [
    "exp_delta_3m",
    "past_progress_delta_3m",
    "n_prior_schedule_extensions",
    "observed_tenure_months",
]

REGIME_FEATURE_SETS = {
    "LEGACY": {
        "trajectory_only": list(TRAJECTORY_FEATURES),
        "trajectory_plus_minimal_static": list(TRAJECTORY_FEATURES)
        + LEGACY_MINIMAL_STATIC_NUMERIC,
        "full_v1": list(FULL_V1_FEATURES),
    },
    "MODERN": {
        "static_only": list(STATIC_AT_T_FEATURES),
        "static_plus_selected_trajectory": list(STATIC_AT_T_FEATURES)
        + MODERN_SELECTED_TRAJECTORY,
        "full_v1": list(FULL_V1_FEATURES),
    },
}

FEATURE_SET_RATIONALE = {
    "LEGACY": {
        "trajectory_only": "Accepted trajectory family; primary Legacy candidate from robustness.",
        "trajectory_plus_minimal_static": (
            "Adds only project age, current effective schedule distance, revision magnitude, "
            "expenditure/cost scale, and revised-date presence; no categorical fields."
        ),
        "full_v1": "Accepted original 36-input baseline for direct reconciliation.",
    },
    "MODERN": {
        "static_only": "Accepted static-at-T family; primary Modern candidate from robustness.",
        "static_plus_selected_trajectory": (
            "Adds only medium-horizon expenditure/progress movement, prior schedule-extension "
            "count, and observed tenure; it does not carry the full Legacy trajectory family."
        ),
        "full_v1": "Accepted original 36-input baseline for direct reconciliation.",
    },
}

WEIGHT_VARIANTS = {"unweighted": None, "balanced": "balanced"}
REFERENCE_MODELS = ("prevalence", "lagged_rule_latest_valid_transition")
CI_METRICS = (
    "average_precision",
    "roc_auc",
    "brier_score",
    "ece_10bin",
    "precision",
    "recall",
    "f1",
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _serialise(value: Any) -> Any:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    if isinstance(value, (float, np.floating)):
        return format(float(value), ".15g")
    return value


def _write_csv(path: Path, fields: Sequence[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _serialise(row.get(field)) for field in fields})


def candidate_model_name(feature_set: str, weighting: str) -> str:
    return f"logistic_{feature_set}__{weighting}"


def fit_logistic_variant(
    training_rows: Sequence[dict[str, str]],
    evaluation_rows: Sequence[dict[str, str]],
    feature_columns: Sequence[str],
    class_weight: str | None,
) -> tuple[np.ndarray, FoldPreprocessor, LogisticRegression]:
    """Fit one fixed L2 variant with preprocessing learned only from training."""
    processor = FoldPreprocessor(feature_columns).fit(training_rows)
    x_train = processor.transform(training_rows)
    x_eval = processor.transform(evaluation_rows)
    y_train = np.asarray([int(row[TARGET]) for row in training_rows], dtype=int)
    model = LogisticRegression(
        l1_ratio=0.0,
        C=1.0,
        solver="lbfgs",
        max_iter=2000,
        class_weight=class_weight,
        random_state=RANDOM_SEED,
    )
    model.fit(x_train, y_train)
    return model.predict_proba(x_eval)[:, 1], processor, model


def project_cluster_intervals(
    rows: Sequence[dict[str, Any]], iterations: int, seed: int
) -> dict[str, tuple[float | None, float | None]]:
    """Resample whole project clusters and retain all OOF rows per sampled draw."""
    grouped: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        grouped[str(row["project_code"])].append(index)
    clusters = sorted(grouped)
    if not clusters or iterations <= 0:
        return {metric: (None, None) for metric in CI_METRICS}
    y_all = np.asarray([int(row["actual_label"]) for row in rows], dtype=int)
    score_all = np.asarray([float(row["predicted_probability"]) for row in rows], dtype=float)
    predicted_all = np.asarray([int(row["predicted_label"]) for row in rows], dtype=int)
    rng = np.random.default_rng(seed)
    values: dict[str, list[float]] = defaultdict(list)
    for _ in range(iterations):
        selected = rng.choice(clusters, size=len(clusters), replace=True)
        indices = np.concatenate([np.asarray(grouped[str(cluster)], dtype=int) for cluster in selected])
        point = _point_metrics(y_all[indices], score_all[indices], predicted_all[indices])
        for metric in CI_METRICS:
            if point[metric] is not None:
                values[metric].append(float(point[metric]))
    return {
        metric: (
            float(np.quantile(values[metric], 0.025)),
            float(np.quantile(values[metric], 0.975)),
        )
        if values[metric]
        else (None, None)
        for metric in CI_METRICS
    }


def _fold_record(
    regime: str,
    month: str,
    model: str,
    feature_set: str,
    weighting: str,
    training: Sequence[dict[str, str]],
    evaluation: Sequence[dict[str, str]],
    y: np.ndarray,
    score: np.ndarray,
    predicted: np.ndarray,
    input_feature_count: int,
    matrix_column_count: int,
) -> dict[str, Any]:
    return {
        "regime": regime,
        "evaluation_month": month,
        "model": model,
        "feature_set": feature_set,
        "weighting": weighting,
        "training_rows": len(training),
        "training_month_min": min(row["report_month"] for row in training),
        "training_month_max": max(row["report_month"] for row in training),
        "maximum_training_label_window_end": max(
            row["target_window_end_month"] for row in training
        ),
        "training_positives": sum(int(row[TARGET]) for row in training),
        "training_positive_rate": np.mean([int(row[TARGET]) for row in training]),
        "evaluation_rows": len(evaluation),
        "evaluation_positives": int(y.sum()),
        "evaluation_positive_rate": float(y.mean()),
        "predicted_positives": int(predicted.sum()),
        "decision_threshold": 0.5,
        "input_feature_count": input_feature_count,
        "matrix_column_count": matrix_column_count,
        **_point_metrics(y, score, predicted),
    }


def _prediction_rows(
    evaluation: Sequence[dict[str, str]],
    model: str,
    feature_set: str,
    weighting: str,
    score: np.ndarray,
    predicted: np.ndarray,
) -> list[dict[str, Any]]:
    return [
        {
            "project_code": row["project_code"],
            "report_month": row["report_month"],
            "identifier_regime": row["identifier_regime"],
            "continuous_segment": row["continuous_segment"],
            "model": model,
            "feature_set": feature_set,
            "weighting": weighting,
            "actual_label": int(row[TARGET]),
            "predicted_probability": float(score[index]),
            "predicted_label": int(predicted[index]),
        }
        for index, row in enumerate(evaluation)
    ]


def _aggregate_records(
    fold_metrics: Sequence[dict[str, Any]], predictions: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    result = []
    model_keys = sorted(
        {(row["identifier_regime"], row["model"]) for row in predictions}
    )
    for regime, model in model_keys:
        selected = [
            row
            for row in predictions
            if row["identifier_regime"] == regime and row["model"] == model
        ]
        folds = [row for row in fold_metrics if row["regime"] == regime and row["model"] == model]
        y = np.asarray([int(row["actual_label"]) for row in selected], dtype=int)
        score = np.asarray([float(row["predicted_probability"]) for row in selected], dtype=float)
        predicted = np.asarray([int(row["predicted_label"]) for row in selected], dtype=int)
        ap_values = np.asarray([float(row["average_precision"]) for row in folds], dtype=float)
        record = {
            "regime": regime,
            "model": model,
            "feature_set": selected[0]["feature_set"],
            "weighting": selected[0]["weighting"],
            "evaluation_folds": len(folds),
            "evaluation_rows": len(selected),
            "positives": int(y.sum()),
            "positive_rate": float(y.mean()),
            "predicted_positives": int(predicted.sum()),
            "decision_threshold": 0.5,
            **_point_metrics(y, score, predicted),
            "fold_ap_mean": float(ap_values.mean()),
            "fold_ap_std": float(ap_values.std()),
            "fold_ap_min": float(ap_values.min()),
            "fold_ap_max": float(ap_values.max()),
            "feb_2025_ap": None,
            "pooled_ap_without_feb_2025": None,
        }
        if regime == "LEGACY":
            feb_fold = next(row for row in folds if row["evaluation_month"] == "2025-02")
            without_feb = [row for row in selected if row["report_month"] != "2025-02"]
            y_without = np.asarray([int(row["actual_label"]) for row in without_feb], dtype=int)
            score_without = np.asarray(
                [float(row["predicted_probability"]) for row in without_feb], dtype=float
            )
            record["feb_2025_ap"] = feb_fold["average_precision"]
            record["pooled_ap_without_feb_2025"] = float(
                sklearn.metrics.average_precision_score(y_without, score_without)
            )
        result.append(record)
    return result


def run(root: Path, bootstrap_iterations: int = BOOTSTRAP_ITERATIONS) -> dict[str, Any]:
    root = root.resolve()
    dataset_dir = root / "data/ml/schedule_extension_3m"
    evaluation_dir = dataset_dir / "evaluation"
    output_dir = evaluation_dir / "refinement"
    output_dir.mkdir(parents=True, exist_ok=True)

    dataset_manifest_path = dataset_dir / "manifest.json"
    baseline_manifest_path = evaluation_dir / "evaluation_manifest.json"
    robustness_manifest_path = evaluation_dir / "robustness/robustness_manifest.json"
    dataset_manifest = json.loads(dataset_manifest_path.read_text(encoding="utf-8"))
    baseline_manifest = json.loads(baseline_manifest_path.read_text(encoding="utf-8"))
    manifest_features = list(dataset_manifest["feature_columns"])
    if dataset_manifest["target"] != TARGET:
        raise RuntimeError(f"Unexpected target: {dataset_manifest['target']}")
    if baseline_manifest["evaluated_origins"] != EVALUATION_ORIGINS:
        raise RuntimeError("Accepted evaluation origins differ from refinement origins")

    declared_features = {
        feature for regime_sets in REGIME_FEATURE_SETS.values() for features in regime_sets.values()
        for feature in features
    }
    missing = sorted(declared_features - set(manifest_features))
    leakage = sorted(declared_features & PROHIBITED_FEATURES)
    if missing or leakage:
        raise RuntimeError(f"Invalid refinement features; missing={missing}, leakage={leakage}")
    if REGIME_FEATURE_SETS["LEGACY"]["full_v1"] != manifest_features:
        raise RuntimeError("Legacy full-v1 no longer matches the dataset manifest")
    if REGIME_FEATURE_SETS["MODERN"]["full_v1"] != manifest_features:
        raise RuntimeError("Modern full-v1 no longer matches the dataset manifest")

    canonical_hashes = {
        "projects_monthly.csv": sha256(root / "data/processed/projects_monthly.csv"),
        "projects_completed.csv": sha256(root / "data/processed/projects_completed.csv"),
    }
    expected_hashes = {
        "projects_monthly.csv": ONGOING_SHA256,
        "projects_completed.csv": COMPLETED_SHA256,
    }
    if canonical_hashes != expected_hashes:
        raise RuntimeError(f"Canonical hash mismatch; refusing refinement: {canonical_hashes}")

    rows_by_regime = {
        "LEGACY": _read_csv(dataset_dir / "eligible_legacy.csv"),
        "MODERN": _read_csv(dataset_dir / "eligible_modern.csv"),
    }
    accepted_prediction_rows = _read_csv(evaluation_dir / "predictions.csv")
    accepted_full_scores = {
        (row["identifier_regime"], row["project_code"], row["report_month"]): float(
            row["predicted_probability_or_score"]
        )
        for row in accepted_prediction_rows
        if row["model"] == "logistic_l2_unweighted"
    }

    fold_metrics: list[dict[str, Any]] = []
    predictions: list[dict[str, Any]] = []
    preprocessing_audit: list[dict[str, Any]] = []
    reconciliation_differences: list[float] = []
    skipped_folds: list[dict[str, Any]] = []

    for regime in ("LEGACY", "MODERN"):
        regime_rows = rows_by_regime[regime]
        if any(row["identifier_regime"] != regime for row in regime_rows):
            raise RuntimeError(f"Regime contamination in {regime}")
        for evaluation_month in EVALUATION_ORIGINS[regime]:
            evaluation = [row for row in regime_rows if row["report_month"] == evaluation_month]
            training = select_training_rows(regime_rows, regime, evaluation_month)
            reasons = []
            if not evaluation:
                reasons.append("ZERO_ELIGIBLE_EVALUATION_ROWS")
            if not training:
                reasons.append("ZERO_ELIGIBLE_TRAINING_ROWS")
            if training and len({row[TARGET] for row in training}) < 2:
                reasons.append("TRAINING_TARGET_HAS_ONE_CLASS")
            if evaluation and len({row[TARGET] for row in evaluation}) < 2:
                reasons.append("EVALUATION_TARGET_HAS_ONE_CLASS")
            if reasons:
                skipped_folds.append(
                    {"regime": regime, "evaluation_month": evaluation_month, "reason": "|".join(reasons)}
                )
                continue
            if max(row["target_window_end_month"] for row in training) >= evaluation_month:
                raise RuntimeError(f"Strict embargo violation in {regime} {evaluation_month}")

            y_train = np.asarray([int(row[TARGET]) for row in training], dtype=int)
            y_eval = np.asarray([int(row[TARGET]) for row in evaluation], dtype=int)
            prevalence_score = np.full(len(evaluation), float(y_train.mean()), dtype=float)
            lagged_prediction, _covered = lagged_rule_predictions(evaluation, regime_rows)
            references = {
                "prevalence": prevalence_score,
                "lagged_rule_latest_valid_transition": lagged_prediction.astype(float),
            }
            for model, score in references.items():
                predicted = (score >= 0.5).astype(int)
                fold_metrics.append(
                    _fold_record(
                        regime, evaluation_month, model, "REFERENCE", "REFERENCE", training,
                        evaluation, y_eval, score, predicted, 0, 0,
                    )
                )
                predictions.extend(
                    _prediction_rows(evaluation, model, "REFERENCE", "REFERENCE", score, predicted)
                )

            for feature_set, features in REGIME_FEATURE_SETS[regime].items():
                for weighting, class_weight in WEIGHT_VARIANTS.items():
                    model_name = candidate_model_name(feature_set, weighting)
                    score, processor, _model = fit_logistic_variant(
                        training, evaluation, features, class_weight
                    )
                    predicted = (score >= 0.5).astype(int)
                    fold_metrics.append(
                        _fold_record(
                            regime, evaluation_month, model_name, feature_set, weighting,
                            training, evaluation, y_eval, score, predicted, len(features),
                            len(processor.output_columns),
                        )
                    )
                    predictions.extend(
                        _prediction_rows(
                            evaluation, model_name, feature_set, weighting, score, predicted
                        )
                    )
                    preprocessing_audit.append(
                        {
                            "regime": regime,
                            "evaluation_month": evaluation_month,
                            "model": model_name,
                            "feature_set": feature_set,
                            "weighting": weighting,
                            "training_month_min": min(row["report_month"] for row in training),
                            "training_month_max": max(row["report_month"] for row in training),
                            "maximum_training_label_window_end": max(
                                row["target_window_end_month"] for row in training
                            ),
                            **processor.audit(evaluation),
                        }
                    )
                    if feature_set == "full_v1" and weighting == "unweighted":
                        for index, row in enumerate(evaluation):
                            key = (regime, row["project_code"], row["report_month"])
                            reconciliation_differences.append(abs(float(score[index]) - accepted_full_scores[key]))

    aggregates = _aggregate_records(fold_metrics, predictions)
    aggregate_index = {(row["regime"], row["model"]): row for row in aggregates}
    comparison = []
    winners = {}
    for regime in ("LEGACY", "MODERN"):
        prevalence = aggregate_index[(regime, "prevalence")]
        lagged = aggregate_index[(regime, "lagged_rule_latest_valid_transition")]
        original = aggregate_index[(regime, candidate_model_name("full_v1", "unweighted"))]
        candidates = [
            row for row in aggregates if row["regime"] == regime and row["feature_set"] != "REFERENCE"
        ]
        winner = max(candidates, key=lambda row: row["average_precision"])
        winners[regime] = {
            "model": winner["model"],
            "feature_set": winner["feature_set"],
            "weighting": winner["weighting"],
            "average_precision": winner["average_precision"],
        }
        for row in sorted(candidates, key=lambda item: item["average_precision"], reverse=True):
            comparison.append(
                {
                    **row,
                    "ap_rank_within_regime": 1 + sum(
                        other["average_precision"] > row["average_precision"] for other in candidates
                    ),
                    "is_regime_winner": row["model"] == winner["model"],
                    "prevalence_average_precision": prevalence["average_precision"],
                    "ap_delta_vs_prevalence": row["average_precision"] - prevalence["average_precision"],
                    "lagged_rule_average_precision": lagged["average_precision"],
                    "ap_delta_vs_lagged_rule": row["average_precision"] - lagged["average_precision"],
                    "original_full_v1_average_precision": original["average_precision"],
                    "ap_delta_vs_original_full_v1": row["average_precision"] - original["average_precision"],
                }
            )

    ci_rows = []
    for aggregate in aggregates:
        selected = [
            row for row in predictions
            if row["identifier_regime"] == aggregate["regime"] and row["model"] == aggregate["model"]
        ]
        seed_text = f"{RANDOM_SEED}:{aggregate['regime']}:{aggregate['model']}:PROJECT_CLUSTER"
        seed = int.from_bytes(hashlib.sha256(seed_text.encode()).digest()[:8], "big")
        intervals = project_cluster_intervals(selected, bootstrap_iterations, seed)
        for metric in CI_METRICS:
            ci_rows.append(
                {
                    "regime": aggregate["regime"],
                    "model": aggregate["model"],
                    "feature_set": aggregate["feature_set"],
                    "weighting": aggregate["weighting"],
                    "method": "PROJECT_CLUSTER_BOOTSTRAP",
                    "cluster_count": len({row["project_code"] for row in selected}),
                    "iterations": bootstrap_iterations,
                    "metric": metric,
                    "point_estimate": aggregate[metric],
                    "ci_lower": intervals[metric][0],
                    "ci_upper": intervals[metric][1],
                }
            )

    metric_fields = list(_point_metrics(np.asarray([0, 1]), np.asarray([0.1, 0.9]), np.asarray([0, 1])))
    fold_fields = [
        "regime", "evaluation_month", "model", "feature_set", "weighting", "training_rows",
        "training_month_min", "training_month_max", "maximum_training_label_window_end",
        "training_positives", "training_positive_rate", "evaluation_rows", "evaluation_positives",
        "evaluation_positive_rate", "predicted_positives", "decision_threshold",
        "input_feature_count", "matrix_column_count", *metric_fields,
    ]
    aggregate_fields = [
        "regime", "model", "feature_set", "weighting", "evaluation_folds", "evaluation_rows",
        "positives", "positive_rate", "predicted_positives", "decision_threshold", *metric_fields,
        "fold_ap_mean", "fold_ap_std", "fold_ap_min", "fold_ap_max", "feb_2025_ap",
        "pooled_ap_without_feb_2025",
    ]
    comparison_fields = aggregate_fields + [
        "ap_rank_within_regime", "is_regime_winner", "prevalence_average_precision",
        "ap_delta_vs_prevalence", "lagged_rule_average_precision", "ap_delta_vs_lagged_rule",
        "original_full_v1_average_precision", "ap_delta_vs_original_full_v1",
    ]
    prediction_fields = [
        "project_code", "report_month", "identifier_regime", "continuous_segment", "model",
        "feature_set", "weighting", "actual_label", "predicted_probability", "predicted_label",
    ]
    ci_fields = [
        "regime", "model", "feature_set", "weighting", "method", "cluster_count",
        "iterations", "metric", "point_estimate", "ci_lower", "ci_upper",
    ]
    output_paths = {
        "candidate_model_comparison.csv": output_dir / "candidate_model_comparison.csv",
        "fold_metrics.csv": output_dir / "fold_metrics.csv",
        "regime_aggregates.csv": output_dir / "regime_aggregates.csv",
        "predictions.csv": output_dir / "predictions.csv",
        "feature_lists.json": output_dir / "feature_lists.json",
        "preprocessing_fit_audit.json": output_dir / "preprocessing_fit_audit.json",
        "cluster_bootstrap_cis.csv": output_dir / "cluster_bootstrap_cis.csv",
    }
    _write_csv(output_paths["candidate_model_comparison.csv"], comparison_fields, comparison)
    _write_csv(output_paths["fold_metrics.csv"], fold_fields, fold_metrics)
    _write_csv(output_paths["regime_aggregates.csv"], aggregate_fields, aggregates)
    _write_csv(output_paths["predictions.csv"], prediction_fields, predictions)
    _write_csv(output_paths["cluster_bootstrap_cis.csv"], ci_fields, ci_rows)
    output_paths["feature_lists.json"].write_text(
        json.dumps(
            {
                regime: {
                    name: {"features": features, "rationale": FEATURE_SET_RATIONALE[regime][name]}
                    for name, features in sets.items()
                }
                for regime, sets in REGIME_FEATURE_SETS.items()
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    output_paths["preprocessing_fit_audit.json"].write_text(
        json.dumps(preprocessing_audit, indent=2) + "\n", encoding="utf-8"
    )

    maximum_reconciliation_difference = max(reconciliation_differences, default=math.inf)
    if maximum_reconciliation_difference > 1e-12:
        raise RuntimeError(
            f"Refined full-v1 unweighted scores do not reconcile: {maximum_reconciliation_difference}"
        )
    generated_files = {}
    for name, path in output_paths.items():
        entry: dict[str, Any] = {"sha256": sha256(path)}
        if path.suffix == ".csv":
            entry["rows"] = len(_read_csv(path))
        generated_files[name] = entry

    balancing_effects = {
        regime: {
            feature_set: {
                "unweighted_average_precision": aggregate_index[
                    (regime, candidate_model_name(feature_set, "unweighted"))
                ]["average_precision"],
                "balanced_average_precision": aggregate_index[
                    (regime, candidate_model_name(feature_set, "balanced"))
                ]["average_precision"],
                "balanced_minus_unweighted_average_precision": aggregate_index[
                    (regime, candidate_model_name(feature_set, "balanced"))
                ]["average_precision"]
                - aggregate_index[
                    (regime, candidate_model_name(feature_set, "unweighted"))
                ]["average_precision"],
            }
            for feature_set in REGIME_FEATURE_SETS[regime]
        }
        for regime in ("LEGACY", "MODERN")
    }
    modern_original = aggregate_index[("MODERN", candidate_model_name("full_v1", "unweighted"))]
    modern_winner = aggregate_index[("MODERN", winners["MODERN"]["model"])]
    modern_winner_folds = [
        row
        for row in fold_metrics
        if row["regime"] == "MODERN" and row["model"] == winners["MODERN"]["model"]
    ]
    calibration_findings = {
        "calibration_fitted": False,
        "modern_original_full_v1_predicted_minus_observed": (
            modern_original["mean_predicted_probability"] - modern_original["positive_rate"]
        ),
        "modern_winner_predicted_minus_observed": (
            modern_winner["mean_predicted_probability"] - modern_winner["positive_rate"]
        ),
        "modern_underprediction_absolute_gap_reduction": abs(
            modern_original["mean_predicted_probability"] - modern_original["positive_rate"]
        )
        - abs(modern_winner["mean_predicted_probability"] - modern_winner["positive_rate"]),
        "modern_winner_underpredicting_fold_count": sum(
            row["mean_predicted_probability"] < row["evaluation_positive_rate"]
            for row in modern_winner_folds
        ),
        "modern_winner_evaluated_fold_count": len(modern_winner_folds),
    }

    configuration = {
        "evaluation_name": "schedule_extension_3m_regime_logistic_refinement_v1",
        "runtime_versions": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "scikit_learn": sklearn.__version__,
        },
        "target": TARGET,
        "horizon_months": HORIZON,
        "source_manifests": {
            "dataset_manifest_sha256": sha256(dataset_manifest_path),
            "baseline_evaluation_manifest_sha256": sha256(baseline_manifest_path),
            "robustness_manifest_sha256": sha256(robustness_manifest_path),
        },
        "canonical_hashes": canonical_hashes,
        "evaluation_origins": EVALUATION_ORIGINS,
        "feature_sets": REGIME_FEATURE_SETS,
        "feature_set_rationale": FEATURE_SET_RATIONALE,
        "weight_variants": WEIGHT_VARIANTS,
        "logistic_regression": {
            "penalty": "l2 via l1_ratio=0.0",
            "C": 1.0,
            "solver": "lbfgs",
            "max_iter": 2000,
            "random_state": RANDOM_SEED,
            "decision_threshold": 0.5,
            "threshold_policy": "Fixed descriptive threshold only; no test-fold tuning.",
        },
        "preprocessing": (
            "Fold-local training frequency encoding and numeric mean/std scaling; missing values "
            "map to standardized zero only in matrix space with explicit input missing bits."
        ),
        "embargo": "T_train + 3 calendar months < evaluation origin E (strict).",
        "selection_criterion": "Concatenated out-of-fold average precision / PR-AUC within regime.",
        "calibration": "No calibration fitted; natural mean-score/observed-rate behavior reported.",
        "bootstrap": {
            "method": "PROJECT_CLUSTER_BOOTSTRAP",
            "iterations": bootstrap_iterations,
            "confidence": 0.95,
            "semantics": "Sample project_code clusters with replacement and retain all OOF rows per draw.",
        },
        "winners": winners,
        "class_weight_effects": balancing_effects,
        "calibration_findings": calibration_findings,
        "skipped_folds": skipped_folds,
        "validation": {
            "prohibited_feature_intersection": leakage,
            "declared_features_missing_from_manifest": missing,
            "evaluated_fold_count": len({(row["regime"], row["evaluation_month"]) for row in fold_metrics}),
            "embargo_violations": 0,
            "random_split_created": False,
            "row_shuffle_performed": False,
            "calibration_fitted": False,
            "nonlinear_models_implemented": [],
            "accepted_full_v1_score_reconciliation_max_absolute_difference": maximum_reconciliation_difference,
            "canonical_hashes_unchanged": canonical_hashes == expected_hashes,
        },
        "generated_files": generated_files,
        "aggregate_results": aggregates,
    }
    manifest_path = output_dir / "configuration_manifest.json"
    manifest_path.write_text(json.dumps(configuration, indent=2) + "\n", encoding="utf-8")
    return configuration


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--bootstrap-iterations", type=int, default=BOOTSTRAP_ITERATIONS)
    args = parser.parse_args()
    result = run(args.root, args.bootstrap_iterations)
    print(json.dumps(result["winners"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
