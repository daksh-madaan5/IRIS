"""Controlled CatBoost nonlinear challenger for the H=3 schedule-extension target.

This module evaluates CatBoost as the first nonlinear challenger against the
locked regime-specific Logistic baselines. It reuses the exact same 17
walk-forward evaluation origins, strict ``T + 3 < E`` embargo, and regime
separation. Categorical features are handled natively by CatBoost using
training-fold-only statistics, with string missingness sentinels. Missing
numerics are preserved as NaN. Fixed iteration count (300) is used with no test-fold
tuning or early stopping.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Sequence

import catboost as cb
import numpy as np
import pandas as pd
import scipy
import sklearn
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from src.ml.dataset_builder import COMPLETED_SHA256, HORIZON, ONGOING_SHA256, sha256
from src.ml.evaluate_baselines import (
    BOOTSTRAP_ITERATIONS,
    CATEGORICAL_FEATURES,
    EVALUATION_ORIGINS,
    PROHIBITED_FEATURES,
    RANDOM_SEED,
    TARGET,
    _as_float,
    _point_metrics,
    lagged_rule_predictions,
    select_training_rows,
)
from src.ml.refine_logistic import (
    CI_METRICS,
    project_cluster_intervals,
)
from src.ml.robustness_audit import FULL_V1_FEATURES, STATIC_AT_T_FEATURES, TRAJECTORY_FEATURES


CATBOOST_PARAMS = {
    "iterations": 300,
    "learning_rate": 0.05,
    "depth": 5,
    "l2_leaf_reg": 3.0,
    "random_seed": RANDOM_SEED,
    "verbose": False,
    "thread_count": 4,
    "allow_writing_files": False,
}

CATBOOST_FEATURE_SETS = {
    "LEGACY": {
        "trajectory_only": list(TRAJECTORY_FEATURES),
        "full_v1": list(FULL_V1_FEATURES),
    },
    "MODERN": {
        "static_only": list(STATIC_AT_T_FEATURES),
        "full_v1": list(FULL_V1_FEATURES),
    },
}

CATBOOST_FEATURE_SET_RATIONALE = {
    "LEGACY": {
        "trajectory_only": (
            "Primary Legacy candidate; matches the winning Logistic benchmark feature set "
            "(11 trajectory features)."
        ),
        "full_v1": (
            "Secondary comparison; full 36-input feature set including static, categorical, "
            "and trajectory features."
        ),
    },
    "MODERN": {
        "static_only": (
            "Primary Modern candidate; matches the winning Logistic benchmark feature set "
            "(25 static features)."
        ),
        "full_v1": (
            "Secondary comparison; full 36-input feature set including static, categorical, "
            "and trajectory features."
        ),
    },
}

CATBOOST_WEIGHT_VARIANTS = {
    "unweighted": None,
    "balanced": "Balanced",
}

LOGISTIC_WINNERS = {
    "LEGACY": "logistic_trajectory_only__balanced",
    "MODERN": "logistic_static_only__unweighted",
}

CATEGORICAL_MISSING_SENTINEL = "__MISSING__"


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


def catboost_model_name(feature_set: str, weighting: str) -> str:
    return f"catboost_{feature_set}__{weighting}"


def prepare_catboost_df(
    rows: Sequence[dict[str, str]], feature_columns: Sequence[str]
) -> tuple[pd.DataFrame, list[str]]:
    """Build a DataFrame where categoricals are strings and missing numerics are NaN.

    Categorical missing values use the explicit training-safe sentinel
    ``__MISSING__`` to ensure CatBoost native string handling without numeric
    casting.
    """
    cat_cols = [col for col in feature_columns if col in CATEGORICAL_FEATURES]
    data: dict[str, list[Any]] = {}
    for col in feature_columns:
        if col in CATEGORICAL_FEATURES:
            col_vals = []
            for row in rows:
                val = (row.get(col, "") or "").strip()
                col_vals.append(val if val != "" else CATEGORICAL_MISSING_SENTINEL)
            data[col] = col_vals
        else:
            col_vals = []
            for row in rows:
                val = row.get(col, "")
                col_vals.append(_as_float(val))
            data[col] = col_vals
    df = pd.DataFrame(data, columns=list(feature_columns))
    return df, cat_cols


def fit_catboost_variant(
    training_rows: Sequence[dict[str, str]],
    evaluation_rows: Sequence[dict[str, str]],
    feature_columns: Sequence[str],
    auto_class_weights: str | None,
) -> tuple[np.ndarray, cb.CatBoostClassifier, dict[str, float]]:
    """Fit one CatBoost classifier with native categoricals and return evaluation probabilities."""
    x_train, cat_cols = prepare_catboost_df(training_rows, feature_columns)
    x_eval, _ = prepare_catboost_df(evaluation_rows, feature_columns)
    y_train = np.asarray([int(row[TARGET]) for row in training_rows], dtype=int)

    model = cb.CatBoostClassifier(
        **CATBOOST_PARAMS,
        auto_class_weights=auto_class_weights,
    )
    model.fit(
        x_train,
        y_train,
        cat_features=cat_cols if cat_cols else None,
        verbose=False,
    )
    preds = model.predict_proba(x_eval)[:, 1]
    importances = dict(zip(feature_columns, model.get_feature_importance()))
    return preds, model, importances


def audit_fold_categories(
    training_rows: Sequence[dict[str, str]],
    evaluation_rows: Sequence[dict[str, str]],
    feature_columns: Sequence[str],
) -> dict[str, Any]:
    """Audit categorical distributions, training levels, and unseen evaluation levels."""
    cat_cols = [col for col in feature_columns if col in CATEGORICAL_FEATURES]
    audit: dict[str, Any] = {"categorical_columns": cat_cols}
    for col in cat_cols:
        train_counts = Counter(
            (row.get(col, "") or "").strip() or CATEGORICAL_MISSING_SENTINEL
            for row in training_rows
        )
        eval_counts = Counter(
            (row.get(col, "") or "").strip() or CATEGORICAL_MISSING_SENTINEL
            for row in evaluation_rows
        )
        unseen = {cat: count for cat, count in eval_counts.items() if cat not in train_counts}
        audit[col] = {
            "training_distinct_count": len(train_counts),
            "evaluation_distinct_count": len(eval_counts),
            "unseen_in_training_count": sum(unseen.values()),
            "unseen_categories": sorted(unseen.keys()),
        }
    return audit


def paired_cluster_bootstrap(
    catboost_rows: Sequence[dict[str, Any]],
    logistic_rows: Sequence[dict[str, Any]],
    iterations: int,
    seed: int,
) -> dict[str, dict[str, float | None]]:
    """Compute project-cluster bootstrap CIs for paired CatBoost minus Logistic differences."""
    if len(catboost_rows) != len(logistic_rows):
        raise ValueError("CatBoost and Logistic prediction row counts must match for paired bootstrap")

    # Verify exact row-by-row alignment
    for cb_row, log_row in zip(catboost_rows, logistic_rows):
        if (
            cb_row["project_code"] != log_row["project_code"]
            or cb_row["report_month"] != log_row["report_month"]
            or int(cb_row["actual_label"]) != int(log_row["actual_label"])
        ):
            raise ValueError(
                f"Row misalignment in paired bootstrap: {cb_row['project_code']}:{cb_row['report_month']}"
            )

    grouped: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(catboost_rows):
        grouped[str(row["project_code"])].append(index)
    clusters = sorted(grouped)

    y_all = np.asarray([int(row["actual_label"]) for row in catboost_rows], dtype=int)
    cb_scores = np.asarray([float(row["predicted_probability"]) for row in catboost_rows], dtype=float)
    cb_preds = np.asarray([int(row["predicted_label"]) for row in catboost_rows], dtype=int)
    log_scores = np.asarray([float(row["predicted_probability"]) for row in logistic_rows], dtype=float)
    log_preds = np.asarray([int(row["predicted_label"]) for row in logistic_rows], dtype=int)

    cb_point = _point_metrics(y_all, cb_scores, cb_preds)
    log_point = _point_metrics(y_all, log_scores, log_preds)

    delta_metrics = ("average_precision", "roc_auc", "brier_score", "ece_10bin")
    deltas: dict[str, list[float]] = defaultdict(list)

    rng = np.random.default_rng(seed)
    for _ in range(iterations):
        selected = rng.choice(clusters, size=len(clusters), replace=True)
        indices = np.concatenate([np.asarray(grouped[str(c)], dtype=int) for c in selected])
        y_samp = y_all[indices]
        cb_p = _point_metrics(y_samp, cb_scores[indices], cb_preds[indices])
        log_p = _point_metrics(y_samp, log_scores[indices], log_preds[indices])
        for metric in delta_metrics:
            if cb_p[metric] is not None and log_p[metric] is not None:
                deltas[metric].append(float(cb_p[metric]) - float(log_p[metric]))

    result: dict[str, dict[str, float | None]] = {}
    for metric in delta_metrics:
        cb_val = cb_point[metric]
        log_val = log_point[metric]
        delta_pt = (
            float(cb_val) - float(log_val)
            if cb_val is not None and log_val is not None
            else None
        )
        if deltas[metric]:
            ci_low = float(np.quantile(deltas[metric], 0.025))
            ci_high = float(np.quantile(deltas[metric], 0.975))
        else:
            ci_low, ci_high = None, None
        result[metric] = {
            "catboost_point": cb_val,
            "logistic_point": log_val,
            "delta_point": delta_pt,
            "delta_ci_lower": ci_low,
            "delta_ci_upper": ci_high,
        }
    return result


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
    refinement_dir = evaluation_dir / "refinement"
    output_dir = evaluation_dir / "catboost"
    output_dir.mkdir(parents=True, exist_ok=True)

    dataset_manifest_path = dataset_dir / "manifest.json"
    baseline_manifest_path = evaluation_dir / "evaluation_manifest.json"
    refinement_manifest_path = refinement_dir / "configuration_manifest.json"

    dataset_manifest = json.loads(dataset_manifest_path.read_text(encoding="utf-8"))
    baseline_manifest = json.loads(baseline_manifest_path.read_text(encoding="utf-8"))
    refinement_manifest = json.loads(refinement_manifest_path.read_text(encoding="utf-8"))

    manifest_features = list(dataset_manifest["feature_columns"])
    if dataset_manifest["target"] != TARGET:
        raise RuntimeError(f"Unexpected target: {dataset_manifest['target']}")
    if baseline_manifest["evaluated_origins"] != EVALUATION_ORIGINS:
        raise RuntimeError("Accepted evaluation origins differ from CatBoost origins")

    declared_features = {
        feature
        for regime_sets in CATBOOST_FEATURE_SETS.values()
        for features in regime_sets.values()
        for feature in features
    }
    missing = sorted(declared_features - set(manifest_features))
    leakage = sorted(declared_features & PROHIBITED_FEATURES)
    if missing or leakage:
        raise RuntimeError(f"Invalid CatBoost features; missing={missing}, leakage={leakage}")

    canonical_hashes = {
        "projects_monthly.csv": sha256(root / "data/processed/projects_monthly.csv"),
        "projects_completed.csv": sha256(root / "data/processed/projects_completed.csv"),
    }
    expected_hashes = {
        "projects_monthly.csv": ONGOING_SHA256,
        "projects_completed.csv": COMPLETED_SHA256,
    }
    if canonical_hashes != expected_hashes:
        raise RuntimeError(f"Canonical hash mismatch; refusing CatBoost run: {canonical_hashes}")

    rows_by_regime = {
        "LEGACY": _read_csv(dataset_dir / "eligible_legacy.csv"),
        "MODERN": _read_csv(dataset_dir / "eligible_modern.csv"),
    }

    # Load locked winning Logistic benchmark predictions from refinement
    refinement_preds = _read_csv(refinement_dir / "predictions.csv")
    logistic_benchmark_preds = {
        "LEGACY": [
            row
            for row in refinement_preds
            if row["identifier_regime"] == "LEGACY"
            and row["model"] == LOGISTIC_WINNERS["LEGACY"]
        ],
        "MODERN": [
            row
            for row in refinement_preds
            if row["identifier_regime"] == "MODERN"
            and row["model"] == LOGISTIC_WINNERS["MODERN"]
        ],
    }

    # Load Logistic winner aggregates for benchmark reference
    refinement_aggregates = _read_csv(refinement_dir / "regime_aggregates.csv")
    logistic_winner_stats = {
        row["regime"]: row
        for row in refinement_aggregates
        if row["model"] == LOGISTIC_WINNERS[row["regime"]]
    }

    fold_metrics: list[dict[str, Any]] = []
    predictions: list[dict[str, Any]] = []
    preprocessing_audit: list[dict[str, Any]] = []
    feature_importance_records: list[dict[str, Any]] = []
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
                    {
                        "regime": regime,
                        "evaluation_month": evaluation_month,
                        "reason": "|".join(reasons),
                    }
                )
                continue
            if max(row["target_window_end_month"] for row in training) >= evaluation_month:
                raise RuntimeError(f"Strict embargo violation in {regime} {evaluation_month}")

            y_train = np.asarray([int(row[TARGET]) for row in training], dtype=int)
            y_eval = np.asarray([int(row[TARGET]) for row in evaluation], dtype=int)

            # References
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
                        regime,
                        evaluation_month,
                        model,
                        "REFERENCE",
                        "REFERENCE",
                        training,
                        evaluation,
                        y_eval,
                        score,
                        predicted,
                        0,
                    )
                )
                predictions.extend(
                    _prediction_rows(
                        evaluation, model, "REFERENCE", "REFERENCE", score, predicted
                    )
                )

            # CatBoost models
            for feature_set, features in CATBOOST_FEATURE_SETS[regime].items():
                for weighting, auto_weights in CATBOOST_WEIGHT_VARIANTS.items():
                    model_name = catboost_model_name(feature_set, weighting)
                    score, _model, importances = fit_catboost_variant(
                        training, evaluation, features, auto_weights
                    )
                    predicted = (score >= 0.5).astype(int)

                    fold_metrics.append(
                        _fold_record(
                            regime,
                            evaluation_month,
                            model_name,
                            feature_set,
                            weighting,
                            training,
                            evaluation,
                            y_eval,
                            score,
                            predicted,
                            len(features),
                        )
                    )
                    predictions.extend(
                        _prediction_rows(
                            evaluation,
                            model_name,
                            feature_set,
                            weighting,
                            score,
                            predicted,
                        )
                    )

                    # Track feature importances
                    for feat_name, feat_imp in importances.items():
                        feature_importance_records.append(
                            {
                                "regime": regime,
                                "evaluation_month": evaluation_month,
                                "model": model_name,
                                "feature_set": feature_set,
                                "weighting": weighting,
                                "feature": feat_name,
                                "importance": feat_imp,
                            }
                        )

                    # Categorical handling audit
                    cat_audit = audit_fold_categories(training, evaluation, features)
                    preprocessing_audit.append(
                        {
                            "regime": regime,
                            "evaluation_month": evaluation_month,
                            "model": model_name,
                            "feature_set": feature_set,
                            "weighting": weighting,
                            "training_rows": len(training),
                            "training_positives": int(y_train.sum()),
                            "training_positive_rate": float(y_train.mean()),
                            "auto_class_weights_mode": auto_weights,
                            "class_weights_computed_from_train_only": True,
                            "training_month_min": min(row["report_month"] for row in training),
                            "training_month_max": max(row["report_month"] for row in training),
                            "maximum_training_label_window_end": max(
                                row["target_window_end_month"] for row in training
                            ),
                            **cat_audit,
                        }
                    )

    aggregates = _aggregate_records(fold_metrics, predictions)
    aggregate_index = {(row["regime"], row["model"]): row for row in aggregates}

    # Model comparison & winners
    comparison = []
    winners = {}
    for regime in ("LEGACY", "MODERN"):
        prevalence = aggregate_index[(regime, "prevalence")]
        lagged = aggregate_index[(regime, "lagged_rule_latest_valid_transition")]
        logistic_win = logistic_winner_stats[regime]
        candidates = [
            row
            for row in aggregates
            if row["regime"] == regime and row["feature_set"] != "REFERENCE"
        ]
        winner = max(candidates, key=lambda row: row["average_precision"])
        winners[regime] = {
            "model": winner["model"],
            "feature_set": winner["feature_set"],
            "weighting": winner["weighting"],
            "average_precision": winner["average_precision"],
            "winning_logistic_benchmark": LOGISTIC_WINNERS[regime],
            "winning_logistic_average_precision": float(logistic_win["average_precision"]),
            "catboost_minus_logistic_ap": (
                winner["average_precision"] - float(logistic_win["average_precision"])
            ),
        }

        for row in sorted(candidates, key=lambda item: item["average_precision"], reverse=True):
            comparison.append(
                {
                    **row,
                    "ap_rank_within_regime": 1
                    + sum(
                        other["average_precision"] > row["average_precision"]
                        for other in candidates
                    ),
                    "is_regime_winner": row["model"] == winner["model"],
                    "prevalence_average_precision": prevalence["average_precision"],
                    "ap_delta_vs_prevalence": row["average_precision"]
                    - prevalence["average_precision"],
                    "lagged_rule_average_precision": lagged["average_precision"],
                    "ap_delta_vs_lagged_rule": row["average_precision"]
                    - lagged["average_precision"],
                    "winning_logistic_model": LOGISTIC_WINNERS[regime],
                    "winning_logistic_average_precision": float(
                        logistic_win["average_precision"]
                    ),
                    "ap_delta_vs_winning_logistic": row["average_precision"]
                    - float(logistic_win["average_precision"]),
                }
            )

    # 1000-resample project-cluster bootstrap CIs for each candidate
    ci_rows = []
    for aggregate in aggregates:
        selected = [
            row
            for row in predictions
            if row["identifier_regime"] == aggregate["regime"]
            and row["model"] == aggregate["model"]
        ]
        seed_text = (
            f"{RANDOM_SEED}:{aggregate['regime']}:{aggregate['model']}:PROJECT_CLUSTER_CB"
        )
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

    # Paired project-cluster bootstrap comparison vs winning Logistic benchmark
    paired_comparison_rows = []
    for regime in ("LEGACY", "MODERN"):
        log_rows = logistic_benchmark_preds[regime]
        log_model_name = LOGISTIC_WINNERS[regime]
        candidates = [
            row
            for row in aggregates
            if row["regime"] == regime and row["feature_set"] != "REFERENCE"
        ]
        for candidate in candidates:
            cb_model_name = candidate["model"]
            cb_rows = [
                row
                for row in predictions
                if row["identifier_regime"] == regime and row["model"] == cb_model_name
            ]
            seed_text = f"{RANDOM_SEED}:{regime}:{cb_model_name}:vs:{log_model_name}:PAIRED_BOOTSTRAP"
            seed = int.from_bytes(hashlib.sha256(seed_text.encode()).digest()[:8], "big")
            paired_res = paired_cluster_bootstrap(
                cb_rows, log_rows, bootstrap_iterations, seed
            )
            for metric, res in paired_res.items():
                is_sig = (
                    res["delta_ci_lower"] is not None
                    and res["delta_ci_upper"] is not None
                    and (
                        res["delta_ci_lower"] > 0
                        or res["delta_ci_upper"] < 0
                    )
                )
                paired_comparison_rows.append(
                    {
                        "regime": regime,
                        "catboost_model": cb_model_name,
                        "catboost_feature_set": candidate["feature_set"],
                        "catboost_weighting": candidate["weighting"],
                        "logistic_benchmark": log_model_name,
                        "metric": metric,
                        "catboost_point": res["catboost_point"],
                        "logistic_point": res["logistic_point"],
                        "delta_point": res["delta_point"],
                        "delta_ci_lower": res["delta_ci_lower"],
                        "delta_ci_upper": res["delta_ci_upper"],
                        "is_significant_at_95": is_sig,
                    }
                )

    # Aggregate feature importance across folds
    mean_importances: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for rec in feature_importance_records:
        key = (rec["regime"], rec["model"], rec["feature"])
        mean_importances[key].append(rec["importance"])

    aggregated_feature_importances = []
    for (regime, model, feat), vals in sorted(mean_importances.items()):
        aggregated_feature_importances.append(
            {
                "regime": regime,
                "model": model,
                "feature": feat,
                "mean_importance": float(np.mean(vals)),
                "std_importance": float(np.std(vals)),
                "min_importance": float(np.min(vals)),
                "max_importance": float(np.max(vals)),
                "fold_count": len(vals),
            }
        )

    # Write output artifacts
    metric_fields = list(
        _point_metrics(np.asarray([0, 1]), np.asarray([0.1, 0.9]), np.asarray([0, 1]))
    )
    fold_fields = [
        "regime",
        "evaluation_month",
        "model",
        "feature_set",
        "weighting",
        "training_rows",
        "training_month_min",
        "training_month_max",
        "maximum_training_label_window_end",
        "training_positives",
        "training_positive_rate",
        "evaluation_rows",
        "evaluation_positives",
        "evaluation_positive_rate",
        "predicted_positives",
        "decision_threshold",
        "input_feature_count",
        *metric_fields,
    ]
    aggregate_fields = [
        "regime",
        "model",
        "feature_set",
        "weighting",
        "evaluation_folds",
        "evaluation_rows",
        "positives",
        "positive_rate",
        "predicted_positives",
        "decision_threshold",
        *metric_fields,
        "fold_ap_mean",
        "fold_ap_std",
        "fold_ap_min",
        "fold_ap_max",
        "feb_2025_ap",
        "pooled_ap_without_feb_2025",
    ]
    comparison_fields = aggregate_fields + [
        "ap_rank_within_regime",
        "is_regime_winner",
        "prevalence_average_precision",
        "ap_delta_vs_prevalence",
        "lagged_rule_average_precision",
        "ap_delta_vs_lagged_rule",
        "winning_logistic_model",
        "winning_logistic_average_precision",
        "ap_delta_vs_winning_logistic",
    ]
    prediction_fields = [
        "project_code",
        "report_month",
        "identifier_regime",
        "continuous_segment",
        "model",
        "feature_set",
        "weighting",
        "actual_label",
        "predicted_probability",
        "predicted_label",
    ]
    ci_fields = [
        "regime",
        "model",
        "feature_set",
        "weighting",
        "method",
        "cluster_count",
        "iterations",
        "metric",
        "point_estimate",
        "ci_lower",
        "ci_upper",
    ]
    paired_fields = [
        "regime",
        "catboost_model",
        "catboost_feature_set",
        "catboost_weighting",
        "logistic_benchmark",
        "metric",
        "catboost_point",
        "logistic_point",
        "delta_point",
        "delta_ci_lower",
        "delta_ci_upper",
        "is_significant_at_95",
    ]
    feat_imp_fields = [
        "regime",
        "model",
        "feature",
        "mean_importance",
        "std_importance",
        "min_importance",
        "max_importance",
        "fold_count",
    ]

    output_paths = {
        "candidate_model_comparison.csv": output_dir / "candidate_model_comparison.csv",
        "fold_metrics.csv": output_dir / "fold_metrics.csv",
        "regime_aggregates.csv": output_dir / "regime_aggregates.csv",
        "predictions.csv": output_dir / "predictions.csv",
        "feature_lists.json": output_dir / "feature_lists.json",
        "feature_importance.csv": output_dir / "feature_importance.csv",
        "cluster_bootstrap_cis.csv": output_dir / "cluster_bootstrap_cis.csv",
        "paired_logistic_comparison.csv": output_dir / "paired_logistic_comparison.csv",
        "preprocessing_fit_audit.json": output_dir / "preprocessing_fit_audit.json",
    }

    _write_csv(output_paths["candidate_model_comparison.csv"], comparison_fields, comparison)
    _write_csv(output_paths["fold_metrics.csv"], fold_fields, fold_metrics)
    _write_csv(output_paths["regime_aggregates.csv"], aggregate_fields, aggregates)
    _write_csv(output_paths["predictions.csv"], prediction_fields, predictions)
    _write_csv(output_paths["cluster_bootstrap_cis.csv"], ci_fields, ci_rows)
    _write_csv(
        output_paths["paired_logistic_comparison.csv"], paired_fields, paired_comparison_rows
    )
    _write_csv(
        output_paths["feature_importance.csv"],
        feat_imp_fields,
        aggregated_feature_importances,
    )

    output_paths["feature_lists.json"].write_text(
        json.dumps(
            {
                regime: {
                    name: {
                        "features": features,
                        "rationale": CATBOOST_FEATURE_SET_RATIONALE[regime][name],
                    }
                    for name, features in sets.items()
                }
                for regime, sets in CATBOOST_FEATURE_SETS.items()
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    output_paths["preprocessing_fit_audit.json"].write_text(
        json.dumps(preprocessing_audit, indent=2) + "\n", encoding="utf-8"
    )

    generated_files = {}
    for name, path in output_paths.items():
        entry: dict[str, Any] = {"sha256": sha256(path)}
        if path.suffix == ".csv":
            entry["rows"] = len(_read_csv(path))
        generated_files[name] = entry

    # Recommendations and summary
    legacy_winner = winners["LEGACY"]
    modern_winner = winners["MODERN"]

    # Check paired test significance for primary winners
    legacy_paired_ap = next(
        row
        for row in paired_comparison_rows
        if row["regime"] == "LEGACY"
        and row["catboost_model"] == legacy_winner["model"]
        and row["metric"] == "average_precision"
    )
    modern_paired_ap = next(
        row
        for row in paired_comparison_rows
        if row["regime"] == "MODERN"
        and row["catboost_model"] == modern_winner["model"]
        and row["metric"] == "average_precision"
    )

    recommendations = {
        "LEGACY": {
            "winner_model": legacy_winner["model"],
            "catboost_ap": legacy_winner["average_precision"],
            "logistic_benchmark_ap": legacy_winner["winning_logistic_average_precision"],
            "ap_delta": legacy_winner["catboost_minus_logistic_ap"],
            "delta_95_ci": [
                legacy_paired_ap["delta_ci_lower"],
                legacy_paired_ap["delta_ci_upper"],
            ],
            "is_significant_at_95": legacy_paired_ap["is_significant_at_95"],
            "recommendation": (
                "PREFER_CATBOOST"
                if legacy_paired_ap["is_significant_at_95"]
                and legacy_winner["catboost_minus_logistic_ap"] > 0
                else (
                    "INCONCLUSIVE"
                    if abs(legacy_winner["catboost_minus_logistic_ap"]) < 0.01
                    or not legacy_paired_ap["is_significant_at_95"]
                    else "KEEP_LOGISTIC"
                )
            ),
        },
        "MODERN": {
            "winner_model": modern_winner["model"],
            "catboost_ap": modern_winner["average_precision"],
            "logistic_benchmark_ap": modern_winner["winning_logistic_average_precision"],
            "ap_delta": modern_winner["catboost_minus_logistic_ap"],
            "delta_95_ci": [
                modern_paired_ap["delta_ci_lower"],
                modern_paired_ap["delta_ci_upper"],
            ],
            "is_significant_at_95": modern_paired_ap["is_significant_at_95"],
            "recommendation": (
                "PREFER_CATBOOST"
                if modern_paired_ap["is_significant_at_95"]
                and modern_winner["catboost_minus_logistic_ap"] > 0
                else (
                    "INCONCLUSIVE"
                    if abs(modern_winner["catboost_minus_logistic_ap"]) < 0.01
                    or not modern_paired_ap["is_significant_at_95"]
                    else "KEEP_LOGISTIC"
                )
            ),
        },
    }

    configuration = {
        "evaluation_name": "schedule_extension_3m_catboost_challenger_v1",
        "runtime_versions": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "scikit_learn": sklearn.__version__,
            "catboost": cb.__version__,
            "pandas": pd.__version__,
        },
        "target": TARGET,
        "horizon_months": HORIZON,
        "source_manifests": {
            "dataset_manifest_sha256": sha256(dataset_manifest_path),
            "baseline_evaluation_manifest_sha256": sha256(baseline_manifest_path),
            "refinement_manifest_sha256": sha256(refinement_manifest_path),
        },
        "canonical_hashes": canonical_hashes,
        "evaluation_origins": EVALUATION_ORIGINS,
        "feature_sets": CATBOOST_FEATURE_SETS,
        "feature_set_rationale": CATBOOST_FEATURE_SET_RATIONALE,
        "weight_variants": CATBOOST_WEIGHT_VARIANTS,
        "catboost_params": CATBOOST_PARAMS,
        "preprocessing_policy": {
            "categorical": (
                "Native CatBoost categorical handling with string missingness sentinel "
                f"'{CATEGORICAL_MISSING_SENTINEL}'; zero evaluation category information enters training."
            ),
            "numeric": (
                "Numeric missing values preserved as NaN; native CatBoost tree splits handle "
                "missingness directions without artificial imputation."
            ),
            "class_weighting": (
                "auto_class_weights='Balanced' is computed exclusively from each walk-forward "
                "training fold; no evaluation-fold prevalence is used."
            ),
        },
        "embargo": "T_train + 3 calendar months < evaluation origin E (strict).",
        "selection_criterion": "Concatenated out-of-fold average precision / PR-AUC within regime.",
        "calibration": "No calibration fitted; natural probability distributions reported.",
        "bootstrap": {
            "method": "PROJECT_CLUSTER_BOOTSTRAP",
            "iterations": bootstrap_iterations,
            "confidence": 0.95,
            "semantics": "Sample project_code clusters with replacement and retain all OOF rows per draw.",
        },
        "winners": winners,
        "recommendations": recommendations,
        "skipped_folds": skipped_folds,
        "validation": {
            "prohibited_feature_intersection": leakage,
            "declared_features_missing_from_manifest": missing,
            "evaluated_fold_count": len(
                {(row["regime"], row["evaluation_month"]) for row in fold_metrics}
            ),
            "embargo_violations": 0,
            "random_split_created": False,
            "row_shuffle_performed": False,
            "calibration_fitted": False,
            "other_nonlinear_models_implemented": [],
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
    print(json.dumps(result["recommendations"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
