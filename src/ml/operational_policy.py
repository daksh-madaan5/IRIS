"""Approved calibration and operational-policy evaluation for IRIS v1.

The model-family decisions are closed: Legacy uses unweighted full-v1
CatBoost with raw operational probabilities, while Modern uses unweighted
static-only Logistic Regression with leakage-safe temporal Platt scaling when
the approved nested-OOF minimum is met.  Main and nested embargoes are strict.
No random split, in-sample threshold fallback, test-fold threshold fitting,
secondary target, or additional model family is permitted here.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
from pathlib import Path
from typing import Any, Iterable, Sequence

import catboost as cb
import numpy as np
import scipy
import sklearn
from sklearn.linear_model import LogisticRegression

from src.ml.challenger_catboost import (
    CATBOOST_PARAMS,
    fit_catboost_variant,
    prepare_catboost_df,
)
from src.ml.dataset_builder import (
    COMPLETED_SHA256,
    HORIZON,
    ONGOING_SHA256,
    sha256,
    training_reference_is_embargo_safe,
)
from src.ml.evaluate_baselines import (
    BOOTSTRAP_ITERATIONS,
    EVALUATION_ORIGINS,
    PROHIBITED_FEATURES,
    RANDOM_SEED,
    TARGET,
    FoldPreprocessor,
    _point_metrics,
    calibration_rows,
    select_training_rows,
)
from src.ml.refine_logistic import project_cluster_intervals
from src.ml.robustness_audit import FULL_V1_FEATURES, STATIC_AT_T_FEATURES


LOCKED_MODELS = {
    "LEGACY": "catboost_full_v1__unweighted",
    "MODERN": "logistic_static_only__unweighted",
}
LOCKED_FEATURES = {
    "LEGACY": list(FULL_V1_FEATURES),
    "MODERN": list(STATIC_AT_T_FEATURES),
}

RECALL_FLOORS = (0.50, 0.60, 0.70, 0.80)
PRECISION_FLOORS = (0.30, 0.40, 0.50)
TOP_K = {"LEGACY": (50, 100, 150, 200), "MODERN": (50, 100, 200)}
ALERT_RATE_CAPS = (0.15, 0.20, 0.25)
TOP_SECTORS = (
    "ROAD TRANSPORT AND HIGHWAYS",
    "RAILWAYS",
    "PETROLEUM",
    "POWER",
)

CALIBRATION_MINIMUM_CANDIDATES = (
    {
        "criterion": "MIN_500_ROWS_1_MONTH_50_PER_CLASS",
        "minimum_rows": 500,
        "minimum_months": 1,
        "minimum_per_class": 50,
        "selected": False,
    },
    {
        "criterion": "MIN_750_ROWS_1_MONTH_75_PER_CLASS",
        "minimum_rows": 750,
        "minimum_months": 1,
        "minimum_per_class": 75,
        "selected": False,
    },
    {
        "criterion": "MIN_1000_ROWS_2_MONTHS_100_PER_CLASS",
        "minimum_rows": 1000,
        "minimum_months": 2,
        "minimum_per_class": 100,
        "selected": True,
    },
)
SELECTED_MINIMUM = next(item for item in CALIBRATION_MINIMUM_CANDIDATES if item["selected"])


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _serialise(value: Any) -> Any:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    if isinstance(value, (float, np.floating)):
        return format(float(value), ".15g")
    if isinstance(value, bool):
        return str(value)
    return value


def _write_csv(path: Path, fields: Sequence[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _serialise(row.get(field)) for field in fields})


def fit_locked_scores(
    regime: str,
    training_rows: Sequence[dict[str, str]],
    scoring_rows: Sequence[dict[str, str]],
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Fit the closed v1 model and return raw probabilities and raw logits."""
    if regime == "LEGACY":
        probabilities, model, _ = fit_catboost_variant(
            training_rows, scoring_rows, LOCKED_FEATURES[regime], None
        )
        x_score, _ = prepare_catboost_df(scoring_rows, LOCKED_FEATURES[regime])
        logits = np.asarray(
            model.predict(x_score, prediction_type="RawFormulaVal"), dtype=float
        ).reshape(-1)
        return probabilities, logits, {
            "model_class": type(model).__name__,
            "feature_count": len(LOCKED_FEATURES[regime]),
            "catboost_params": CATBOOST_PARAMS,
        }

    processor = FoldPreprocessor(LOCKED_FEATURES[regime]).fit(training_rows)
    x_train = processor.transform(training_rows)
    x_score = processor.transform(scoring_rows)
    y_train = np.asarray([int(row[TARGET]) for row in training_rows], dtype=int)
    model = LogisticRegression(
        l1_ratio=0.0,
        C=1.0,
        solver="lbfgs",
        max_iter=2000,
        class_weight=None,
        random_state=RANDOM_SEED,
    )
    model.fit(x_train, y_train)
    return model.predict_proba(x_score)[:, 1], model.decision_function(x_score), {
        "model_class": type(model).__name__,
        "feature_count": len(LOCKED_FEATURES[regime]),
        "preprocessor": processor.audit(scoring_rows),
    }


def fit_platt(logits: np.ndarray, labels: np.ndarray) -> tuple[float, float, LogisticRegression]:
    """Fit two-parameter Platt scaling directly on raw model logits."""
    if logits.ndim != 1:
        raise ValueError("Platt inputs must be one-dimensional raw logits")
    if len(logits) != len(labels) or len(np.unique(labels)) != 2:
        raise ValueError("Platt fitting requires aligned logits and both target classes")
    model = LogisticRegression(
        l1_ratio=0.0,
        C=1_000_000.0,
        solver="lbfgs",
        max_iter=2000,
        class_weight=None,
        random_state=RANDOM_SEED,
    )
    model.fit(logits.reshape(-1, 1), labels)
    return float(model.coef_[0, 0]), float(model.intercept_[0]), model


def apply_platt(logits: np.ndarray, slope: float, intercept: float) -> np.ndarray:
    values = np.clip(slope * logits + intercept, -709.0, 709.0)
    return 1.0 / (1.0 + np.exp(-values))


def minimum_status(
    rows: Sequence[dict[str, Any]], criterion: dict[str, Any]
) -> tuple[bool, dict[str, Any]]:
    labels = np.asarray([int(row["actual_label"]) for row in rows], dtype=int)
    positives = int(labels.sum()) if len(labels) else 0
    negatives = int(len(labels) - positives)
    months = sorted({str(row["report_month"]) for row in rows})
    active = (
        len(rows) >= criterion["minimum_rows"]
        and len(months) >= criterion["minimum_months"]
        and positives >= criterion["minimum_per_class"]
        and negatives >= criterion["minimum_per_class"]
    )
    return active, {
        "pool_rows": len(rows),
        "pool_month_count": len(months),
        "pool_months": ";".join(months),
        "pool_positives": positives,
        "pool_negatives": negatives,
        "pool_prevalence": positives / len(rows) if rows else None,
    }


def generate_nested_oof_month(
    regime: str,
    target_month: str,
    regime_rows: Sequence[dict[str, str]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Generate one target month's scores using only strict sub-embargo history."""
    target_rows = [row for row in regime_rows if row["report_month"] == target_month]
    sub_training = select_training_rows(regime_rows, regime, target_month)
    reasons = []
    if not target_rows:
        reasons.append("NO_TARGET_ROWS")
    if not sub_training:
        reasons.append("NO_SUBTRAINING_ROWS")
    if sub_training and len({row[TARGET] for row in sub_training}) < 2:
        reasons.append("SUBTRAINING_TARGET_HAS_ONE_CLASS")
    if reasons:
        return [], {
            "regime": regime,
            "target_month": target_month,
            "status": "SKIPPED",
            "reason": "|".join(reasons),
            "target_rows": len(target_rows),
            "subtraining_rows": len(sub_training),
        }
    if any(
        not training_reference_is_embargo_safe(row["report_month"], target_month, HORIZON)
        for row in sub_training
    ):
        raise RuntimeError(f"Nested embargo violation for {regime} target {target_month}")
    maximum_end = max(row["target_window_end_month"] for row in sub_training)
    if maximum_end >= target_month:
        raise RuntimeError(f"Nested label window reaches target month {target_month}")
    probabilities, logits, model_audit = fit_locked_scores(
        regime, sub_training, target_rows
    )
    records = [
        {
            "project_code": row["project_code"],
            "report_month": target_month,
            "identifier_regime": regime,
            "actual_label": int(row[TARGET]),
            "raw_probability": float(probabilities[index]),
            "raw_logit": float(logits[index]),
            "subtraining_rows": len(sub_training),
            "subtraining_month_min": min(row["report_month"] for row in sub_training),
            "subtraining_month_max": max(row["report_month"] for row in sub_training),
            "maximum_subtraining_label_window_end": maximum_end,
        }
        for index, row in enumerate(target_rows)
    ]
    return records, {
        "regime": regime,
        "target_month": target_month,
        "status": "GENERATED",
        "reason": "",
        "target_rows": len(target_rows),
        "target_positives": sum(int(row[TARGET]) for row in target_rows),
        "subtraining_rows": len(sub_training),
        "subtraining_month_min": min(row["report_month"] for row in sub_training),
        "subtraining_month_max": max(row["report_month"] for row in sub_training),
        "maximum_subtraining_label_window_end": maximum_end,
        "model_audit": model_audit,
    }


def select_recall_threshold(
    scores: np.ndarray, labels: np.ndarray, recall_floor: float
) -> tuple[float | None, dict[str, Any]]:
    """Highest historical threshold whose recall reaches the candidate floor."""
    best = None
    best_metrics: dict[str, Any] = {}
    for threshold in np.unique(scores):
        metrics = confusion_metrics(labels, scores >= threshold)
        if metrics["recall"] is not None and metrics["recall"] >= recall_floor:
            if best is None or float(threshold) > best:
                best = float(threshold)
                best_metrics = metrics
    return best, best_metrics


def select_precision_threshold(
    scores: np.ndarray, labels: np.ndarray, precision_floor: float
) -> tuple[float | None, dict[str, Any]]:
    """Lowest historical threshold satisfying the approved precision floor."""
    for threshold in np.unique(scores):
        metrics = confusion_metrics(labels, scores >= threshold)
        if metrics["precision"] is not None and metrics["precision"] >= precision_floor:
            return float(threshold), metrics
    return None, {}


def confusion_metrics(labels: np.ndarray, predicted: np.ndarray) -> dict[str, Any]:
    labels = labels.astype(int)
    predicted = predicted.astype(bool)
    tp = int(((labels == 1) & predicted).sum())
    fp = int(((labels == 0) & predicted).sum())
    fn = int(((labels == 1) & ~predicted).sum())
    tn = int(((labels == 0) & ~predicted).sum())
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and precision + recall > 0
        else 0.0 if precision is not None and recall is not None else None
    )
    return {
        "alert_count": int(predicted.sum()),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def deterministic_rank(scores: np.ndarray, rows: Sequence[dict[str, str]]) -> np.ndarray:
    tie_keys = np.asarray([f"{row['project_code']}:{index:08d}" for index, row in enumerate(rows)])
    return np.lexsort((tie_keys, -scores))


def top_k_metrics(
    scores: np.ndarray,
    labels: np.ndarray,
    rows: Sequence[dict[str, str]],
    k: int,
) -> dict[str, Any]:
    applied = min(k, len(rows))
    predicted = np.zeros(len(rows), dtype=bool)
    predicted[deterministic_rank(scores, rows)[:applied]] = True
    result = confusion_metrics(labels, predicted)
    result["requested_k"] = k
    result["applied_k"] = applied
    result["population_permits_requested_k"] = len(rows) >= k
    return result


def _policy_fold_row(
    regime: str,
    evaluation_month: str,
    policy: str,
    candidate_value: float,
    threshold_status: str,
    threshold: float | None,
    historical: dict[str, Any],
    evaluation_scores: np.ndarray,
    evaluation_labels: np.ndarray,
    evaluation_rows: Sequence[dict[str, str]],
    calibration_active: bool,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "regime": regime,
        "evaluation_month": evaluation_month,
        "locked_model": LOCKED_MODELS[regime],
        "policy": policy,
        "candidate_value": candidate_value,
        "threshold_status": threshold_status,
        "selected_threshold": threshold,
        "threshold_frozen_before_evaluation": True,
        "calibration_active": calibration_active,
        "evaluation_rows": len(evaluation_rows),
        "evaluation_positives": int(evaluation_labels.sum()),
        "historical_alert_count": historical.get("alert_count"),
        "historical_precision": historical.get("precision"),
        "historical_recall": historical.get("recall"),
        "alert_count": None,
        "alert_rate": None,
        "tp": None,
        "fp": None,
        "fn": None,
        "tn": None,
        "precision": None,
        "recall": None,
        "f1": None,
        "precision_at_100": top_k_metrics(
            evaluation_scores, evaluation_labels, evaluation_rows, 100
        )["precision"],
        "precision_at_200": (
            top_k_metrics(evaluation_scores, evaluation_labels, evaluation_rows, 200)["precision"]
            if len(evaluation_rows) >= 200
            else None
        ),
    }
    if threshold_status == "AVAILABLE" and threshold is not None:
        metrics = confusion_metrics(evaluation_labels, evaluation_scores >= threshold)
        record.update(metrics)
        record["alert_rate"] = metrics["alert_count"] / len(evaluation_rows)
    return record


def _freeze_audit(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    """Persist thresholds and calibrator parameters before evaluation scoring."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(list(rows), indent=2) + "\n", encoding="utf-8")


def _aggregate_policy_rows(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    keys = sorted({(row["regime"], row["policy"], row["candidate_value"]) for row in rows})
    for regime, policy, candidate in keys:
        selected = [
            row for row in rows
            if row["regime"] == regime and row["policy"] == policy
            and row["candidate_value"] == candidate
        ]
        available = [row for row in selected if row["threshold_status"] == "AVAILABLE"]
        if available:
            tp = sum(int(row["tp"]) for row in available)
            fp = sum(int(row["fp"]) for row in available)
            fn = sum(int(row["fn"]) for row in available)
            tn = sum(int(row["tn"]) for row in available)
            precision = tp / (tp + fp) if tp + fp else None
            recall = tp / (tp + fn) if tp + fn else None
            f1 = 2 * precision * recall / (precision + recall) if precision and recall else 0.0
            alert_counts = np.asarray([int(row["alert_count"]) for row in available], dtype=float)
            alert_rates = np.asarray([float(row["alert_rate"]) for row in available], dtype=float)
            recalls = np.asarray([float(row["recall"]) for row in available], dtype=float)
            precisions = np.asarray([float(row["precision"]) for row in available], dtype=float)
        else:
            tp = fp = fn = tn = 0
            precision = recall = f1 = None
            alert_counts = alert_rates = recalls = precisions = np.asarray([], dtype=float)
        result.append(
            {
                "regime": regime,
                "policy": policy,
                "candidate_value": candidate,
                "total_folds": len(selected),
                "available_folds": len(available),
                "unavailable_folds": len(selected) - len(available),
                "evaluation_rows_available": sum(int(row["evaluation_rows"]) for row in available),
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "tn": tn,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "mean_alert_count": float(alert_counts.mean()) if len(alert_counts) else None,
                "min_alert_count": int(alert_counts.min()) if len(alert_counts) else None,
                "max_alert_count": int(alert_counts.max()) if len(alert_counts) else None,
                "mean_alert_rate": float(alert_rates.mean()) if len(alert_rates) else None,
                "min_alert_rate": float(alert_rates.min()) if len(alert_rates) else None,
                "max_alert_rate": float(alert_rates.max()) if len(alert_rates) else None,
                "fold_precision_mean": float(precisions.mean()) if len(precisions) else None,
                "fold_precision_std": float(precisions.std()) if len(precisions) else None,
                "fold_recall_mean": float(recalls.mean()) if len(recalls) else None,
                "fold_recall_std": float(recalls.std()) if len(recalls) else None,
            }
        )
    return result


def run(root: Path, bootstrap_iterations: int = BOOTSTRAP_ITERATIONS) -> dict[str, Any]:
    root = root.resolve()
    dataset_dir = root / "data/ml/schedule_extension_3m"
    evaluation_dir = dataset_dir / "evaluation"
    catboost_dir = evaluation_dir / "catboost"
    refinement_dir = evaluation_dir / "refinement"
    output_dir = evaluation_dir / "operational_policy"
    output_dir.mkdir(parents=True, exist_ok=True)

    dataset_manifest_path = dataset_dir / "manifest.json"
    catboost_manifest_path = catboost_dir / "configuration_manifest.json"
    refinement_manifest_path = refinement_dir / "configuration_manifest.json"
    dataset_manifest = json.loads(dataset_manifest_path.read_text(encoding="utf-8"))
    catboost_manifest = json.loads(catboost_manifest_path.read_text(encoding="utf-8"))
    refinement_manifest = json.loads(refinement_manifest_path.read_text(encoding="utf-8"))

    if dataset_manifest["target"] != TARGET:
        raise RuntimeError(f"Unexpected target: {dataset_manifest['target']}")
    if catboost_manifest["recommendations"]["LEGACY"]["recommendation"] != "PREFER_CATBOOST":
        raise RuntimeError("Legacy CatBoost family decision contradicts the approved policy")
    if catboost_manifest["winners"]["LEGACY"]["model"] != LOCKED_MODELS["LEGACY"]:
        raise RuntimeError("Locked Legacy model contradicts CatBoost results")
    if refinement_manifest["winners"]["MODERN"]["model"] != LOCKED_MODELS["MODERN"]:
        raise RuntimeError("Locked Modern model contradicts Logistic refinement")
    if catboost_manifest["evaluation_origins"] != EVALUATION_ORIGINS:
        raise RuntimeError("CatBoost origins contradict the accepted fold schedule")
    if refinement_manifest["evaluation_origins"] != EVALUATION_ORIGINS:
        raise RuntimeError("Logistic origins contradict the accepted fold schedule")
    declared = set(LOCKED_FEATURES["LEGACY"] + LOCKED_FEATURES["MODERN"])
    leakage = sorted(declared & PROHIBITED_FEATURES)
    missing = sorted(declared - set(dataset_manifest["feature_columns"]))
    if leakage or missing:
        raise RuntimeError(f"Locked features invalid; leakage={leakage}, missing={missing}")

    canonical_hashes = {
        "projects_monthly.csv": sha256(root / "data/processed/projects_monthly.csv"),
        "projects_completed.csv": sha256(root / "data/processed/projects_completed.csv"),
    }
    expected_hashes = {
        "projects_monthly.csv": ONGOING_SHA256,
        "projects_completed.csv": COMPLETED_SHA256,
    }
    if canonical_hashes != expected_hashes:
        raise RuntimeError(f"Canonical hash mismatch; refusing operational evaluation: {canonical_hashes}")

    rows_by_regime = {
        "LEGACY": _read_csv(dataset_dir / "eligible_legacy.csv"),
        "MODERN": _read_csv(dataset_dir / "eligible_modern.csv"),
    }
    accepted_locked_scores: dict[tuple[str, str, str], float] = {}
    for row in _read_csv(catboost_dir / "predictions.csv"):
        if row["identifier_regime"] == "LEGACY" and row["model"] == LOCKED_MODELS["LEGACY"]:
            accepted_locked_scores[("LEGACY", row["project_code"], row["report_month"])] = float(
                row["predicted_probability"]
            )
    for row in _read_csv(refinement_dir / "predictions.csv"):
        if row["identifier_regime"] == "MODERN" and row["model"] == LOCKED_MODELS["MODERN"]:
            accepted_locked_scores[("MODERN", row["project_code"], row["report_month"])] = float(
                row["predicted_probability"]
            )

    fold_calibration: list[dict[str, Any]] = []
    calibration_audit: list[dict[str, Any]] = []
    minimum_sensitivity: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    cap_rows: list[dict[str, Any]] = []
    topk_rows: list[dict[str, Any]] = []
    prediction_rows: list[dict[str, Any]] = []
    reliability: list[dict[str, Any]] = []
    nested_audit: list[dict[str, Any]] = []
    freeze_rows: list[dict[str, Any]] = []
    score_ci_rows: list[dict[str, Any]] = []
    sector_rows: list[dict[str, Any]] = []
    score_reconciliation: list[float] = []
    nested_cache: dict[tuple[str, str], list[dict[str, Any]]] = {}

    freeze_path = output_dir / "threshold_freeze_audit.json"
    _freeze_audit(freeze_path, freeze_rows)

    for regime in ("LEGACY", "MODERN"):
        regime_rows = rows_by_regime[regime]
        for evaluation_month in EVALUATION_ORIGINS[regime]:
            evaluation = [row for row in regime_rows if row["report_month"] == evaluation_month]
            training = select_training_rows(regime_rows, regime, evaluation_month)
            if not evaluation or not training or len({row[TARGET] for row in training}) < 2:
                raise RuntimeError(f"Approved fold became unusable: {regime} {evaluation_month}")
            if max(row["target_window_end_month"] for row in training) >= evaluation_month:
                raise RuntimeError(f"Main embargo violation: {regime} {evaluation_month}")

            training_months = sorted({row["report_month"] for row in training})
            for target_month in training_months:
                key = (regime, target_month)
                if key not in nested_cache:
                    records, audit = generate_nested_oof_month(
                        regime, target_month, regime_rows
                    )
                    nested_cache[key] = records
                    nested_audit.append(audit)
            calibration_pool = [
                row
                for month in training_months
                for row in nested_cache[(regime, month)]
            ]
            if any(row["report_month"] >= evaluation_month for row in calibration_pool):
                raise RuntimeError(f"Evaluation leakage in calibration pool: {regime} {evaluation_month}")
            selected_active, pool_summary = minimum_status(calibration_pool, SELECTED_MINIMUM)
            for criterion in CALIBRATION_MINIMUM_CANDIDATES:
                active, summary = minimum_status(calibration_pool, criterion)
                minimum_sensitivity.append(
                    {
                        "regime": regime,
                        "evaluation_month": evaluation_month,
                        **criterion,
                        **summary,
                        "criterion_satisfied": active,
                    }
                )

            pool_labels = np.asarray(
                [int(row["actual_label"]) for row in calibration_pool], dtype=int
            )
            pool_logits = np.asarray(
                [float(row["raw_logit"]) for row in calibration_pool], dtype=float
            )
            pool_raw = np.asarray(
                [float(row["raw_probability"]) for row in calibration_pool], dtype=float
            )
            slope = intercept = None
            platt_model = None
            diagnostic_platt_available = False
            if selected_active:
                slope, intercept, platt_model = fit_platt(pool_logits, pool_labels)
                diagnostic_platt_available = True
            calibration_active = bool(regime == "MODERN" and selected_active)
            threshold_available = bool(selected_active)

            threshold_score_pool = (
                apply_platt(pool_logits, slope, intercept)
                if calibration_active and slope is not None and intercept is not None
                else pool_raw
            )
            frozen_policies: list[dict[str, Any]] = []
            for floor in RECALL_FLOORS:
                if threshold_available:
                    threshold, historical = select_recall_threshold(
                        threshold_score_pool, pool_labels, floor
                    )
                    status = "AVAILABLE" if threshold is not None else "UNAVAILABLE"
                else:
                    threshold, historical, status = None, {}, "UNAVAILABLE"
                frozen_policies.append(
                    {
                        "policy": "RECALL_FLOOR",
                        "candidate_value": floor,
                        "threshold_status": status,
                        "threshold": threshold,
                        "historical_metrics": historical,
                    }
                )
            for floor in PRECISION_FLOORS:
                if threshold_available:
                    threshold, historical = select_precision_threshold(
                        threshold_score_pool, pool_labels, floor
                    )
                    status = "AVAILABLE" if threshold is not None else "UNAVAILABLE"
                else:
                    threshold, historical, status = None, {}, "UNAVAILABLE"
                frozen_policies.append(
                    {
                        "policy": "PRECISION_FLOOR",
                        "candidate_value": floor,
                        "threshold_status": status,
                        "threshold": threshold,
                        "historical_metrics": historical,
                    }
                )

            freeze_entry = {
                "regime": regime,
                "evaluation_month": evaluation_month,
                "locked_model": LOCKED_MODELS[regime],
                "training_months": training_months,
                "maximum_training_label_window_end": max(
                    row["target_window_end_month"] for row in training
                ),
                "calibration_pool": pool_summary,
                "selected_minimum": SELECTED_MINIMUM,
                "calibration_active": calibration_active,
                "diagnostic_platt_available": diagnostic_platt_available,
                "platt_slope": slope,
                "platt_intercept": intercept,
                "policies": frozen_policies,
                "frozen_before_evaluation_scoring": True,
            }
            freeze_rows.append(freeze_entry)
            _freeze_audit(freeze_path, freeze_rows)

            raw_probability, raw_logit, model_audit = fit_locked_scores(
                regime, training, evaluation
            )
            y_eval = np.asarray([int(row[TARGET]) for row in evaluation], dtype=int)
            for index, row in enumerate(evaluation):
                key = (regime, row["project_code"], row["report_month"])
                score_reconciliation.append(abs(float(raw_probability[index]) - accepted_locked_scores[key]))
            operational_probability = (
                apply_platt(raw_logit, slope, intercept)
                if calibration_active and slope is not None and intercept is not None
                else raw_probability.copy()
            )
            diagnostic_probability = (
                apply_platt(raw_logit, slope, intercept)
                if diagnostic_platt_available and slope is not None and intercept is not None
                else None
            )
            raw_metrics = _point_metrics(
                y_eval, raw_probability, (raw_probability >= 0.5).astype(int)
            )
            operational_metrics = _point_metrics(
                y_eval, operational_probability, (operational_probability >= 0.5).astype(int)
            )
            diagnostic_metrics = (
                _point_metrics(
                    y_eval, diagnostic_probability, (diagnostic_probability >= 0.5).astype(int)
                )
                if diagnostic_probability is not None
                else {}
            )
            calibration_audit.append(
                {
                    "regime": regime,
                    "evaluation_month": evaluation_month,
                    "locked_model": LOCKED_MODELS[regime],
                    "main_training_rows": len(training),
                    "main_training_months": ";".join(training_months),
                    "main_training_month_min": min(training_months),
                    "main_training_month_max": max(training_months),
                    "maximum_main_training_label_window_end": max(
                        row["target_window_end_month"] for row in training
                    ),
                    **pool_summary,
                    "selected_minimum_criterion": SELECTED_MINIMUM["criterion"],
                    "minimum_satisfied": selected_active,
                    "calibration_active": calibration_active,
                    "calibration_status": (
                        "ACTIVE_PLATT" if calibration_active else "INACTIVE_RAW_OPERATIONAL_SCORE"
                    ),
                    "threshold_status": "AVAILABLE" if threshold_available else "UNAVAILABLE",
                    "platt_slope": slope,
                    "platt_intercept": intercept,
                    "platt_input": "RAW_DECISION_LOGIT" if diagnostic_platt_available else None,
                    "no_in_sample_fallback": True,
                    "nested_embargo_violations": 0,
                }
            )
            fold_calibration.append(
                {
                    "regime": regime,
                    "evaluation_month": evaluation_month,
                    "locked_model": LOCKED_MODELS[regime],
                    "evaluation_rows": len(evaluation),
                    "evaluation_positives": int(y_eval.sum()),
                    "evaluation_prevalence": float(y_eval.mean()),
                    **pool_summary,
                    "calibration_active": calibration_active,
                    "calibration_status": (
                        "ACTIVE_PLATT" if calibration_active else "INACTIVE_RAW_OPERATIONAL_SCORE"
                    ),
                    "platt_slope": slope if calibration_active else None,
                    "platt_intercept": intercept if calibration_active else None,
                    "diagnostic_platt_available": diagnostic_platt_available,
                    "diagnostic_platt_slope": slope,
                    "diagnostic_platt_intercept": intercept,
                    "raw_average_precision": raw_metrics["average_precision"],
                    "raw_roc_auc": raw_metrics["roc_auc"],
                    "raw_brier_score": raw_metrics["brier_score"],
                    "raw_ece_10bin": raw_metrics["ece_10bin"],
                    "operational_average_precision": operational_metrics["average_precision"],
                    "operational_roc_auc": operational_metrics["roc_auc"],
                    "operational_brier_score": operational_metrics["brier_score"],
                    "operational_ece_10bin": operational_metrics["ece_10bin"],
                    "diagnostic_platt_brier_score": diagnostic_metrics.get("brier_score"),
                    "diagnostic_platt_ece_10bin": diagnostic_metrics.get("ece_10bin"),
                    "brier_change_operational_minus_raw": operational_metrics["brier_score"]
                    - raw_metrics["brier_score"],
                    "ece_change_operational_minus_raw": operational_metrics["ece_10bin"]
                    - raw_metrics["ece_10bin"],
                    "ap_change_operational_minus_raw": operational_metrics["average_precision"]
                    - raw_metrics["average_precision"],
                    "roc_change_operational_minus_raw": operational_metrics["roc_auc"]
                    - raw_metrics["roc_auc"],
                    "precision_at_100": top_k_metrics(
                        operational_probability, y_eval, evaluation, 100
                    )["precision"],
                    "precision_at_200": (
                        top_k_metrics(operational_probability, y_eval, evaluation, 200)["precision"]
                        if len(evaluation) >= 200 else None
                    ),
                    "model_audit": json.dumps(model_audit, sort_keys=True),
                }
            )

            for score_type, score in (
                ("RAW", raw_probability),
                ("OPERATIONAL", operational_probability),
            ):
                if score_type == "OPERATIONAL" and np.array_equal(score, raw_probability):
                    continue
                reliability.extend(
                    calibration_rows(
                        y_eval, score, regime, LOCKED_MODELS[regime], score_type, evaluation_month
                    )
                )
                ci_input = [
                    {
                        "project_code": row["project_code"],
                        "actual_label": int(row[TARGET]),
                        "predicted_probability": float(score[index]),
                        "predicted_label": int(score[index] >= 0.5),
                    }
                    for index, row in enumerate(evaluation)
                ]
                seed_text = f"{RANDOM_SEED}:{regime}:{evaluation_month}:{score_type}:POLICY_CI"
                seed = int.from_bytes(hashlib.sha256(seed_text.encode()).digest()[:8], "big")
                intervals = project_cluster_intervals(ci_input, bootstrap_iterations, seed)
                points = _point_metrics(y_eval, score, (score >= 0.5).astype(int))
                for metric in ("average_precision", "roc_auc", "brier_score", "ece_10bin"):
                    score_ci_rows.append(
                        {
                            "regime": regime,
                            "evaluation_month": evaluation_month,
                            "score_type": score_type,
                            "metric": metric,
                            "point_estimate": points[metric],
                            "ci_lower": intervals[metric][0],
                            "ci_upper": intervals[metric][1],
                            "iterations": bootstrap_iterations,
                            "method": "PROJECT_CLUSTER_BOOTSTRAP",
                        }
                    )

            for item in frozen_policies:
                row = _policy_fold_row(
                    regime, evaluation_month, item["policy"], item["candidate_value"],
                    item["threshold_status"], item["threshold"], item["historical_metrics"],
                    operational_probability, y_eval, evaluation, calibration_active,
                )
                threshold_rows.append(row)
                if item["policy"] == "RECALL_FLOOR":
                    for cap in ALERT_RATE_CAPS:
                        cap_record = {
                            "regime": regime,
                            "evaluation_month": evaluation_month,
                            "policy": item["policy"],
                            "target_recall_floor": item["candidate_value"],
                            "alert_rate_cap": cap,
                            "threshold_status": item["threshold_status"],
                            "selected_threshold": item["threshold"],
                            "original_alert_count": row["alert_count"],
                            "original_alert_rate": row["alert_rate"],
                            "capped_alert_count": None,
                            "capped_alert_rate": None,
                            "alert_cap_triggered": None,
                            "suppressed_alerts": None,
                            "target_recall": item["candidate_value"],
                            "achieved_recall_before_cap": row["recall"],
                            "achieved_recall_after_cap": None,
                            "recall_shortfall": None,
                            "precision_after_cap": None,
                            "f1_after_cap": None,
                            "tp": None, "fp": None, "fn": None, "tn": None,
                        }
                        if item["threshold_status"] == "AVAILABLE" and item["threshold"] is not None:
                            original = operational_probability >= item["threshold"]
                            cap_count = min(int(original.sum()), int(math.floor(cap * len(evaluation))))
                            capped = np.zeros(len(evaluation), dtype=bool)
                            capped[deterministic_rank(operational_probability, evaluation)[:cap_count]] = True
                            capped_metrics = confusion_metrics(y_eval, capped)
                            cap_record.update(
                                {
                                    "capped_alert_count": cap_count,
                                    "capped_alert_rate": cap_count / len(evaluation),
                                    "alert_cap_triggered": int(original.sum()) > cap_count,
                                    "suppressed_alerts": int(original.sum()) - cap_count,
                                    "achieved_recall_after_cap": capped_metrics["recall"],
                                    "recall_shortfall": max(
                                        0.0, item["candidate_value"] - (capped_metrics["recall"] or 0.0)
                                    ),
                                    "precision_after_cap": capped_metrics["precision"],
                                    "f1_after_cap": capped_metrics["f1"],
                                    "tp": capped_metrics["tp"], "fp": capped_metrics["fp"],
                                    "fn": capped_metrics["fn"], "tn": capped_metrics["tn"],
                                }
                            )
                        cap_rows.append(cap_record)

            for k in TOP_K[regime]:
                metrics = top_k_metrics(operational_probability, y_eval, evaluation, k)
                topk_rows.append(
                    {
                        "regime": regime,
                        "evaluation_month": evaluation_month,
                        "locked_model": LOCKED_MODELS[regime],
                        "calibration_active": calibration_active,
                        "evaluation_rows": len(evaluation),
                        "evaluation_positives": int(y_eval.sum()),
                        **metrics,
                        "alert_rate": metrics["alert_count"] / len(evaluation),
                    }
                )

            for item in frozen_policies:
                if item["policy"] != "RECALL_FLOOR" or item["threshold_status"] != "AVAILABLE":
                    continue
                for sector in TOP_SECTORS:
                    indices = [i for i, row in enumerate(evaluation) if row["sector"] == sector]
                    if not indices:
                        continue
                    idx = np.asarray(indices, dtype=int)
                    sector_metrics = confusion_metrics(
                        y_eval[idx], operational_probability[idx] >= item["threshold"]
                    )
                    sector_rows.append(
                        {
                            "regime": regime,
                            "evaluation_month": evaluation_month,
                            "sector": sector,
                            "target_recall_floor": item["candidate_value"],
                            "selected_threshold": item["threshold"],
                            "rows": len(idx),
                            "positives": int(y_eval[idx].sum()),
                            **sector_metrics,
                        }
                    )

            rank = np.empty(len(evaluation), dtype=int)
            rank[deterministic_rank(operational_probability, evaluation)] = np.arange(1, len(evaluation) + 1)
            prediction_rows.extend(
                {
                    "project_code": row["project_code"],
                    "report_month": evaluation_month,
                    "identifier_regime": regime,
                    "continuous_segment": row["continuous_segment"],
                    "sector": row["sector"],
                    "locked_model": LOCKED_MODELS[regime],
                    "actual_label": int(row[TARGET]),
                    "raw_probability": float(raw_probability[index]),
                    "raw_logit": float(raw_logit[index]),
                    "operational_probability": float(operational_probability[index]),
                    "calibration_active": calibration_active,
                    "platt_slope": slope if calibration_active else None,
                    "platt_intercept": intercept if calibration_active else None,
                    "operational_rank": int(rank[index]),
                }
                for index, row in enumerate(evaluation)
            )

    policy_aggregates = _aggregate_policy_rows(threshold_rows)
    alert_volume = [
        {
            "regime": row["regime"],
            "policy": row["policy"],
            "candidate_value": row["candidate_value"],
            "available_folds": row["available_folds"],
            "mean_alert_count": row["mean_alert_count"],
            "min_alert_count": row["min_alert_count"],
            "max_alert_count": row["max_alert_count"],
            "mean_alert_rate": row["mean_alert_rate"],
            "min_alert_rate": row["min_alert_rate"],
            "max_alert_rate": row["max_alert_rate"],
            "precision": row["precision"],
            "recall": row["recall"],
            "fold_recall_std": row["fold_recall_std"],
        }
        for row in policy_aggregates
    ]

    max_reconciliation = max(score_reconciliation, default=math.inf)
    if max_reconciliation > 1e-8:
        raise RuntimeError(f"Locked model scores failed accepted reconciliation: {max_reconciliation}")

    fields = {
        "fold_calibration_metrics.csv": list(fold_calibration[0]),
        "calibration_pools_audit.csv": list(calibration_audit[0]),
        "calibration_minimum_sensitivity.csv": list(minimum_sensitivity[0]),
        "threshold_policy_fold_metrics.csv": list(threshold_rows[0]),
        "policy_aggregate_metrics.csv": list(policy_aggregates[0]),
        "alert_volume_sensitivity.csv": list(alert_volume[0]),
        "cap_sensitivity.csv": list(cap_rows[0]),
        "top_k_metrics.csv": list(topk_rows[0]),
        "predictions.csv": list(prediction_rows[0]),
        "reliability_bins.csv": [
            "regime", "model", "scope", "evaluation_month", "bin_index", "lower_bound",
            "upper_bound", "rows", "mean_predicted_probability", "observed_positive_rate",
        ],
        "threshold_free_cluster_bootstrap_cis.csv": list(score_ci_rows[0]),
        "sector_policy_metrics.csv": list(sector_rows[0]),
    }
    output_paths: dict[str, Path] = {}
    row_map = {
        "fold_calibration_metrics.csv": fold_calibration,
        "calibration_pools_audit.csv": calibration_audit,
        "calibration_minimum_sensitivity.csv": minimum_sensitivity,
        "threshold_policy_fold_metrics.csv": threshold_rows,
        "policy_aggregate_metrics.csv": policy_aggregates,
        "alert_volume_sensitivity.csv": alert_volume,
        "cap_sensitivity.csv": cap_rows,
        "top_k_metrics.csv": topk_rows,
        "predictions.csv": prediction_rows,
        "reliability_bins.csv": reliability,
        "threshold_free_cluster_bootstrap_cis.csv": score_ci_rows,
        "sector_policy_metrics.csv": sector_rows,
    }
    for name, rows in row_map.items():
        path = output_dir / name
        _write_csv(path, fields[name], rows)
        output_paths[name] = path
    nested_path = output_dir / "nested_oof_audit.json"
    nested_path.write_text(json.dumps(nested_audit, indent=2) + "\n", encoding="utf-8")
    output_paths["nested_oof_audit.json"] = nested_path
    output_paths["threshold_freeze_audit.json"] = freeze_path

    generated_files = {}
    for name, path in output_paths.items():
        item: dict[str, Any] = {"sha256": sha256(path)}
        if path.suffix == ".csv":
            item["rows"] = len(_read_csv(path))
        generated_files[name] = item

    configuration = {
        "evaluation_name": "schedule_extension_3m_calibration_operational_policy_v1",
        "runtime_versions": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "scikit_learn": sklearn.__version__,
            "catboost": cb.__version__,
        },
        "target": TARGET,
        "horizon_months": HORIZON,
        "source_manifests": {
            "dataset_manifest_sha256": sha256(dataset_manifest_path),
            "catboost_manifest_sha256": sha256(catboost_manifest_path),
            "refinement_manifest_sha256": sha256(refinement_manifest_path),
        },
        "canonical_hashes": canonical_hashes,
        "closed_model_decisions": {
            "LEGACY": {"decision": "PREFER_CATBOOST", "model": LOCKED_MODELS["LEGACY"]},
            "MODERN": {"decision": "KEEP_LOGISTIC", "model": LOCKED_MODELS["MODERN"]},
        },
        "locked_features": LOCKED_FEATURES,
        "evaluation_origins": EVALUATION_ORIGINS,
        "main_embargo": "T + 3 < E (strict)",
        "nested_embargo": "T' + 3 < T (strict)",
        "calibration_minimum_candidates": CALIBRATION_MINIMUM_CANDIDATES,
        "selected_calibration_minimum": SELECTED_MINIMUM,
        "selected_minimum_rationale": (
            "A two-parameter temporal calibrator must span at least two chronological OOF "
            "target months, at least 1,000 rows, and at least 100 observations per class. "
            "This prevents activation from M4's single-month 772-row pool while allowing "
            "M5's 2,110-row two-month pool; looser 500/750-row candidates are reported only "
            "as sensitivity analyses."
        ),
        "legacy_calibration_policy": (
            "No active layer. Raw CatBoost probabilities remain operational; historical "
            "nested-OOF Platt is diagnostic only when the selected minimum is met."
        ),
        "modern_calibration_policy": "Platt scaling on raw Logistic decision logits only.",
        "threshold_policy": {
            "no_in_sample_fallback": True,
            "recall_floors": RECALL_FLOORS,
            "precision_floors": PRECISION_FLOORS,
            "top_k": TOP_K,
            "cost_sensitive": "DEFERRED_NOT_IMPLEMENTED",
            "alert_rate_caps_sensitivity_only": ALERT_RATE_CAPS,
            "final_threshold_frozen": False,
        },
        "bootstrap": {
            "iterations": bootstrap_iterations,
            "confidence": 0.95,
            "method": "PROJECT_CLUSTER_BOOTSTRAP",
        },
        "validation": {
            "main_embargo_violations": 0,
            "nested_embargo_violations": 0,
            "evaluation_leakage_rows": 0,
            "in_sample_threshold_fallbacks": 0,
            "random_split_created": False,
            "row_shuffle_performed": False,
            "legacy_active_calibration_folds": [],
            "modern_active_calibration_folds": [
                row["evaluation_month"] for row in fold_calibration
                if row["regime"] == "MODERN" and row["calibration_active"]
            ],
            "locked_score_reconciliation_max_absolute_difference": max_reconciliation,
            "prohibited_feature_intersection": leakage,
            "declared_features_missing_from_manifest": missing,
            "other_model_families_implemented": [],
            "secondary_targets_implemented": [],
            "calibration_fitted_from_raw_logits_only": True,
            "canonical_hashes_unchanged": canonical_hashes == expected_hashes,
        },
        "fold_calibration_results": fold_calibration,
        "policy_aggregate_results": policy_aggregates,
        "generated_files": generated_files,
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
    print(json.dumps({
        "modern_active_calibration_folds": result["validation"]["modern_active_calibration_folds"],
        "generated_files": result["generated_files"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
