"""Reliable native-PDF extraction for PAIMANA All Ongoing Projects tables."""

from __future__ import annotations

import csv
import json
import logging
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pdfplumber

from src.cleaning.parsers import (
    ProjectIdentity,
    is_missing,
    normalize_space,
    parse_month,
    parse_legacy_month,
    parse_number,
    parse_project_identity,
    split_legacy_triplet,
    split_parenthesized_pair,
)
from src.validation.core import build_quality_control_rows, validate_records

LOGGER = logging.getLogger("paimana.extraction")
EXTRACTION_METHOD = "pdfplumber-lines-v1"
TABLE_SELECTION_METHOD = "semantic-table6-header-v1"
PAGE_FRAME_EXCLUSION_RATIO = 0.04
TABLE_SETTINGS = {
    "vertical_strategy": "lines",
    "horizontal_strategy": "lines",
    "snap_tolerance": 3,
    "join_tolerance": 3,
    "intersection_tolerance": 4,
}
EXPECTED_HEADER = (
    "sl.no",
    "project name",
    "state",
    "date of approval",
    "doc",
    "cost",
    "expenditure",
    "physical progress",
)
TABLE6_HEADER_SIGNATURE = (
    ("sl.no",),
    ("project name", "agency", "project code"),
    ("state",),
    ("date of approval", "start date"),
    ("doc", "revised doc"),
    ("cost", "revised cost"),
    ("cumulative", "expenditure"),
    ("physical progress",),
)
TABLE6_APPROVAL_ONLY_HEADER_SIGNATURE = (
    ("sl.no",),
    ("project name", "agency", "project code"),
    ("state",),
    ("date of approval",),
    ("orignal/target doc", "revised doc"),
    ("orignal cost", "revised cost"),
    ("cumulative", "expenditure"),
    ("physical progress",),
)
LEGACY_ALL_ONGOING_HEADER_SIGNATURE = (
    ("state",),
    ("sector",),
    ("sl no",),
    ("project name", "agency name", "project code"),
    ("date", "approval"),
    ("date of commissioning", "original", "revised", "anticipated"),
    ("cost original", "revised", "anticipated"),
    ("cumulative", "expenditure"),
    ("physical", "progress"),
)
LEGACY_ALL_ONGOING_PROGRESS_ONLY_HEADER_SIGNATURE = (
    ("state",),
    ("sector",),
    ("sl no",),
    ("project name", "agency name", "project code"),
    ("date", "approval"),
    ("date of commissioning", "original", "revised", "anticipated"),
    ("cost original", "revised", "anticipated"),
    ("cumulative", "expenditure"),
    ("progress",),
)
LEGACY_ANNEXURE_XVIII_HEADER_SIGNATURE = (
    ("si.no",),
    ("project",),
    ("approval",),
    ("commissioning",),
    ("cost",),
    ("expenditure",),
)
ANNEXURE_XVIII_LAYOUT = "legacy-annexure-xviii-six-column-v1"
TABLE6_LAYOUT_SIGNATURES = {
    "table6-eight-column-v1": TABLE6_HEADER_SIGNATURE,
    "table6-eight-column-approval-only-v1": TABLE6_APPROVAL_ONLY_HEADER_SIGNATURE,
    "legacy-all-ongoing-nine-column-v1": LEGACY_ALL_ONGOING_HEADER_SIGNATURE,
    "legacy-all-ongoing-nine-column-progress-only-v1": LEGACY_ALL_ONGOING_PROGRESS_ONLY_HEADER_SIGNATURE,
    ANNEXURE_XVIII_LAYOUT: LEGACY_ANNEXURE_XVIII_HEADER_SIGNATURE,
}
LEGACY_LAYOUTS = {
    "legacy-all-ongoing-nine-column-v1",
    "legacy-all-ongoing-nine-column-progress-only-v1",
    ANNEXURE_XVIII_LAYOUT,
}
ANNEXURE_XVIII_STATES = {
    "ANDAMAN AND NICOBAR ISLANDS", "ANDHRA PRADESH", "ARUNACHAL PRADESH", "ASSAM", "BIHAR",
    "CHHATTISGARH", "DELHI", "GOA", "GUJARAT", "HARYANA", "HIMACHAL PRADESH",
    "JAMMU AND KASHMIR", "JHARKHAND", "KARNATAKA", "KERALA", "LADAKH", "MADHYA PRADESH",
    "MAHARASHTRA", "MANIPUR", "MEGHALAYA", "MIZORAM", "MULTI STATE", "NAGALAND",
    "ODISHA", "PUNJAB", "RAJASTHAN", "SIKKIM", "TAMIL NADU", "TELANGANA", "TRIPURA",
    "UTTAR PRADESH", "UTTARAKHAND", "WEST BENGAL"
}
ANNEXURE_XVIII_SECTORS = {
    "atomic energy", "civil aviation", "coal", "department of higher education", "doner",
    "dpiit", "finance", "health and family welfare", "home affairs", "mines", "petroleum",
    "power", "railways", "renewable energy", "road transport and highways", "shipping and ports",
    "social justice", "steel", "telecommunications", "urban development", "water resources"
}
MONTH_NAMES = {
    name.upper(): index
    for index, name in enumerate(
        ("", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
    )
    if name
}

CLEAN_FIELDS = [
    "project_code",
    "legacy_ocms_code",
    "pmgid",
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
    "report_month",
    "approval_date_raw",
    "start_date_raw",
    "original_completion_date_raw",
    "revised_completion_date_raw",
    "original_cost_raw",
    "revised_cost_raw",
    "cumulative_expenditure_raw",
    "physical_progress_raw",
    "source_file",
    "source_page",
    "source_pages",
    "source_row_number",
    "source_serial_number",
    "extraction_method",
]


class SchemaChangeDetected(RuntimeError):
    pass


class TableCandidateSelectionError(SchemaChangeDetected):
    def __init__(
        self,
        message: str,
        audits: list[dict[str, Any]],
        tables: list[list[list[str | None]]] | None = None,
    ) -> None:
        super().__init__(message)
        self.audits = audits
        self.tables = tables or []


@dataclass
class PipelinePaths:
    root: Path

    def extracted(self, month: str) -> Path:
        return self.root / "data" / "extracted" / month

    @property
    def cleaned(self) -> Path:
        return self.root / "data" / "cleaned"

    @property
    def uncoded_cleaned(self) -> Path:
        return self.root / "data" / "cleaned_uncoded"

    @property
    def processed(self) -> Path:
        return self.root / "data" / "processed"

    @property
    def validation(self) -> Path:
        return self.root / "data" / "validation"


def _write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_schema_failure(
    extracted_dir: Path,
    pdf_name: str,
    page_number: int,
    page_text: str,
    tables: list[list[list[str | None]]],
    message: str,
    raw_rows: list[dict[str, Any]],
    raw_pages: list[dict[str, Any]],
    table_audits: list[dict[str, Any]] | None = None,
) -> None:
    """Preserve partial raw output and the offending page before failing closed."""
    _write_jsonl(extracted_dir / "raw_table6_rows.partial.jsonl", raw_rows)
    _write_jsonl(extracted_dir / "raw_table6_pages.partial.jsonl", raw_pages)
    _write_json(
        extracted_dir / f"SCHEMA_CHANGE_DETECTED_page_{page_number}.json",
        {
            "source_file": pdf_name,
            "source_page": page_number,
            "message": message,
            "page_text": page_text,
            "tables": tables,
            "table_audits": table_audits or [],
        },
    )
    LOGGER.error("SCHEMA CHANGE DETECTED: %s", message)


def _clear_stale_schema_failures(extracted_dir: Path) -> None:
    """Remove failure-only artifacts after a later complete successful run."""
    for name in ("raw_table6_rows.partial.jsonl", "raw_table6_pages.partial.jsonl"):
        path = extracted_dir / name
        if path.exists():
            path.unlink()
    for path in extracted_dir.glob("SCHEMA_CHANGE_DETECTED_page_*.json"):
        path.unlink()


def _is_table6_page(text: str) -> bool:
    normalized = normalize_space(text).lower()
    current = all(token in normalized for token in ("all ongoing projects", "sl.no", "project name", "physical progress"))
    legacy = all(
        token in normalized
        for token in (
            "project list: ongoing projects as of",
            "state",
            "sector",
            "sl no",
            "project name",
            "cumulative",
            "expenditure",
            "progress",
        )
    )
    first_lines = " ".join(normalize_space(line).lower() for line in (text or "").splitlines()[:2])
    legacy_continuation = (
        "project list: ongoing projects as of" in first_lines
        and "north-east" not in first_lines
        and "north east" not in first_lines
    )
    annexure_xviii = "details of ongoing projects" in normalized and any(
        token in normalized for token in ("annexure xviii", "annexure - xviii", "annexure-xviii")
    )
    return current or legacy or legacy_continuation or annexure_xviii


def _detect_report_month(text: str, filename: str, pdf_path: Path | None = None) -> str:
    month_pattern = "|".join(MONTH_NAMES)
    match = re.search(r"\b(" + month_pattern + r")\s+(20\d{2})\b", text.upper())
    if not match:
        match = re.search(r"(" + month_pattern + r")[_ -]+(20\d{2})", filename.upper())
    if not match and pdf_path is not None:
        parent_year_match = re.search(r"\b(20\d{2})\b", str(pdf_path))
        month_match = re.search(r"(?:^|[^A-Z])(" + month_pattern + r")(?:[^A-Z]|$)", filename.upper()) or re.search(r"\b(" + month_pattern + r")\b", text.upper())
        if parent_year_match and month_match:
            return f"{parent_year_match.group(1)}-{MONTH_NAMES[month_match.group(1)]:02d}"
    if not match:
        raise SchemaChangeDetected(f"Could not determine report month for {filename}")
    return f"{match.group(2)}-{MONTH_NAMES[match.group(1)]:02d}"


def _classify_table6_header(row: list[str | None]) -> tuple[str | None, list[str]]:
    cells = [normalize_space(x).lower() for x in row]
    matches: list[str] = []
    failures: list[str] = []
    for layout_version, signature in TABLE6_LAYOUT_SIGNATURES.items():
        if len(row) != len(signature):
            failures.append(f"{layout_version}: expected {len(signature)} columns; found {len(row)}")
            continue
        missing: list[str] = []
        for column, (actual, required_tokens) in enumerate(zip(cells, signature), 1):
            absent = [token for token in required_tokens if token not in actual]
            if absent:
                missing.append(f"column {column} missing {', '.join(absent)}")
        if layout_version == "table6-eight-column-approval-only-v1" and "start date" in cells[3]:
            missing.append("column 4 unexpectedly contains start date")
        if (
            layout_version == "legacy-all-ongoing-nine-column-progress-only-v1"
            and "physical" in cells[8]
        ):
            missing.append("column 9 unexpectedly contains physical")
        if missing:
            failures.append(f"{layout_version}: {'; '.join(missing)}")
        else:
            matches.append(layout_version)
    if len(matches) != 1:
        reason = "no supported header signature" if not matches else "ambiguous supported header signatures"
        return None, [f"{reason}: {' | '.join(failures)}"]
    return matches[0], []


def _validate_header(row: list[str | None]) -> str:
    layout_version, reasons = _classify_table6_header(row)
    if layout_version is None:
        raise SchemaChangeDetected(f"Unexpected Table 6 header: {'; '.join(reasons)}")
    return layout_version


def _table_candidate_audit(
    table: Any,
    table_index: int,
    page_number: int,
    page_width: float,
    page_height: float,
    legacy_header_established: bool | str = False,
) -> tuple[list[list[str | None]], dict[str, Any]]:
    """Assess one detected table against the canonical positional signature."""
    data = table.extract()
    row_count = len(data)
    column_count = max((len(row) for row in data), default=0)
    bbox = [round(float(value), 4) for value in table.bbox]
    within_page = (
        bbox[0] >= 0
        and bbox[1] >= 0
        and bbox[2] <= page_width
        and bbox[3] <= page_height
        and bbox[0] < bbox[2]
        and bbox[1] < bbox[3]
    )
    reasons: list[str] = []
    header = data[0] if data else []
    if data and len(data) > 1 and data[0][0] and "details of ongoing" in str(data[0][0]).lower():
        header = data[1]
    layout_version = None
    layout_version, header_reasons = _classify_table6_header(header)
    is_legacy_continuation = False
    
    established_layout = legacy_header_established if isinstance(legacy_header_established, str) else None
    if layout_version is None:
        if established_layout == ANNEXURE_XVIII_LAYOUT and column_count == 6:
            layout_version = ANNEXURE_XVIII_LAYOUT
            is_legacy_continuation = True
        elif established_layout in {
            "legacy-all-ongoing-nine-column-v1",
            "legacy-all-ongoing-nine-column-progress-only-v1",
        } and column_count in (7, 8, 9):
            layout_version = established_layout
            is_legacy_continuation = True
        elif legacy_header_established is True and column_count in (7, 8, 9):
            # Backward-compatible test/helper behavior for an established coded legacy header.
            layout_version = "legacy-all-ongoing-nine-column-v1"
            is_legacy_continuation = True
    if layout_version is None:
        reasons.extend(header_reasons)

    serial_column = 0 if layout_version == ANNEXURE_XVIII_LAYOUT else (2 if layout_version in LEGACY_LAYOUTS else 0)
    if is_legacy_continuation:
        serial_column = 0 if column_count in (6, 7) else (2 if column_count == 9 else 1)

    expected_columns = len(TABLE6_LAYOUT_SIGNATURES[layout_version]) if layout_version and not is_legacy_continuation else column_count
    start_row = 0 if is_legacy_continuation else 1
    if layout_version == ANNEXURE_XVIII_LAYOUT and not is_legacy_continuation:
        if data and len(data) > 1 and data[0][0] and "details of ongoing" in str(data[0][0]).lower():
            start_row = 2
        elif data and len(data) > 0 and data[0][0] and "si.no" in str(data[0][0]).lower():
            start_row = 1
        else:
            start_row = 0

    project_rows = sum(
        bool(row) and len(row) == expected_columns and normalize_space(row[serial_column]).isdigit()
        for row in data[start_row:]
    )
    if project_rows == 0:
        reasons.append("no rows with a numeric serial in the first column")

    audit = {
        "page_number": page_number,
        "table_index": table_index,
        "row_count": row_count,
        "column_count": column_count,
        "dimensions": f"{row_count}x{column_count}",
        "bbox": bbox,
        "bbox_within_page": within_page,
        "project_row_count": project_rows,
        "layout_version": layout_version,
        "matches_table6_signature": not reasons,
        "reason": "matched canonical Table 6 signature" if not reasons else "; ".join(reasons),
    }
    return data, audit


def _select_table6_candidate(
    tables: list[Any], page_number: int, page_width: float, page_height: float, legacy_header_established: bool | str = False
) -> tuple[list[list[str | None]], int, list[dict[str, Any]]]:
    """Select exactly one semantic Table 6 candidate or fail closed."""
    extracted: list[list[list[str | None]]] = []
    audits: list[dict[str, Any]] = []
    for table_index, table in enumerate(tables):
        data, audit = _table_candidate_audit(table, table_index, page_number, page_width, page_height, legacy_header_established)
        extracted.append(data)
        audits.append(audit)
    matching = [audit["table_index"] for audit in audits if audit["matches_table6_signature"]]
    if len(matching) != 1:
        raise TableCandidateSelectionError(
            f"Page {page_number}: expected exactly 1 canonical Table 6 candidate; found {len(matching)} among {len(tables)} detected tables",
            audits,
            extracted,
        )
    selected_index = matching[0]
    return extracted[selected_index], selected_index, audits


def _locate_table6_candidate(
    page: Any, page_number: int, legacy_header_established: bool | str = False
) -> tuple[list[list[str | None]], int, str, list[dict[str, Any]], list[list[list[str | None]]]]:
    """Find the canonical table, retrying inside the page frame only after zero full-page matches."""
    full_tables = page.find_tables(TABLE_SETTINGS)
    full_extracted = [table.extract() for table in full_tables]
    try:
        table, selected_index, audits = _select_table6_candidate(
            full_tables, page_number, float(page.width), float(page.height), legacy_header_established
        )
        for audit in audits:
            audit["detection_pass"] = "full_page"
        return table, selected_index, "full_page", audits, full_extracted
    except TableCandidateSelectionError as full_error:
        for audit in full_error.audits:
            audit["detection_pass"] = "full_page"
        full_matches = sum(audit["matches_table6_signature"] for audit in full_error.audits)
        if full_matches > 0:
            raise
        full_audits = full_error.audits

    inset = float(page.width) * PAGE_FRAME_EXCLUSION_RATIO
    cropped = page.crop((inset, 0, float(page.width) - inset, float(page.height)))
    inset_tables = cropped.find_tables(TABLE_SETTINGS)
    inset_extracted = [table.extract() for table in inset_tables]
    try:
        table, selected_index, inset_audits = _select_table6_candidate(
            inset_tables, page_number, float(page.width), float(page.height), legacy_header_established
        )
    except TableCandidateSelectionError as inset_error:
        for audit in inset_error.audits:
            audit["detection_pass"] = "page_frame_excluded"
        combined_audits = [*full_audits, *inset_error.audits]
        matching = sum(audit["matches_table6_signature"] for audit in combined_audits)
        raise TableCandidateSelectionError(
            f"Page {page_number}: expected exactly 1 canonical Table 6 candidate; found {matching} after full-page and page-frame-excluded detection",
            combined_audits,
            [*full_extracted, *inset_extracted],
        ) from inset_error
    for audit in inset_audits:
        audit["detection_pass"] = "page_frame_excluded"
    return (
        table,
        selected_index,
        "page_frame_excluded",
        [*full_audits, *inset_audits],
        [*full_extracted, *inset_extracted],
    )


def _normalize_cell(value: str | None) -> str:
    """Normalize each visual line while preserving semantic line boundaries."""
    return "\n".join(normalize_space(line) for line in (value or "").splitlines() if normalize_space(line))


def _legacy_group_cells(page: Any, selection_pass: str, selected_index: int, is_continuation: bool = False, col_count: int = 9) -> list[tuple[str, str]]:
    """Recover State/Sector text split by underlines inside visually merged cells or continuation margins."""
    source = page
    if selection_pass == "page_frame_excluded":
        inset = float(page.width) * PAGE_FRAME_EXCLUSION_RATIO
        source = page.crop((inset, 0, float(page.width) - inset, float(page.height)))
    table = source.find_tables(TABLE_SETTINGS)[selected_index]
    recovered: list[tuple[str, str]] = []

    if not is_continuation and col_count == 9:
        header_cells = table.rows[0].cells
        columns = [header_cells[0], header_cells[1]]
        row_tops = [min(cell[1] for cell in row.cells if cell is not None) for row in table.rows]
        for row_index, row in enumerate(table.rows):
            boxes = [cell for cell in row.cells if cell is not None]
            if not boxes:
                recovered.append(("", ""))
                continue
            top = row_tops[row_index]
            bottom = row_tops[row_index + 1] if row_index + 1 < len(row_tops) else float(table.bbox[3])
            values = []
            for column in columns:
                assert column is not None
                bbox = (column[0] + 0.2, top + 0.2, column[2] - 0.2, bottom - 0.2)
                values.append(_normalize_cell(page.crop(bbox).extract_text() or ""))
            recovered.append((values[0], values[1]))
        return recovered

    words = page.extract_words()
    page_words = [w for w in words if 80 < w["top"] < 750 and w["text"].lower() not in ("state", "sector", "sl", "no.", "table:-7.", "mospi_")]
    sl_idx = 2 if col_count == 9 else (1 if col_count == 8 else 0)

    for row in table.rows:
        boxes = [cell for cell in row.cells[sl_idx:] if cell is not None]
        if not boxes:
            boxes = [cell for cell in row.cells if cell is not None]
        if not boxes:
            recovered.append(("", ""))
            continue
        r_top = min(b[1] for b in boxes)
        r_bottom = max(b[3] for b in boxes)

        s_words = [w for w in page_words if 30.0 <= w["x0"] < 81.5 and r_top - 2.5 <= w["top"] <= r_bottom - 1.5]
        sec_words = [w for w in page_words if 81.5 <= w["x0"] < 132.0 and r_top - 2.5 <= w["top"] <= r_bottom - 1.5]

        s_words.sort(key=lambda w: (w["top"], w["x0"]))
        sec_words.sort(key=lambda w: (w["top"], w["x0"]))

        s_text = " ".join(w["text"] for w in s_words) if s_words else ""
        sec_text = " ".join(w["text"] for w in sec_words) if sec_words else ""

        recovered.append((_normalize_cell(s_text), _normalize_cell(sec_text)))

    return recovered


def _parse_legacy_identity(cell: str) -> ProjectIdentity:
    text = normalize_space(cell)
    code_match = re.fullmatch(r"(.*)\s*\((N\d{8}|\d{9})\)", text)
    if not code_match:
        return ProjectIdentity(text, None, None, None, None)
    prefix = code_match.group(1).rstrip()
    depth = 0
    agency_start = None
    if prefix.endswith(")"):
        for index in range(len(prefix) - 1, -1, -1):
            if prefix[index] == ")":
                depth += 1
            elif prefix[index] == "(":
                depth -= 1
                if depth == 0:
                    agency_start = index
                    break
    if agency_start is None:
        return ProjectIdentity(prefix, None, code_match.group(2), None, None)
    return ProjectIdentity(
        project_name=normalize_space(prefix[:agency_start]),
        agency=normalize_space(prefix[agency_start + 1 : -1]) or None,
        project_code=code_match.group(2),
        legacy_ocms_code=None,
        pmgid=None,
    )


def _merge_legacy_group_fragment(current: str | None, fragment: str) -> str:
    """Join text fragments created when underlines split a visually merged label."""
    if not current:
        return fragment
    current_compact = current.casefold().replace(" ", "")
    fragment_compact = fragment.casefold().replace(" ", "")
    if fragment_compact in current_compact:
        return current
    if current_compact in fragment_compact:
        return fragment
    current_words = current.split()
    fragment_words = fragment.split()
    for size in range(min(len(current_words), len(fragment_words)), 0, -1):
        if [word.casefold() for word in current_words[-size:]] == [word.casefold() for word in fragment_words[:size]]:
            return " ".join([*current_words, *fragment_words[size:]])
    return f"{current} {fragment}"


def _repair_legacy_project_code_bleed(
    table: list[list[str | None]], page_text: str
) -> list[dict[str, Any]]:
    """Repair only evidenced one-row code displacement in coded legacy tables.

    A leading code is moved to the preceding serial row only when the serials
    are adjacent, the preceding row has no code, and the current row either
    contains another code or is followed by another leading-code row. A final
    missing code is restored only when the page text contains exactly one code
    not already assigned anywhere in the table. These constraints prevent a
    valid current-row code from being borrowed merely because its predecessor
    is malformed.
    """
    if not table:
        return []
    column_count = len(table[0])
    project_column = 3 if column_count == 9 else (2 if column_count == 8 else 1)
    serial_column = 2 if column_count == 9 else (1 if column_count == 8 else 0)
    code_pattern = re.compile(r"^\((N\d{8}|\d{9})\)$")

    def lines(row: list[str | None]) -> list[str]:
        value = row[project_column] if len(row) > project_column else ""
        return [line.strip() for line in (value or "").splitlines() if line.strip()]

    def serial(row: list[str | None]) -> int | None:
        value = normalize_space(row[serial_column] if len(row) > serial_column else "")
        return int(value) if value.isdigit() else None

    repairs: list[dict[str, Any]] = []
    for index in range(1, len(table)):
        current_lines = lines(table[index])
        if not current_lines or not code_pattern.fullmatch(current_lines[0]):
            continue
        previous_lines = lines(table[index - 1])
        current_serial = serial(table[index])
        previous_serial = serial(table[index - 1])
        adjacent_serials = (
            current_serial is not None
            and previous_serial is not None
            and current_serial == previous_serial + 1
        )
        previous_missing_code = not any(code_pattern.fullmatch(line) for line in previous_lines)
        current_has_own_code = any(code_pattern.fullmatch(line) for line in current_lines[1:])
        next_leads_with_code = index + 1 < len(table) and bool(lines(table[index + 1])) and bool(
            code_pattern.fullmatch(lines(table[index + 1])[0])
        )
        if not (adjacent_serials and previous_missing_code and (current_has_own_code or next_leads_with_code)):
            continue
        displaced_code = current_lines[0]
        table[index - 1][project_column] = "\n".join([*(previous_lines or []), displaced_code])
        table[index][project_column] = "\n".join(current_lines[1:])
        repairs.append(
            {
                "type": "legacy_project_code_bleed_repaired",
                "method": "adjacent_serial_and_code_chain",
                "from_serial": current_serial,
                "to_serial": previous_serial,
                "project_code": displaced_code[1:-1],
            }
        )

    numeric_rows = [row for row in table if serial(row) is not None]
    if numeric_rows:
        last_row = numeric_rows[-1]
        last_lines = lines(last_row)
        if not any(code_pattern.fullmatch(line) for line in last_lines):
            assigned = Counter(
                line
                for row in table
                for line in lines(row)
                if code_pattern.fullmatch(line)
            )
            reported = Counter(re.findall(r"\(N\d{8}\)|\(\d{9}\)", page_text or ""))
            unassigned = list((reported - assigned).elements())
            if len(unassigned) == 1 and re.findall(r"\(N\d{8}\)|\(\d{9}\)", page_text or "")[-1:] == unassigned:
                restored_code = unassigned[0]
                last_row[project_column] = "\n".join([*last_lines, restored_code])
                repairs.append(
                    {
                        "type": "legacy_project_code_bleed_repaired",
                        "method": "unique_unassigned_final_page_code",
                        "to_serial": serial(last_row),
                        "project_code": restored_code[1:-1],
                    }
                )
    return repairs


def _clean_legacy_project_row(
    cells: list[str], month: str, source_file: str, source_page: int, raw_row_number: int,
    state: str | None, sector: str | None,
) -> dict[str, Any]:
    identity = _parse_legacy_identity(cells[3])
    original_doc_raw, revised_doc_raw, _anticipated_doc_raw = split_legacy_triplet(cells[5])
    original_cost_raw, revised_cost_raw, _anticipated_cost_raw = split_legacy_triplet(cells[6])
    approval_value = normalize_space(cells[4])
    expenditure_value = normalize_space(cells[7])
    progress_value = normalize_space(cells[8])
    approval_raw = None if is_missing(approval_value) else approval_value
    expenditure_raw = None if is_missing(expenditure_value) else expenditure_value
    progress_raw = None if is_missing(progress_value) else progress_value
    return {
        "project_code": identity.project_code,
        "legacy_ocms_code": identity.legacy_ocms_code,
        "pmgid": identity.pmgid,
        "project_name": identity.project_name,
        "agency": identity.agency,
        "ministry": None,
        "sector": sector,
        "state": state,
        "approval_date": parse_legacy_month(approval_raw),
        "start_date": None,
        "original_completion_date": parse_legacy_month(original_doc_raw),
        "revised_completion_date": parse_legacy_month(revised_doc_raw),
        "original_cost": parse_number(original_cost_raw),
        "revised_cost": parse_number(revised_cost_raw),
        "cumulative_expenditure": parse_number(expenditure_raw),
        "physical_progress": parse_number(progress_raw),
        "report_month": month,
        "approval_date_raw": approval_raw,
        "start_date_raw": None,
        "original_completion_date_raw": original_doc_raw,
        "revised_completion_date_raw": revised_doc_raw,
        "original_cost_raw": original_cost_raw,
        "revised_cost_raw": revised_cost_raw,
        "cumulative_expenditure_raw": expenditure_raw,
        "physical_progress_raw": progress_raw,
        "source_file": source_file,
        "source_page": source_page,
        "source_pages": str(source_page),
        "source_row_number": raw_row_number,
        "source_serial_number": int(cells[2]),
        "extraction_method": EXTRACTION_METHOD,
    }


def _clean_annexure_xviii_row(
    cells: list[str], month: str, source_file: str, source_page: int, raw_row_number: int,
    state: str | None, sector: str | None,
) -> dict[str, Any]:
    original_doc_raw, revised_doc_raw, _anticipated_doc_raw = split_legacy_triplet(cells[3])
    original_cost_raw, revised_cost_raw, _anticipated_cost_raw = split_legacy_triplet(cells[4])
    approval_value = normalize_space(cells[2])
    approval_raw = None if is_missing(approval_value) else approval_value

    exp_lines = [normalize_space(l) for l in (cells[5] or "").splitlines() if normalize_space(l)]
    exp_val = exp_lines[0] if exp_lines else None
    if exp_val and (exp_val.startswith("(") or exp_val.startswith("[")):
        exp_val = None
    expenditure_raw = None if is_missing(exp_val) else exp_val

    proj_text = cells[1]

    return {
        "project_code": None,
        "legacy_ocms_code": None,
        "pmgid": None,
        "project_name": proj_text,
        # Annexure XVIII has no agency column. Parenthetical text is part of
        # the source project name and must not be reinterpreted as an agency.
        "agency": None,
        "ministry": None,
        "sector": sector,
        "state": state,
        "approval_date": parse_legacy_month(approval_raw),
        "start_date": None,
        "original_completion_date": parse_legacy_month(original_doc_raw),
        "revised_completion_date": parse_legacy_month(revised_doc_raw),
        "original_cost": parse_number(original_cost_raw),
        "revised_cost": parse_number(revised_cost_raw),
        "cumulative_expenditure": parse_number(expenditure_raw),
        "physical_progress": None,
        "report_month": month,
        "approval_date_raw": approval_raw,
        "start_date_raw": None,
        "original_completion_date_raw": original_doc_raw,
        "revised_completion_date_raw": revised_doc_raw,
        "original_cost_raw": original_cost_raw,
        "revised_cost_raw": revised_cost_raw,
        "cumulative_expenditure_raw": expenditure_raw,
        "physical_progress_raw": None,
        "source_file": source_file,
        "source_page": source_page,
        "source_pages": str(source_page),
        "source_row_number": raw_row_number,
        "source_serial_number": int(cells[0]),
        "extraction_method": EXTRACTION_METHOD,
    }


def _clean_project_row(
    cells: list[str], month: str, source_file: str, source_page: int, raw_row_number: int, ministry: str | None, sector: str | None
) -> dict[str, Any]:
    identity = parse_project_identity(cells[1])
    approval_raw, start_raw = split_parenthesized_pair(cells[3])
    original_doc_raw, revised_doc_raw = split_parenthesized_pair(cells[4])
    original_cost_raw, revised_cost_raw = split_parenthesized_pair(cells[5])
    expenditure_raw = normalize_space(cells[6]) or None
    progress_raw = normalize_space(cells[7]) or None
    return {
        "project_code": identity.project_code,
        "legacy_ocms_code": identity.legacy_ocms_code,
        "pmgid": identity.pmgid,
        "project_name": identity.project_name,
        "agency": identity.agency,
        "ministry": ministry,
        "sector": sector,
        "state": normalize_space(cells[2]) or None,
        "approval_date": parse_month(approval_raw),
        "start_date": parse_month(start_raw),
        "original_completion_date": parse_month(original_doc_raw),
        "revised_completion_date": parse_month(revised_doc_raw),
        "original_cost": parse_number(original_cost_raw),
        "revised_cost": parse_number(revised_cost_raw),
        "cumulative_expenditure": parse_number(expenditure_raw),
        "physical_progress": parse_number(progress_raw),
        "report_month": month,
        "approval_date_raw": approval_raw,
        "start_date_raw": start_raw,
        "original_completion_date_raw": original_doc_raw,
        "revised_completion_date_raw": revised_doc_raw,
        "original_cost_raw": original_cost_raw,
        "revised_cost_raw": revised_cost_raw,
        "cumulative_expenditure_raw": expenditure_raw,
        "physical_progress_raw": progress_raw,
        "source_file": source_file,
        "source_page": source_page,
        "source_pages": str(source_page),
        "source_row_number": raw_row_number,
        "source_serial_number": int(cells[0]),
        "extraction_method": EXTRACTION_METHOD,
    }


def process_pdf(pdf_path: Path, paths: PipelinePaths) -> dict[str, Any]:
    LOGGER.info("Processing %s", pdf_path.name)
    raw_rows: list[dict[str, Any]] = []
    raw_pages: list[dict[str, Any]] = []
    projects: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    removed_counts = {"repeated_header": 0, "total": 0, "ministry_heading": 0, "sector_heading": 0}
    schema_events: list[dict[str, Any]] = []
    layout_versions: set[str] = set()
    ministry = sector = None
    state = None
    legacy_state_group: list[int] = []
    legacy_sector_group: list[int] = []

    with pdfplumber.open(pdf_path) as pdf:
        page_texts = [(index + 1, page.extract_text() or "") for index, page in enumerate(pdf.pages)]

        annexure_start = None
        for p_num, text in page_texts:
            leading_lines = [normalize_space(line).lower() for line in (text or "").splitlines()[:5]]
            semantic_leading_lines = [
                normalize_space(re.sub(r"[^a-z0-9]+", " ", line)) for line in leading_lines
            ]
            has_annexure_label = "annexure xviii" in semantic_leading_lines
            has_details_heading = any(
                heading in semantic_leading_lines
                for heading in ("details of on going projects", "details of ongoing projects")
            )
            if has_annexure_label and has_details_heading:
                page = pdf.pages[p_num - 1]
                if not page.find_tables(TABLE_SETTINGS):
                    # A contents page can name the annexure without containing
                    # its project grid; it is not a candidate table page.
                    continue
                _, _, _, audits, _ = _locate_table6_candidate(page, p_num)
                matching = [audit for audit in audits if audit["matches_table6_signature"]]
                if matching[0]["layout_version"] != ANNEXURE_XVIII_LAYOUT:
                    raise SchemaChangeDetected(
                        f"Page {p_num}: Annexure XVIII heading did not match its six-column schema"
                    )
                annexure_start = p_num
                break

        if annexure_start is not None:
            table_pages = [annexure_start]
            for p_num in range(annexure_start + 1, len(pdf.pages) + 1):
                page = pdf.pages[p_num - 1]
                if page.find_tables(TABLE_SETTINGS):
                    table_pages.append(p_num)
                else:
                    break
        else:
            table_pages = [number for number, text in page_texts if _is_table6_page(text)]

        if not table_pages:
            raise SchemaChangeDetected(f"Table 6 not detected in {pdf_path.name}")
        if table_pages != list(range(table_pages[0], table_pages[-1] + 1)):
            schema_events.append({"type": "noncontiguous_table_pages", "pages": table_pages})
        month = _detect_report_month(dict(page_texts)[table_pages[0]], pdf_path.name, pdf_path=pdf_path)
        extracted_dir = paths.extracted(month)
        LOGGER.info("Detected report month: %s", month)
        LOGGER.info("Detected Table 6 pages: %s-%s", table_pages[0], table_pages[-1])

        raw_sequence = 0
        legacy_header_established: bool | str = False
        for page_number in table_pages:
            page = pdf.pages[page_number - 1]
            try:
                table, selected_table_index, selection_pass, table_audits, extracted_tables = _locate_table6_candidate(page, page_number, legacy_header_established)
            except TableCandidateSelectionError as exc:
                message = str(exc)
                raw_pages.append(
                    {
                        "source_file": pdf_path.name,
                        "source_page": page_number,
                        "extraction_method": EXTRACTION_METHOD,
                        "table_selection_method": TABLE_SELECTION_METHOD,
                        "table_count": len(exc.audits),
                        "matching_table_candidates": sum(audit["matches_table6_signature"] for audit in exc.audits),
                        "table_audits": exc.audits,
                        "page_text": dict(page_texts)[page_number],
                    }
                )
                _write_schema_failure(
                    extracted_dir,
                    pdf_path.name,
                    page_number,
                    dict(page_texts)[page_number],
                    exc.tables,
                    message,
                    raw_rows,
                    raw_pages,
                    exc.audits,
                )
                raise
            for audit in table_audits:
                if audit["matches_table6_signature"]:
                    continue
                ignored_event = {"type": "ignored_noncanonical_table", **audit}
                schema_events.append(ignored_event)
                LOGGER.info(
                    "Ignored table on page %s: dimensions=%s columns=%s bbox=%s reason=%s",
                    page_number,
                    audit["dimensions"],
                    audit["column_count"],
                    audit["bbox"],
                    audit["reason"],
                )
            raw_pages.append(
                {
                    "source_file": pdf_path.name,
                    "source_page": page_number,
                    "extraction_method": EXTRACTION_METHOD,
                    "table_selection_method": TABLE_SELECTION_METHOD,
                    "table_count": len(table_audits),
                    "selected_table_index": selected_table_index,
                    "selected_detection_pass": selection_pass,
                    "matching_table_candidates": 1,
                    "table_audits": table_audits,
                    "page_text": dict(page_texts)[page_number],
                }
            )
            is_legacy_continuation = False
            try:
                candidate_header = table[1] if (len(table) > 1 and table[0][0] and "details of ongoing" in str(table[0][0]).lower()) else table[0]
                layout_version = _validate_header(candidate_header)
                if layout_version in LEGACY_LAYOUTS:
                    legacy_header_established = layout_version
            except SchemaChangeDetected as exc:
                if legacy_header_established == ANNEXURE_XVIII_LAYOUT and len(table[0]) == 6:
                    layout_version = ANNEXURE_XVIII_LAYOUT
                    is_legacy_continuation = True
                elif legacy_header_established in {
                    "legacy-all-ongoing-nine-column-v1",
                    "legacy-all-ongoing-nine-column-progress-only-v1",
                } and len(table[0]) in (7, 8, 9):
                    layout_version = str(legacy_header_established)
                    is_legacy_continuation = True
                else:
                    _write_schema_failure(
                        extracted_dir,
                        pdf_path.name,
                        page_number,
                        dict(page_texts)[page_number],
                        extracted_tables,
                        str(exc),
                        raw_rows,
                        raw_pages,
                        table_audits,
                    )
                    raise
            layout_versions.add(layout_version)
            raw_pages[-1]["layout_version"] = layout_version
            
            if layout_version in ("legacy-all-ongoing-nine-column-v1", "legacy-all-ongoing-nine-column-progress-only-v1"):
                repairs = _repair_legacy_project_code_bleed(table, dict(page_texts)[page_number])
                raw_pages[-1]["project_code_bleed_repairs"] = repairs
                schema_events.extend({"source_page": page_number, **repair} for repair in repairs)

            if is_legacy_continuation:
                legacy_groups = (
                    _legacy_group_cells(page, selection_pass, selected_table_index, is_continuation=True, col_count=len(table[0]))
                    if layout_version != ANNEXURE_XVIII_LAYOUT
                    else []
                )
                start_row = 0
            else:
                removed_counts["repeated_header"] += 1
                legacy_groups = (
                    _legacy_group_cells(page, selection_pass, selected_table_index, is_continuation=False, col_count=len(table[0]))
                    if layout_version in LEGACY_LAYOUTS and layout_version != ANNEXURE_XVIII_LAYOUT
                    else []
                )
                start_row = (
                    2
                    if layout_version == ANNEXURE_XVIII_LAYOUT
                    and table
                    and len(table) > 1
                    and table[0][0]
                    and "details of ongoing" in str(table[0][0]).lower()
                    else (
                        1
                        if table
                        and len(table) > 0
                        and table[0][0]
                        and ("si.no" in str(table[0][0]).lower() or "sl no" in str(table[0][0]).lower() or "sl.no" in str(table[0][0]).lower())
                        else 0
                    )
                )

            for page_row_number, source_row in enumerate(table[start_row:], start_row):
                raw_sequence += 1
                cells = [_normalize_cell(cell) for cell in source_row]
                
                if is_legacy_continuation and layout_version != ANNEXURE_XVIII_LAYOUT:
                    if len(cells) == 7:
                        cells = ["", ""] + cells
                    elif len(cells) == 8:
                        cells = ["", ""] + cells[1:]
                
                if legacy_groups:
                    s_rec, sec_rec = legacy_groups[page_row_number]
                    if s_rec:
                        cells[0] = s_rec
                    if sec_rec:
                        cells[1] = sec_rec
                raw = {
                    "raw_sequence": raw_sequence,
                    "source_file": pdf_path.name,
                    "source_page": page_number,
                    "source_row_number": page_row_number,
                    "extraction_method": EXTRACTION_METHOD,
                    "cells": cells,
                }
                raw_rows.append(raw)

                if layout_version == ANNEXURE_XVIII_LAYOUT:
                    serial = normalize_space(cells[0])
                    populated = sum(bool(cell) for cell in cells)
                    if serial.isdigit():
                        projects.append(
                            _clean_annexure_xviii_row(
                                cells, month, pdf_path.name, page_number, page_row_number, state, sector
                            )
                        )
                    elif re.fullmatch(r"\d+(?:\s+\d+)+", serial):
                        rejected.append(
                            {
                                **raw,
                                "raw_text": " | ".join(cells),
                                "reason": "multiple_source_projects_merged_in_one_detected_row",
                            }
                        )
                    elif re.match(r"^\d+\s+\S", serial) and not cells[1]:
                        rejected.append(
                            {**raw, "raw_text": " | ".join(cells), "reason": "serial_project_cell_bleed"}
                        )
                    elif not serial and cells[1]:
                        if cells[1].upper() in ANNEXURE_XVIII_STATES:
                            state = cells[1].upper()
                        elif cells[1].lower() in ANNEXURE_XVIII_SECTORS:
                            sector = cells[1]
                        elif "total" in cells[1].lower() or "si.no" in cells[1].lower() or "details of ongoing" in cells[1].lower():
                            removed_counts["total"] += 1
                        else:
                            if projects:
                                projects[-1]["project_name"] = f"{projects[-1]['project_name']} {cells[1]}"
                    elif not serial and not cells[1] and cells[2] and cells[3] and cells[4] and cells[5]:
                        rejected.append({**raw, "raw_text": " | ".join(cells), "reason": "source_omitted_serial_project_row"})
                    elif not serial and not populated:
                        rejected.append({**raw, "raw_text": "", "reason": "empty_table_row"})
                    else:
                        rejected.append({**raw, "raw_text": " | ".join(cells), "reason": "unclassified_non_project_row"})
                    continue

                serial_column = 2 if layout_version in LEGACY_LAYOUTS else 0
                serial = cells[serial_column]
                populated = sum(bool(cell) for cell in cells)
                if serial.isdigit() and layout_version in LEGACY_LAYOUTS:
                    if cells[0]:
                        fragment = normalize_space(cells[0])
                        if state and fragment.casefold().replace(" ", "") in state.casefold().replace(" ", ""):
                            fragment = state
                        state = fragment
                        legacy_state_group = []
                    if cells[1]:
                        fragment = normalize_space(cells[1])
                        if sector and fragment.casefold().replace(" ", "") in sector.casefold().replace(" ", ""):
                            fragment = sector
                        sector = fragment
                        legacy_sector_group = []
                    projects.append(
                        _clean_legacy_project_row(
                            cells, month, pdf_path.name, page_number, page_row_number, state, sector
                        )
                    )
                    project_index = len(projects) - 1
                    legacy_state_group.append(project_index)
                    legacy_sector_group.append(project_index)
                elif serial.isdigit():
                    projects.append(_clean_project_row(cells, month, pdf_path.name, page_number, page_row_number, ministry, sector))
                elif layout_version in LEGACY_LAYOUTS and (cells[0] or cells[1]) and populated <= 2:
                    if cells[0]:
                        fragment = normalize_space(cells[0])
                        state = _merge_legacy_group_fragment(state, fragment)
                        for index in legacy_state_group:
                            projects[index]["state"] = state
                    if cells[1]:
                        fragment = normalize_space(cells[1])
                        sector = _merge_legacy_group_fragment(sector, fragment)
                        for index in legacy_sector_group:
                            projects[index]["sector"] = sector
                elif not serial and cells[1].lower().startswith("total"):
                    removed_counts["total"] += 1
                elif layout_version in LEGACY_LAYOUTS and not serial and cells[3].lower().startswith("total"):
                    removed_counts["total"] += 1
                elif not serial and populated == 1 and cells[1]:
                    if cells[1].startswith(("Ministry of ", "Department of ", "Department for ")):
                        ministry, sector = cells[1], None
                        removed_counts["ministry_heading"] += 1
                    else:
                        sector = cells[1]
                        removed_counts["sector_heading"] += 1
                elif not serial and not populated:
                    rejected.append({**raw, "raw_text": "", "reason": "empty_table_row"})
                else:
                    rejected.append({**raw, "raw_text": " | ".join(cells), "reason": "unclassified_non_project_row"})

    _clear_stale_schema_failures(extracted_dir)
    _write_jsonl(extracted_dir / "raw_table6_rows.jsonl", raw_rows)
    _write_jsonl(extracted_dir / "raw_table6_pages.jsonl", raw_pages)
    uncoded_annexure = layout_versions == {ANNEXURE_XVIII_LAYOUT}
    warnings, duplicates, validation_metrics = validate_records(
        projects, project_code_structurally_absent=uncoded_annexure
    )
    qc_rows = build_quality_control_rows(projects, warnings)

    # Identifier/serial failures are retained for review, never silently dropped.
    for record in projects:
        if not record["project_code"] and not uncoded_annexure:
            rejected.append(
                {
                    "raw_text": record["project_name"],
                    "source_page": record["source_page"],
                    "source_row_number": record["source_row_number"],
                    "source_file": record["source_file"],
                    "reason": "missing_project_code",
                }
            )

    month_token = month.replace("-", "_")
    clean_path = (
        paths.uncoded_cleaned if uncoded_annexure else paths.cleaned
    ) / f"projects_{month_token}.csv"
    _write_csv(clean_path, projects, CLEAN_FIELDS)
    if uncoded_annexure:
        stale_canonical_path = paths.cleaned / f"projects_{month_token}.csv"
        if stale_canonical_path.exists() and stale_canonical_path.resolve() != clean_path.resolve():
            stale_canonical_path.unlink()
    warning_fields = [
        "project_code",
        "report_month",
        "source_file",
        "source_page",
        "source_row_number",
        "field",
        "rule",
        "severity",
        "priority",
        "category",
        "message",
    ]
    rejected_fields = ["source_file", "source_page", "source_row_number", "reason", "raw_text"]
    duplicate_fields = ["project_code", "report_month", "source_file", "source_page", "source_row_number", "duplicate_count"]
    qc_fields = [
        "project_code",
        "report_month",
        "start_date",
        "original_completion_date",
        "revised_completion_date",
        "original_cost",
        "revised_cost",
        "cumulative_expenditure",
        "physical_progress",
        "financial_progress",
        "physical_financial_gap",
        "warning_rules",
        "source_file",
        "source_page",
        "source_row_number",
    ]
    _write_csv(paths.validation / f"warnings_{month_token}.csv", warnings, warning_fields)
    _write_csv(paths.validation / f"rejected_{month_token}.csv", rejected, rejected_fields)
    _write_csv(paths.validation / f"duplicates_{month_token}.csv", duplicates, duplicate_fields)
    qc_path = paths.validation / f"qc_metrics_{month_token}.csv"
    _write_csv(qc_path, qc_rows, qc_fields)

    serials = [x["source_serial_number"] for x in projects]
    expected_serials = list(range(1, max(serials) + 1)) if serials else []
    serial_gaps = sorted(set(expected_serials) - set(serials))
    serial_duplicates = sorted(number for number in set(serials) if serials.count(number) > 1)
    parse_metrics = {}
    for field in ("original_cost", "revised_cost", "cumulative_expenditure", "physical_progress"):
        raw_field = f"{field}_raw"
        denominator = sum(bool(record[raw_field]) for record in projects)
        numerator = sum(bool(record[raw_field]) and record[field] is not None for record in projects)
        parse_metrics[field] = {"parsed": numerator, "source_present": denominator, "success_rate": numerator / denominator if denominator else None}
    date_present = sum(bool(record[f"{field}_raw"]) for record in projects for field in ("approval_date", "start_date", "original_completion_date", "revised_completion_date"))
    date_parsed = sum(bool(record[f"{field}_raw"]) and record[field] is not None for record in projects for field in ("approval_date", "start_date", "original_completion_date", "revised_completion_date"))

    manifest = {
        "source_file": pdf_path.name,
        "source_path": str(pdf_path.resolve()),
        "report_month": month,
        "table": "Annexure XVIII: Details of Ongoing Projects" if uncoded_annexure else "All Ongoing Projects (Table 6)",
        "extractor": EXTRACTION_METHOD,
        "table_selection_method": TABLE_SELECTION_METHOD,
        "layout_versions": sorted(layout_versions),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "pages_in_report": len(page_texts),
        "pages_processed": table_pages,
        "table6_start_page": table_pages[0],
        "table6_end_page": table_pages[-1],
        "raw_rows": len(raw_rows),
        "candidate_project_rows": len(projects),
        "clean_rows": len(projects),
        "warning_rows": validation_metrics["warning_rows"],
        "warning_count": validation_metrics["warning_count"],
        "rejected_rows": len(rejected),
        "missing_project_codes": validation_metrics["missing_project_codes"],
        "structurally_missing_project_codes": validation_metrics["structurally_missing_project_codes"],
        "duplicate_project_codes": validation_metrics["duplicate_project_codes"],
        "duplicate_rows": validation_metrics["duplicate_rows"],
        "removed_nonproject_rows": removed_counts,
        "serial_gaps": serial_gaps,
        "serial_duplicates": serial_duplicates,
        "numeric_parse": parse_metrics,
        "date_parse": {"parsed": date_parsed, "source_present": date_present, "success_rate": date_parsed / date_present if date_present else None},
        "warnings_by_rule": validation_metrics["warnings_by_rule"],
        "warnings_by_severity": validation_metrics["warnings_by_severity"],
        "warnings_by_priority": validation_metrics["warnings_by_priority"],
        "warnings_by_category": validation_metrics["warnings_by_category"],
        "quality_control": {
            "output_csv": str(qc_path.resolve()),
            "financial_progress_formula": "cumulative_expenditure / revised_cost * 100",
            "physical_financial_gap_formula": "physical_progress - financial_progress",
            "derived_values_in_ml_dataset": False,
        },
        "schema_events": schema_events,
        "canonical_integration_eligible": not uncoded_annexure,
        "canonical_exclusion_reason": (
            "Source layout has no project identifier; no surrogate identity may be created"
            if uncoded_annexure
            else None
        ),
        "structurally_absent_fields": (
            ["project_code", "legacy_ocms_code", "pmgid", "ministry", "start_date", "physical_progress"]
            if uncoded_annexure
            else []
        ),
        "output_csv": str(clean_path.resolve()),
    }
    _write_json(paths.validation / f"manifest_{month_token}.json", manifest)
    _write_json(paths.validation / f"quality_{month_token}.json", manifest)
    quality_text = f"""REPORT: {month}

Source file: {pdf_path.name}
Pages in report: {len(page_texts)}
Table 6 pages: {table_pages[0]}-{table_pages[-1]} ({len(table_pages)} pages)

Raw rows: {len(raw_rows)}
Candidate project rows: {len(projects)}
Clean project rows: {len(projects)}
Rejected rows: {len(rejected)}
Warning rows: {validation_metrics['warning_rows']}

Missing project codes: {validation_metrics['missing_project_codes']}
Structurally missing project codes: {validation_metrics['structurally_missing_project_codes']}
Duplicate project codes: {validation_metrics['duplicate_project_codes']}
Serial gaps: {serial_gaps}
Serial duplicates: {serial_duplicates}

Original cost parse success: {parse_metrics['original_cost']['parsed']}/{parse_metrics['original_cost']['source_present']}
Revised cost parse success: {parse_metrics['revised_cost']['parsed']}/{parse_metrics['revised_cost']['source_present']}
Expenditure parse success: {parse_metrics['cumulative_expenditure']['parsed']}/{parse_metrics['cumulative_expenditure']['source_present']}
Physical progress parse success: {parse_metrics['physical_progress']['parsed']}/{parse_metrics['physical_progress']['source_present']}
Date parse success: {date_parsed}/{date_present}

Warnings by rule: {json.dumps(validation_metrics['warnings_by_rule'], sort_keys=True)}
Warnings by severity: {json.dumps(validation_metrics['warnings_by_severity'], sort_keys=True)}
Warnings by priority: {json.dumps(validation_metrics['warnings_by_priority'], sort_keys=True)}
Schema events: {json.dumps(schema_events, sort_keys=True)}
Canonical integration eligible: {not uncoded_annexure}
"""
    quality_path = paths.validation / f"quality_{month_token}.txt"
    quality_path.parent.mkdir(parents=True, exist_ok=True)
    quality_path.write_text(quality_text, encoding="utf-8")
    LOGGER.info("Extracted %s candidate records; warnings=%s rejected=%s", len(projects), validation_metrics["warning_count"], len(rejected))
    return {"manifest": manifest, "records": projects, "clean_path": clean_path}


def combine_months(results: list[dict[str, Any]], paths: PipelinePaths) -> Path:
    records = [record for result in results for record in result["records"]]
    records.sort(key=lambda row: (row["report_month"], str(row["project_code"] or "")))
    combined = paths.processed / "projects_monthly.csv"
    _write_csv(combined, records, CLEAN_FIELDS)
    key_counts = Counter((record["project_code"], record["report_month"]) for record in records)
    months = sorted({record["report_month"] for record in records})
    codes_by_month = {month: {record["project_code"] for record in records if record["report_month"] == month} for month in months}
    adjacent_matching = []
    for earlier, later in zip(months, months[1:]):
        a, b = codes_by_month[earlier], codes_by_month[later]
        adjacent_matching.append(
            {
                "earlier_month": earlier,
                "later_month": later,
                "projects_in_both": len(a & b),
                "earlier_only": len(a - b),
                "later_only": len(b - a),
            }
        )
    summary = {
        "rows": len(records),
        "report_months": months,
        "rows_by_month": dict(Counter(record["report_month"] for record in records)),
        "duplicate_project_month_keys": sum(count > 1 for count in key_counts.values()),
        "duplicate_project_month_rows": sum(count for count in key_counts.values() if count > 1),
        "adjacent_month_matching": adjacent_matching,
        "output_csv": str(combined.resolve()),
    }
    _write_json(paths.validation / "combined_summary.json", summary)
    rule_codes = sorted(
        {
            rule
            for result in results
            for rule in result["manifest"].get("warnings_by_rule", {})
        }
    )
    rule_summary = {
        "unit": "project-month records",
        "counts_by_report_month": {
            result["manifest"]["report_month"]: {
                rule: result["manifest"].get("warnings_by_rule", {}).get(rule, 0)
                for rule in rule_codes
            }
            for result in sorted(results, key=lambda item: item["manifest"]["report_month"])
        },
        "counts_all_months": {
            rule: sum(result["manifest"].get("warnings_by_rule", {}).get(rule, 0) for result in results)
            for rule in rule_codes
        },
    }
    _write_json(paths.validation / "validation_rule_summary.json", rule_summary)
    return combined
