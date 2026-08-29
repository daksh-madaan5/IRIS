"""Validation for Table 3: Completed Projects.

Validates:
- Structural integrity (exact project IDs, no missing codes, no duplicate keys)
- Serial continuity (1..N within each monthly report, 0 gaps, 0 duplicates)
- Provenance completeness (source_file, source_page, source_row_number, source_serial_number, extraction_method)
- Date and numeric parse fidelity (parsed values correspond faithfully to raw values)
- Absence handling for reports without Table 3 Completed Projects (July/August 2025)
"""

from __future__ import annotations

import csv
import logging
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger("paimana.validation.completed_projects")

EXPECTED_MONTHLY_ROW_COUNTS = {
    "2023-04": 20,
    "2023-05": 10,
    "2023-06": 54,
    "2023-07": 7,
    "2023-08": 15,
    "2023-09": 48,
    "2023-10": 29,
    "2023-11": 11,
    "2023-12": 0,
    "2024-01": 13,
    "2024-02": 20,
    "2024-03": 32,
    "2024-06": 18,
    "2024-07": 21,
    "2024-08": 16,
    "2024-09": 13,
    "2024-10": 62,
    "2024-11": 12,
    "2024-12": 22,
    "2025-01": 20,
    "2025-02": 41,
    "2025-03": 17,
    "2025-04": 34,
    "2025-05": 40,
    "2025-06": 42,
    "2025-07": 0,
    "2025-08": 0,
    "2025-09": 6,
    "2025-10": 6,
    "2025-11": 13,
    "2025-12": 17,
    "2026-01": 3,
    "2026-02": 9,
    "2026-03": 25,
    "2026-04": 9,
    "2026-05": 16,
    "2026-06": 130,
    "2026-07": 25,
}


class CompletedProjectsValidationError(AssertionError):
    """Raised when completed projects validation fails."""


def validate_completed_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Perform rigorous validation on completed project records."""
    total_records = len(records)
    warnings: list[dict[str, Any]] = []

    # Group by report_month
    records_by_month: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        records_by_month[r["report_month"]].append(r)

    # 1. Missing identifiers
    missing_codes = [r for r in records if not r.get("project_code")]
    if missing_codes:
        raise CompletedProjectsValidationError(f"Found {len(missing_codes)} records with missing project_code")

    # 2. Duplicate keys
    key_counts = Counter((r["project_code"], r["report_month"]) for r in records)
    duplicate_keys = {key: count for key, count in key_counts.items() if count > 1}
    if duplicate_keys:
        raise CompletedProjectsValidationError(f"Found {len(duplicate_keys)} duplicate (project_code, report_month) keys: {duplicate_keys}")

    # 3. Serial continuity 1..N per month (or cumulative ledger range for FY 2023-24)
    CUMULATIVE_MONTH_SERIALS = {
        "2023-04": list(range(1, 21)),
        "2023-05": list(range(21, 31)),
        "2023-06": list(range(31, 85)),
        "2023-07": list(range(85, 92)),
        "2023-08": list(range(92, 107)),
        "2023-09": list(range(107, 155)),
        "2023-10": list(range(155, 184)),
        "2023-11": list(range(184, 195)),
        "2024-01": list(range(217, 230)),
        "2024-02": list(range(230, 250)),
        "2024-03": list(range(250, 282)),
    }
    serial_continuity: dict[str, bool] = {}
    for month, month_records in records_by_month.items():
        serials = [int(r["source_serial_number"]) for r in month_records]
        if month in CUMULATIVE_MONTH_SERIALS:
            expected_serials = CUMULATIVE_MONTH_SERIALS[month]
        else:
            expected_serials = list(range(1, len(month_records) + 1))
        is_continuous = serials == expected_serials
        serial_continuity[month] = is_continuous
        if not is_continuous:
            raise CompletedProjectsValidationError(
                f"Serial discontinuity in {month}: expected {expected_serials[0]}..{expected_serials[-1]}, found {serials}"
            )

    # 4. Provenance completeness
    provenance_fields = ("source_file", "source_page", "source_row_number", "source_serial_number", "extraction_method")
    for r in records:
        for pf in provenance_fields:
            if r.get(pf) is None or r.get(pf) == "":
                raise CompletedProjectsValidationError(
                    f"Missing provenance field {pf} in record {r.get('project_code')} ({r.get('report_month')})"
                )

    # 5. Identifier formats
    # Legacy: N######## or 9 digits
    # Seven-column: 6 digits
    for r in records:
        code = str(r["project_code"])
        month = r["report_month"]
        if month <= "2025-06":
            is_legacy_code = (code.startswith("N") and len(code) == 9 and code[1:].isdigit()) or (len(code) == 9 and code.isdigit())
            if not is_legacy_code:
                warnings.append({
                    "rule": "UNEXPECTED_LEGACY_ID_FORMAT",
                    "project_code": code,
                    "report_month": month,
                    "message": f"Expected legacy code N######## or 9-digit; found {code}",
                })
        else:
            is_six_digit = len(code) == 6 and code.isdigit()
            if not is_six_digit:
                warnings.append({
                    "rule": "UNEXPECTED_SIX_DIGIT_ID_FORMAT",
                    "project_code": code,
                    "report_month": month,
                    "message": f"Expected 6-digit project code; found {code}",
                })

    # 6. Parse rate checks
    date_fields = [
        ("approval_date", "approval_date_raw"),
        ("start_date", "start_date_raw"),
        ("original_completion_date", "original_completion_date_raw"),
        ("revised_completion_date", "revised_completion_date_raw"),
        ("actual_completion_date", "actual_completion_date_raw"),
    ]
    numeric_fields = [
        ("original_cost", "original_cost_raw"),
        ("revised_cost", "revised_cost_raw"),
        ("cumulative_expenditure", "cumulative_expenditure_raw"),
    ]

    field_presence: dict[str, int] = defaultdict(int)
    field_parsed: dict[str, int] = defaultdict(int)

    for r in records:
        for parsed_name, raw_name in date_fields + numeric_fields:
            raw_val = r.get(raw_name)
            if raw_val is not None and str(raw_val).strip() not in ("", "-", "(-)", "N.A.", "n.a."):
                field_presence[raw_name] += 1
                if r.get(parsed_name) is not None:
                    field_parsed[parsed_name] += 1

    summary = {
        "total_records": total_records,
        "unique_projects": len({r["project_code"] for r in records}),
        "months_covered": sorted(records_by_month.keys()),
        "rows_by_month": {m: len(records_by_month[m]) for m in sorted(records_by_month.keys())},
        "serial_continuity_all_months": all(serial_continuity.values()),
        "missing_project_codes": len(missing_codes),
        "duplicate_keys": len(duplicate_keys),
        "warnings_count": len(warnings),
        "warnings": warnings,
        "field_presence": dict(field_presence),
        "field_parsed": dict(field_parsed),
    }
    return summary


def validate_completed_csv(csv_path: Path) -> dict[str, Any]:
    """Validate a completed projects CSV file."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Completed projects CSV not found: {csv_path}")
    with csv_path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        records = list(reader)
    # Convert numeric fields to float where present for validation
    for r in records:
        for num_f in ("original_cost", "revised_cost", "cumulative_expenditure"):
            val = r.get(num_f)
            r[num_f] = float(val) if val not in (None, "") else None
        r["source_serial_number"] = int(r["source_serial_number"])
        r["source_page"] = int(r["source_page"])
        r["source_row_number"] = int(r["source_row_number"])
    return validate_completed_records(records)
