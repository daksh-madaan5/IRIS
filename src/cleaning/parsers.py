"""Pure parsing helpers for PAIMANA Table 6 cells."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

MISSING_TOKENS = {"", "-", "/", "(-)", "na", "n/a", "n.a.", "nil", "none"}
MONTH_RE = re.compile(r"^(0[1-9]|1[0-2])/(19|20)\d{2}$")
LEGACY_MONTH_NAME = {
    name.lower(): index
    for index, name in enumerate(("", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"))
    if name
}


def normalize_space(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def is_missing(value: str | None) -> bool:
    normalized = normalize_space(value).lower()
    compact = re.sub(r"\s+", "", normalized)
    return normalized in MISSING_TOKENS or compact in MISSING_TOKENS


def normalize_identifier(value: str | None) -> str | None:
    value = normalize_space(value)
    if is_missing(value):
        return None
    return value


def parse_number(value: str | None) -> float | None:
    """Parse a source number without treating missing as zero."""
    value = normalize_space(value).replace(",", "").replace("%", "")
    if is_missing(value):
        return None
    if value.startswith("(") and value.endswith(")"):
        value = value[1:-1].strip()
    try:
        return float(Decimal(value))
    except (InvalidOperation, ValueError):
        return None


def parse_month(value: str | None) -> str | None:
    """Convert MM/YYYY to YYYY-MM; retain no invented day component."""
    value = normalize_space(value)
    if is_missing(value) or not MONTH_RE.fullmatch(value):
        return None
    month, year = value.split("/")
    return f"{year}-{month}"


def parse_legacy_month(value: str | None) -> str | None:
    """Parse the explicitly reported month formats in the legacy project list."""
    value = normalize_space(value)
    # January and March 2025 use the same visual date semantics as the other
    # legacy reports, but their embedded text layer inserts spaces between
    # characters (for example ``2 - 2 0 1 8`` and ``J u n -24``). Keep that
    # representation in the *_raw field and compact only the parser input.
    compact = re.sub(r"\s+", "", value)
    if is_missing(value) or compact.lower() in MISSING_TOKENS:
        return None
    numeric = re.fullmatch(r"(0?[1-9]|1[0-2])[-/](19|20)(\d{2})", compact)
    if numeric:
        return f"{numeric.group(2)}{numeric.group(3)}-{int(numeric.group(1)):02d}"
    named = re.fullmatch(r"([A-Za-z]{3})-(\d{2}|20\d{2})", compact)
    if named and named.group(1).lower() in LEGACY_MONTH_NAME:
        year = named.group(2) if len(named.group(2)) == 4 else f"20{named.group(2)}"
        return f"{year}-{LEGACY_MONTH_NAME[named.group(1).lower()]:02d}"
    return None


def split_legacy_triplet(value: str | None) -> tuple[str | None, str | None, str | None]:
    """Split original, parenthesized revised, and braced/bracketed anticipated source values."""
    lines = [normalize_space(x) for x in (value or "").splitlines() if normalize_space(x)]
    original = revised = anticipated = None
    for line in lines:
        if line.startswith("(") and line.endswith(")"):
            candidate = line[1:-1].strip()
            revised = None if is_missing(candidate) else candidate
        elif (line.startswith("{") and line.endswith("}")) or (line.startswith("[") and line.endswith("]")):
            candidate = line[1:-1].strip()
            anticipated = None if is_missing(candidate) else candidate
        elif original is None:
            original = None if is_missing(line) else line
    return original, revised, anticipated


def split_parenthesized_pair(value: str | None) -> tuple[str | None, str | None]:
    """Split a two-line original/revised or approval/start source cell."""
    lines = [normalize_space(x) for x in (value or "").splitlines() if normalize_space(x)]
    if not lines:
        return None, None
    first = lines[0]
    second = " ".join(lines[1:]).strip() if len(lines) > 1 else ""
    if second.startswith("(") and second.endswith(")"):
        second = second[1:-1].strip()
    return (None if is_missing(first) else first, None if is_missing(second) else second)


@dataclass(frozen=True)
class ProjectIdentity:
    project_name: str
    agency: str | None
    project_code: str | None
    legacy_ocms_code: str | None
    pmgid: str | None


def parse_project_identity(cell: str | None) -> ProjectIdentity:
    """Parse the styled composite Project Name/Agency/identifier cell.

    The report renders the final lines in a stable logical order:
    agency, project code, then legacy OCMS code and PMGID. Project and agency
    text may each wrap over multiple visual lines.
    """
    lines = [normalize_space(x) for x in (cell or "").splitlines() if normalize_space(x)]
    pair_index = None
    legacy = pmgid = None
    pair_re = re.compile(r"^\(([^()]*)\)\s+\(([^()]*)\)$")
    for i in range(len(lines) - 1, -1, -1):
        match = pair_re.fullmatch(lines[i])
        if match:
            pair_index = i
            legacy, pmgid = map(normalize_identifier, match.groups())
            break

    search_end = pair_index if pair_index is not None else len(lines)
    code_index = None
    project_code = None
    code_re = re.compile(r"^\((\d{6})\)$")
    for i in range(search_end - 1, -1, -1):
        match = code_re.fullmatch(lines[i])
        if match:
            code_index = i
            project_code = normalize_identifier(match.group(1))
            break

    # January has only the project code. February and March put the optional
    # legacy code on its own following line. April onward put legacy and PMGID
    # together on one line, which is handled by pair_re above.
    if code_index is not None and pair_index is None:
        single_identifier_re = re.compile(r"^\(([^()]*)\)$")
        trailing_identifiers = []
        for line in lines[code_index + 1 :]:
            match = single_identifier_re.fullmatch(line)
            if not match:
                break
            trailing_identifiers.append(normalize_identifier(match.group(1)))
        if trailing_identifiers:
            legacy = trailing_identifiers[0]
        if len(trailing_identifiers) > 1:
            pmgid = trailing_identifiers[1]

    agency = None
    agency_start = code_index if code_index is not None else search_end
    for i in range(agency_start - 1, -1, -1):
        candidate = " ".join(lines[i:agency_start])
        if lines[i].startswith("(") and candidate.endswith(")"):
            agency = normalize_space(candidate[1:-1]) or None
            agency_start = i
            break

    name = normalize_space(" ".join(lines[:agency_start]))
    return ProjectIdentity(name, agency, project_code, legacy, pmgid)
