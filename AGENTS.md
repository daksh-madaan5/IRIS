# PAIMANA repository agent guide

## Mission and current phase

This repository extracts auditable, source-faithful historical infrastructure project records from PAIMANA/OCMS monthly Flash Report PDFs. The working unit is one ongoing project in one report month.

The project is in the **data-extraction and validation phase only**. Do not perform machine learning, feature engineering, normalization, imputation, target creation, dashboard work, completed-project integration, or model training unless a later user request explicitly changes the project phase. Validation-only metrics belong under `data/validation/`, never in the canonical project-month dataset.

Read `docs/HANDOFF.md` before starting historical work. It records the exact accepted range, hashes, layouts, test status, known quirks, and next task.

## Repository map

- `data/raw/`: source PDFs. Immutable input; ignored by Git.
- `data/extracted/YYYY-MM/`: raw/intermediate page and row JSONL, table-selection audits, and fail-closed schema artifacts. Generated and ignored by Git.
- `data/cleaned/projects_YYYY_MM.csv`: accepted monthly source-faithful project records. Generated and ignored by Git.
- `data/cleaned_uncoded/projects_YYYY_MM.csv`: accepted source-faithful records from layouts that structurally omit project identity. These retain canonical columns but are deliberately excluded from `projects_monthly.csv`; never create a surrogate key to move them into `data/cleaned/`.
- `data/processed/projects_monthly.csv`: explicitly rebuilt multi-month canonical dataset. Generated and ignored by Git.
- `data/validation/`: manifests, warnings, rejected rows, duplicates, QC-only metrics, longitudinal summaries, diagnostics, and the June-July 2025 crosswalk investigation. Generated and ignored by Git.
- `schemas/project_month.schema.json`: documented record schema. See the legacy-ID caveat below.
- `src/extraction/`: month detection, semantic table selection, raw extraction, layout adapters, cleaning orchestration, and monthly outputs.
- `src/cleaning/`: source-aware parsers for identifiers, dates, paired values, numerics, and legacy triplets.
- `src/validation/`: record validation, diagnostics, revalidation, and the diagnostic identifier-crosswalk investigation.
- `src/build_dataset/monthly.py`: explicit combined-dataset rebuild and adjacent-month longitudinal validation.
- `tests/`: parser, selector, generated-data, manual-fixture, longitudinal, and crosswalk regression tests.
- `reports/`: concise acceptance, validation, diagnostic, and data-dictionary documentation.
- `tmp/`: disposable local inspection artifacts; ignored by Git.

## Canonical project-month record

The canonical key is `(project_code, report_month)`. Duplicates are reported and retained until investigated; they are never silently deduplicated.

The cleaned/combined column order is defined by `CLEAN_FIELDS` in `src/extraction/pipeline.py`:

1. Identity and source labels: `project_code`, `legacy_ocms_code`, `pmgid`, `project_name`, `agency`, `ministry`, `sector`, `state`.
2. Parsed dates: `approval_date`, `start_date`, `original_completion_date`, `revised_completion_date`.
3. Parsed numerics: `original_cost`, `revised_cost`, `cumulative_expenditure`, `physical_progress`.
4. Time: `report_month`.
5. Source representations: `approval_date_raw`, `start_date_raw`, `original_completion_date_raw`, `revised_completion_date_raw`, `original_cost_raw`, `revised_cost_raw`, `cumulative_expenditure_raw`, `physical_progress_raw`.
6. Provenance: `source_file`, `source_page`, `source_pages`, `source_row_number`, `source_serial_number`, `extraction_method`.

Dates printed as `MM/YYYY` are represented as `YYYY-MM`; no day is invented. Numeric canonical fields are parsed values, while the corresponding `*_raw` fields preserve the reported representation. Units for cost and expenditure are Rs crore; physical progress is a percentage and is not clamped.

`schemas/project_month.schema.json` currently constrains `project_code` to six digits, but production validation deliberately also accepts the source-reported legacy formats `N########` and nine-digit numeric identifiers used from June 2024 through June 2025. This schema file predates the legacy adapter. Do **not** rewrite legacy codes to satisfy its six-digit regex. If strict JSON-schema enforcement is introduced, update the schema and tests to describe all accepted source formats without changing data.

## Source-faithful data rules

- Never modify raw reported values.
- Never normalize canonical agency, project name, ministry, sector, state, identifier, date, cost, expenditure, or progress values for analytical convenience.
- Never infer a missing value. Empty means source-absent or source-missing; it is not zero.
- Never backfill a later value into an earlier month.
- Never copy original cost/date into a missing revised field unless the source structure explicitly prints that revised value.
- Never infer a start date in a layout that omits it. July 2025 legitimately has no Start Date column.
- Preserve `project_code` exactly as reported. Do not strip `N`, pad, truncate, translate, or replace it.
- Preserve source spelling, punctuation, casing, abbreviations, and grouping labels in canonical text fields. Comparison-only normalized representations may exist in diagnostics, never as replacements.
- Join wrapped visual lines only as required to reconstruct the printed cell; retain the raw/intermediate table extraction for audit.
- Preserve original, revised, and anticipated semantics. In the legacy layout, braced anticipated values must not be promoted to canonical revised values.
- Do not correct source-data anomalies. Flag them and retain the reported record.

## June-July 2025 identifier redesign

January-June 2025 use legacy `N########` or nine-digit-style project identifiers. July 2025 onward uses six-digit project codes. Direct June-to-July `project_code` overlap is therefore zero.

Neither June nor July prints an explicit old-to-new crosswalk, populated legacy OCMS code, or PMGID bridge. `data/validation/id_crosswalk_june_july_2025.csv` contains 137 conservative high-confidence **analytical proposals**, not source mappings. The ambiguous table and investigation report must remain separate from canonical data.

Never automatically integrate the proposed crosswalk, create `stable_project_id`, rewrite `project_code`, or treat fuzzy/name similarity as identity. Any future stable-ID layer requires explicit user approval and must retain source `project_code`, mapping status, method, evidence, conflicts, and provenance. Read `reports/id_crosswalk_june_july_2025.md` before any identity work.

## Fail-closed schema behavior

- Detect the report month from report text, with filename only as a fallback. If the month cannot be determined, stop that report.
- Locate the ongoing-project section semantically (`All Ongoing Projects`, or the verified legacy ongoing-project heading), not by assumed page numbers.
- Every Table page may contain multiple `pdfplumber` table detections. Evaluate every candidate against a verified positional header signature.
- Exactly one canonical candidate on a page means process it. Zero candidates or more than one candidate means `SCHEMA_CHANGE`; preserve partial raw extraction and the offending-page/table audits, then stop that report.
- Never select by fixed table index, largest table, most rows, most columns, or table size alone.
- The known enclosing two-column detection may be ignored only because it clearly fails the project-table signature. Log its page, index, dimensions/column count, bbox, detection pass, and reason.
- Geometry/bboxes may support rejection and auditing, but semantic header structure is decisive.
- Page-frame exclusion is a narrowly scoped recovery pass only after the full-page pass finds zero canonical matches. If the full-page pass already finds one or more matches, do not use cropping to override that result.
- Require a supported layout signature and consistent source semantics. Do not force an unsupported header through an existing adapter.
- On failure, preserve `raw_table6_rows.partial.jsonl`, `raw_table6_pages.partial.jsonl`, and `SCHEMA_CHANGE_DETECTED_page_*.json`. Do not create a cleaned monthly CSV for a failed report.

## Supported layout adapters

- `legacy-annexure-xviii-six-column-v1`: April and May 2024 only. This is `Annexure XVIII: Details of On-going Projects`, not Table 6/7. It contains serial, project, approval, completion triplet, cost triplet, and expenditure triplet columns, while structurally omitting project code, agency, ministry, Start Date, and physical progress. Output must remain under `data/cleaned_uncoded/` and is not eligible for canonical integration.
- `legacy-all-ongoing-nine-column-v1`: June through October 2024, December 2024, and January through June 2025. The reports call the project list Table 7. Columns include separate State and Sector, but no Ministry or Start Date. Project codes are legacy formats. Original/revised/anticipated triplets require legacy parsing. January and March 2025 have character-spaced embedded date text and use `Mon-YY`; parser compaction must not alter `*_raw` values.
- `legacy-all-ongoing-nine-column-progress-only-v1`: November 2024 only. It has the same verified legacy nine-column semantics, but the final header is printed `Progress (%)` rather than `Physical Progress (%)`. Keep this distinct signature narrow; do not accept arbitrary progress-only tables without the full positional legacy header match.
- `table6-eight-column-approval-only-v1`: July 2025 only. This verified Table 6 variant has Date of Approval without Start Date; keep `start_date` empty.
- `table6-eight-column-v1`: August 2025 through July 2026. The standard eight-column Table 6 structure includes approval/start, original/revised completion, original/revised cost, expenditure, and progress semantics.

Do not broaden an adapter merely because a new report is similar. A new source structure gets a narrowly scoped semantic adapter and regression fixture only after visual inspection establishes its semantics.

## Data flow and provenance

The required flow is:

`source PDF -> raw/intermediate JSONL -> cleaned monthly CSV (coded or explicitly uncoded) -> explicit coded combined rebuild -> validation/longitudinal artifacts`

Raw extraction must precede cleaning and must be preserved. Every cleaned record requires `source_file`, physical `source_page`, `source_pages` where a logical record spans pages, `source_row_number`, printed `source_serial_number`, and versioned `extraction_method`. Manifests must record pages processed, Table start/end pages, layout version, selector method, parse rates, serial gaps/duplicates, warnings, rejected rows, duplicates, schema events, and output paths.

## Validation philosophy

Separate structure from source-data quality:

- **Structural/schema failures:** unsupported or ambiguous tables, missing required row structure, unparseable required identifiers, discontinuous/duplicate serials, or other failures that invalidate extraction. Fail closed or reject the structural non-project row with an exact reason.
- **Source-data warnings:** plausible or implausible values printed by the source. Keep the project row and exact source value; emit a warning with rule, severity, priority, category, message, and provenance.
- Repeated headers, group headings, totals, and empty table rows are non-project material. Remove or reject them explicitly and count the exact reason.
- Missing/invalid identifiers, duplicates, date/numeric parse failures, and serial continuity must be validated for every report.
- Duplicates are emitted separately and are not silently dropped.
- Validation-only `financial_progress` and `physical_financial_gap` belong only in `qc_metrics_YYYY_MM.csv`; never add them to cleaned or combined data.

Cross-field source-quality rules are documented in `reports/validation_rules.md` and currently include:

- `ZERO_EXPENDITURE_POSITIVE_PROGRESS`
- `PROGRESS_REPORTED_BEFORE_START`
- `EXPENDITURE_WITH_ZERO_PROGRESS`
- `FULL_PROGRESS_STILL_ONGOING`
- `PHYSICAL_PROGRESS_ABOVE_100`
- `NEGATIVE_EXPENDITURE`
- `EXTREME_EXPENDITURE_COST_MISMATCH`
- `REVISED_COST_BELOW_ORIGINAL`
- `COMPLETION_DATE_BEFORE_START_DATE`

Adjacent-month longitudinal validation compares only exact `project_code` matches and reports overlap, earlier-only/later-only projects, expenditure-state transitions, and these warning counts:

- `AGENCY_CHANGED`, `PROJECT_NAME_CHANGED`, `MINISTRY_CHANGED`, `SECTOR_CHANGED`, `STATE_CHANGED`
- `CUMULATIVE_EXPENDITURE_DECREASED`, `PHYSICAL_PROGRESS_DECREASED`, `REVISED_COST_DECREASED`
- positive cumulative expenditure becoming exactly zero

Do not run ordinary exact-code longitudinal comparisons across June-July 2025 as though zero overlap meant zero project continuity. The ID system changed, and the separate crosswalk investigation remains diagnostic only.

## Regression and hash protection

- Run the full regression suite before production parser changes and after them.
- Add a regression test for every new layout and for any parser bug that could alter accepted records.
- Include a representative source page for the new layout and keep fail-closed zero/multiple-candidate tests.
- Snapshot SHA-256 hashes for every previously accepted monthly CSV and `data/processed/projects_monthly.csv` before processing a new report.
- After extraction/parser changes, require all previously accepted hashes to remain byte-for-byte unchanged. Stop and investigate any unexpected change.
- Do not rebuild the combined dataset until every new month passes individual extraction, structural validation, parse-rate checks, provenance checks, and manual PDF comparison.
- Rebuild with an explicit ordered month list. Never rely on `DEFAULT_MONTHS`, which currently covers only January-July 2026.
- Confirm the rebuilt combined row count, months, unique projects, missing IDs, duplicate keys, overlap counts, longitudinal warnings, and final SHA-256.

## Commands

Run commands from the repository root. Use the active Python environment after installing `requirements.txt`.

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -v
```

Safely process one newly supplied PDF without rebuilding `projects_monthly.csv`:

```powershell
python -c "from pathlib import Path; from src.extraction.pipeline import PipelinePaths, process_pdf; root=Path.cwd().resolve(); process_pdf(Path('data/raw/2025/REPORT.pdf').resolve(), PipelinePaths(root))"
```

The general CLI recursively processes every PDF under its input and then combines only the results from that invocation:

```powershell
python -m src.extraction --input data/raw
```

Do not point that CLI at a single new PDF if the accepted multi-month `projects_monthly.csv` must be preserved; use `process_pdf` as above, validate the month, then rebuild explicitly.

Explicit accepted-range rebuild command:

```powershell
python -m src.build_dataset.monthly --months 2024-06 2024-07 2024-08 2024-09 2024-10 2024-11 2024-12 2025-01 2025-02 2025-03 2025-04 2025-05 2025-06 2025-07 2025-08 2025-09 2025-10 2025-11 2025-12 2026-01 2026-02 2026-03 2026-04 2026-05 2026-06 2026-07
```

Reproduce the diagnostic June-July crosswalk outputs only when identity diagnostics are explicitly requested:

```powershell
python -m src.validation.id_crosswalk --root .
```

Hash checks:

```powershell
Get-FileHash data/processed/projects_monthly.csv -Algorithm SHA256
Get-FileHash data/cleaned/projects_*.csv -Algorithm SHA256
```

## Adding a historical PDF or layout

1. Confirm the user placed the PDF in scope; do not process additional months.
2. Record accepted monthly and combined hashes, then run the full tests.
3. Detect the month and visually inspect the first Table page, a continuation/page boundary, and the final Table page.
4. Run semantic selection. If zero or multiple candidates qualify, preserve `SCHEMA_CHANGE` artifacts and inspect; do not force extraction.
5. If a new structure is real, add the narrowest adapter and header signature. Document absent fields and source conventions; never infer them.
6. Add selector/parser regression coverage using the actual new layout while retaining all older layout tests.
7. Process only the new PDF through `process_pdf` until its monthly output passes.
   If its source layout has no defensible project identifier, route it to `data/cleaned_uncoded/`, record structural absence and canonical ineligibility in the manifest, and do not include that month in the coded combined rebuild.
8. Verify serial continuity, identifiers, duplicates, rejected reasons, date/numeric parse rates, cross-field warnings, provenance, first/last records, at least two page boundaries, multiline names, paired values, missing values, and unusual numerics.
9. Manually compare representative records with rendered PDF pages.
10. Rerun the full tests and verify every previously accepted monthly hash is unchanged.
11. Only then rebuild the combined dataset with the full explicit ordered month list and review adjacent-month diagnostics.
12. Write/update a concise acceptance report and `docs/HANDOFF.md`; stop at the user-specified boundary.

## Git rules

- Preserve user changes. Inspect `git status` before editing and do not reset, checkout, clean, delete, or overwrite unrelated work.
- Track source code, schemas, tests, `AGENTS.md`, `docs/*.md`, and concise Markdown reports.
- Source PDFs and generated `data/extracted`, `data/cleaned`, `data/processed`, and `data/validation` outputs are intentionally ignored by Git. Do not force-add them unless the user explicitly changes repository policy.
- Do not commit archives, temporary renders, inspection outputs, logs, or local environments. The currently untracked `IRIS_data_2025_2026.7z` is outside this handoff task; do not stage, modify, or delete it without explicit instruction.
- Do not amend, rebase, force-push, or create commits unless explicitly requested.
- Before handoff, report tests, relevant hashes, generated artifacts, and any dirty/untracked files that another agent must preserve.
