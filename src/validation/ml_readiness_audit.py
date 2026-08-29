from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


MONTHS = [
    *[f"2023-{month:02d}" for month in range(1, 12)],
    "2024-01",
    "2024-02",
    "2024-03",
    "2024-06",
    "2024-07",
    "2024-08",
    "2024-09",
    "2024-10",
    "2024-11",
    "2024-12",
    *[f"2025-{month:02d}" for month in range(1, 13)],
    *[f"2026-{month:02d}" for month in range(1, 8)],
]
ERAS = {
    "legacy_id_era": [month for month in MONTHS if month <= "2025-06"],
    "six_digit_id_era": [month for month in MONTHS if month >= "2025-07"],
}
VERIFIED_LAYOUT_BY_MONTH = {
    **{f"2023-{month:02d}": "legacy-detail-ongoing-nine-column-milestones-v1" for month in range(1, 12)},
    "2024-01": "legacy-detail-ongoing-nine-column-milestones-v1",
    "2024-02": "legacy-detail-ongoing-nine-column-milestones-v1",
    "2024-03": "legacy-detail-ongoing-nine-column-milestones-v1",
    "2024-06": "legacy-all-ongoing-nine-column-v1",
    "2024-07": "legacy-all-ongoing-nine-column-v1",
    "2024-08": "legacy-all-ongoing-nine-column-v1",
    "2024-09": "legacy-all-ongoing-nine-column-v1",
    "2024-10": "legacy-all-ongoing-nine-column-v1",
    "2024-11": "legacy-all-ongoing-nine-column-progress-only-v1",
    "2024-12": "legacy-all-ongoing-nine-column-v1",
    **{f"2025-{month:02d}": "legacy-all-ongoing-nine-column-v1" for month in range(1, 7)},
    "2025-07": "table6-eight-column-approval-only-v1",
    **{f"2025-{month:02d}": "table6-eight-column-v1" for month in range(8, 13)},
    **{f"2026-{month:02d}": "table6-eight-column-v1" for month in range(1, 8)},
}
MODELLING_FIELDS = [
    "project_code",
    "project_name",
    "agency",
    "ministry",
    "sector",
    "state",
    "approval_date",
    "start_date",
    "original_completion_date",
    "revised_completion_date",
    "original_cost",
    "revised_cost",
    "cumulative_expenditure",
    "physical_progress",
]
STRUCTURALLY_ABSENT = {
    "legacy-detail-ongoing-nine-column-milestones-v1": {"ministry", "start_date", "physical_progress"},
    "legacy-all-ongoing-nine-column-v1": {"ministry", "start_date"},
    "legacy-all-ongoing-nine-column-progress-only-v1": {"ministry", "start_date"},
    "table6-eight-column-approval-only-v1": {"start_date"},
    "table6-eight-column-v1": set(),
}


def is_missing(value: Any) -> bool:
    return value is None or str(value).strip() == ""


def numeric(value: str) -> float | None:
    if is_missing(value):
        return None
    return float(value)


def month_number(value: str) -> int:
    year, month = value[:7].split("-")
    return int(year) * 12 + int(month)


def month_distance(earlier: str, later: str) -> int:
    return month_number(later) - month_number(earlier)


def get_consecutive_calendar_months(start_m: str, horizon: int) -> list[str]:
    y, m = int(start_m[:4]), int(start_m[5:7])
    res = []
    for step in range(horizon + 1):
        cur_m = m + step
        cur_y = y + (cur_m - 1) // 12
        cur_m = (cur_m - 1) % 12 + 1
        res.append(f"{cur_y:04d}-{cur_m:02d}")
    return res


def quantile(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def rounded(value: float | None, places: int = 4) -> float | None:
    return None if value is None else round(value, places)


def distribution(values: Iterable[float]) -> dict[str, Any]:
    items = list(values)
    if not items:
        return {
            "count": 0,
            "minimum": None,
            "p25": None,
            "median": None,
            "mean": None,
            "p75": None,
            "maximum": None,
            "sum": None,
        }
    return {
        "count": len(items),
        "minimum": rounded(min(items)),
        "p25": rounded(quantile(items, 0.25)),
        "median": rounded(statistics.median(items)),
        "mean": rounded(statistics.fmean(items)),
        "p75": rounded(quantile(items, 0.75)),
        "maximum": rounded(max(items)),
        "sum": rounded(sum(items)),
    }


def load_rows(root: Path) -> tuple[list[dict[str, str]], dict[str, str]]:
    combined = root / "data" / "processed" / "projects_monthly.csv"
    with combined.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    layouts: dict[str, str] = {}
    for month in MONTHS:
        token = month.replace("-", "_")
        manifest = json.loads(
            (root / "data" / "validation" / f"manifest_{token}.json").read_text(encoding="utf-8")
        )
        versions = manifest.get("layout_versions", [VERIFIED_LAYOUT_BY_MONTH[month]])
        if len(versions) != 1:
            raise ValueError(f"Expected exactly one layout for {month}, got {versions}")
        layouts[month] = versions[0]
    for row in rows:
        row["_layout"] = layouts[row["report_month"]]
        row["_era"] = "legacy_id_era" if row["report_month"] <= "2025-06" else "six_digit_id_era"
    return rows, layouts


def group_by_project(rows: Iterable[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["project_code"]].append(row)
    for project_rows in grouped.values():
        project_rows.sort(key=lambda item: item["report_month"])
    return grouped


def adjacent_pairs(rows: Iterable[dict[str, str]]) -> list[tuple[dict[str, str], dict[str, str]]]:
    pairs: list[tuple[dict[str, str], dict[str, str]]] = []
    for project_rows in group_by_project(rows).values():
        for previous, current in zip(project_rows, project_rows[1:]):
            if previous["_era"] == current["_era"] and month_distance(
                previous["report_month"], current["report_month"]
            ) == 1:
                pairs.append((previous, current))
    return pairs


def observation_summary(rows: list[dict[str, str]], era_months: list[str]) -> dict[str, Any]:
    counts = [len(items) for items in group_by_project(rows).values()]
    summary = distribution(counts)
    return {
        "months": era_months,
        "project_month_rows": len(rows),
        "unique_source_project_codes": len(counts),
        "observations_per_project": summary,
        "projects_with_at_least_3_observations": sum(value >= 3 for value in counts),
        "projects_with_at_least_6_observations": sum(value >= 6 for value in counts),
        "projects_with_at_least_9_observations": sum(value >= 9 for value in counts),
        "projects_with_at_least_12_observations": sum(value >= 12 for value in counts),
        "projects_with_at_least_16_observations": sum(value >= 16 for value in counts),
        "projects_with_at_least_18_observations": sum(value >= 18 for value in counts),
        "projects_with_at_least_24_observations": sum(value >= 24 for value in counts),
        "projects_with_at_least_27_observations": sum(value >= 27 for value in counts),
        "projects_present_in_every_era_month": sum(value == len(era_months) for value in counts),
    }


def monthly_coverage(rows: list[dict[str, str]], layouts: dict[str, str]) -> list[dict[str, Any]]:
    by_month = {month: [row for row in rows if row["report_month"] == month] for month in MONTHS}
    result = []
    for era, era_months in ERAS.items():
        for index, month in enumerate(era_months):
            current = {row["project_code"] for row in by_month[month]}
            previous = (
                {row["project_code"] for row in by_month[era_months[index - 1]]} if index > 0 else None
            )
            following = (
                {row["project_code"] for row in by_month[era_months[index + 1]]}
                if index + 1 < len(era_months)
                else None
            )
            note = (
                "initial era stock; no prior same-era month"
                if previous is None
                else (
                    "end of identifier era; June-to-July redesign is not churn"
                    if month == "2025-06"
                    else (
                        "precedes 2-month gap (2023-12 unavailable)"
                        if month == "2023-11"
                        else (
                            "comparison across 2-month gap (2023-12 unavailable)"
                            if month == "2024-01"
                            else (
                                "precedes 3-month gap (April/May uncoded)"
                                if month == "2024-03"
                                else (
                                    "comparison across 3-month gap (April/May uncoded)"
                                    if month == "2024-06"
                                    else ("right-censored dataset endpoint" if following is None else "same-era comparison")
                                )
                            )
                        )
                    )
                )
            )
            result.append(
                {
                    "report_month": month,
                    "identifier_era": era,
                    "layout": layouts[month],
                    "project_rows": len(by_month[month]),
                    "unique_projects": len(current),
                    "new_project_codes_vs_previous_same_era_month": (
                        None if previous is None else len(current - previous)
                    ),
                    "project_codes_disappearing_before_next_same_era_month": (
                        None if following is None else len(current - following)
                    ),
                    "comparison_note": note,
                }
            )
    return result


def missingness_for_rows(rows: list[dict[str, str]]) -> dict[str, Any]:
    result: dict[str, Any] = {"rows": len(rows), "fields": {}}
    for field in MODELLING_FIELDS:
        structural = sum(field in STRUCTURALLY_ABSENT[row["_layout"]] for row in rows)
        source_missing = sum(
            field not in STRUCTURALLY_ABSENT[row["_layout"]] and is_missing(row[field]) for row in rows
        )
        present = len(rows) - structural - source_missing
        applicable = len(rows) - structural
        result["fields"][field] = {
            "present": present,
            "structurally_absent": structural,
            "source_missing": source_missing,
            "completeness_rate_all_rows": rounded(present / len(rows) if rows else None),
            "source_completeness_rate_when_applicable": rounded(present / applicable if applicable else None),
            "source_missing_rate_when_applicable": rounded(source_missing / applicable if applicable else None),
        }
    return result


def missingness_summary(rows: list[dict[str, str]]) -> dict[str, Any]:
    by_month = {
        month: missingness_for_rows([row for row in rows if row["report_month"] == month]) for month in MONTHS
    }
    layouts = sorted({row["_layout"] for row in rows})
    by_layout = {
        layout: missingness_for_rows([row for row in rows if row["_layout"] == layout]) for layout in layouts
    }
    by_sector = {
        key: missingness_for_rows(items)
        for key, items in sorted(group_records(rows, "sector").items(), key=lambda item: (-len(item[1]), item[0]))
    }
    by_agency = {
        key: missingness_for_rows(items)
        for key, items in sorted(group_records(rows, "agency").items(), key=lambda item: (-len(item[1]), item[0]))
    }
    return {
        "definitions": {
            "structurally_absent": "The source layout does not contain this field; it is not random missingness.",
            "source_missing": "The layout supports the field but the source-faithful value is empty.",
        },
        "overall": missingness_for_rows(rows),
        "by_month": by_month,
        "by_layout": by_layout,
        "by_sector_exact_source_value": by_sector,
        "by_agency_exact_source_value": by_agency,
    }


def change_event_summary(rows: list[dict[str, str]], field: str, kind: str) -> dict[str, Any]:
    pairs = adjacent_pairs(rows)
    comparable = []
    for previous, current in pairs:
        if is_missing(previous[field]) or is_missing(current[field]):
            continue
        comparable.append((previous, current))
    changes_by_project: Counter[str] = Counter()
    upward: list[float] = []
    downward: list[float] = []
    unchanged = 0
    for previous, current in comparable:
        if kind == "numeric":
            before = numeric(previous[field])
            after = numeric(current[field])
            assert before is not None and after is not None
            delta = after - before
        else:
            delta = month_distance(previous[field], current[field])
        if delta > 0:
            upward.append(delta)
            changes_by_project[previous["project_code"]] += 1
        elif delta < 0:
            downward.append(abs(delta))
            changes_by_project[previous["project_code"]] += 1
        else:
            unchanged += 1
    return {
        "comparison_definition": "Adjacent report-month observations within one identifier era; both values must be present.",
        "comparable_adjacent_pairs": len(comparable),
        "unchanged_pairs": unchanged,
        "projects_with_at_least_one_change": len(changes_by_project),
        "projects_with_multiple_changes": sum(count >= 2 for count in changes_by_project.values()),
        "changes_per_changed_project": distribution(changes_by_project.values()),
        "upward_changes": len(upward),
        "downward_changes": len(downward),
        "upward_magnitude": distribution(upward),
        "downward_magnitude_absolute": distribution(downward),
    }


def reported_observation_counts(rows: list[dict[str, str]], field: str) -> dict[str, Any]:
    counts = [
        sum(not is_missing(row[field]) for row in project_rows)
        for project_rows in group_by_project(rows).values()
    ]
    return {
        "projects": len(counts),
        "projects_with_at_least_2_reported_observations": sum(value >= 2 for value in counts),
        "projects_with_at_least_3_reported_observations": sum(value >= 3 for value in counts),
        "projects_with_at_least_6_reported_observations": sum(value >= 6 for value in counts),
        "projects_with_at_least_9_reported_observations": sum(value >= 9 for value in counts),
        "projects_with_at_least_12_reported_observations": sum(value >= 12 for value in counts),
        "reported_observations_per_project": distribution(counts),
    }


def unchanged_runs(rows: list[dict[str, str]], field: str) -> dict[str, Any]:
    runs: list[int] = []
    max_by_project: dict[str, int] = {}
    for project_code, project_rows in group_by_project(rows).items():
        current_run = 1
        best = 1
        previous = None
        for row in project_rows:
            value = numeric(row[field])
            if value is None:
                if current_run >= 2:
                    runs.append(current_run)
                current_run = 1
                previous = None
                continue
            if (
                previous is not None
                and previous["_era"] == row["_era"]
                and month_distance(previous["report_month"], row["report_month"]) == 1
                and numeric(previous[field]) == value
            ):
                current_run += 1
            else:
                if current_run >= 2:
                    runs.append(current_run)
                current_run = 1
            best = max(best, current_run)
            previous = row
        if current_run >= 2:
            runs.append(current_run)
        max_by_project[project_code] = best
    return {
        "definition": "A run is consecutive same-era report months with the same reported numeric value; missing months/values break a run.",
        "unchanged_runs_total": len(runs),
        "projects_with_any_unchanged_run": sum(value >= 2 for value in max_by_project.values()),
        "runs_of_at_least_2_months": sum(value >= 2 for value in runs),
        "runs_of_at_least_3_months": sum(value >= 3 for value in runs),
        "runs_of_at_least_6_months": sum(value >= 6 for value in runs),
        "runs_of_at_least_9_months": sum(value >= 9 for value in runs),
        "runs_of_at_least_12_months": sum(value >= 12 for value in runs),
        "maximum_run_months": max(runs, default=0),
        "run_length_distribution_months": distribution(runs),
    }


def numeric_history_summary(rows: list[dict[str, str]], field: str) -> dict[str, Any]:
    pairs = [
        (previous, current)
        for previous, current in adjacent_pairs(rows)
        if not is_missing(previous[field]) and not is_missing(current[field])
    ]
    increases = decreases = unchanged = positive_to_zero = 0
    for previous, current in pairs:
        before = numeric(previous[field])
        after = numeric(current[field])
        assert before is not None and after is not None
        if after > before:
            increases += 1
        elif after < before:
            decreases += 1
        else:
            unchanged += 1
        if before > 0 and after == 0:
            positive_to_zero += 1
    return {
        "comparable_adjacent_pairs": len(pairs),
        "increases": increases,
        "unchanged": unchanged,
        "reported_decreases_or_corrections": decreases,
        "positive_to_zero_resets": positive_to_zero,
    }


def progress_and_expenditure(rows: list[dict[str, str]]) -> dict[str, Any]:
    progress: dict[str, Any] = {
        "overall": reported_observation_counts(rows, "physical_progress"),
        "legacy_id_era": reported_observation_counts(
            [row for row in rows if row["_era"] == "legacy_id_era"], "physical_progress"
        ),
        "six_digit_id_era": reported_observation_counts(
            [row for row in rows if row["_era"] == "six_digit_id_era"], "physical_progress"
        ),
        "adjacent_changes": numeric_history_summary(rows, "physical_progress"),
        "unchanged_progress_runs": unchanged_runs(rows, "physical_progress"),
    }
    expenditure_observations = [row for row in rows if not is_missing(row["cumulative_expenditure"])]
    zero_rows = [row for row in expenditure_observations if numeric(row["cumulative_expenditure"]) == 0]
    zero_positive = [
        row
        for row in zero_rows
        if numeric(row["physical_progress"]) is not None and numeric(row["physical_progress"]) > 0
    ]
    grouped = group_by_project(expenditure_observations)
    agency_records = []
    for agency, agency_rows in group_records(expenditure_observations, "agency").items():
        agency_zero = [row for row in agency_rows if numeric(row["cumulative_expenditure"]) == 0]
        agency_zero_positive = [
            row
            for row in agency_zero
            if numeric(row["physical_progress"]) is not None and numeric(row["physical_progress"]) > 0
        ]
        agency_records.append(
            {
                "agency_exact": agency,
                "project_month_rows_with_expenditure": len(agency_rows),
                "unique_projects": len({row["project_code"] for row in agency_rows}),
                "zero_expenditure_rows": len(agency_zero),
                "zero_expenditure_rate": rounded(len(agency_zero) / len(agency_rows)),
                "zero_expenditure_positive_progress_rows": len(agency_zero_positive),
                "projects_with_zero_expenditure_positive_progress": len(
                    {row["project_code"] for row in agency_zero_positive}
                ),
            }
        )
    agency_records.sort(
        key=lambda item: (
            -item["zero_expenditure_positive_progress_rows"],
            -item["zero_expenditure_rows"],
            item["agency_exact"],
        )
    )
    expenditure = {
        "overall": reported_observation_counts(rows, "cumulative_expenditure"),
        "legacy_id_era": reported_observation_counts(
            [row for row in rows if row["_era"] == "legacy_id_era"], "cumulative_expenditure"
        ),
        "six_digit_id_era": reported_observation_counts(
            [row for row in rows if row["_era"] == "six_digit_id_era"], "cumulative_expenditure"
        ),
        "adjacent_changes": numeric_history_summary(rows, "cumulative_expenditure"),
        "rows_with_reported_expenditure": len(expenditure_observations),
        "zero_expenditure_rows": len(zero_rows),
        "projects_ever_reporting_zero": len({row["project_code"] for row in zero_rows}),
        "projects_always_zero_when_reported": sum(
            all(numeric(row["cumulative_expenditure"]) == 0 for row in project_rows)
            for project_rows in grouped.values()
        ),
        "zero_expenditure_positive_progress_rows": len(zero_positive),
        "projects_with_zero_expenditure_positive_progress": len(
            {row["project_code"] for row in zero_positive}
        ),
        "agency_specific_exact_source_values": agency_records,
    }
    return {"physical_progress": progress, "cumulative_expenditure": expenditure}


def group_records(rows: Iterable[dict[str, str]], field: str) -> dict[str, list[dict[str, str]]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row[field] if not is_missing(row[field]) else "(MISSING)"].append(row)
    return groups


def category_coverage(rows: list[dict[str, str]]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "sparse_definition": "Extremely sparse means fewer than 10 project-month rows or fewer than 3 unique source project codes; this is an audit flag, not a modelling cutoff.",
        "dimensions": {},
    }
    for field in ["ministry", "sector", "agency", "state"]:
        records = []
        for value, items in group_records(rows, field).items():
            records.append(
                {
                    "source_value": value,
                    "project_month_rows": len(items),
                    "unique_source_project_codes": len({row["project_code"] for row in items}),
                    "months_present": len({row["report_month"] for row in items}),
                    "extremely_sparse": len(items) < 10
                    or len({row["project_code"] for row in items}) < 3,
                }
            )
        records.sort(key=lambda item: (-item["project_month_rows"], item["source_value"]))
        nonmissing = [record for record in records if record["source_value"] != "(MISSING)"]
        result["dimensions"][field] = {
            "exact_nonmissing_categories": len(nonmissing),
            "missing_project_month_rows": next(
                (record["project_month_rows"] for record in records if record["source_value"] == "(MISSING)"),
                0,
            ),
            "extremely_sparse_nonmissing_categories": sum(
                record["extremely_sparse"] for record in nonmissing
            ),
            "categories": records,
        }
    return result


def horizon_eligibility(rows: list[dict[str, str]]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "definition": "Primary eligibility requires the same exact source project code in every report month from T through T+H within one identifier era. Coverage ceiling only requires H later report months in the era and ignores project attrition. Cost escalation is defined as a future upward reported cost revision (revised_cost_{T+H} > revised_cost_T). Schedule revision is defined as a future schedule extension (revised_completion_date_{T+H} > revised_completion_date_T). Stagnation is defined as zero delta across the window.",
        "eras": {},
    }
    for era, era_months in ERAS.items():
        era_rows = [row for row in rows if row["_era"] == era]
        era_months_set = set(era_months)
        grouped_p = group_by_project(era_rows)
        project_months = {
            project: {row["report_month"]: row for row in project_rows}
            for project, project_rows in grouped_p.items()
        }
        horizons = {}
        for horizon in [1, 3, 6, 12]:
            coverage_ceiling = 0
            complete = 0
            cost_comp = 0
            cost_up_endpoint = 0
            cost_up_any = 0
            sched_comp = 0
            sched_up_endpoint = 0
            sched_up_any = 0
            prog_comp = 0
            prog_stagnant = 0
            exp_comp = 0
            exp_stagnant = 0

            cost_up_endpoint_projects = set()
            cost_up_any_projects = set()
            sched_up_endpoint_projects = set()
            sched_up_any_projects = set()
            prog_stagnant_projects = set()
            exp_stagnant_projects = set()

            for row in era_rows:
                p = row["project_code"]
                T = row["report_month"]
                req_months = get_consecutive_calendar_months(T, horizon)

                if set(req_months).issubset(era_months_set):
                    coverage_ceiling += 1
                    p_month_dict = project_months[p]
                    if set(req_months).issubset(set(p_month_dict.keys())):
                        complete += 1
                        window_rows = [p_month_dict[m] for m in req_months]

                        # Cost
                        c_start = numeric(window_rows[0]["revised_cost"])
                        c_end = numeric(window_rows[-1]["revised_cost"])
                        if c_start is not None and c_end is not None:
                            cost_comp += 1
                            if c_end > c_start:
                                cost_up_endpoint += 1
                                cost_up_endpoint_projects.add(p)
                        costs_in_win = [
                            numeric(w["revised_cost"])
                            for w in window_rows
                            if numeric(w["revised_cost"]) is not None
                        ]
                        if len(costs_in_win) >= 2 and max(costs_in_win) > costs_in_win[0]:
                            cost_up_any += 1
                            cost_up_any_projects.add(p)

                        # Schedule
                        d_start = window_rows[0]["revised_completion_date"]
                        d_end = window_rows[-1]["revised_completion_date"]
                        if d_start and d_end:
                            sched_comp += 1
                            if month_distance(d_start, d_end) > 0:
                                sched_up_endpoint += 1
                                sched_up_endpoint_projects.add(p)
                        dates_in_win = [
                            w["revised_completion_date"]
                            for w in window_rows
                            if w["revised_completion_date"]
                        ]
                        if len(dates_in_win) >= 2 and any(
                            month_distance(dates_in_win[0], d) > 0 for d in dates_in_win[1:]
                        ):
                            sched_up_any += 1
                            sched_up_any_projects.add(p)

                        # Progress stagnation
                        p_start = numeric(window_rows[0]["physical_progress"])
                        p_end = numeric(window_rows[-1]["physical_progress"])
                        if p_start is not None and p_end is not None:
                            prog_comp += 1
                            if p_end == p_start:
                                prog_stagnant += 1
                                prog_stagnant_projects.add(p)

                        # Expenditure stagnation
                        e_start = numeric(window_rows[0]["cumulative_expenditure"])
                        e_end = numeric(window_rows[-1]["cumulative_expenditure"])
                        if e_start is not None and e_end is not None:
                            exp_comp += 1
                            if e_end == e_start:
                                exp_stagnant += 1
                                exp_stagnant_projects.add(p)

            horizons[str(horizon)] = {
                "complete_project_history_observations": complete,
                "calendar_coverage_ceiling_observations": coverage_ceiling,
                "observable_events": {
                    "cost_escalation": {
                        "comparable_windows": cost_comp,
                        "upward_endpoint_changes": cost_up_endpoint,
                        "upward_endpoint_rate": rounded(cost_up_endpoint / cost_comp if cost_comp else None),
                        "unique_projects_with_endpoint_escalation": len(cost_up_endpoint_projects),
                        "any_upward_window_changes": cost_up_any,
                        "unique_projects_with_any_escalation": len(cost_up_any_projects),
                        "approximate_class_imbalance": (
                            f"1:{round((cost_comp - cost_up_endpoint) / cost_up_endpoint, 1)}"
                            if cost_up_endpoint else "N/A"
                        ),
                    },
                    "schedule_revision": {
                        "comparable_windows": sched_comp,
                        "upward_endpoint_extensions": sched_up_endpoint,
                        "upward_endpoint_rate": rounded(sched_up_endpoint / sched_comp if sched_comp else None),
                        "unique_projects_with_endpoint_extension": len(sched_up_endpoint_projects),
                        "any_upward_window_extensions": sched_up_any,
                        "unique_projects_with_any_extension": len(sched_up_any_projects),
                        "approximate_class_imbalance": (
                            f"1:{round((sched_comp - sched_up_endpoint) / sched_up_endpoint, 1)}"
                            if sched_up_endpoint else "N/A"
                        ),
                    },
                    "physical_progress_stagnation": {
                        "comparable_windows": prog_comp,
                        "stagnant_observations": prog_stagnant,
                        "stagnation_rate": rounded(prog_stagnant / prog_comp if prog_comp else None),
                        "unique_projects_with_stagnation": len(prog_stagnant_projects),
                        "approximate_class_imbalance": (
                            f"1:{round((prog_comp - prog_stagnant) / prog_stagnant, 1)}"
                            if prog_stagnant else "N/A"
                        ),
                    },
                    "cumulative_expenditure_stagnation": {
                        "comparable_windows": exp_comp,
                        "stagnant_observations": exp_stagnant,
                        "stagnation_rate": rounded(exp_stagnant / exp_comp if exp_comp else None),
                        "unique_projects_with_stagnation": len(exp_stagnant_projects),
                        "approximate_class_imbalance": (
                            f"1:{round((exp_comp - exp_stagnant) / exp_stagnant, 1)}"
                            if exp_stagnant else "N/A"
                        ),
                    },
                },
            }
        result["eras"][era] = {
            "months": era_months,
            "project_month_rows": len(era_rows),
            "horizons_months": horizons,
        }
    return result


def leakage_risk() -> dict[str, Any]:
    return {
        "classifications": [
            "SAFE_BASE_FEATURE",
            "CONDITIONALLY_SAFE",
            "LIKELY_LEAKAGE_FOR_CERTAIN_TARGETS",
            "IDENTIFIER_ONLY",
        ],
        "fields": [
            {"field": "project_code", "classification": "IDENTIFIER_ONLY", "reason": "Exact source identifier; useful for grouping/splitting, not as a predictive signal. The June-July redesign must remain unbridged."},
            {"field": "legacy_ocms_code", "classification": "IDENTIFIER_ONLY", "reason": "Identifier/provenance only; sparsity and era specificity make it unsuitable as a general feature."},
            {"field": "pmgid", "classification": "IDENTIFIER_ONLY", "reason": "Identifier/provenance only."},
            {"field": "project_name", "classification": "IDENTIFIER_ONLY", "reason": "Near-unique text can memorize project identity; any future text analysis requires grouped temporal evaluation and a separate normalized representation."},
            {"field": "agency", "classification": "SAFE_BASE_FEATURE", "reason": "Source-reported category known at T, subject to label drift and sparse levels."},
            {"field": "ministry", "classification": "CONDITIONALLY_SAFE", "reason": "Known at T where present, but structurally absent in legacy layouts (100% of legacy era) and missingness strongly encodes era/schema."},
            {"field": "sector", "classification": "SAFE_BASE_FEATURE", "reason": "Source-reported category known at T; preserve exact labels and handle sparse levels only in a separate analytical layer."},
            {"field": "state", "classification": "SAFE_BASE_FEATURE", "reason": "Source-reported geography known at T, with multi-state/text conventions requiring careful analytical encoding."},
            {"field": "approval_date", "classification": "SAFE_BASE_FEATURE", "reason": "Historical date known by T; derived age would be feature engineering and is not created here."},
            {"field": "start_date", "classification": "CONDITIONALLY_SAFE", "reason": "Historical state known at T where present, but structurally absent through July 2025 (61.75% of dataset) and therefore strongly tied to layout/era."},
            {"field": "original_completion_date", "classification": "SAFE_BASE_FEATURE", "reason": "Baseline schedule known at T; safe when taken strictly from the T snapshot."},
            {"field": "revised_completion_date", "classification": "LIKELY_LEAKAGE_FOR_CERTAIN_TARGETS", "reason": "Legitimate state at T for predicting a later revision, but direct leakage if the target is defined as whether a revision already exists or current delay."},
            {"field": "original_cost", "classification": "SAFE_BASE_FEATURE", "reason": "Baseline cost known at T; safe when source-present and measured at T."},
            {"field": "revised_cost", "classification": "LIKELY_LEAKAGE_FOR_CERTAIN_TARGETS", "reason": "Legitimate state at T for future-horizon escalation, but direct leakage for targets based on current escalation or any revision to date."},
            {"field": "cumulative_expenditure", "classification": "CONDITIONALLY_SAFE", "reason": "T-snapshot value can describe current state; any later snapshot or future-derived delta leaks future information. Zero reporting is agency-dependent."},
            {"field": "physical_progress", "classification": "CONDITIONALLY_SAFE", "reason": "T-snapshot value is historical state, but future progress or stagnation-window summaries must not enter predictors for the same horizon. Structurally absent in Jan-Mar 2024."},
            {"field": "report_month", "classification": "CONDITIONALLY_SAFE", "reason": "Needed for temporal splitting and regime controls; can encode schema/reporting changes and should not support random row splits."},
            {"field": "*_raw", "classification": "IDENTIFIER_ONLY", "reason": "Audit/source representation; parsed canonical state should be preferred for modelling while raw values remain available for traceability."},
            {"field": "source_file/source_page/source_pages/source_row_number/source_serial_number/extraction_method", "classification": "IDENTIFIER_ONLY", "reason": "Provenance and extraction metadata; using them as predictors would encode report layout/order rather than project risk."},
        ],
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run(root: Path) -> dict[str, Any]:
    rows, layouts = load_rows(root)
    if len(rows) != 64608:
        raise ValueError(f"Unexpected canonical row count: {len(rows)}")
    if sorted({row["report_month"] for row in rows}) != MONTHS:
        raise ValueError("Canonical month coverage differs from the accepted 40-month baseline")

    overall_counts = [len(items) for items in group_by_project(rows).values()]

    era_summaries = {}
    for era, era_months in ERAS.items():
        era_rows = [row for row in rows if row["_era"] == era]
        era_summaries[era] = observation_summary(era_rows, era_months)

    events = {
        "revised_cost": {
            "overall": change_event_summary(rows, "revised_cost", "numeric"),
            "legacy_id_era": change_event_summary(
                [row for row in rows if row["_era"] == "legacy_id_era"], "revised_cost", "numeric"
            ),
            "six_digit_id_era": change_event_summary(
                [row for row in rows if row["_era"] == "six_digit_id_era"], "revised_cost", "numeric"
            ),
            "magnitude_unit": "Rs crore; downward magnitudes are absolute values",
        },
        "revised_completion_date": {
            "overall": change_event_summary(rows, "revised_completion_date", "month"),
            "legacy_id_era": change_event_summary(
                [row for row in rows if row["_era"] == "legacy_id_era"],
                "revised_completion_date",
                "month",
            ),
            "six_digit_id_era": change_event_summary(
                [row for row in rows if row["_era"] == "six_digit_id_era"],
                "revised_completion_date",
                "month",
            ),
            "magnitude_unit": "calendar months; upward means extension and downward means reduction",
        },
    }

    output_dir = root / "data" / "validation" / "audit"
    output_dir.mkdir(parents=True, exist_ok=True)
    payloads = {
        "coverage_summary.json": {
            "dataset": {
                "months": MONTHS,
                "project_month_rows": len(rows),
                "unique_source_project_codes": len({row["project_code"] for row in rows}),
                "missing_project_codes": sum(is_missing(row["project_code"]) for row in rows),
                "duplicate_project_month_keys": len(rows)
                - len({(row["project_code"], row["report_month"]) for row in rows}),
                "projects_with_at_least_3_observations": sum(v >= 3 for v in overall_counts),
                "projects_with_at_least_6_observations": sum(v >= 6 for v in overall_counts),
                "projects_with_at_least_12_observations": sum(v >= 12 for v in overall_counts),
                "projects_with_at_least_18_observations": sum(v >= 18 for v in overall_counts),
                "projects_with_at_least_24_observations": sum(v >= 24 for v in overall_counts),
                "projects_with_at_least_30_observations": sum(v >= 30 for v in overall_counts),
            },
            "monthly": monthly_coverage(rows, layouts),
            "identifier_eras": era_summaries,
        },
        "field_missingness.json": missingness_summary(rows),
        "event_audit.json": {
            **events,
            **progress_and_expenditure(rows),
        },
        "category_coverage.json": category_coverage(rows),
        "horizon_eligibility.json": horizon_eligibility(rows),
        "leakage_risk.json": leakage_risk(),
    }
    for filename, payload in payloads.items():
        write_json(output_dir / filename, payload)

    manifest = {
        "audit_scope": "Read-only ML-readiness and coverage audit; no feature or target construction",
        "source_combined_csv": str(root / "data" / "processed" / "projects_monthly.csv"),
        "source_combined_sha256": sha256(root / "data" / "processed" / "projects_monthly.csv"),
        "canonical_rows_read": len(rows),
        "output_files": sorted(payloads),
        "canonical_files_written": False,
        "identifier_crosswalk_integrated": False,
        "completed_projects_extracted": False,
    }
    write_json(output_dir / "audit_manifest.json", manifest)
    return {"manifest": manifest, "outputs": payloads}


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit ML readiness without modifying canonical PAIMANA data")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    result = run(args.root.resolve())
    print(json.dumps(result["manifest"], indent=2))


if __name__ == "__main__":
    main()
