"""Record-level and report-level validation."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any

DATE_FIELDS = (
    "approval_date",
    "start_date",
    "original_completion_date",
    "revised_completion_date",
)
NUMERIC_FIELDS = (
    "original_cost",
    "revised_cost",
    "cumulative_expenditure",
    "physical_progress",
)

# Cross-field warning codes are stable public outputs. They identify source-data
# plausibility conditions only; they never change or reject a parsed record.
ZERO_EXPENDITURE_POSITIVE_PROGRESS = "ZERO_EXPENDITURE_POSITIVE_PROGRESS"
EXPENDITURE_WITH_ZERO_PROGRESS = "EXPENDITURE_WITH_ZERO_PROGRESS"
FULL_PROGRESS_STILL_ONGOING = "FULL_PROGRESS_STILL_ONGOING"
PHYSICAL_PROGRESS_ABOVE_100 = "PHYSICAL_PROGRESS_ABOVE_100"
NEGATIVE_EXPENDITURE = "NEGATIVE_EXPENDITURE"
EXTREME_EXPENDITURE_COST_MISMATCH = "EXTREME_EXPENDITURE_COST_MISMATCH"
REVISED_COST_BELOW_ORIGINAL = "REVISED_COST_BELOW_ORIGINAL"
COMPLETION_DATE_BEFORE_START_DATE = "COMPLETION_DATE_BEFORE_START_DATE"
PROGRESS_REPORTED_BEFORE_START = "PROGRESS_REPORTED_BEFORE_START"
CROSS_FIELD_RULES = (
    ZERO_EXPENDITURE_POSITIVE_PROGRESS,
    PROGRESS_REPORTED_BEFORE_START,
    EXPENDITURE_WITH_ZERO_PROGRESS,
    FULL_PROGRESS_STILL_ONGOING,
    PHYSICAL_PROGRESS_ABOVE_100,
    NEGATIVE_EXPENDITURE,
    EXTREME_EXPENDITURE_COST_MISMATCH,
    REVISED_COST_BELOW_ORIGINAL,
    COMPLETION_DATE_BEFORE_START_DATE,
)

ERROR_HIGH = ("ERROR", "HIGH", "STRUCTURAL_OR_IMPOSSIBLE")
WARNING_MEDIUM = ("WARNING", "MEDIUM", "STRONG_PLAUSIBILITY_ANOMALY")
INFO_LOW = ("INFO", "LOW", "UNUSUAL_BUSINESS_STATE")

RULE_CLASSIFICATION = {
    "missing_project_code": ERROR_HIGH,
    "invalid_project_code": ERROR_HIGH,
    "unparseable_date": ERROR_HIGH,
    "unparseable_numeric": ERROR_HIGH,
    "nonpositive_original_cost": ERROR_HIGH,
    "nonpositive_revised_cost": ERROR_HIGH,
    PHYSICAL_PROGRESS_ABOVE_100: ERROR_HIGH,
    NEGATIVE_EXPENDITURE: ERROR_HIGH,
    COMPLETION_DATE_BEFORE_START_DATE: ERROR_HIGH,
    EXTREME_EXPENDITURE_COST_MISMATCH: WARNING_MEDIUM,
    PROGRESS_REPORTED_BEFORE_START: WARNING_MEDIUM,
    ZERO_EXPENDITURE_POSITIVE_PROGRESS: INFO_LOW,
    EXPENDITURE_WITH_ZERO_PROGRESS: INFO_LOW,
    FULL_PROGRESS_STILL_ONGOING: INFO_LOW,
    REVISED_COST_BELOW_ORIGINAL: INFO_LOW,
}


def validate_records(
    records: list[dict[str, Any]], *, project_code_structurally_absent: bool = False
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    by_code: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def warn(record: dict[str, Any], rule: str, message: str, field: str = "") -> None:
        severity, priority, category = RULE_CLASSIFICATION.get(rule, WARNING_MEDIUM)
        warnings.append(
            {
                "project_code": record.get("project_code", ""),
                "report_month": record.get("report_month", ""),
                "source_file": record.get("source_file", ""),
                "source_page": record.get("source_page", ""),
                "source_row_number": record.get("source_row_number", ""),
                "field": field,
                "rule": rule,
                "severity": severity,
                "priority": priority,
                "category": category,
                "message": message,
            }
        )

    for record in records:
        code = record.get("project_code")
        if not code:
            if not project_code_structurally_absent:
                warn(record, "missing_project_code", "Project code is missing", "project_code")
        elif not re.fullmatch(r"(?:\d{6}|N\d{8}|\d{9})", str(code)):
            warn(record, "invalid_project_code", "Expected a supported source project-code format", "project_code")
        else:
            by_code[str(code)].append(record)

        for field in DATE_FIELDS:
            raw_key = {
                "approval_date": "approval_date_raw",
                "start_date": "start_date_raw",
                "original_completion_date": "original_completion_date_raw",
                "revised_completion_date": "revised_completion_date_raw",
            }[field]
            if record.get(raw_key) and not record.get(field):
                warn(record, "unparseable_date", f"Could not parse {record[raw_key]!r}", field)

        for field in NUMERIC_FIELDS:
            raw_key = f"{field}_raw"
            if record.get(raw_key) and record.get(field) is None:
                warn(record, "unparseable_numeric", f"Could not parse {record[raw_key]!r}", field)

        original = record.get("original_cost")
        revised = record.get("revised_cost")
        expenditure = record.get("cumulative_expenditure")
        progress = record.get("physical_progress")
        if original is not None and original <= 0:
            warn(record, "nonpositive_original_cost", "Original cost is not positive", "original_cost")
        if revised is not None and revised <= 0:
            warn(record, "nonpositive_revised_cost", "Revised cost is not positive", "revised_cost")
        start = record.get("start_date")
        report_month = record.get("report_month")
        original_completion = record.get("original_completion_date")
        revised_completion = record.get("revised_completion_date")

        if expenditure is not None and expenditure < 0:
            warn(record, NEGATIVE_EXPENDITURE, "Cumulative expenditure is negative", "cumulative_expenditure")
        if revised and expenditure is not None and expenditure > 3 * revised:
            warn(record, EXTREME_EXPENDITURE_COST_MISMATCH, "Cumulative expenditure exceeds three times revised cost", "cumulative_expenditure")
        if original is not None and revised is not None and revised < original:
            warn(record, REVISED_COST_BELOW_ORIGINAL, "Revised cost is below original cost", "revised_cost")
        if progress is not None and progress > 100:
            warn(record, PHYSICAL_PROGRESS_ABOVE_100, "Physical progress is above 100", "physical_progress")
        if expenditure == 0 and progress is not None and progress > 0:
            if start and report_month and start > report_month:
                warn(record, PROGRESS_REPORTED_BEFORE_START, "Positive physical progress is reported before the project start month", "physical_progress")
            else:
                warn(
                    record,
                    ZERO_EXPENDITURE_POSITIVE_PROGRESS,
                    "Cumulative expenditure is zero while physical progress is positive and start is not after the report month",
                    "cumulative_expenditure,physical_progress",
                )
        if expenditure is not None and expenditure > 0 and progress == 0:
            warn(record, EXPENDITURE_WITH_ZERO_PROGRESS, "Cumulative expenditure is positive while physical progress is zero", "cumulative_expenditure,physical_progress")
        if progress == 100:
            warn(record, FULL_PROGRESS_STILL_ONGOING, "Physical progress is 100 in the All Ongoing Projects table", "physical_progress")

        completion_fields = []
        if start and original_completion and original_completion < start:
            completion_fields.append("original_completion_date")
        if start and revised_completion and revised_completion < start:
            completion_fields.append("revised_completion_date")
        if completion_fields:
            warn(
                record,
                COMPLETION_DATE_BEFORE_START_DATE,
                f"Completion month precedes start month for: {', '.join(completion_fields)}",
                ",".join(completion_fields),
            )

    duplicates: list[dict[str, Any]] = []
    for code, group in by_code.items():
        if len(group) > 1:
            for record in group:
                duplicates.append(
                    {
                        "project_code": code,
                        "report_month": record["report_month"],
                        "source_file": record["source_file"],
                        "source_page": record["source_page"],
                        "source_row_number": record["source_row_number"],
                        "duplicate_count": len(group),
                    }
                )

    warning_counts = Counter(x["rule"] for x in warnings)
    warning_codes = sorted(set(CROSS_FIELD_RULES) | set(warning_counts))
    severity_counts = Counter(x["severity"] for x in warnings)
    priority_counts = Counter(x["priority"] for x in warnings)
    category_counts = Counter(x["category"] for x in warnings)
    missing_project_codes = sum(not record.get("project_code") for record in records)
    metrics = {
        "clean_project_rows": len(records),
        "warning_rows": len({(x["source_page"], x["source_row_number"]) for x in warnings}),
        "warning_count": len(warnings),
        "warnings_by_rule": {code: warning_counts.get(code, 0) for code in warning_codes},
        "warnings_by_severity": {code: severity_counts.get(code, 0) for code in ("ERROR", "WARNING", "INFO")},
        "warnings_by_priority": {code: priority_counts.get(code, 0) for code in ("HIGH", "MEDIUM", "LOW")},
        "warnings_by_category": dict(sorted(category_counts.items())),
        "missing_project_codes": missing_project_codes,
        "structurally_missing_project_codes": missing_project_codes if project_code_structurally_absent else 0,
        "invalid_project_codes": warning_counts.get("invalid_project_code", 0),
        "duplicate_project_codes": len([code for code, group in by_code.items() if len(group) > 1]),
        "duplicate_rows": len(duplicates),
    }
    return warnings, duplicates, metrics


def build_quality_control_rows(records: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Create validation-only financial/physical metrics without mutating records."""
    rules_by_source: dict[tuple[Any, Any, Any], set[str]] = defaultdict(set)
    for warning in warnings:
        key = (warning.get("source_file"), warning.get("source_page"), warning.get("source_row_number"))
        rules_by_source[key].add(str(warning["rule"]))

    output = []
    for record in records:
        expenditure = record.get("cumulative_expenditure")
        revised_cost = record.get("revised_cost")
        physical_progress = record.get("physical_progress")
        financial_progress = None
        if expenditure is not None and revised_cost is not None and revised_cost > 0:
            financial_progress = round(expenditure / revised_cost * 100, 6)
        physical_financial_gap = None
        if physical_progress is not None and financial_progress is not None:
            physical_financial_gap = round(physical_progress - financial_progress, 6)
        key = (record.get("source_file"), record.get("source_page"), record.get("source_row_number"))
        output.append(
            {
                "project_code": record.get("project_code"),
                "report_month": record.get("report_month"),
                "start_date": record.get("start_date"),
                "original_completion_date": record.get("original_completion_date"),
                "revised_completion_date": record.get("revised_completion_date"),
                "original_cost": record.get("original_cost"),
                "revised_cost": revised_cost,
                "cumulative_expenditure": expenditure,
                "physical_progress": physical_progress,
                "financial_progress": financial_progress,
                "physical_financial_gap": physical_financial_gap,
                "warning_rules": "|".join(sorted(rules_by_source.get(key, set()))),
                "source_file": record.get("source_file"),
                "source_page": record.get("source_page"),
                "source_row_number": record.get("source_row_number"),
            }
        )
    return output
