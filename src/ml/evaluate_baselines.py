"""Walk-forward baseline evaluation for the H=3 schedule-extension dataset.

The evaluator is deliberately narrow: it evaluates Legacy and Modern regimes
separately, uses only ``manifest.json["feature_columns"]``, applies the strict
``T_train + 3 < E`` embargo, and writes generated artifacts only beneath the ML
dataset's ``evaluation`` directory.
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

import numpy as np
import scipy
import sklearn
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from src.ml.dataset_builder import (
    COMPLETED_SHA256,
    HORIZON,
    ONGOING_SHA256,
    add_months,
    segment_for_month,
    sha256,
    training_reference_is_embargo_safe,
)


RANDOM_SEED = 20260829
BOOTSTRAP_ITERATIONS = 1000
TARGET = "target_effective_schedule_ext_3m"
CATEGORICAL_FEATURES = ("sector", "agency", "state")
PROHIBITED_FEATURES = {
    "project_code",
    "project_name",
    "eventually_completed",
    "completion_report_month",
    "baseline_completion_date",
    "target_event_month",
    "target_event_revised_completion_date",
    "extension_type",
    "target_window_end_month",
}

EVALUATION_ORIGINS = {
    "LEGACY": [
        "2023-07",
        "2023-08",
        "2024-06",
        "2024-07",
        "2024-08",
        "2024-09",
        "2024-10",
        "2024-11",
        "2024-12",
        "2025-01",
        "2025-02",
        "2025-03",
    ],
    "MODERN": ["2025-12", "2026-01", "2026-02", "2026-03", "2026-04"],
}

MODEL_ORDER = (
    "prevalence",
    "always_negative",
    "lagged_rule_latest_valid_transition",
    "logistic_l2_unweighted",
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, fields: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _serialise(row.get(field)) for field in fields})


def _serialise(value: Any) -> Any:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    if isinstance(value, (float, np.floating)):
        return format(float(value), ".15g")
    return value


def _as_float(value: str) -> float:
    if value is None or value.strip() == "":
        return math.nan
    return float(value)


class FoldPreprocessor:
    """Training-fold-only frequency encoding and numeric standardisation.

    Each numeric input expands to a standardised value and an explicit missingness
    indicator. Missing values receive 0 only in standardised matrix space (the
    training mean), never in a persisted source/feature column. Categorical unseen
    values receive frequency 0.
    """

    def __init__(self, feature_columns: Sequence[str]) -> None:
        self.feature_columns = list(feature_columns)
        self.categorical = [name for name in self.feature_columns if name in CATEGORICAL_FEATURES]
        self.numeric = [name for name in self.feature_columns if name not in CATEGORICAL_FEATURES]
        self.category_frequency: dict[str, dict[str, float]] = {}
        self.numeric_mean: dict[str, float] = {}
        self.numeric_scale: dict[str, float] = {}
        self.numeric_missing_count: dict[str, int] = {}
        self.fit_row_count = 0
        self.fitted = False

    @property
    def output_columns(self) -> list[str]:
        fields = [f"{name}__train_frequency" for name in self.categorical]
        for name in self.numeric:
            fields.extend((f"{name}__standardized", f"{name}__missing"))
        return fields

    def fit(self, rows: Sequence[dict[str, str]]) -> "FoldPreprocessor":
        if not rows:
            raise ValueError("Cannot fit preprocessing on an empty training fold")
        self.fit_row_count = len(rows)
        for name in self.categorical:
            counts = Counter((row.get(name, "") or "__MISSING__") for row in rows)
            self.category_frequency[name] = {
                category: count / len(rows) for category, count in sorted(counts.items())
            }
        for name in self.numeric:
            values = np.asarray([_as_float(row.get(name, "")) for row in rows], dtype=float)
            valid = values[np.isfinite(values)]
            self.numeric_missing_count[name] = int(len(values) - len(valid))
            if len(valid):
                mean = float(valid.mean())
                scale = float(valid.std())
                self.numeric_mean[name] = mean
                self.numeric_scale[name] = scale if scale > 0 else 1.0
            else:
                self.numeric_mean[name] = 0.0
                self.numeric_scale[name] = 1.0
        self.fitted = True
        return self

    def transform(self, rows: Sequence[dict[str, str]]) -> np.ndarray:
        if not self.fitted:
            raise RuntimeError("Preprocessor must be fit on training rows before transform")
        matrix = np.zeros((len(rows), len(self.output_columns)), dtype=float)
        for row_index, row in enumerate(rows):
            column_index = 0
            for name in self.categorical:
                category = row.get(name, "") or "__MISSING__"
                matrix[row_index, column_index] = self.category_frequency[name].get(category, 0.0)
                column_index += 1
            for name in self.numeric:
                value = _as_float(row.get(name, ""))
                if math.isnan(value):
                    matrix[row_index, column_index] = 0.0
                    matrix[row_index, column_index + 1] = 1.0
                else:
                    matrix[row_index, column_index] = (
                        value - self.numeric_mean[name]
                    ) / self.numeric_scale[name]
                column_index += 2
        return matrix

    def audit(self, evaluation_rows: Sequence[dict[str, str]]) -> dict[str, Any]:
        unseen = {}
        for name in self.categorical:
            known = self.category_frequency[name]
            unseen[name] = sum(
                1 for row in evaluation_rows if (row.get(name, "") or "__MISSING__") not in known
            )
        return {
            "fit_row_count": self.fit_row_count,
            "input_feature_count": len(self.feature_columns),
            "output_matrix_column_count": len(self.output_columns),
            "categorical_cardinality": {
                name: len(values) for name, values in self.category_frequency.items()
            },
            "unseen_evaluation_categories": unseen,
            "numeric_training_missing_counts": self.numeric_missing_count,
            "numeric_representation": "training-fold standardization; missing maps to 0 in matrix space plus explicit __missing=1",
        }


def select_training_rows(
    rows: Sequence[dict[str, str]], regime: str, evaluation_month: str
) -> list[dict[str, str]]:
    """Return same-regime rows whose entire H=3 label window predates E."""
    return [
        row
        for row in rows
        if row["identifier_regime"] == regime
        and training_reference_is_embargo_safe(row["report_month"], evaluation_month, HORIZON)
    ]


def lagged_rule_predictions(
    evaluation_rows: Sequence[dict[str, str]],
    regime_rows: Sequence[dict[str, str]],
) -> tuple[np.ndarray, np.ndarray]:
    """Predict 1 when the latest valid T-1→T transition added an extension.

    The cumulative extension count is an approved at-T historical feature. The
    rule compares it only with the exact same-project T-1 row in the same segment.
    If that prior eligible feature row is unavailable, the deterministic fallback
    is 0 and coverage is reported as false.
    """
    index = {
        (row["project_code"], row["report_month"], row["continuous_segment"]): row
        for row in regime_rows
    }
    prediction = np.zeros(len(evaluation_rows), dtype=int)
    covered = np.zeros(len(evaluation_rows), dtype=int)
    for offset, row in enumerate(evaluation_rows):
        prior_key = (
            row["project_code"],
            add_months(row["report_month"], -1),
            row["continuous_segment"],
        )
        prior = index.get(prior_key)
        if prior is None:
            continue
        covered[offset] = 1
        current_count = int(float(row["n_prior_schedule_extensions"]))
        prior_count = int(float(prior["n_prior_schedule_extensions"]))
        prediction[offset] = int(current_count > prior_count)
    return prediction, covered


def fit_logistic_scores(
    training_rows: Sequence[dict[str, str]],
    evaluation_rows: Sequence[dict[str, str]],
    feature_columns: Sequence[str],
) -> tuple[np.ndarray, FoldPreprocessor, LogisticRegression]:
    """Fit the fixed unweighted L2 baseline and return evaluation probabilities."""
    preprocessor = FoldPreprocessor(feature_columns).fit(training_rows)
    x_train = preprocessor.transform(training_rows)
    x_eval = preprocessor.transform(evaluation_rows)
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
    return model.predict_proba(x_eval)[:, 1], preprocessor, model


def _point_metrics(y: np.ndarray, score: np.ndarray, predicted: np.ndarray) -> dict[str, float | None]:
    positives = int(y.sum())
    predicted_positives = int(predicted.sum())
    true_positives = int(((y == 1) & (predicted == 1)).sum())
    precision = true_positives / predicted_positives if predicted_positives else None
    recall = true_positives / positives if positives else None
    if predicted_positives == 0 and positives > 0:
        f1 = 0.0
    elif precision is not None and recall is not None and precision + recall > 0:
        f1 = 2 * precision * recall / (precision + recall)
    else:
        f1 = None
    return {
        "average_precision": float(average_precision_score(y, score)) if positives else None,
        "roc_auc": float(roc_auc_score(y, score)) if len(np.unique(y)) == 2 else None,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "brier_score": float(brier_score_loss(y, score)),
        "mean_predicted_probability": float(score.mean()),
        "ece_10bin": expected_calibration_error(y, score),
    }


def expected_calibration_error(y: np.ndarray, score: np.ndarray, bins: int = 10) -> float:
    edges = np.linspace(0.0, 1.0, bins + 1)
    result = 0.0
    for index in range(bins):
        if index == bins - 1:
            mask = (score >= edges[index]) & (score <= edges[index + 1])
        else:
            mask = (score >= edges[index]) & (score < edges[index + 1])
        if mask.any():
            result += mask.mean() * abs(float(score[mask].mean()) - float(y[mask].mean()))
    return result


def calibration_rows(
    y: np.ndarray,
    score: np.ndarray,
    regime: str,
    model: str,
    scope: str,
    evaluation_month: str,
    bins: int = 10,
) -> list[dict[str, Any]]:
    edges = np.linspace(0.0, 1.0, bins + 1)
    rows = []
    for index in range(bins):
        if index == bins - 1:
            mask = (score >= edges[index]) & (score <= edges[index + 1])
        else:
            mask = (score >= edges[index]) & (score < edges[index + 1])
        if not mask.any():
            continue
        rows.append(
            {
                "regime": regime,
                "model": model,
                "scope": scope,
                "evaluation_month": evaluation_month,
                "bin_index": index + 1,
                "lower_bound": edges[index],
                "upper_bound": edges[index + 1],
                "rows": int(mask.sum()),
                "mean_predicted_probability": float(score[mask].mean()),
                "observed_positive_rate": float(y[mask].mean()),
            }
        )
    return rows


def bootstrap_intervals(
    y: np.ndarray,
    score: np.ndarray,
    predicted: np.ndarray,
    seed: int,
    iterations: int = BOOTSTRAP_ITERATIONS,
) -> dict[str, tuple[float | None, float | None]]:
    """Deterministic label-stratified nonparametric 95% intervals."""
    positive = np.flatnonzero(y == 1)
    negative = np.flatnonzero(y == 0)
    if not len(positive) or not len(negative):
        return {name: (None, None) for name in _point_metrics(y, score, predicted)}
    rng = np.random.default_rng(seed)
    values: dict[str, list[float]] = defaultdict(list)
    for _ in range(iterations):
        sample = np.concatenate(
            (
                rng.choice(positive, size=len(positive), replace=True),
                rng.choice(negative, size=len(negative), replace=True),
            )
        )
        metrics = _point_metrics(y[sample], score[sample], predicted[sample])
        for name, value in metrics.items():
            if value is not None:
                values[name].append(value)
    result = {}
    for name in _point_metrics(y, score, predicted):
        samples = values.get(name, [])
        result[name] = (
            (float(np.quantile(samples, 0.025)), float(np.quantile(samples, 0.975)))
            if samples
            else (None, None)
        )
    return result


def _metric_record(
    regime: str,
    evaluation_month: str,
    model: str,
    train_rows: Sequence[dict[str, str]],
    evaluation_rows: Sequence[dict[str, str]],
    y: np.ndarray,
    score: np.ndarray,
    predicted: np.ndarray,
    lagged_coverage: float | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "regime": regime,
        "evaluation_month": evaluation_month,
        "model": model,
        "training_rows": len(train_rows),
        "training_month_min": min((row["report_month"] for row in train_rows), default=""),
        "training_month_max": max((row["report_month"] for row in train_rows), default=""),
        "training_positives": sum(int(row[TARGET]) for row in train_rows),
        "training_positive_rate": (
            sum(int(row[TARGET]) for row in train_rows) / len(train_rows) if train_rows else None
        ),
        "evaluation_rows": len(evaluation_rows),
        "evaluation_positives": int(y.sum()),
        "evaluation_positive_rate": float(y.mean()),
        "predicted_positives": int(predicted.sum()),
        "decision_threshold": 0.5,
        "lagged_rule_history_coverage": lagged_coverage,
    }
    record.update(_point_metrics(y, score, predicted))
    return record


def _prediction_records(
    rows: Sequence[dict[str, str]],
    model: str,
    score: np.ndarray,
    predicted: np.ndarray,
    lagged_covered: np.ndarray | None = None,
) -> list[dict[str, Any]]:
    return [
        {
            "project_code": row["project_code"],
            "report_month": row["report_month"],
            "identifier_regime": row["identifier_regime"],
            "continuous_segment": row["continuous_segment"],
            "model": model,
            "actual_label": int(row[TARGET]),
            "predicted_probability_or_score": float(score[index]),
            "predicted_label": int(predicted[index]),
            "lagged_rule_history_available": (
                int(lagged_covered[index]) if lagged_covered is not None else ""
            ),
        }
        for index, row in enumerate(rows)
    ]


def evaluate(root: Path, bootstrap_iterations: int = BOOTSTRAP_ITERATIONS) -> dict[str, Any]:
    root = root.resolve()
    dataset_dir = root / "data" / "ml" / "schedule_extension_3m"
    output_dir = dataset_dir / "evaluation"
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset_manifest_path = dataset_dir / "manifest.json"
    dataset_manifest = json.loads(dataset_manifest_path.read_text(encoding="utf-8"))
    feature_columns = list(dataset_manifest["feature_columns"])
    leakage = sorted(set(feature_columns) & PROHIBITED_FEATURES)
    if leakage:
        raise RuntimeError(f"Manifest feature columns contain prohibited metadata: {leakage}")
    if dataset_manifest["target"] != TARGET:
        raise RuntimeError(f"Unexpected target: {dataset_manifest['target']}")

    canonical_hashes = {
        "projects_monthly.csv": sha256(root / "data/processed/projects_monthly.csv"),
        "projects_completed.csv": sha256(root / "data/processed/projects_completed.csv"),
    }
    if canonical_hashes != {
        "projects_monthly.csv": ONGOING_SHA256,
        "projects_completed.csv": COMPLETED_SHA256,
    }:
        raise RuntimeError(f"Canonical hash mismatch; refusing evaluation: {canonical_hashes}")

    rows_by_regime = {
        "LEGACY": _read_csv(dataset_dir / "eligible_legacy.csv"),
        "MODERN": _read_csv(dataset_dir / "eligible_modern.csv"),
    }
    for regime, rows in rows_by_regime.items():
        if any(row["identifier_regime"] != regime for row in rows):
            raise RuntimeError(f"Regime contamination in {regime} input")
        missing_features = sorted(set(feature_columns) - set(rows[0])) if rows else feature_columns
        if missing_features:
            raise RuntimeError(f"Missing manifest features in {regime}: {missing_features}")

    fold_metrics: list[dict[str, Any]] = []
    predictions: list[dict[str, Any]] = []
    calibration: list[dict[str, Any]] = []
    preprocessing_audits: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for regime in ("LEGACY", "MODERN"):
        regime_rows = rows_by_regime[regime]
        for evaluation_month in EVALUATION_ORIGINS[regime]:
            evaluation_rows = [row for row in regime_rows if row["report_month"] == evaluation_month]
            training_rows = select_training_rows(regime_rows, regime, evaluation_month)
            reasons = []
            if not evaluation_rows:
                reasons.append("ZERO_ELIGIBLE_EVALUATION_ROWS")
            if not training_rows:
                reasons.append("ZERO_ELIGIBLE_TRAINING_ROWS")
            if training_rows and len({row[TARGET] for row in training_rows}) < 2:
                reasons.append("TRAINING_TARGET_HAS_ONE_CLASS")
            if evaluation_rows and len({row[TARGET] for row in evaluation_rows}) < 2:
                reasons.append("EVALUATION_TARGET_HAS_ONE_CLASS")
            if reasons:
                skipped.append(
                    {
                        "regime": regime,
                        "evaluation_month": evaluation_month,
                        "training_rows": len(training_rows),
                        "evaluation_rows": len(evaluation_rows),
                        "reason": "|".join(reasons),
                    }
                )
                continue

            if any(not training_reference_is_embargo_safe(row["report_month"], evaluation_month) for row in training_rows):
                raise RuntimeError(f"Embargo violation at {regime} {evaluation_month}")
            if max(row["target_window_end_month"] for row in training_rows) >= evaluation_month:
                raise RuntimeError(f"Training label consumes evaluation snapshot at {evaluation_month}")

            y_train = np.asarray([int(row[TARGET]) for row in training_rows], dtype=int)
            y_eval = np.asarray([int(row[TARGET]) for row in evaluation_rows], dtype=int)
            training_prevalence = float(y_train.mean())

            model_outputs: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray | None]] = {}
            prevalence_score = np.full(len(evaluation_rows), training_prevalence, dtype=float)
            model_outputs["prevalence"] = (
                prevalence_score,
                (prevalence_score >= 0.5).astype(int),
                None,
            )
            always_score = np.zeros(len(evaluation_rows), dtype=float)
            model_outputs["always_negative"] = (always_score, np.zeros(len(evaluation_rows), dtype=int), None)

            lagged_prediction, lagged_covered = lagged_rule_predictions(evaluation_rows, regime_rows)
            model_outputs["lagged_rule_latest_valid_transition"] = (
                lagged_prediction.astype(float),
                lagged_prediction,
                lagged_covered,
            )

            logistic_score, preprocessor, _logistic = fit_logistic_scores(
                training_rows, evaluation_rows, feature_columns
            )
            model_outputs["logistic_l2_unweighted"] = (
                logistic_score,
                (logistic_score >= 0.5).astype(int),
                None,
            )

            preprocessing_audits.append(
                {
                    "regime": regime,
                    "evaluation_month": evaluation_month,
                    "training_month_min": min(row["report_month"] for row in training_rows),
                    "training_month_max": max(row["report_month"] for row in training_rows),
                    "maximum_training_label_window_end": max(
                        row["target_window_end_month"] for row in training_rows
                    ),
                    "evaluation_rows": len(evaluation_rows),
                    **preprocessor.audit(evaluation_rows),
                }
            )

            for model in MODEL_ORDER:
                score, predicted, covered = model_outputs[model]
                coverage = float(covered.mean()) if covered is not None else None
                fold_metrics.append(
                    _metric_record(
                        regime,
                        evaluation_month,
                        model,
                        training_rows,
                        evaluation_rows,
                        y_eval,
                        score,
                        predicted,
                        coverage,
                    )
                )
                predictions.extend(
                    _prediction_records(evaluation_rows, model, score, predicted, covered)
                )
                if model in {"prevalence", "logistic_l2_unweighted"}:
                    calibration.extend(
                        calibration_rows(
                            y_eval, score, regime, model, "FOLD", evaluation_month
                        )
                    )

    aggregate_metrics: list[dict[str, Any]] = []
    for regime in ("LEGACY", "MODERN"):
        for model in MODEL_ORDER:
            selected = [
                row for row in predictions if row["identifier_regime"] == regime and row["model"] == model
            ]
            if not selected:
                continue
            y = np.asarray([row["actual_label"] for row in selected], dtype=int)
            score = np.asarray([row["predicted_probability_or_score"] for row in selected], dtype=float)
            predicted = np.asarray([row["predicted_label"] for row in selected], dtype=int)
            point = _point_metrics(y, score, predicted)
            seed = int.from_bytes(hashlib.sha256(f"{RANDOM_SEED}:{regime}:{model}".encode()).digest()[:8], "big")
            intervals = bootstrap_intervals(y, score, predicted, seed, bootstrap_iterations)
            record: dict[str, Any] = {
                "regime": regime,
                "model": model,
                "evaluation_folds": len({row["report_month"] for row in selected}),
                "evaluation_rows": len(selected),
                "positives": int(y.sum()),
                "positive_rate": float(y.mean()),
                "predicted_positives": int(predicted.sum()),
                "decision_threshold": 0.5,
                "lagged_rule_history_coverage": (
                    sum(int(row["lagged_rule_history_available"]) for row in selected)
                    / len(selected)
                    if model == "lagged_rule_latest_valid_transition"
                    else None
                ),
            }
            for name, value in point.items():
                record[name] = value
                record[f"{name}_ci_lower"] = intervals[name][0]
                record[f"{name}_ci_upper"] = intervals[name][1]
            aggregate_metrics.append(record)
            if model in {"prevalence", "logistic_l2_unweighted"}:
                calibration.extend(calibration_rows(y, score, regime, model, "AGGREGATE", ""))

    fold_fields = [
        "regime", "evaluation_month", "model", "training_rows", "training_month_min",
        "training_month_max", "training_positives", "training_positive_rate", "evaluation_rows",
        "evaluation_positives", "evaluation_positive_rate", "predicted_positives",
        "decision_threshold", "lagged_rule_history_coverage", "average_precision", "roc_auc",
        "precision", "recall", "f1", "brier_score", "mean_predicted_probability", "ece_10bin",
    ]
    metric_names = list(_point_metrics(np.array([0, 1]), np.array([0.0, 1.0]), np.array([0, 1])))
    aggregate_fields = [
        "regime", "model", "evaluation_folds", "evaluation_rows", "positives", "positive_rate",
        "predicted_positives", "decision_threshold", "lagged_rule_history_coverage",
    ]
    for name in metric_names:
        aggregate_fields.extend((name, f"{name}_ci_lower", f"{name}_ci_upper"))
    prediction_fields = [
        "project_code", "report_month", "identifier_regime", "continuous_segment", "model",
        "actual_label", "predicted_probability_or_score", "predicted_label",
        "lagged_rule_history_available",
    ]
    calibration_fields = [
        "regime", "model", "scope", "evaluation_month", "bin_index", "lower_bound",
        "upper_bound", "rows", "mean_predicted_probability", "observed_positive_rate",
    ]
    skipped_fields = ["regime", "evaluation_month", "training_rows", "evaluation_rows", "reason"]

    output_paths = {
        "fold_metrics.csv": output_dir / "fold_metrics.csv",
        "regime_aggregate_metrics.csv": output_dir / "regime_aggregate_metrics.csv",
        "predictions.csv": output_dir / "predictions.csv",
        "calibration_bins.csv": output_dir / "calibration_bins.csv",
        "skipped_folds.csv": output_dir / "skipped_folds.csv",
        "preprocessing_fit_audit.json": output_dir / "preprocessing_fit_audit.json",
        "configuration.json": output_dir / "configuration.json",
    }
    _write_csv(output_paths["fold_metrics.csv"], fold_fields, fold_metrics)
    _write_csv(output_paths["regime_aggregate_metrics.csv"], aggregate_fields, aggregate_metrics)
    _write_csv(output_paths["predictions.csv"], prediction_fields, predictions)
    _write_csv(output_paths["calibration_bins.csv"], calibration_fields, calibration)
    _write_csv(output_paths["skipped_folds.csv"], skipped_fields, skipped)
    output_paths["preprocessing_fit_audit.json"].write_text(
        json.dumps(preprocessing_audits, indent=2) + "\n", encoding="utf-8"
    )
    configuration = {
        "runtime_versions": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "scikit_learn": sklearn.__version__,
        },
        "feature_source": "data/ml/schedule_extension_3m/manifest.json[feature_columns]",
        "input_feature_columns": feature_columns,
        "prohibited_feature_columns": sorted(PROHIBITED_FEATURES),
        "feature_leakage_intersection": leakage,
        "regime_policy": "Legacy and Modern evaluated separately; no pooled model.",
        "categorical_preprocessing": "Training-fold frequency encoding; unseen evaluation category = 0.",
        "numeric_preprocessing": "Training-fold mean/std standardization on non-null values; missing represented as standardized 0 plus explicit per-input missing indicator; canonical/generated input columns are not imputed or altered.",
        "logistic_regression": {
            "penalty": "l2 via l1_ratio=0.0", "C": 1.0, "solver": "lbfgs", "max_iter": 2000,
            "class_weight": None, "random_state": RANDOM_SEED, "threshold": 0.5,
        },
        "prevalence_baseline": "Constant probability equal to training-fold positive prevalence; deterministic alternative to random scores.",
        "always_negative_baseline": "Probability/score 0 and label 0; precision is NA when no positives are predicted.",
        "lagged_rule": "Predict 1 only when n_prior_schedule_extensions(T) exceeds its value at the exact same-project T-1 row in the same segment; missing T-1 feature row falls back deterministically to 0 and is reported as uncovered.",
        "embargo": "T_train + 3 calendar months < evaluation reference month E (strict).",
        "row_order": "Source CSV order retained for temporal assignment; no shuffle/random split.",
        "bootstrap": {
            "iterations": bootstrap_iterations,
            "confidence": 0.95,
            "method": "deterministic label-stratified nonparametric bootstrap",
            "seed": RANDOM_SEED,
        },
        "extension_type_interpretation": {
            "stored_value": "FIRST_REVISION",
            "documented_meaning": "FIRST_REVISION_FROM_UNREVISED_BASELINE",
            "limitation": "It means no revised completion date was reported at T; it does not prove the first revision in the project's entire pre-observation history.",
            "labels_changed": False,
        },
    }
    output_paths["configuration.json"].write_text(
        json.dumps(configuration, indent=2) + "\n", encoding="utf-8"
    )

    generated = {}
    for name, path in output_paths.items():
        item: dict[str, Any] = {"sha256": sha256(path)}
        if path.suffix == ".csv":
            item["rows"] = len(_read_csv(path))
        generated[name] = item
    validation = {
        "feature_columns_loaded_from_dataset_manifest": feature_columns,
        "prohibited_feature_intersection": leakage,
        "regime_contamination_rows": 0,
        "embargo_violations": 0,
        "training_windows_consuming_evaluation_month": 0,
        "random_split_created": False,
        "row_shuffle_performed": False,
        "skipped_fold_count": len(skipped),
    }
    evaluation_manifest = {
        "evaluation_name": "schedule_extension_3m_walk_forward_baselines_v1",
        "dataset_manifest_sha256": sha256(dataset_manifest_path),
        "canonical_hashes": canonical_hashes,
        "input_dataset_counts": dataset_manifest["summary"],
        "target": TARGET,
        "horizon_months": HORIZON,
        "requested_evaluation_origins": EVALUATION_ORIGINS,
        "evaluated_origins": {
            regime: sorted(
                {row["evaluation_month"] for row in fold_metrics if row["regime"] == regime}
            )
            for regime in ("LEGACY", "MODERN")
        },
        "skipped_folds": skipped,
        "models": list(MODEL_ORDER),
        "configuration": configuration,
        "aggregate_results": aggregate_metrics,
        "validation": validation,
        "generated_files": generated,
    }
    manifest_path = output_dir / "evaluation_manifest.json"
    manifest_path.write_text(json.dumps(evaluation_manifest, indent=2) + "\n", encoding="utf-8")
    return evaluation_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--bootstrap-iterations", type=int, default=BOOTSTRAP_ITERATIONS)
    args = parser.parse_args()
    manifest = evaluate(args.root, args.bootstrap_iterations)
    print(json.dumps(manifest["aggregate_results"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
