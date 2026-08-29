"""Rebuild the combined dataset and longitudinal summaries from clean months."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from src.extraction.pipeline import CLEAN_FIELDS

DEFAULT_MONTHS = ("2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06", "2026-07")


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _number(value: str) -> float | None:
    return None if value == "" else float(value)


def _change(left: str, right: str) -> str:
    a, b = _number(left), _number(right)
    if a is None or b is None:
        return "missing"
    if b > a:
        return "increased"
    if b < a:
        return "decreased"
    return "unchanged"


def _expenditure_state(value: str) -> str:
    number = _number(value)
    if number is None:
        return "missing"
    if number == 0:
        return "zero"
    if number > 0:
        return "positive"
    return "negative"


def _normalize_diagnostic(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _are_consecutive_months(earlier: str, later: str) -> bool:
    earlier_year, earlier_month = (int(part) for part in earlier.split("-"))
    later_year, later_month = (int(part) for part in later.split("-"))
    expected_year = earlier_year + (1 if earlier_month == 12 else 0)
    expected_month = 1 if earlier_month == 12 else earlier_month + 1
    return (later_year, later_month) == (expected_year, expected_month)


def _pair_summary(earlier: str, later: str, rows_by_month: dict[str, list[dict[str, str]]]) -> dict[str, Any]:
    left = {row["project_code"]: row for row in rows_by_month[earlier]}
    right = {row["project_code"]: row for row in rows_by_month[later]}
    if len(left) != len(rows_by_month[earlier]) or len(right) != len(rows_by_month[later]):
        raise ValueError(f"Duplicate project code prevents longitudinal comparison: {earlier}->{later}")
    both = sorted(set(left) & set(right))
    numeric_changes = {
        field: Counter(_change(left[code][field], right[code][field]) for code in both)
        for field in ("revised_cost", "cumulative_expenditure", "physical_progress")
    }
    expenditure_transitions = Counter(
        f"{_expenditure_state(left[code]['cumulative_expenditure'])}_to_{_expenditure_state(right[code]['cumulative_expenditure'])}"
        for code in both
    )
    identity_changes = {
        field: sum(left[code][field] != right[code][field] for code in both)
        for field in ("project_name", "agency", "ministry")
    }
    for field in ("sector", "state"):
        identity_changes[field] = sum(
            _normalize_diagnostic(left[code][field]) != _normalize_diagnostic(right[code][field])
            for code in both
        )
        identity_changes[f"{field}_exact"] = sum(
            left[code][field] != right[code][field] for code in both
        )
    warning_counts = {
        "revised_cost_decreased": numeric_changes["revised_cost"].get("decreased", 0),
        "cumulative_expenditure_decreased": numeric_changes["cumulative_expenditure"].get("decreased", 0),
        "physical_progress_decreased": numeric_changes["physical_progress"].get("decreased", 0),
        "positive_to_zero_expenditure": expenditure_transitions.get("positive_to_zero", 0),
        "project_name_changed": identity_changes["project_name"],
        "agency_changed": identity_changes["agency"],
        "ministry_changed": identity_changes["ministry"],
        "sector_changed": identity_changes["sector"],
        "state_changed": identity_changes["state"],
    }
    warning_counts["total"] = sum(warning_counts.values())
    return {
        "earlier_month": earlier,
        "later_month": later,
        "earlier_project_rows": len(left),
        "later_project_rows": len(right),
        "projects_in_both": len(both),
        "earlier_only": len(set(left) - set(right)),
        "later_only": len(set(right) - set(left)),
        "expenditure_state_transitions": dict(sorted(expenditure_transitions.items())),
        "numeric_field_changes": {
            field: {key: counts.get(key, 0) for key in ("increased", "decreased", "unchanged", "missing")}
            for field, counts in numeric_changes.items()
        },
        "identity_field_change_counts": identity_changes,
        "longitudinal_warning_counts": warning_counts,
    }


def rebuild(root: Path, months: tuple[str, ...] = DEFAULT_MONTHS) -> tuple[Path, Path]:
    rows_by_month = {
        month: _read(root / "data" / "cleaned" / f"projects_{month.replace('-', '_')}.csv")
        for month in months
    }
    records = [row for month in months for row in rows_by_month[month]]
    records.sort(key=lambda row: (row["report_month"], row["project_code"]))
    key_counts = Counter((row["project_code"], row["report_month"]) for row in records)
    duplicate_keys = {key: count for key, count in key_counts.items() if count > 1}
    observations_by_project = Counter(row["project_code"] for row in records)

    combined_path = root / "data" / "processed" / "projects_monthly.csv"
    combined_path.parent.mkdir(parents=True, exist_ok=True)
    with combined_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CLEAN_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)

    transitions = [
        _pair_summary(a, b, rows_by_month)
        for a, b in zip(months, months[1:])
        if _are_consecutive_months(a, b)
    ]
    longitudinal_warning_codes = sorted(
        {code for transition in transitions for code in transition["longitudinal_warning_counts"] if code != "total"}
    )
    longitudinal_warning_counts = {
        code: sum(transition["longitudinal_warning_counts"][code] for transition in transitions)
        for code in longitudinal_warning_codes
    }
    longitudinal_warning_counts["total"] = sum(longitudinal_warning_counts.values())
    summary = {
        "rows": len(records),
        "report_months": list(months),
        "rows_by_month": {month: len(rows_by_month[month]) for month in months},
        "unique_projects": len(observations_by_project),
        "projects_with_at_least_3_observations": sum(count >= 3 for count in observations_by_project.values()),
        "projects_with_at_least_6_observations": sum(count >= 6 for count in observations_by_project.values()),
        "projects_with_at_least_10_observations": sum(count >= 10 for count in observations_by_project.values()),
        "projects_with_at_least_12_observations": sum(count >= 12 for count in observations_by_project.values()),
        "projects_with_at_least_16_observations": sum(count >= 16 for count in observations_by_project.values()),
        "projects_with_at_least_18_observations": sum(count >= 18 for count in observations_by_project.values()),
        "projects_with_at_least_19_observations": sum(count >= 19 for count in observations_by_project.values()),
        "projects_present_in_all_months": sum(count == len(months) for count in observations_by_project.values()),
        "duplicate_project_month_keys": len(duplicate_keys),
        "duplicate_project_month_rows": sum(duplicate_keys.values()),
        "adjacent_month_transitions": transitions,
        "longitudinal_warning_counts": longitudinal_warning_counts,
        "output_csv": str(combined_path.resolve()),
    }
    start_year, start_month = months[0].split("-")
    end_year, end_month = months[-1].split("-")
    summary_name = (
        f"longitudinal_summary_{start_year}_{start_month}_{end_month}.json"
        if start_year == end_year
        else f"longitudinal_summary_{start_year}_{start_month}_{end_year}_{end_month}.json"
    )
    summary_path = root / "data" / "validation" / summary_name
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Keep the established combined-summary location synchronized.
    combined_summary = {
        "rows": summary["rows"],
        "report_months": summary["report_months"],
        "rows_by_month": summary["rows_by_month"],
        "unique_projects": summary["unique_projects"],
        "projects_with_at_least_3_observations": summary["projects_with_at_least_3_observations"],
        "projects_with_at_least_6_observations": summary["projects_with_at_least_6_observations"],
        "projects_with_at_least_10_observations": summary["projects_with_at_least_10_observations"],
        "projects_with_at_least_12_observations": summary["projects_with_at_least_12_observations"],
        "projects_with_at_least_16_observations": summary["projects_with_at_least_16_observations"],
        "projects_with_at_least_18_observations": summary["projects_with_at_least_18_observations"],
        "projects_with_at_least_19_observations": summary["projects_with_at_least_19_observations"],
        "projects_present_in_all_months": summary["projects_present_in_all_months"],
        "duplicate_project_month_keys": summary["duplicate_project_month_keys"],
        "duplicate_project_month_rows": summary["duplicate_project_month_rows"],
        "adjacent_month_matching": [
            {
                "earlier_month": item["earlier_month"],
                "later_month": item["later_month"],
                "projects_in_both": item["projects_in_both"],
                "earlier_only": item["earlier_only"],
                "later_only": item["later_only"],
            }
            for item in transitions
        ],
        "longitudinal_warning_counts": summary["longitudinal_warning_counts"],
        "output_csv": str(combined_path.resolve()),
    }
    (root / "data" / "validation" / "combined_summary.json").write_text(
        json.dumps(combined_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    manifests = {
        month: json.loads(
            (root / "data" / "validation" / f"manifest_{month.replace('-', '_')}.json").read_text(encoding="utf-8")
        )
        for month in months
    }
    rule_codes = sorted({rule for manifest in manifests.values() for rule in manifest["warnings_by_rule"]})
    rule_summary = {
        "unit": "project-month records",
        "counts_by_report_month": {
            month: {rule: manifests[month]["warnings_by_rule"].get(rule, 0) for rule in rule_codes}
            for month in months
        },
        "counts_all_months": {
            rule: sum(manifests[month]["warnings_by_rule"].get(rule, 0) for month in months)
            for rule in rule_codes
        },
    }
    (root / "data" / "validation" / "validation_rule_summary.json").write_text(
        json.dumps(rule_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return combined_path, summary_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--months", nargs="+", default=list(DEFAULT_MONTHS))
    args = parser.parse_args()
    combined, summary = rebuild(args.root.resolve(), tuple(args.months))
    print(combined)
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
