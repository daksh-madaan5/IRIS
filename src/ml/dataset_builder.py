"""Build the v1 three-month schedule-extension prediction dataset.

This module reads the immutable canonical ongoing/completed CSVs and writes only
under ``data/ml/schedule_extension_3m``.  It intentionally performs no encoding,
imputation, splitting, feature fitting, or model training.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


ONGOING_SHA256 = "9512A9881E17DFDED6E182D87A8DFB1C4EDBD36C0D9B8A7DA9FD1ABB7E002FBF"
COMPLETED_SHA256 = "89BEA84FD68A22E327090C1E4E4533F5BCD745ADCA61EB4E66172EE9023BB910"
HORIZON = 3

SEGMENTS = (
    ("SEGMENT_1", "LEGACY", "2023-01", "2023-11"),
    ("SEGMENT_2", "LEGACY", "2024-01", "2024-03"),
    ("SEGMENT_3", "LEGACY", "2024-06", "2025-06"),
    ("SEGMENT_4", "MODERN", "2025-07", "2026-07"),
)

METADATA_COLUMNS = [
    "project_code",
    "report_month",
    "identifier_regime",
    "continuous_segment",
    "target_horizon_months",
    "target_window_end_month",
    "target_effective_schedule_ext_3m",
    "extension_type",
    "baseline_completion_date",
    "baseline_completion_source",
    "target_event_month",
    "target_event_revised_completion_date",
    "eventually_completed",
    "completion_report_month",
]

FEATURE_COLUMNS = [
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

LEAKAGE_METADATA_COLUMNS = ["eventually_completed", "completion_report_month"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def month_index(value: str) -> int:
    year, month = (int(part) for part in value.split("-"))
    return year * 12 + month - 1


def add_months(value: str, count: int) -> str:
    index = month_index(value) + count
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def months_between(start: str, end: str) -> int | None:
    if not start or not end:
        return None
    return month_index(end) - month_index(start)


def segment_for_month(month: str) -> tuple[str, str] | None:
    for name, regime, start, end in SEGMENTS:
        if start <= month <= end:
            return name, regime
    return None


def training_reference_is_embargo_safe(
    training_month: str, evaluation_month: str, horizon: int = HORIZON
) -> bool:
    """Strict maturity rule: the training label must end before evaluation T."""
    return month_index(add_months(training_month, horizon)) < month_index(evaluation_month)


def _number(value: str) -> float | None:
    if value is None or value.strip() == "":
        return None
    return float(value)


def _out(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, float):
        return format(value, ".15g")
    return value


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _out(row.get(field)) for field in fieldnames})


def _effective_commitment(row: dict[str, str]) -> tuple[str, str]:
    if row.get("revised_completion_date", ""):
        return row["revised_completion_date"], "REVISED"
    if row.get("original_completion_date", ""):
        return row["original_completion_date"], "ORIGINAL"
    return "", "MISSING"


@dataclass(frozen=True)
class TargetDecision:
    eligible: bool
    reason: str
    label: int | None = None
    extension_type: str = ""
    event_month: str = ""
    event_value: str = ""
    baseline: str = ""
    baseline_source: str = ""
    window_end: str = ""


def classify_target(
    current: dict[str, str],
    by_month: dict[str, dict[str, str]],
    history: list[dict[str, str]],
    horizon: int = HORIZON,
) -> TargetDecision:
    """Classify one reference row using conservative reported-revision semantics.

    A later null never resets a known revised commitment to the original. A
    would-be negative window that contains such an unresolved null is ineligible.
    An actually reported future revised date later than the T baseline is direct
    positive evidence even if another future snapshot is null.
    """
    report_month = current["report_month"]
    assignment = segment_for_month(report_month)
    window_end = add_months(report_month, horizon)
    end_assignment = segment_for_month(window_end)
    if assignment is None or assignment != end_assignment:
        return TargetDecision(False, "STRUCTURAL_GAP_OR_REGIME_BOUNDARY", window_end=window_end)

    future_months = [add_months(report_month, step) for step in range(1, horizon + 1)]
    if any(month not in by_month for month in future_months):
        return TargetDecision(False, "PROJECT_DISAPPEARED_OR_MONTH_MISSING", window_end=window_end)

    baseline, source = _effective_commitment(current)
    if not baseline:
        return TargetDecision(False, "MISSING_BASELINE_COMPLETION_COMMITMENT", window_end=window_end)

    prior_revision_seen = any(
        row["report_month"] < report_month and row.get("revised_completion_date", "")
        for row in history
    )
    if not current.get("revised_completion_date", "") and prior_revision_seen:
        return TargetDecision(
            False,
            "BASELINE_REVISION_PERSISTENCE_AMBIGUOUS",
            baseline=baseline,
            baseline_source=source,
            window_end=window_end,
        )

    future = [by_month[month] for month in future_months]
    positive_events = [
        row
        for row in future
        if row.get("revised_completion_date", "")
        and month_index(row["revised_completion_date"]) > month_index(baseline)
    ]
    if positive_events:
        event = positive_events[0]
        kind = "SUBSEQUENT_REVISION" if current.get("revised_completion_date", "") else "FIRST_REVISION"
        return TargetDecision(
            True,
            "ELIGIBLE_POSITIVE",
            1,
            kind,
            event["report_month"],
            event["revised_completion_date"],
            baseline,
            source,
            window_end,
        )

    revision_seen = bool(current.get("revised_completion_date", ""))
    for row in future:
        revised = row.get("revised_completion_date", "")
        if revised:
            revision_seen = True
        elif revision_seen:
            return TargetDecision(
                False,
                "FUTURE_REVISION_PERSISTENCE_AMBIGUOUS",
                baseline=baseline,
                baseline_source=source,
                window_end=window_end,
            )

    return TargetDecision(
        True,
        "ELIGIBLE_NEGATIVE",
        0,
        "NONE",
        baseline=baseline,
        baseline_source=source,
        window_end=window_end,
    )


def _prior_counts(history: list[dict[str, str]], report_month: str) -> tuple[int, int, int]:
    rows = [row for row in history if row["report_month"] <= report_month]
    schedule_count = 0
    cost_count = 0
    last_schedule = ""
    last_cost: float | None = None
    for row in rows:
        original_date = row.get("original_completion_date", "")
        revised_date = row.get("revised_completion_date", "")
        if not last_schedule and original_date:
            last_schedule = original_date
        if revised_date:
            if last_schedule and month_index(revised_date) > month_index(last_schedule):
                schedule_count += 1
            last_schedule = revised_date

        original_cost = _number(row.get("original_cost", ""))
        revised_cost = _number(row.get("revised_cost", ""))
        if last_cost is None and original_cost is not None:
            last_cost = original_cost
        if revised_cost is not None:
            if last_cost is not None and revised_cost > last_cost:
                cost_count += 1
            last_cost = revised_cost
    return schedule_count, cost_count, len(rows)


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def build_features(
    current: dict[str, str],
    by_month: dict[str, dict[str, str]],
    history: list[dict[str, str]],
    baseline: str,
) -> dict[str, Any]:
    month = current["report_month"]
    original_cost = _number(current.get("original_cost", ""))
    revised_cost = _number(current.get("revised_cost", ""))
    expenditure = _number(current.get("cumulative_expenditure", ""))
    progress = _number(current.get("physical_progress", ""))
    prior_1 = by_month.get(add_months(month, -1))
    prior_3 = by_month.get(add_months(month, -3))
    same_segment = segment_for_month(month)

    def usable_prior(row: dict[str, str] | None) -> bool:
        return row is not None and segment_for_month(row["report_month"]) == same_segment

    exp_1 = _number(prior_1.get("cumulative_expenditure", "")) if usable_prior(prior_1) else None
    exp_3 = _number(prior_3.get("cumulative_expenditure", "")) if usable_prior(prior_3) else None
    prog_3 = _number(prior_3.get("physical_progress", "")) if usable_prior(prior_3) else None
    exp_delta_1 = expenditure - exp_1 if expenditure is not None and exp_1 is not None else None
    exp_delta_3 = expenditure - exp_3 if expenditure is not None and exp_3 is not None else None
    progress_delta_3 = progress - prog_3 if progress is not None and prog_3 is not None else None
    schedule_count, cost_count, depth = _prior_counts(history, month)
    physical_supported = month >= "2024-06"
    start_supported = month >= "2025-08"

    return {
        "sector": current.get("sector", ""),
        "agency": current.get("agency", ""),
        "state": current.get("state", ""),
        "original_cost": original_cost,
        "cumulative_expenditure_t": expenditure,
        "revised_cost_t": revised_cost,
        "physical_progress_t": progress,
        "project_age_months": months_between(current.get("approval_date", ""), month),
        "months_to_original_schedule": months_between(month, current.get("original_completion_date", "")),
        "months_to_effective_schedule": months_between(month, baseline),
        "schedule_revision_lag_months": months_between(
            current.get("original_completion_date", ""), current.get("revised_completion_date", "")
        ),
        "schedule_has_been_revised": int(bool(current.get("revised_completion_date", ""))),
        "months_since_start": months_between(current.get("start_date", ""), month),
        "expenditure_to_original_cost_ratio": _ratio(expenditure, original_cost),
        "revised_to_original_cost_ratio": _ratio(revised_cost, original_cost),
        "cost_has_been_revised": int(revised_cost is not None),
        "exp_delta_1m": exp_delta_1,
        "exp_delta_3m": exp_delta_3,
        "past_exp_stagnant_3m": int(exp_delta_3 == 0) if exp_delta_3 is not None else None,
        "past_progress_delta_3m": progress_delta_3,
        "past_progress_stagnant_3m": int(progress_delta_3 == 0) if progress_delta_3 is not None else None,
        "n_prior_schedule_extensions": schedule_count,
        "n_prior_cost_revisions": cost_count,
        "observed_tenure_months": depth,
        "state_is_missing": int(not bool(current.get("state", ""))),
        "approval_date_is_missing": int(not bool(current.get("approval_date", ""))),
        "original_completion_date_is_missing": int(not bool(current.get("original_completion_date", ""))),
        "revised_cost_is_present": int(revised_cost is not None),
        "revised_date_is_present": int(bool(current.get("revised_completion_date", ""))),
        "physical_progress_is_present": int(progress is not None),
        "physical_progress_supported": int(physical_supported),
        "start_date_is_present": int(bool(current.get("start_date", ""))),
        "start_date_supported": int(start_supported),
        "exp_delta_1m_is_supported": int(exp_delta_1 is not None),
        "exp_delta_3m_is_supported": int(exp_delta_3 is not None),
        "progress_delta_3m_is_supported": int(progress_delta_3 is not None),
    }


def persistence_audit(rows: list[dict[str, str]]) -> dict[str, Any]:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        segment, regime = segment_for_month(row["report_month"]) or ("UNASSIGNED", "UNASSIGNED")
        grouped[(row["project_code"], segment, regime)].append(row)

    result: dict[str, Any] = {}
    for field in ("revised_completion_date", "revised_cost"):
        result[field] = {}
        total_projects: set[str] = set()
        total_observations = 0
        total_transitions = 0
        for regime in ("LEGACY", "MODERN"):
            affected: set[str] = set()
            later_nulls = 0
            transitions = 0
            examples: list[dict[str, str]] = []
            for (code, segment, item_regime), items in grouped.items():
                if item_regime != regime:
                    continue
                ordered = sorted(items, key=lambda row: row["report_month"])
                seen = False
                for index, row in enumerate(ordered):
                    value = row.get(field, "")
                    if value:
                        seen = True
                    elif seen:
                        affected.add(code)
                        later_nulls += 1
                    if index and ordered[index - 1].get(field, "") and not value:
                        transitions += 1
                        if len(examples) < 10:
                            examples.append(
                                {
                                    "project_code": code,
                                    "continuous_segment": segment,
                                    "previous_month": ordered[index - 1]["report_month"],
                                    "previous_value": ordered[index - 1][field],
                                    "current_month": row["report_month"],
                                    "project_name": row.get("project_name", ""),
                                    "agency": row.get("agency", ""),
                                }
                            )
            result[field][regime] = {
                "projects_affected": len(affected),
                "later_null_project_months": later_nulls,
                "adjacent_non_null_to_null_transitions": transitions,
                "representative_examples": examples,
            }
            total_projects.update(affected)
            total_observations += later_nulls
            total_transitions += transitions
        result[field]["TOTAL"] = {
            "projects_affected": len(total_projects),
            "later_null_project_months": total_observations,
            "adjacent_non_null_to_null_transitions": total_transitions,
        }
    return result


def _completed_metadata(rows: list[dict[str, str]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in rows:
        code = row["project_code"]
        month = row["report_month"]
        if not result.get(code) or month < result[code]:
            result[code] = month
    return result


def _validate_outputs(eligible: list[dict[str, Any]]) -> dict[str, Any]:
    keys = [(row["project_code"], row["report_month"]) for row in eligible]
    duplicate_keys = len(keys) - len(set(keys))
    bad_positive = sum(
        1
        for row in eligible
        if row["target_effective_schedule_ext_3m"] == 1
        and (
            not row["target_event_revised_completion_date"]
            or month_index(row["target_event_revised_completion_date"])
            <= month_index(row["baseline_completion_date"])
        )
    )
    bad_negative = sum(
        1
        for row in eligible
        if row["target_effective_schedule_ext_3m"] == 0
        and row["target_window_end_month"] != add_months(row["report_month"], HORIZON)
    )
    boundary_crossings = sum(
        1
        for row in eligible
        if segment_for_month(row["report_month"]) != segment_for_month(row["target_window_end_month"])
    )
    if duplicate_keys or bad_positive or bad_negative or boundary_crossings:
        raise RuntimeError(
            "Generated dataset validation failed: "
            f"duplicates={duplicate_keys}, bad_positive={bad_positive}, "
            f"bad_negative={bad_negative}, boundary_crossings={boundary_crossings}"
        )
    return {
        "duplicate_prediction_keys": duplicate_keys,
        "positive_event_reproduction_failures": bad_positive,
        "negative_window_validation_failures": bad_negative,
        "structural_gap_or_regime_crossings": boundary_crossings,
        "future_derived_feature_columns": [],
        "completed_project_feature_columns": sorted(set(FEATURE_COLUMNS) & set(LEAKAGE_METADATA_COLUMNS)),
    }


def build(root: Path) -> dict[str, Any]:
    root = root.resolve()
    ongoing_path = root / "data" / "processed" / "projects_monthly.csv"
    completed_path = root / "data" / "processed" / "projects_completed.csv"
    output_dir = root / "data" / "ml" / "schedule_extension_3m"
    output_dir.mkdir(parents=True, exist_ok=True)

    actual_hashes = {"projects_monthly.csv": sha256(ongoing_path), "projects_completed.csv": sha256(completed_path)}
    expected_hashes = {"projects_monthly.csv": ONGOING_SHA256, "projects_completed.csv": COMPLETED_SHA256}
    if actual_hashes != expected_hashes:
        raise RuntimeError(f"Canonical hash mismatch; refusing to build: {actual_hashes}")

    ongoing = _read_csv(ongoing_path)
    completed = _read_csv(completed_path)
    completed_month = _completed_metadata(completed)
    persistence = persistence_audit(ongoing)

    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in ongoing:
        assignment = segment_for_month(row["report_month"])
        if assignment is None:
            raise RuntimeError(f"Unassigned report month {row['report_month']}")
        grouped[(row["project_code"], assignment[0])].append(row)

    eligible: list[dict[str, Any]] = []
    ineligible: list[dict[str, Any]] = []
    reason_counts: Counter[tuple[str, str]] = Counter()
    for (code, segment), history in sorted(grouped.items()):
        history.sort(key=lambda row: row["report_month"])
        by_month = {row["report_month"]: row for row in history}
        regime = segment_for_month(history[0]["report_month"])[1]  # type: ignore[index]
        for current in history:
            decision = classify_target(current, by_month, history)
            if not decision.eligible:
                reason_counts[(regime, decision.reason)] += 1
                ineligible.append(
                    {
                        "project_code": code,
                        "report_month": current["report_month"],
                        "identifier_regime": regime,
                        "continuous_segment": segment,
                        "target_horizon_months": HORIZON,
                        "target_window_end_month": decision.window_end,
                        "eligibility_status": "INELIGIBLE",
                        "rejection_reason": decision.reason,
                        "baseline_completion_date": decision.baseline,
                        "baseline_completion_source": decision.baseline_source,
                    }
                )
                continue

            record: dict[str, Any] = {
                "project_code": code,
                "report_month": current["report_month"],
                "identifier_regime": regime,
                "continuous_segment": segment,
                "target_horizon_months": HORIZON,
                "target_window_end_month": decision.window_end,
                "target_effective_schedule_ext_3m": decision.label,
                "extension_type": decision.extension_type,
                "baseline_completion_date": decision.baseline,
                "baseline_completion_source": decision.baseline_source,
                "target_event_month": decision.event_month,
                "target_event_revised_completion_date": decision.event_value,
                "eventually_completed": int(code in completed_month),
                "completion_report_month": completed_month.get(code, ""),
            }
            record.update(build_features(current, by_month, history, decision.baseline))
            eligible.append(record)

    eligible.sort(key=lambda row: (row["report_month"], row["project_code"]))
    ineligible.sort(key=lambda row: (row["report_month"], row["project_code"]))
    legacy = [row for row in eligible if row["identifier_regime"] == "LEGACY"]
    modern = [row for row in eligible if row["identifier_regime"] == "MODERN"]
    validation = _validate_outputs(eligible)

    output_fields = METADATA_COLUMNS + FEATURE_COLUMNS
    legacy_path = output_dir / "eligible_legacy.csv"
    modern_path = output_dir / "eligible_modern.csv"
    ineligible_path = output_dir / "ineligible_window_audit.csv"
    reason_path = output_dir / "ineligible_reason_counts.csv"
    persistence_path = output_dir / "effective_commitment_persistence_audit.json"
    _write_csv(legacy_path, output_fields, legacy)
    _write_csv(modern_path, output_fields, modern)
    _write_csv(
        ineligible_path,
        [
            "project_code", "report_month", "identifier_regime", "continuous_segment",
            "target_horizon_months", "target_window_end_month", "eligibility_status",
            "rejection_reason", "baseline_completion_date", "baseline_completion_source",
        ],
        ineligible,
    )
    reason_rows = [
        {"identifier_regime": regime, "rejection_reason": reason, "count": count}
        for (regime, reason), count in sorted(reason_counts.items())
    ]
    _write_csv(reason_path, ["identifier_regime", "rejection_reason", "count"], reason_rows)
    persistence_path.write_text(json.dumps(persistence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def regime_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
        positives = sum(row["target_effective_schedule_ext_3m"] for row in rows)
        first = sum(row["extension_type"] == "FIRST_REVISION" for row in rows)
        subsequent = sum(row["extension_type"] == "SUBSEQUENT_REVISION" for row in rows)
        return {
            "eligible_rows": len(rows),
            "positive_rows": positives,
            "negative_rows": len(rows) - positives,
            "positive_rate": positives / len(rows) if rows else 0,
            "first_revision_positives": first,
            "subsequent_revision_positives": subsequent,
        }

    generated_paths = [legacy_path, modern_path, ineligible_path, reason_path, persistence_path]
    manifest: dict[str, Any] = {
        "dataset_name": "schedule_extension_3m_v1",
        "builder": "src.ml.dataset_builder",
        "target": "target_effective_schedule_ext_3m",
        "target_horizon_months": HORIZON,
        "canonical_inputs": {
            "projects_monthly.csv": {"rows": len(ongoing), "sha256": actual_hashes["projects_monthly.csv"]},
            "projects_completed.csv": {"rows": len(completed), "sha256": actual_hashes["projects_completed.csv"]},
        },
        "continuous_segments": [
            {"name": name, "identifier_regime": regime, "start": start, "end": end}
            for name, regime, start, end in SEGMENTS
        ],
        "target_rule": {
            "baseline": "revised_completion_date(T) when actually reported, else original_completion_date(T)",
            "positive": "At least one actually reported revised_completion_date in T+1..T+3 is later than the usable T baseline.",
            "negative": "Complete same-segment T+1..T+3 observations, no reported extension, and no unresolved revised-value null after a revision has appeared.",
            "ambiguity": "A null never resets a previously reported revision to the original commitment. Such baseline/window ambiguity is ineligible unless a reported future extension already proves a positive.",
            "first_vs_subsequent": "FIRST_REVISION when no revised date is reported at T; SUBSEQUENT_REVISION when T has a revised date; NONE for negatives.",
        },
        "feature_columns": FEATURE_COLUMNS,
        "metadata_columns": METADATA_COLUMNS,
        "metadata_only_leakage_do_not_use": LEAKAGE_METADATA_COLUMNS,
        "identifier_only_metadata": ["project_code"],
        "target_and_reproducibility_metadata": [
            column
            for column in METADATA_COLUMNS
            if column not in LEAKAGE_METADATA_COLUMNS and column != "project_code"
        ],
        "excluded_from_v1": ["project_name", "ministry", "source provenance", "raw fields", "completed-project fields other than explicit metadata"],
        "categorical_policy": "Raw source-faithful categorical values retained; no encoder fitted.",
        "missingness_policy": "No imputation. Structural/source missingness remains empty with support/presence indicators.",
        "walk_forward_embargo_rule": "For evaluation reference month E, training T is usable only when T + 3 months < E.",
        "random_split_created": False,
        "summary": {"LEGACY": regime_summary(legacy), "MODERN": regime_summary(modern)},
        "ineligible_rows": len(ineligible),
        "ineligible_reason_counts": reason_rows,
        "persistence_audit": persistence,
        "design_estimate_reconciliation": {
            "design_effective_semantics": {"eligible_rows": 39932, "positive_rows": 7845},
            "corrected_conservative_semantics": {
                "eligible_rows": len(eligible),
                "positive_rows": sum(row["target_effective_schedule_ext_3m"] for row in eligible),
            },
            "explanation": "Differences arise because the implementation requires actual reported future revised values for positives and excludes null-return windows after a revision instead of treating null as a return to the original commitment.",
        },
        "validations": validation,
        "generated_files": {},
    }
    manifest_path = output_dir / "manifest.json"
    for path in generated_paths:
        manifest["generated_files"][path.name] = {"sha256": sha256(path)}
        if path.suffix == ".csv":
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                manifest["generated_files"][path.name]["rows"] = sum(1 for _ in csv.DictReader(handle))
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    manifest["generated_files"][manifest_path.name] = {"sha256": sha256(manifest_path)}
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    manifest = build(args.root)
    print(json.dumps(manifest["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
