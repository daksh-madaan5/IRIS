"""Focused robustness diagnostics for the accepted H=3 baseline evaluation.

This module does not rebuild labels or alter canonical/generated input datasets.
It reuses the exact approved walk-forward folds and Logistic configuration, writes
only under ``evaluation/robustness``, and implements no advanced model family.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
from sklearn.metrics import precision_recall_curve

from src.ml.dataset_builder import COMPLETED_SHA256, ONGOING_SHA256, sha256
from src.ml.evaluate_baselines import (
    BOOTSTRAP_ITERATIONS,
    EVALUATION_ORIGINS,
    MODEL_ORDER,
    RANDOM_SEED,
    TARGET,
    _point_metrics,
    calibration_rows,
    expected_calibration_error,
    fit_logistic_scores,
    select_training_rows,
)


STATIC_AT_T_FEATURES = [
    "sector",
    "agency",
    "state",
    "original_cost",
    "cumulative_expenditure_t",
    "revised_cost_t",
    "physical_progress_t",
    "project_age_months",
    "months_to_original_schedule",
    "months_to_effective_schedule",
    "schedule_revision_lag_months",
    "schedule_has_been_revised",
    "months_since_start",
    "expenditure_to_original_cost_ratio",
    "revised_to_original_cost_ratio",
    "cost_has_been_revised",
    "state_is_missing",
    "approval_date_is_missing",
    "original_completion_date_is_missing",
    "revised_cost_is_present",
    "revised_date_is_present",
    "physical_progress_is_present",
    "physical_progress_supported",
    "start_date_is_present",
    "start_date_supported",
]

TRAJECTORY_FEATURES = [
    "exp_delta_1m",
    "exp_delta_3m",
    "past_exp_stagnant_3m",
    "past_progress_delta_3m",
    "past_progress_stagnant_3m",
    "n_prior_schedule_extensions",
    "n_prior_cost_revisions",
    "observed_tenure_months",
    "exp_delta_1m_is_supported",
    "exp_delta_3m_is_supported",
    "progress_delta_3m_is_supported",
]

FULL_V1_FEATURES = [
    "sector",
    "agency",
    "state",
    "original_cost",
    "cumulative_expenditure_t",
    "revised_cost_t",
    "physical_progress_t",
    "project_age_months",
    "months_to_original_schedule",
    "months_to_effective_schedule",
    "schedule_revision_lag_months",
    "schedule_has_been_revised",
    "months_since_start",
    "expenditure_to_original_cost_ratio",
    "revised_to_original_cost_ratio",
    "cost_has_been_revised",
    "exp_delta_1m",
    "exp_delta_3m",
    "past_exp_stagnant_3m",
    "past_progress_delta_3m",
    "past_progress_stagnant_3m",
    "n_prior_schedule_extensions",
    "n_prior_cost_revisions",
    "observed_tenure_months",
    "state_is_missing",
    "approval_date_is_missing",
    "original_completion_date_is_missing",
    "revised_cost_is_present",
    "revised_date_is_present",
    "physical_progress_is_present",
    "physical_progress_supported",
    "start_date_is_present",
    "start_date_supported",
    "exp_delta_1m_is_supported",
    "exp_delta_3m_is_supported",
    "progress_delta_3m_is_supported",
]

FEATURE_FAMILIES = {
    "static_at_t": STATIC_AT_T_FEATURES,
    "trajectory_only": TRAJECTORY_FEATURES,
    "full_v1": FULL_V1_FEATURES,
    "numeric_only_full_v1": [
        name for name in FULL_V1_FEATURES
        if name not in {"sector", "agency", "state"}
    ],
}

MAJOR_NUMERIC_FEATURES = [
    "original_cost",
    "cumulative_expenditure_t",
    "revised_cost_t",
    "physical_progress_t",
    "project_age_months",
    "months_to_original_schedule",
    "months_to_effective_schedule",
    "expenditure_to_original_cost_ratio",
    "revised_to_original_cost_ratio",
    "exp_delta_1m",
    "exp_delta_3m",
    "n_prior_schedule_extensions",
    "n_prior_cost_revisions",
    "observed_tenure_months",
]

DIAGNOSTIC_MONTHS = ("2025-01", "2025-02", "2025-03")
CI_METRICS = ("average_precision", "roc_auc", "brier_score")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _serialise(value: Any) -> Any:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    if isinstance(value, (float, np.floating)):
        return format(float(value), ".15g")
    return value


def _write_csv(path: Path, fields: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _serialise(row.get(field)) for field in fields})


def _numeric(value: str) -> float:
    return float(value) if value is not None and value.strip() else math.nan


def aggregate_metric_views(
    fold_rows: Sequence[dict[str, Any]], prediction_rows: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Return micro, unweighted fold macro, and row-weighted fold metrics."""
    result: list[dict[str, Any]] = []
    for regime in ("LEGACY", "MODERN"):
        for model in MODEL_ORDER:
            folds = [row for row in fold_rows if row["regime"] == regime and row["model"] == model]
            predictions = [
                row for row in prediction_rows
                if row["identifier_regime"] == regime and row["model"] == model
            ]
            if not folds or not predictions:
                continue
            y = np.asarray([int(row["actual_label"]) for row in predictions], dtype=int)
            score = np.asarray(
                [float(row["predicted_probability_or_score"]) for row in predictions], dtype=float
            )
            predicted = np.asarray([int(row["predicted_label"]) for row in predictions], dtype=int)
            micro = _point_metrics(y, score, predicted)
            for metric in CI_METRICS:
                values = np.asarray([float(row[metric]) for row in folds], dtype=float)
                weights = np.asarray([int(row["evaluation_rows"]) for row in folds], dtype=float)
                result.append(
                    {
                        "regime": regime,
                        "model": model,
                        "metric": metric,
                        "micro_concatenated_oof": micro[metric],
                        "macro_fold_mean": float(values.mean()),
                        "evaluation_row_weighted_fold_mean": float(np.average(values, weights=weights)),
                        "folds": len(folds),
                        "evaluation_rows": int(weights.sum()),
                    }
                )
    return result


def _bootstrap_metric_samples(
    rows: Sequence[dict[str, Any]],
    cluster_field: str,
    iterations: int,
    seed: int,
) -> dict[str, tuple[float, float]]:
    """Sample whole project or month clusters, retaining all rows per draw."""
    grouped: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        grouped[str(row[cluster_field])].append(index)
    clusters = sorted(grouped)
    rng = np.random.default_rng(seed)
    y_all = np.asarray([int(row["actual_label"]) for row in rows], dtype=int)
    score_all = np.asarray([float(row["predicted_probability_or_score"]) for row in rows])
    predicted_all = np.asarray([int(row["predicted_label"]) for row in rows], dtype=int)
    values: dict[str, list[float]] = defaultdict(list)
    for _ in range(iterations):
        selected_clusters = rng.choice(clusters, size=len(clusters), replace=True)
        indices = np.concatenate(
            [np.asarray(grouped[str(cluster)], dtype=int) for cluster in selected_clusters]
        )
        metrics = _point_metrics(y_all[indices], score_all[indices], predicted_all[indices])
        for metric in CI_METRICS:
            value = metrics[metric]
            if value is not None:
                values[metric].append(float(value))
    return {
        metric: (
            float(np.quantile(values[metric], 0.025)),
            float(np.quantile(values[metric], 0.975)),
        )
        for metric in CI_METRICS
    }


def clustered_confidence_intervals(
    prediction_rows: Sequence[dict[str, Any]], iterations: int
) -> list[dict[str, Any]]:
    result = []
    for regime in ("LEGACY", "MODERN"):
        for model in MODEL_ORDER:
            rows = [
                row for row in prediction_rows
                if row["identifier_regime"] == regime and row["model"] == model
            ]
            y = np.asarray([int(row["actual_label"]) for row in rows], dtype=int)
            score = np.asarray([float(row["predicted_probability_or_score"]) for row in rows])
            predicted = np.asarray([int(row["predicted_label"]) for row in rows], dtype=int)
            point = _point_metrics(y, score, predicted)
            for method, field in (
                ("PROJECT_CLUSTER_BOOTSTRAP", "project_code"),
                ("EVALUATION_MONTH_BLOCK_BOOTSTRAP", "report_month"),
            ):
                seed_text = f"{RANDOM_SEED}:{regime}:{model}:{method}"
                seed = int.from_bytes(hashlib.sha256(seed_text.encode()).digest()[:8], "big")
                intervals = _bootstrap_metric_samples(rows, field, iterations, seed)
                for metric in CI_METRICS:
                    result.append(
                        {
                            "regime": regime,
                            "model": model,
                            "method": method,
                            "cluster_count": len({row[field] for row in rows}),
                            "iterations": iterations,
                            "metric": metric,
                            "point_estimate": point[metric],
                            "ci_lower": intervals[metric][0],
                            "ci_upper": intervals[metric][1],
                        }
                    )
    return result


def evaluate_feature_families(
    rows_by_regime: dict[str, list[dict[str, str]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    fold_metrics: list[dict[str, Any]] = []
    predictions: list[dict[str, Any]] = []
    for regime in ("LEGACY", "MODERN"):
        regime_rows = rows_by_regime[regime]
        for evaluation_month in EVALUATION_ORIGINS[regime]:
            evaluation = [row for row in regime_rows if row["report_month"] == evaluation_month]
            training = select_training_rows(regime_rows, regime, evaluation_month)
            y = np.asarray([int(row[TARGET]) for row in evaluation], dtype=int)
            for family, features in FEATURE_FAMILIES.items():
                score, processor, _model = fit_logistic_scores(training, evaluation, features)
                predicted = (score >= 0.5).astype(int)
                metrics = _point_metrics(y, score, predicted)
                fold_metrics.append(
                    {
                        "regime": regime,
                        "evaluation_month": evaluation_month,
                        "feature_family": family,
                        "training_rows": len(training),
                        "evaluation_rows": len(evaluation),
                        "positives": int(y.sum()),
                        "positive_rate": float(y.mean()),
                        "input_feature_count": len(features),
                        "matrix_column_count": len(processor.output_columns),
                        **metrics,
                    }
                )
                predictions.extend(
                    {
                        "project_code": row["project_code"],
                        "report_month": row["report_month"],
                        "identifier_regime": regime,
                        "feature_family": family,
                        "actual_label": int(row[TARGET]),
                        "predicted_probability": float(score[index]),
                        "predicted_label": int(predicted[index]),
                    }
                    for index, row in enumerate(evaluation)
                )
    return fold_metrics, predictions


def aggregate_feature_families(
    fold_rows: Sequence[dict[str, Any]], prediction_rows: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    result = []
    for regime in ("LEGACY", "MODERN"):
        for family in FEATURE_FAMILIES:
            rows = [
                row for row in prediction_rows
                if row["identifier_regime"] == regime and row["feature_family"] == family
            ]
            folds = [
                row for row in fold_rows
                if row["regime"] == regime and row["feature_family"] == family
            ]
            y = np.asarray([int(row["actual_label"]) for row in rows], dtype=int)
            score = np.asarray([float(row["predicted_probability"]) for row in rows])
            predicted = np.asarray([int(row["predicted_label"]) for row in rows], dtype=int)
            metrics = _point_metrics(y, score, predicted)
            record: dict[str, Any] = {
                "regime": regime,
                "feature_family": family,
                "folds": len(folds),
                "evaluation_rows": len(rows),
                "positives": int(y.sum()),
                "positive_rate": float(y.mean()),
                "input_feature_count": len(FEATURE_FAMILIES[family]),
            }
            record.update(metrics)
            for metric in CI_METRICS:
                values = np.asarray([float(row[metric]) for row in folds])
                weights = np.asarray([int(row["evaluation_rows"]) for row in folds])
                record[f"{metric}_macro_fold_mean"] = float(values.mean())
                record[f"{metric}_weighted_fold_mean"] = float(np.average(values, weights=weights))
            result.append(record)
    return result


def fold_stability_rows(
    fold_rows: Sequence[dict[str, str]], preprocessing_audit: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    audit_index = {
        (row["regime"], row["evaluation_month"]): row for row in preprocessing_audit
    }
    metric_index = {
        (row["regime"], row["evaluation_month"], row["model"]): row for row in fold_rows
    }
    result = []
    for regime in ("LEGACY", "MODERN"):
        for month in EVALUATION_ORIGINS[regime]:
            logistic = metric_index[(regime, month, "logistic_l2_unweighted")]
            lagged = metric_index[(regime, month, "lagged_rule_latest_valid_transition")]
            prevalence = metric_index[(regime, month, "prevalence")]
            audit = audit_index[(regime, month)]
            unseen = audit["unseen_evaluation_categories"]
            evaluation_rows = int(logistic["evaluation_rows"])
            result.append(
                {
                    "regime": regime,
                    "evaluation_month": month,
                    "training_rows": int(logistic["training_rows"]),
                    "evaluation_rows": evaluation_rows,
                    "positives": int(logistic["evaluation_positives"]),
                    "positive_rate": float(logistic["evaluation_positive_rate"]),
                    "logistic_average_precision": float(logistic["average_precision"]),
                    "logistic_roc_auc": float(logistic["roc_auc"]),
                    "lagged_average_precision": float(lagged["average_precision"]),
                    "prevalence_average_precision": float(prevalence["average_precision"]),
                    "logistic_brier_score": float(logistic["brier_score"]),
                    "categorical_unseen_cell_rate": sum(unseen.values()) / (evaluation_rows * 3),
                    "sector_unseen_rate": unseen["sector"] / evaluation_rows,
                    "agency_unseen_rate": unseen["agency"] / evaluation_rows,
                    "state_unseen_rate": unseen["state"] / evaluation_rows,
                }
            )
    return result


def _distribution(rows: Sequence[dict[str, str]], field: str) -> dict[str, float]:
    counts = Counter((row.get(field, "") or "__MISSING__") for row in rows)
    return {key: value / len(rows) for key, value in counts.items()}


def _total_variation(left: dict[str, float], right: dict[str, float]) -> float:
    return 0.5 * sum(abs(left.get(key, 0.0) - right.get(key, 0.0)) for key in set(left) | set(right))


def february_diagnostics(
    legacy_rows: Sequence[dict[str, str]],
) -> dict[str, list[dict[str, Any]] | dict[str, Any]]:
    month_rows = {
        month: [row for row in legacy_rows if row["report_month"] == month]
        for month in DIAGNOSTIC_MONTHS
    }
    categorical_rows = []
    distribution_summary: dict[str, Any] = {}
    for field in ("sector", "agency"):
        distributions = {month: _distribution(rows, field) for month, rows in month_rows.items()}
        distribution_summary[field] = {
            "jan_to_feb_total_variation": _total_variation(distributions["2025-01"], distributions["2025-02"]),
            "feb_to_mar_total_variation": _total_variation(distributions["2025-02"], distributions["2025-03"]),
        }
        for month, rows in month_rows.items():
            counts = Counter((row.get(field, "") or "__MISSING__") for row in rows)
            for rank, (category, count) in enumerate(
                sorted(counts.items(), key=lambda item: (-item[1], item[0])), start=1
            ):
                categorical_rows.append(
                    {
                        "field": field,
                        "evaluation_month": month,
                        "rank": rank,
                        "category": category,
                        "rows": count,
                        "share": count / len(rows),
                    }
                )

    missing_rows = []
    for month, rows in month_rows.items():
        for feature in FEATURE_FAMILIES["full_v1"]:
            missing = sum(not bool(row.get(feature, "")) for row in rows)
            is_indicator = feature.endswith(("_is_missing", "_is_present", "_supported"))
            numeric_values = (
                [
                    _numeric(row.get(feature, "")) for row in rows
                    if row.get(feature, "") != ""
                ]
                if is_indicator
                else []
            )
            missing_rows.append(
                {
                    "evaluation_month": month,
                    "feature": feature,
                    "rows": len(rows),
                    "missing_rows": missing,
                    "missing_rate": missing / len(rows),
                    "mean_indicator_value": (
                        float(np.mean(numeric_values))
                        if is_indicator and numeric_values
                        else None
                    ),
                }
            )

    composition_rows = []
    for month, rows in month_rows.items():
        positives = [row for row in rows if int(row[TARGET]) == 1]
        counts = Counter(row["extension_type"] for row in positives)
        for stored, documented in (
            ("FIRST_REVISION", "FIRST_REVISION_FROM_UNREVISED_BASELINE"),
            ("SUBSEQUENT_REVISION", "SUBSEQUENT_REVISION"),
        ):
            composition_rows.append(
                {
                    "evaluation_month": month,
                    "positive_rows": len(positives),
                    "stored_extension_type": stored,
                    "documented_extension_type": documented,
                    "rows": counts[stored],
                    "share_of_positives": counts[stored] / len(positives) if positives else None,
                }
            )

    numeric_rows = []
    for month, rows in month_rows.items():
        for feature in MAJOR_NUMERIC_FEATURES:
            values = np.asarray(
                [_numeric(row.get(feature, "")) for row in rows], dtype=float
            )
            values = values[np.isfinite(values)]
            numeric_rows.append(
                {
                    "evaluation_month": month,
                    "feature": feature,
                    "reported_rows": len(values),
                    "missing_rows": len(rows) - len(values),
                    "mean": float(values.mean()) if len(values) else None,
                    "std": float(values.std()) if len(values) else None,
                    "q25": float(np.quantile(values, 0.25)) if len(values) else None,
                    "median": float(np.median(values)) if len(values) else None,
                    "q75": float(np.quantile(values, 0.75)) if len(values) else None,
                }
            )

    target_rows = [
        {
            "evaluation_month": month,
            "evaluation_rows": len(rows),
            "positives": sum(int(row[TARGET]) for row in rows),
            "positive_rate": sum(int(row[TARGET]) for row in rows) / len(rows),
        }
        for month, rows in month_rows.items()
    ]
    return {
        "target": target_rows,
        "categorical": categorical_rows,
        "missingness_support": missing_rows,
        "revision_composition": composition_rows,
        "numeric": numeric_rows,
        "distribution_summary": distribution_summary,
    }


def calibration_diagnostics(
    full_predictions: Sequence[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    bins: list[dict[str, Any]] = []
    distributions = []
    deciles = []
    by_fold = []
    for regime in ("LEGACY", "MODERN"):
        rows = [row for row in full_predictions if row["identifier_regime"] == regime]
        y = np.asarray([int(row["actual_label"]) for row in rows], dtype=int)
        score = np.asarray([float(row["predicted_probability"]) for row in rows])
        bins.extend(calibration_rows(y, score, regime, "logistic_full_v1", "AGGREGATE", ""))
        distributions.append(
            {
                "regime": regime,
                "rows": len(score),
                "mean": float(score.mean()),
                "std": float(score.std()),
                "minimum": float(score.min()),
                "p01": float(np.quantile(score, 0.01)),
                "p05": float(np.quantile(score, 0.05)),
                "p10": float(np.quantile(score, 0.10)),
                "p25": float(np.quantile(score, 0.25)),
                "median": float(np.median(score)),
                "p75": float(np.quantile(score, 0.75)),
                "p90": float(np.quantile(score, 0.90)),
                "p95": float(np.quantile(score, 0.95)),
                "p99": float(np.quantile(score, 0.99)),
                "maximum": float(score.max()),
                "observed_event_rate": float(y.mean()),
                "brier_score": _point_metrics(y, score, (score >= 0.5).astype(int))["brier_score"],
                "ece_10bin": expected_calibration_error(y, score),
            }
        )
        order = np.argsort(score)
        for index, indices in enumerate(np.array_split(order, 10), start=1):
            deciles.append(
                {
                    "regime": regime,
                    "probability_decile": index,
                    "rows": len(indices),
                    "minimum_probability": float(score[indices].min()),
                    "maximum_probability": float(score[indices].max()),
                    "mean_probability": float(score[indices].mean()),
                    "observed_event_rate": float(y[indices].mean()),
                }
            )
        for month in EVALUATION_ORIGINS[regime]:
            fold = [row for row in rows if row["report_month"] == month]
            fold_y = np.asarray([int(row["actual_label"]) for row in fold])
            fold_score = np.asarray([float(row["predicted_probability"]) for row in fold])
            metrics = _point_metrics(fold_y, fold_score, (fold_score >= 0.5).astype(int))
            by_fold.append(
                {
                    "regime": regime,
                    "evaluation_month": month,
                    "rows": len(fold),
                    "observed_event_rate": float(fold_y.mean()),
                    "mean_predicted_probability": float(fold_score.mean()),
                    "prediction_minus_observed": float(fold_score.mean() - fold_y.mean()),
                    "brier_score": metrics["brier_score"],
                    "ece_10bin": metrics["ece_10bin"],
                }
            )
    return bins, distributions, deciles, by_fold


def precision_recall_tradeoffs(
    full_predictions: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    result = []
    for regime in ("LEGACY", "MODERN"):
        rows = [row for row in full_predictions if row["identifier_regime"] == regime]
        y = np.asarray([int(row["actual_label"]) for row in rows])
        score = np.asarray([float(row["predicted_probability"]) for row in rows])
        precision, recall, thresholds = precision_recall_curve(y, score)
        for target_recall in (0.90, 0.80, 0.70, 0.50, 0.25):
            candidates = np.flatnonzero(recall[:-1] >= target_recall)
            index = int(candidates[-1]) if len(candidates) else int(np.argmax(recall[:-1]))
            result.append(
                {
                    "regime": regime,
                    "target_recall_anchor": target_recall,
                    "achieved_recall": float(recall[index]),
                    "precision": float(precision[index]),
                    "descriptive_score_threshold": float(thresholds[index]),
                    "selection_status": "DESCRIPTIVE_OOF_CURVE_ONLY_NOT_OPERATIONAL_THRESHOLD",
                }
            )
    return result


def run(root: Path, bootstrap_iterations: int = BOOTSTRAP_ITERATIONS) -> dict[str, Any]:
    root = root.resolve()
    evaluation_dir = root / "data/ml/schedule_extension_3m/evaluation"
    output_dir = evaluation_dir / "robustness"
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset_manifest_path = evaluation_dir.parent / "manifest.json"
    evaluation_manifest_path = evaluation_dir / "evaluation_manifest.json"
    dataset_manifest = json.loads(dataset_manifest_path.read_text(encoding="utf-8"))
    evaluation_manifest = json.loads(evaluation_manifest_path.read_text(encoding="utf-8"))
    manifest_features = dataset_manifest["feature_columns"]
    if FEATURE_FAMILIES["full_v1"] != manifest_features:
        raise RuntimeError("Feature-family partition does not reproduce manifest feature order")

    canonical_hashes = {
        "projects_monthly.csv": sha256(root / "data/processed/projects_monthly.csv"),
        "projects_completed.csv": sha256(root / "data/processed/projects_completed.csv"),
    }
    if canonical_hashes != {
        "projects_monthly.csv": ONGOING_SHA256,
        "projects_completed.csv": COMPLETED_SHA256,
    }:
        raise RuntimeError(f"Canonical hash mismatch: {canonical_hashes}")

    rows_by_regime = {
        "LEGACY": _read_csv(evaluation_dir.parent / "eligible_legacy.csv"),
        "MODERN": _read_csv(evaluation_dir.parent / "eligible_modern.csv"),
    }
    accepted_fold_rows = _read_csv(evaluation_dir / "fold_metrics.csv")
    accepted_prediction_rows = _read_csv(evaluation_dir / "predictions.csv")
    preprocessing_audit = json.loads(
        (evaluation_dir / "preprocessing_fit_audit.json").read_text(encoding="utf-8")
    )
    fold_stability = fold_stability_rows(accepted_fold_rows, preprocessing_audit)
    aggregation = aggregate_metric_views(accepted_fold_rows, accepted_prediction_rows)
    confidence = clustered_confidence_intervals(accepted_prediction_rows, bootstrap_iterations)
    family_folds, family_predictions = evaluate_feature_families(rows_by_regime)
    family_aggregate = aggregate_feature_families(family_folds, family_predictions)

    accepted_full = {
        (row["project_code"], row["report_month"], row["identifier_regime"]): float(
            row["predicted_probability_or_score"]
        )
        for row in accepted_prediction_rows
        if row["model"] == "logistic_l2_unweighted"
    }
    robustness_full = {
        (row["project_code"], row["report_month"], row["identifier_regime"]): float(
            row["predicted_probability"]
        )
        for row in family_predictions
        if row["feature_family"] == "full_v1"
    }
    if accepted_full.keys() != robustness_full.keys():
        raise RuntimeError("Full-v1 robustness prediction keys differ from accepted evaluation")
    max_score_difference = max(
        abs(accepted_full[key] - robustness_full[key]) for key in accepted_full
    )
    if max_score_difference > 1e-12:
        raise RuntimeError(f"Full-v1 score reconciliation failed: {max_score_difference}")

    feb = february_diagnostics(rows_by_regime["LEGACY"])
    full_predictions = [
        row for row in family_predictions if row["feature_family"] == "full_v1"
    ]
    calibration_bins, probability_distribution, calibration_deciles, calibration_by_fold = (
        calibration_diagnostics(full_predictions)
    )
    pr_tradeoffs = precision_recall_tradeoffs(full_predictions)

    output_specs: dict[str, tuple[list[str], list[dict[str, Any]]]] = {
        "fold_stability.csv": (
            [
                "regime", "evaluation_month", "training_rows", "evaluation_rows", "positives",
                "positive_rate", "logistic_average_precision", "logistic_roc_auc",
                "lagged_average_precision", "prevalence_average_precision", "logistic_brier_score",
                "categorical_unseen_cell_rate", "sector_unseen_rate", "agency_unseen_rate",
                "state_unseen_rate",
            ],
            fold_stability,
        ),
        "aggregation_comparison.csv": (
            [
                "regime", "model", "metric", "micro_concatenated_oof", "macro_fold_mean",
                "evaluation_row_weighted_fold_mean", "folds", "evaluation_rows",
            ],
            aggregation,
        ),
        "cluster_and_block_confidence_intervals.csv": (
            [
                "regime", "model", "method", "cluster_count", "iterations", "metric",
                "point_estimate", "ci_lower", "ci_upper",
            ],
            confidence,
        ),
        "feature_family_fold_metrics.csv": (
            [
                "regime", "evaluation_month", "feature_family", "training_rows", "evaluation_rows",
                "positives", "positive_rate", "input_feature_count", "matrix_column_count",
                "average_precision", "roc_auc", "precision", "recall", "f1", "brier_score",
                "mean_predicted_probability", "ece_10bin",
            ],
            family_folds,
        ),
        "feature_family_aggregate_metrics.csv": (
            [
                "regime", "feature_family", "folds", "evaluation_rows", "positives",
                "positive_rate", "input_feature_count", "average_precision", "roc_auc", "precision",
                "recall", "f1", "brier_score", "mean_predicted_probability", "ece_10bin",
                "average_precision_macro_fold_mean", "average_precision_weighted_fold_mean",
                "roc_auc_macro_fold_mean", "roc_auc_weighted_fold_mean",
                "brier_score_macro_fold_mean", "brier_score_weighted_fold_mean",
            ],
            family_aggregate,
        ),
        "feature_family_predictions.csv": (
            [
                "project_code", "report_month", "identifier_regime", "feature_family",
                "actual_label", "predicted_probability", "predicted_label",
            ],
            family_predictions,
        ),
        "feb2025_categorical_distribution.csv": (
            ["field", "evaluation_month", "rank", "category", "rows", "share"],
            feb["categorical"],  # type: ignore[arg-type]
        ),
        "feb2025_missingness_support.csv": (
            [
                "evaluation_month", "feature", "rows", "missing_rows", "missing_rate",
                "mean_indicator_value",
            ],
            feb["missingness_support"],  # type: ignore[arg-type]
        ),
        "feb2025_revision_composition.csv": (
            [
                "evaluation_month", "positive_rows", "stored_extension_type",
                "documented_extension_type", "rows", "share_of_positives",
            ],
            feb["revision_composition"],  # type: ignore[arg-type]
        ),
        "feb2025_numeric_distribution.csv": (
            [
                "evaluation_month", "feature", "reported_rows", "missing_rows", "mean", "std",
                "q25", "median", "q75",
            ],
            feb["numeric"],  # type: ignore[arg-type]
        ),
        "feb2025_target_comparison.csv": (
            ["evaluation_month", "evaluation_rows", "positives", "positive_rate"],
            feb["target"],  # type: ignore[arg-type]
        ),
        "calibration_bins.csv": (
            [
                "regime", "model", "scope", "evaluation_month", "bin_index", "lower_bound",
                "upper_bound", "rows", "mean_predicted_probability", "observed_positive_rate",
            ],
            calibration_bins,
        ),
        "probability_distribution.csv": (
            [
                "regime", "rows", "mean", "std", "minimum", "p01", "p05", "p10", "p25",
                "median", "p75", "p90", "p95", "p99", "maximum", "observed_event_rate",
                "brier_score", "ece_10bin",
            ],
            probability_distribution,
        ),
        "calibration_deciles.csv": (
            [
                "regime", "probability_decile", "rows", "minimum_probability",
                "maximum_probability", "mean_probability", "observed_event_rate",
            ],
            calibration_deciles,
        ),
        "calibration_by_fold.csv": (
            [
                "regime", "evaluation_month", "rows", "observed_event_rate",
                "mean_predicted_probability", "prediction_minus_observed", "brier_score", "ece_10bin",
            ],
            calibration_by_fold,
        ),
        "precision_recall_tradeoffs.csv": (
            [
                "regime", "target_recall_anchor", "achieved_recall", "precision",
                "descriptive_score_threshold", "selection_status",
            ],
            pr_tradeoffs,
        ),
    }
    generated = {}
    for name, (fields, rows) in output_specs.items():
        path = output_dir / name
        _write_csv(path, fields, rows)
        generated[name] = {"rows": len(rows), "sha256": sha256(path)}

    summary = {
        "audit_name": "schedule_extension_3m_baseline_robustness_v1",
        "dataset_manifest_sha256": sha256(dataset_manifest_path),
        "evaluation_manifest_sha256": sha256(evaluation_manifest_path),
        "canonical_hashes": canonical_hashes,
        "target_labels_rebuilt": False,
        "target_defect_found": False,
        "advanced_models_implemented": [],
        "feature_families": FEATURE_FAMILIES,
        "evaluation_origins": EVALUATION_ORIGINS,
        "bootstrap": {
            "iterations": bootstrap_iterations,
            "methods": ["PROJECT_CLUSTER_BOOTSTRAP", "EVALUATION_MONTH_BLOCK_BOOTSTRAP"],
            "project_cluster_semantics": "Sample project_code clusters with replacement and retain every OOF observation for each sampled project draw.",
            "month_block_semantics": "Sample evaluation-month blocks with replacement and retain every OOF observation in each sampled month draw.",
        },
        "full_v1_score_reconciliation_max_absolute_difference": max_score_difference,
        "aggregation_interpretation": {
            "micro": "Metric on concatenated out-of-fold predictions; ranks/scores from different fitted folds are pooled.",
            "macro": "Unweighted arithmetic mean of per-fold metrics.",
            "weighted": "Per-fold metric mean weighted by evaluation rows; equals micro for decomposable Brier but not generally for AP/ROC.",
            "caution": "Cross-fold score scales reflect different fitted models and training prevalences, so concatenated AP/ROC is a pooled operational summary, not a single-model test-set metric.",
        },
        "feb2025_distribution_summary": feb["distribution_summary"],
        "feature_family_aggregate_results": family_aggregate,
        "calibration_summary": probability_distribution,
        "generated_files": generated,
        "validations": {
            "manifest_feature_partition_exact": True,
            "accepted_full_v1_prediction_keys_reconciled": True,
            "accepted_full_v1_scores_reconciled": True,
            "canonical_hashes_unchanged": True,
            "labels_unchanged": True,
        },
    }
    summary_path = output_dir / "robustness_manifest.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--bootstrap-iterations", type=int, default=BOOTSTRAP_ITERATIONS)
    args = parser.parse_args()
    summary = run(args.root, args.bootstrap_iterations)
    print(json.dumps({
        "feature_family_aggregate_results": summary["feature_family_aggregate_results"],
        "calibration_summary": summary["calibration_summary"],
        "feb2025_distribution_summary": summary["feb2025_distribution_summary"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
