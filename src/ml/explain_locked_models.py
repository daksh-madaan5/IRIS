"""Deterministic predictive explanations for the two closed IRIS v1 models.

Legacy explanations use CatBoost-native TreeSHAP contributions in raw-margin
space. Modern explanations use the exact fold-local transformed matrix and
Logistic coefficients in raw-logit space. Calibration is recorded only as a
separate score transformation and never enters the feature-contribution vector.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import platform
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Sequence

import catboost as cb
import numpy as np
import pandas as pd
import scipy
import sklearn
from scipy.stats import spearmanr
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
    CATEGORICAL_FEATURES,
    EVALUATION_ORIGINS,
    PROHIBITED_FEATURES,
    RANDOM_SEED,
    TARGET,
    FoldPreprocessor,
    select_training_rows,
)
from src.ml.operational_policy import LOCKED_FEATURES, LOCKED_MODELS


DEFAULT_TOP_POSITIVE = 5
DEFAULT_TOP_NEGATIVE = 5
RECONCILIATION_TOLERANCE = 1e-10
TOP_STABILITY_FEATURES = 10
CONTRIBUTION_SPACE = "RAW_MARGIN_LOGIT"

EXPLANATION_PROHIBITED_FEATURES = PROHIBITED_FEATURES | {
    "actual_completion_date",
    "eventually_completed",
    "completion_report_month",
    "project_name",
    "legacy_ocms_code",
    "pmgid",
    "ministry",
    "source_file",
    "source_page",
    "source_pages",
    "source_row_number",
    "source_serial_number",
}

LOCAL_FIELDS = [
    "project_code",
    "report_month",
    "regime",
    "model_identifier",
    "raw_predicted_probability",
    "calibrated_probability",
    "calibration_active",
    "raw_decision_score",
    "risk_rank_within_month",
    "risk_percentile_within_month",
    "month_population",
    "source_feature_name",
    "source_feature_value_at_t",
    "encoded_feature_name",
    "model_input_value",
    "encoding",
    "contribution_method",
    "contribution_space",
    "feature_contribution",
    "contribution_direction",
    "contribution_rank",
    "expected_base_value",
]

TOP_FIELDS = [
    "project_code",
    "report_month",
    "regime",
    "model_identifier",
    "raw_predicted_probability",
    "calibrated_probability",
    "calibration_active",
    "raw_decision_score",
    "risk_rank_within_month",
    "risk_percentile_within_month",
    "source_feature_name",
    "source_feature_value_at_t",
    "feature_contribution",
    "contribution_direction",
    "direction_rank",
    "configured_direction_limit",
    "contribution_space",
]

RANK_FIELDS = [
    "project_code",
    "report_month",
    "regime",
    "model_identifier",
    "raw_predicted_probability",
    "calibrated_probability",
    "calibration_active",
    "raw_decision_score",
    "ranking_probability",
    "ranking_score_type",
    "risk_rank_within_month",
    "risk_percentile_within_month",
    "month_population",
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _serialise(value: Any) -> Any:
    if value is None or (isinstance(value, (float, np.floating)) and math.isnan(float(value))):
        return ""
    if isinstance(value, (float, np.floating)):
        return format(float(value), ".15g")
    if isinstance(value, (bool, np.bool_)):
        return str(bool(value))
    return value


def _write_csv(path: Path, fields: Sequence[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _serialise(row.get(field)) for field in fields})


class CsvSink:
    """Streaming deterministic CSV sink for the complete local vectors."""

    def __init__(self, path: Path, fields: Sequence[str]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = path.open("w", encoding="utf-8-sig", newline="")
        self.fields = list(fields)
        self.writer = csv.DictWriter(self.handle, fieldnames=self.fields, extrasaction="ignore")
        self.writer.writeheader()
        self.rows = 0

    def write(self, row: dict[str, Any]) -> None:
        self.writer.writerow({field: _serialise(row.get(field)) for field in self.fields})
        self.rows += 1

    def close(self) -> None:
        self.handle.close()


def contribution_direction(value: float) -> str:
    if value > 0.0:
        return "POSITIVE"
    if value < 0.0:
        return "NEGATIVE"
    return "ZERO"


def deterministic_ranks(
    scores: np.ndarray, rows: Sequence[dict[str, str]]
) -> tuple[np.ndarray, np.ndarray]:
    """Rank one report-month population, highest risk first."""
    if len(scores) != len(rows):
        raise ValueError("Scores and rows must align for within-month ranking")
    codes = [str(row["project_code"]) for row in rows]
    if len(codes) != len(set(codes)):
        raise ValueError("project_code must be unique within an explained report month")
    order = sorted(range(len(rows)), key=lambda index: (-float(scores[index]), codes[index]))
    ranks = np.empty(len(rows), dtype=int)
    for rank, index in enumerate(order, start=1):
        ranks[index] = rank
    percentiles = (len(rows) - ranks + 1) / len(rows)
    return ranks, percentiles.astype(float)


def fit_logistic_contributions(
    training_rows: Sequence[dict[str, str]],
    scoring_rows: Sequence[dict[str, str]],
    feature_columns: Sequence[str],
) -> tuple[
    np.ndarray,
    np.ndarray,
    float,
    list[str],
    list[str],
    list[str],
    np.ndarray,
    FoldPreprocessor,
]:
    """Fit the locked Logistic model and return exact encoded logit contributions."""
    processor = FoldPreprocessor(feature_columns).fit(training_rows)
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
    raw_score = np.asarray(model.decision_function(x_score), dtype=float)
    probability = np.asarray(model.predict_proba(x_score)[:, 1], dtype=float)
    contributions = x_score * np.asarray(model.coef_[0], dtype=float)
    encoded_names = processor.output_columns
    source_names: list[str] = []
    encodings: list[str] = []
    for name in processor.categorical:
        source_names.append(name)
        encodings.append("TRAIN_FREQUENCY")
    for name in processor.numeric:
        source_names.extend((name, name))
        encodings.extend(("TRAIN_STANDARDIZED", "MISSING_INDICATOR"))
    if not (
        contributions.shape[1]
        == len(encoded_names)
        == len(source_names)
        == len(encodings)
    ):
        raise RuntimeError("Logistic encoded-feature mapping is misaligned")
    return (
        probability,
        raw_score,
        float(model.intercept_[0]),
        encoded_names,
        source_names,
        encodings,
        contributions,
        processor,
    )


def _source_contribution_matrix(
    contributions: np.ndarray,
    encoded_source_names: Sequence[str],
    source_features: Sequence[str],
) -> np.ndarray:
    positions = {feature: index for index, feature in enumerate(source_features)}
    result = np.zeros((contributions.shape[0], len(source_features)), dtype=float)
    for encoded_index, feature in enumerate(encoded_source_names):
        result[:, positions[feature]] += contributions[:, encoded_index]
    return result


def _summary(values: np.ndarray) -> dict[str, Any]:
    positive = int((values > 0).sum())
    negative = int((values < 0).sum())
    zero = int((values == 0).sum())
    return {
        "rows": len(values),
        "mean_contribution": float(values.mean()),
        "mean_absolute_contribution": float(np.abs(values).mean()),
        "std_contribution": float(values.std()),
        "minimum_contribution": float(values.min()),
        "p05_contribution": float(np.quantile(values, 0.05)),
        "p25_contribution": float(np.quantile(values, 0.25)),
        "median_contribution": float(np.quantile(values, 0.50)),
        "p75_contribution": float(np.quantile(values, 0.75)),
        "p95_contribution": float(np.quantile(values, 0.95)),
        "maximum_contribution": float(values.max()),
        "positive_count": positive,
        "negative_count": negative,
        "zero_count": zero,
        "positive_frequency": positive / len(values),
        "negative_frequency": negative / len(values),
        "zero_frequency": zero / len(values),
    }


def run(
    root: Path,
    top_positive: int = DEFAULT_TOP_POSITIVE,
    top_negative: int = DEFAULT_TOP_NEGATIVE,
) -> dict[str, Any]:
    if top_positive < 0 or top_negative < 0:
        raise ValueError("Top-contributor limits must be non-negative")
    root = root.resolve()
    dataset_dir = root / "data/ml/schedule_extension_3m"
    evaluation_dir = dataset_dir / "evaluation"
    output_dir = evaluation_dir / "explainability"
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "dataset_manifest": dataset_dir / "manifest.json",
        "catboost_manifest": evaluation_dir / "catboost/configuration_manifest.json",
        "refinement_manifest": evaluation_dir / "refinement/configuration_manifest.json",
        "policy_manifest": evaluation_dir / "operational_policy/configuration_manifest.json",
        "policy_predictions": evaluation_dir / "operational_policy/predictions.csv",
        "catboost_importance": evaluation_dir / "catboost/feature_importance.csv",
    }
    manifests = {
        name: json.loads(path.read_text(encoding="utf-8"))
        for name, path in paths.items()
        if name.endswith("manifest")
    }
    dataset_manifest = manifests["dataset_manifest"]
    policy_manifest = manifests["policy_manifest"]
    if dataset_manifest["target"] != TARGET or policy_manifest["target"] != TARGET:
        raise RuntimeError("Repository target contradicts the locked flagship target")
    if policy_manifest["closed_model_decisions"] != {
        "LEGACY": {"decision": "PREFER_CATBOOST", "model": LOCKED_MODELS["LEGACY"]},
        "MODERN": {"decision": "KEEP_LOGISTIC", "model": LOCKED_MODELS["MODERN"]},
    }:
        raise RuntimeError("Closed model decisions contradict the explainability lock")
    if policy_manifest["locked_features"] != LOCKED_FEATURES:
        raise RuntimeError("Locked feature lists contradict the operational manifest")

    expected_hashes = {
        "projects_monthly.csv": ONGOING_SHA256,
        "projects_completed.csv": COMPLETED_SHA256,
    }
    canonical_hashes = {
        "projects_monthly.csv": sha256(root / "data/processed/projects_monthly.csv"),
        "projects_completed.csv": sha256(root / "data/processed/projects_completed.csv"),
    }
    if canonical_hashes != expected_hashes:
        raise RuntimeError(f"Canonical hash mismatch: {canonical_hashes}")

    manifest_features = set(dataset_manifest["feature_columns"])
    metadata_columns = set(dataset_manifest["metadata_columns"])
    locked_union = set(LOCKED_FEATURES["LEGACY"]) | set(LOCKED_FEATURES["MODERN"])
    missing_declared = sorted(locked_union - manifest_features)
    metadata_in_features = sorted(locked_union & metadata_columns)
    prohibited = sorted(locked_union & EXPLANATION_PROHIBITED_FEATURES)
    if missing_declared or metadata_in_features or prohibited:
        raise RuntimeError(
            "Invalid locked explanation features: "
            f"missing={missing_declared}, metadata={metadata_in_features}, prohibited={prohibited}"
        )

    rows_by_regime = {
        "LEGACY": _read_csv(dataset_dir / "eligible_legacy.csv"),
        "MODERN": _read_csv(dataset_dir / "eligible_modern.csv"),
    }
    operational_rows = _read_csv(paths["policy_predictions"])
    operational_index = {
        (row["identifier_regime"], row["project_code"], row["report_month"]): row
        for row in operational_rows
    }
    if len(operational_index) != len(operational_rows):
        raise RuntimeError("Operational prediction keys are not unique")

    importance_rows = [
        row
        for row in _read_csv(paths["catboost_importance"])
        if row["regime"] == "LEGACY" and row["model"] == LOCKED_MODELS["LEGACY"]
    ]
    importance_sorted = sorted(
        importance_rows,
        key=lambda row: (-float(row["mean_importance"]), row["feature"]),
    )
    importance_rank = {
        row["feature"]: index for index, row in enumerate(importance_sorted, start=1)
    }
    importance_value = {
        row["feature"]: float(row["mean_importance"]) for row in importance_rows
    }

    local_path = output_dir / "local_explanations.csv"
    top_path = output_dir / "top_contributors.csv"
    local_sink = CsvSink(local_path, LOCAL_FIELDS)
    top_sink = CsvSink(top_path, TOP_FIELDS)
    risk_rows: list[dict[str, Any]] = []
    global_chunks: dict[tuple[str, str], list[np.ndarray]] = defaultdict(list)
    fold_chunks: dict[tuple[str, str, str], np.ndarray] = {}
    fold_audits: list[dict[str, Any]] = []
    score_reconciliation: list[float] = []
    contribution_reconciliation = {"LEGACY": [], "MODERN": []}
    explained_keys: set[tuple[str, str, str]] = set()

    try:
        for regime in ("LEGACY", "MODERN"):
            regime_rows = rows_by_regime[regime]
            for evaluation_month in EVALUATION_ORIGINS[regime]:
                evaluation = sorted(
                    [row for row in regime_rows if row["report_month"] == evaluation_month],
                    key=lambda row: row["project_code"],
                )
                training = select_training_rows(regime_rows, regime, evaluation_month)
                if not evaluation or not training:
                    raise RuntimeError(f"Accepted explanation fold is empty: {regime} {evaluation_month}")
                if any(
                    not training_reference_is_embargo_safe(row["report_month"], evaluation_month, HORIZON)
                    for row in training
                ):
                    raise RuntimeError(f"Main embargo violation: {regime} {evaluation_month}")
                maximum_end = max(row["target_window_end_month"] for row in training)
                if maximum_end >= evaluation_month:
                    raise RuntimeError(f"Training labels reach evaluation origin {evaluation_month}")

                source_features = list(LOCKED_FEATURES[regime])
                if regime == "LEGACY":
                    probability, model, _ = fit_catboost_variant(
                        training, evaluation, source_features, None
                    )
                    x_eval, categorical = prepare_catboost_df(evaluation, source_features)
                    pool = cb.Pool(
                        x_eval,
                        cat_features=categorical if categorical else None,
                        feature_names=source_features,
                    )
                    shap_values = np.asarray(
                        model.get_feature_importance(pool, type="ShapValues"), dtype=float
                    )
                    contributions = shap_values[:, :-1]
                    base_values = shap_values[:, -1]
                    raw_scores = np.asarray(
                        model.predict(pool, prediction_type="RawFormulaVal"), dtype=float
                    ).reshape(-1)
                    encoded_names = source_features
                    encoded_source_names = source_features
                    encodings = ["CATBOOST_NATIVE" for _ in source_features]
                    model_inputs = x_eval.to_numpy(dtype=object)
                    method = "CATBOOST_NATIVE_TREESHAP"
                else:
                    (
                        probability,
                        raw_scores,
                        base_value,
                        encoded_names,
                        encoded_source_names,
                        encodings,
                        contributions,
                        processor,
                    ) = fit_logistic_contributions(training, evaluation, source_features)
                    base_values = np.full(len(evaluation), base_value, dtype=float)
                    model_inputs = processor.transform(evaluation).astype(object)
                    method = "LOGISTIC_COEFFICIENT_TIMES_TRANSFORMED_VALUE"

                reconstructed = base_values + contributions.sum(axis=1)
                fold_errors = np.abs(reconstructed - raw_scores)
                contribution_reconciliation[regime].extend(fold_errors.tolist())
                if float(fold_errors.max()) > RECONCILIATION_TOLERANCE:
                    raise RuntimeError(
                        f"Contribution reconciliation failed: {regime} {evaluation_month} "
                        f"max={float(fold_errors.max())}"
                    )

                policy = [
                    operational_index[(regime, row["project_code"], evaluation_month)]
                    for row in evaluation
                ]
                accepted_raw = np.asarray([float(row["raw_probability"]) for row in policy])
                accepted_logit = np.asarray([float(row["raw_logit"]) for row in policy])
                score_reconciliation.extend(np.abs(probability - accepted_raw).tolist())
                score_reconciliation.extend(np.abs(raw_scores - accepted_logit).tolist())
                if max(score_reconciliation, default=0.0) > RECONCILIATION_TOLERANCE:
                    raise RuntimeError("Refitted locked scores do not reconcile with policy artifacts")

                calibration_active = np.asarray(
                    [row["calibration_active"] == "True" for row in policy], dtype=bool
                )
                operational_probability = np.asarray(
                    [float(row["operational_probability"]) for row in policy], dtype=float
                )
                calibrated_probability = [
                    float(row["operational_probability"])
                    if row["calibration_active"] == "True"
                    else None
                    for row in policy
                ]
                ranks, percentiles = deterministic_ranks(operational_probability, evaluation)
                source_matrix = _source_contribution_matrix(
                    contributions, encoded_source_names, source_features
                )
                for feature_index, feature in enumerate(source_features):
                    values = source_matrix[:, feature_index].copy()
                    global_chunks[(regime, feature)].append(values)
                    fold_chunks[(regime, evaluation_month, feature)] = values

                for row_index, row in enumerate(evaluation):
                    key = (regime, row["project_code"], evaluation_month)
                    if key in explained_keys:
                        raise RuntimeError(f"Duplicate explained row: {key}")
                    explained_keys.add(key)
                    common = {
                        "project_code": row["project_code"],
                        "report_month": evaluation_month,
                        "regime": regime,
                        "model_identifier": LOCKED_MODELS[regime],
                        "raw_predicted_probability": float(probability[row_index]),
                        "calibrated_probability": calibrated_probability[row_index],
                        "calibration_active": bool(calibration_active[row_index]),
                        "raw_decision_score": float(raw_scores[row_index]),
                        "risk_rank_within_month": int(ranks[row_index]),
                        "risk_percentile_within_month": float(percentiles[row_index]),
                    }
                    risk_rows.append(
                        {
                            **common,
                            "ranking_probability": float(operational_probability[row_index]),
                            "ranking_score_type": "OPERATIONAL_PROBABILITY",
                            "month_population": len(evaluation),
                        }
                    )

                    component_order = sorted(
                        range(len(encoded_names)),
                        key=lambda index: (
                            -abs(float(contributions[row_index, index])), encoded_names[index]
                        ),
                    )
                    component_rank = {
                        index: rank for rank, index in enumerate(component_order, start=1)
                    }
                    for encoded_index in component_order:
                        source_name = encoded_source_names[encoded_index]
                        source_value = row.get(source_name, "")
                        local_sink.write(
                            {
                                **common,
                                "month_population": len(evaluation),
                                "source_feature_name": source_name,
                                "source_feature_value_at_t": source_value,
                                "encoded_feature_name": encoded_names[encoded_index],
                                "model_input_value": model_inputs[row_index, encoded_index],
                                "encoding": encodings[encoded_index],
                                "contribution_method": method,
                                "contribution_space": CONTRIBUTION_SPACE,
                                "feature_contribution": float(
                                    contributions[row_index, encoded_index]
                                ),
                                "contribution_direction": contribution_direction(
                                    float(contributions[row_index, encoded_index])
                                ),
                                "contribution_rank": component_rank[encoded_index],
                                "expected_base_value": float(base_values[row_index]),
                            }
                        )

                    source_values = source_matrix[row_index]
                    positive_order = sorted(
                        [i for i, value in enumerate(source_values) if value > 0],
                        key=lambda i: (-float(source_values[i]), source_features[i]),
                    )[:top_positive]
                    negative_order = sorted(
                        [i for i, value in enumerate(source_values) if value < 0],
                        key=lambda i: (float(source_values[i]), source_features[i]),
                    )[:top_negative]
                    for direction, indices, limit in (
                        ("POSITIVE", positive_order, top_positive),
                        ("NEGATIVE", negative_order, top_negative),
                    ):
                        for direction_rank, source_index in enumerate(indices, start=1):
                            feature = source_features[source_index]
                            top_sink.write(
                                {
                                    **common,
                                    "source_feature_name": feature,
                                    "source_feature_value_at_t": row.get(feature, ""),
                                    "feature_contribution": float(source_values[source_index]),
                                    "contribution_direction": direction,
                                    "direction_rank": direction_rank,
                                    "configured_direction_limit": limit,
                                    "contribution_space": CONTRIBUTION_SPACE,
                                }
                            )

                fold_audits.append(
                    {
                        "regime": regime,
                        "evaluation_month": evaluation_month,
                        "model": LOCKED_MODELS[regime],
                        "training_rows": len(training),
                        "training_month_min": min(row["report_month"] for row in training),
                        "training_month_max": max(row["report_month"] for row in training),
                        "maximum_training_label_window_end": maximum_end,
                        "evaluation_rows": len(evaluation),
                        "encoded_contribution_count": len(encoded_names),
                        "source_feature_count": len(source_features),
                        "calibration_active": bool(calibration_active.any()),
                        "maximum_contribution_reconciliation_error": float(fold_errors.max()),
                    }
                )
    finally:
        local_sink.close()
        top_sink.close()

    risk_rows.sort(
        key=lambda row: (
            0 if row["regime"] == "LEGACY" else 1,
            row["report_month"],
            row["risk_rank_within_month"],
            row["project_code"],
        )
    )
    _write_csv(output_dir / "risk_rankings.csv", RANK_FIELDS, risk_rows)

    global_records: list[dict[str, Any]] = []
    global_ranks: dict[tuple[str, str], int] = {}
    for regime in ("LEGACY", "MODERN"):
        feature_summaries = []
        for feature in LOCKED_FEATURES[regime]:
            values = np.concatenate(global_chunks[(regime, feature)])
            feature_summaries.append((feature, values, _summary(values)))
        ordered = sorted(
            feature_summaries,
            key=lambda item: (-item[2]["mean_absolute_contribution"], item[0]),
        )
        for rank, (feature, values, summary) in enumerate(ordered, start=1):
            global_ranks[(regime, feature)] = rank
            prior_rank = importance_rank.get(feature) if regime == "LEGACY" else None
            global_records.append(
                {
                    "regime": regime,
                    "model_identifier": LOCKED_MODELS[regime],
                    "source_feature_name": feature,
                    "contribution_method": (
                        "CATBOOST_NATIVE_TREESHAP"
                        if regime == "LEGACY"
                        else "LOGISTIC_SOURCE_AGGREGATED_LOGIT_CONTRIBUTION"
                    ),
                    "contribution_space": CONTRIBUTION_SPACE,
                    "evaluation_folds": len(EVALUATION_ORIGINS[regime]),
                    **summary,
                    "feature_rank": rank,
                    "previous_catboost_importance": importance_value.get(feature),
                    "previous_catboost_importance_rank": prior_rank,
                    "rank_difference_vs_previous_importance": (
                        rank - prior_rank if prior_rank is not None else None
                    ),
                    "ranking_comparison": (
                        "MATCH"
                        if prior_rank == rank
                        else "SHAP_RANK_HIGHER"
                        if prior_rank is not None and rank < prior_rank
                        else "SHAP_RANK_LOWER"
                        if prior_rank is not None
                        else "NOT_APPLICABLE"
                    ),
                }
            )

    global_fields = list(global_records[0])
    _write_csv(
        output_dir / "global_feature_contributions.csv", global_fields, global_records
    )

    fold_records: list[dict[str, Any]] = []
    stability_summary: dict[str, Any] = {}
    for regime in ("LEGACY", "MODERN"):
        global_top = {
            feature
            for feature in LOCKED_FEATURES[regime]
            if global_ranks[(regime, feature)] <= TOP_STABILITY_FEATURES
        }
        jaccards = []
        top_feature_counts: dict[str, int] = defaultdict(int)
        fold_top_features: dict[str, list[str]] = {}
        for month in EVALUATION_ORIGINS[regime]:
            summaries = []
            for feature in LOCKED_FEATURES[regime]:
                values = fold_chunks[(regime, month, feature)]
                summaries.append((feature, _summary(values)))
            ordered = sorted(
                summaries,
                key=lambda item: (-item[1]["mean_absolute_contribution"], item[0]),
            )
            fold_rank = {feature: rank for rank, (feature, _) in enumerate(ordered, start=1)}
            fold_top = {feature for feature, _ in ordered[:TOP_STABILITY_FEATURES]}
            fold_top_features[month] = [feature for feature, _ in ordered[:TOP_STABILITY_FEATURES]]
            for feature in fold_top:
                top_feature_counts[feature] += 1
            jaccard = len(global_top & fold_top) / len(global_top | fold_top)
            jaccards.append(jaccard)
            for feature, summary in summaries:
                fold_records.append(
                    {
                        "regime": regime,
                        "model_identifier": LOCKED_MODELS[regime],
                        "evaluation_month": month,
                        "source_feature_name": feature,
                        "rows": summary["rows"],
                        "mean_contribution": summary["mean_contribution"],
                        "mean_absolute_contribution": summary[
                            "mean_absolute_contribution"
                        ],
                        "std_contribution": summary["std_contribution"],
                        "positive_frequency": summary["positive_frequency"],
                        "negative_frequency": summary["negative_frequency"],
                        "zero_frequency": summary["zero_frequency"],
                        "fold_feature_rank": fold_rank[feature],
                        "is_fold_top_10": fold_rank[feature] <= TOP_STABILITY_FEATURES,
                        "global_feature_rank": global_ranks[(regime, feature)],
                        "absolute_rank_difference": abs(
                            fold_rank[feature] - global_ranks[(regime, feature)]
                        ),
                        "fold_top_10_jaccard_vs_global": jaccard,
                    }
                )
        stability_summary[regime] = {
            "top_10_jaccard_mean": float(np.mean(jaccards)),
            "top_10_jaccard_min": float(np.min(jaccards)),
            "top_10_jaccard_max": float(np.max(jaccards)),
            "features_in_top_10_all_folds": sorted(
                feature
                for feature, count in top_feature_counts.items()
                if count == len(EVALUATION_ORIGINS[regime])
            ),
            "top_10_fold_frequency": dict(
                sorted(top_feature_counts.items(), key=lambda item: (-item[1], item[0]))
            ),
            "fold_top_features": fold_top_features,
        }

    fold_records.sort(
        key=lambda row: (
            0 if row["regime"] == "LEGACY" else 1,
            row["evaluation_month"],
            row["fold_feature_rank"],
            row["source_feature_name"],
        )
    )
    _write_csv(
        output_dir / "fold_explanation_stability.csv",
        list(fold_records[0]),
        fold_records,
    )

    legacy_global = [
        row for row in global_records if row["regime"] == "LEGACY"
    ]
    legacy_global_by_feature = {row["source_feature_name"]: row for row in legacy_global}
    shared_features = sorted(importance_rank)
    correlation = spearmanr(
        [importance_rank[feature] for feature in shared_features],
        [legacy_global_by_feature[feature]["feature_rank"] for feature in shared_features],
    )
    shap_top_10 = {
        row["source_feature_name"] for row in legacy_global if row["feature_rank"] <= 10
    }
    prior_top_10 = {feature for feature, rank in importance_rank.items() if rank <= 10}
    legacy_comparison = {
        "rank_spearman": float(correlation.statistic),
        "rank_spearman_pvalue": float(correlation.pvalue),
        "top_10_overlap_count": len(shap_top_10 & prior_top_10),
        "top_10_jaccard": len(shap_top_10 & prior_top_10) / len(shap_top_10 | prior_top_10),
        "shap_only_top_10": sorted(shap_top_10 - prior_top_10),
        "previous_importance_only_top_10": sorted(prior_top_10 - shap_top_10),
        "largest_absolute_rank_disagreements": [
            {
                "feature": row["source_feature_name"],
                "shap_rank": row["feature_rank"],
                "previous_importance_rank": row["previous_catboost_importance_rank"],
                "rank_difference": row["rank_difference_vs_previous_importance"],
            }
            for row in sorted(
                legacy_global,
                key=lambda item: (
                    -abs(item["rank_difference_vs_previous_importance"]),
                    item["source_feature_name"],
                ),
            )[:10]
        ],
    }

    output_paths = {
        "local_explanations.csv": local_path,
        "top_contributors.csv": top_path,
        "global_feature_contributions.csv": output_dir
        / "global_feature_contributions.csv",
        "fold_explanation_stability.csv": output_dir / "fold_explanation_stability.csv",
        "risk_rankings.csv": output_dir / "risk_rankings.csv",
    }
    generated_files = {
        name: {"rows": len(_read_csv(path)), "sha256": sha256(path)}
        for name, path in output_paths.items()
    }
    if generated_files["local_explanations.csv"]["rows"] != local_sink.rows:
        raise RuntimeError("Local explanation row count failed streaming reconciliation")
    if generated_files["top_contributors.csv"]["rows"] != top_sink.rows:
        raise RuntimeError("Top-contributor row count failed streaming reconciliation")

    max_contribution_error = {
        regime: max(errors, default=math.inf)
        for regime, errors in contribution_reconciliation.items()
    }
    max_score_error = max(score_reconciliation, default=math.inf)
    february = stability_summary["LEGACY"]["fold_top_features"]["2025-02"]
    modern_fold_top = stability_summary["MODERN"]["fold_top_features"]
    manifest = {
        "explainability_name": "schedule_extension_3m_locked_models_explainability_v1",
        "runtime_versions": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
            "catboost": cb.__version__,
        },
        "target": TARGET,
        "horizon_months": HORIZON,
        "locked_models": LOCKED_MODELS,
        "locked_features": LOCKED_FEATURES,
        "evaluation_origins": EVALUATION_ORIGINS,
        "methods": {
            "LEGACY": "CatBoost-native TreeSHAP feature contributions",
            "MODERN": "Fold-local transformed value multiplied by fitted Logistic coefficient",
            "contribution_space": CONTRIBUTION_SPACE,
            "reconciliation": "expected_base_value + sum(feature_contribution) = raw_decision_score",
            "calibration": (
                "Separate monotonic score transformation only; Platt parameters are not "
                "features and do not enter contribution vectors."
            ),
            "interpretation": "Predictive association with the fitted model output; not causal attribution.",
        },
        "top_contributor_configuration": {
            "positive": top_positive,
            "negative": top_negative,
            "selection_level": "SOURCE_FEATURE_AFTER_SUMMING_ENCODED_COMPONENTS",
        },
        "risk_ranking": {
            "scope": "SAME_REPORT_MONTH_AND_SAME_MODEL_REGIME_ONLY",
            "score": "OPERATIONAL_PROBABILITY",
            "rank": "1 is highest risk; equal scores use project_code ascending",
            "percentile": "(month_population - rank + 1) / month_population",
        },
        "source_manifests": {
            name: {"path": str(paths[name].relative_to(root)), "sha256": sha256(paths[name])}
            for name in (
                "dataset_manifest",
                "catboost_manifest",
                "refinement_manifest",
                "policy_manifest",
            )
        },
        "canonical_hashes": canonical_hashes,
        "fold_audits": fold_audits,
        "global_rankings": {
            regime: [
                row["source_feature_name"]
                for row in sorted(
                    [item for item in global_records if item["regime"] == regime],
                    key=lambda item: item["feature_rank"],
                )
            ]
            for regime in ("LEGACY", "MODERN")
        },
        "fold_stability": stability_summary,
        "legacy_shap_vs_previous_importance": legacy_comparison,
        "explicit_fold_inspection": {
            "legacy_february_2025_top_10": february,
            "legacy_february_2025_top_10_jaccard_vs_global": next(
                row["fold_top_10_jaccard_vs_global"]
                for row in fold_records
                if row["regime"] == "LEGACY"
                and row["evaluation_month"] == "2025-02"
            ),
            "modern_top_10_by_fold": modern_fold_top,
        },
        "validation": {
            "main_embargo_violations": 0,
            "explained_fold_count": len(fold_audits),
            "explained_project_month_rows": len(explained_keys),
            "maximum_legacy_shap_reconciliation_error": max_contribution_error["LEGACY"],
            "maximum_modern_logit_reconciliation_error": max_contribution_error["MODERN"],
            "maximum_locked_score_reconciliation_error": max_score_error,
            "reconciliation_tolerance": RECONCILIATION_TOLERANCE,
            "prohibited_feature_intersection": prohibited,
            "metadata_columns_used_as_model_features": metadata_in_features,
            "declared_locked_features_missing": missing_declared,
            "project_code_role": "METADATA_ONLY",
            "project_name_used_as_feature": False,
            "completed_project_data_used_as_feature": False,
            "future_target_event_fields_used_as_features": [],
            "calibration_parameters_used_as_feature_contributions": False,
            "other_model_families_trained": [],
            "secondary_targets_explained": [],
            "canonical_hashes_unchanged": canonical_hashes == expected_hashes,
        },
        "generated_files": generated_files,
    }
    manifest_path = output_dir / "explainability_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--top-positive", type=int, default=DEFAULT_TOP_POSITIVE)
    parser.add_argument("--top-negative", type=int, default=DEFAULT_TOP_NEGATIVE)
    args = parser.parse_args()
    result = run(args.root, args.top_positive, args.top_negative)
    print(
        json.dumps(
            {
                "generated_files": result["generated_files"],
                "validation": result["validation"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
