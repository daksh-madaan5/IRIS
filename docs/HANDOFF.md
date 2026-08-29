# PAIMANA extraction handoff

## Current exact state

The coded canonical ongoing-project extraction covers **2023-04 through 2023-11**, **2024-01 through 2024-03**, and **2024-06 through 2026-07**: 37 monthly reports with an explicit December 2023 gap. December 2023 is `SUMMARY_ONLY`; no monthly project rows were created. The nearby Q3 quarterly report remains a separate, unextracted `FULL_QUARTERLY_CODED` source and is not a December substitute. April and May 2024 have also been accepted as source-faithful **uncoded** monthly extractions under `data/cleaned_uncoded/`; they are intentionally excluded from the canonical combined dataset because Annexure XVIII prints no project identifier.

- Project-month observations: **60,287**
- Unique source-reported project identifiers: **4,649**
- Missing project codes: **0**
- Duplicate `(project_code, report_month)` keys: **0**
- Projects with at least 3 observations: **4,446**
- Projects with at least 6 observations: **4,108**
- Projects with at least 10 observations: **2,705**
- Projects with at least 12 observations: **2,426**
- Projects with at least 16 observations: **1,505**
- Projects with at least 18 observations: **1,362**
- Projects with at least 19 observations: **1,282**
- Combined file: `data/processed/projects_monthly.csv`
- Accepted combined SHA-256: `2301524D9A7AF597672716FB6D483FBBCCCBCAA9B9A57E0A154AC7E42F4878FA`
- Current regression suite: **107/107 passing**

Monthly row counts are:

| Month | Rows | Layout |
|---|---:|---|
| 2023-04 | 1,605 | `legacy-detail-ongoing-nine-column-milestones-v1` |
| 2023-05 | 1,681 | `legacy-detail-ongoing-nine-column-milestones-v1` |
| 2023-06 | 1,643 | `legacy-detail-ongoing-nine-column-milestones-v1` |
| 2023-07 | 1,646 | `legacy-detail-ongoing-nine-column-milestones-v1` |
| 2023-08 | 1,762 | `legacy-detail-ongoing-nine-column-milestones-v1` |
| 2023-09 | 1,763 | `legacy-detail-ongoing-nine-column-milestones-v1` |
| 2023-10 | 1,788 | `legacy-detail-ongoing-nine-column-milestones-v1` |
| 2023-11 | 1,831 | `legacy-detail-ongoing-nine-column-milestones-v1` |
| 2024-01 | 1,821 | `legacy-detail-ongoing-nine-column-milestones-v1` |
| 2024-02 | 1,902 | `legacy-detail-ongoing-nine-column-milestones-v1` |
| 2024-03 | 1,873 | `legacy-detail-ongoing-nine-column-milestones-v1` |
| 2024-06 | 1,810 | `legacy-all-ongoing-nine-column-v1` |
| 2024-07 | 1,793 | `legacy-all-ongoing-nine-column-v1` |
| 2024-08 | 1,783 | `legacy-all-ongoing-nine-column-v1` |
| 2024-09 | 1,792 | `legacy-all-ongoing-nine-column-v1` |
| 2024-10 | 1,747 | `legacy-all-ongoing-nine-column-v1` |
| 2024-11 | 1,742 | `legacy-all-ongoing-nine-column-progress-only-v1` |
| 2024-12 | 1,724 | `legacy-all-ongoing-nine-column-v1` |
| 2025-01 | 1,719 | `legacy-all-ongoing-nine-column-v1` |
| 2025-02 | 1,682 | `legacy-all-ongoing-nine-column-v1` |
| 2025-03 | 1,677 | `legacy-all-ongoing-nine-column-v1` |
| 2025-04 | 1,670 | `legacy-all-ongoing-nine-column-v1` |
| 2025-05 | 1,637 | `legacy-all-ongoing-nine-column-v1` |
| 2025-06 | 1,595 | `legacy-all-ongoing-nine-column-v1` |
| 2025-07 | 791 | `table6-eight-column-approval-only-v1` |
| 2025-08 | 800 | `table6-eight-column-v1` |
| 2025-09 | 794 | `table6-eight-column-v1` |
| 2025-10 | 820 | `table6-eight-column-v1` |
| 2025-11 | 823 | `table6-eight-column-v1` |
| 2025-12 | 1,392 | `table6-eight-column-v1` |
| 2026-01 | 1,702 | `table6-eight-column-v1` |
| 2026-02 | 1,948 | `table6-eight-column-v1` |
| 2026-03 | 1,941 | `table6-eight-column-v1` |
| 2026-04 | 1,981 | `table6-eight-column-v1` |
| 2026-05 | 1,987 | `table6-eight-column-v1` |
| 2026-06 | 1,847 | `table6-eight-column-v1` |
| 2026-07 | 1,775 | `table6-eight-column-v1` |

The authoritative machine-readable current summaries are `data/validation/combined_summary.json` and `data/validation/longitudinal_summary_2023_04_2026_07.json`.

Separate uncoded acceptance outputs:

| Month | Accepted rows | Serial result | Location |
|---|---:|---|---|
| 2024-04 | 1,838 | complete 1-1838 | `data/cleaned_uncoded/projects_2024_04.csv` |
| 2024-05 | 1,812 | source defects at 175, 919/920, 1353, 1785 retained as explicit rejects | `data/cleaned_uncoded/projects_2024_05.csv` |

## Layouts and adapters

Six layouts are accepted:

1. `legacy-detail-ongoing-nine-column-milestones-v1` - April-November 2023 and January-March 2024. Full-population ongoing projects table titled `Detail of ongoing Projects Costing Rs 150 Crore and above.`. It is selected by this verified title and its 9-column positional header signature. Identity (`[project_code]`, agency, and state) is embedded in the project cell. Hierarchical Sector headings are carried forward. `physical_progress`, `start_date`, and `ministry` are structurally absent and remain empty; Milestones Achieved / Total is preserved in raw extraction. Page-boundary wrapped records merge cleanly. Standalone agency headings are filtered cleanly.
2. `legacy-annexure-xviii-six-column-v1` - April-May 2024. It is selected only by the standalone `Annexure XVIII` plus `Details of On-going Projects` heading and its verified six-column positional signature. It has no project code, agency, ministry, Start Date, or physical progress, so its output remains uncoded and separate under `data/cleaned_uncoded/`.
3. `legacy-all-ongoing-nine-column-v1` - June 2024 to October 2024, December 2024, plus January-June 2025. These reports call the project list Table 7 and provide State and Sector separately. They do not provide Ministry or Start Date. Project cells use legacy `N########` or nine-digit-style identifiers. Original/revised/anticipated triplets are parsed without promoting anticipated values to revised fields. June 2024 has narrowly validated code-cell bleed recovery: a code moves only with independent adjacent-row evidence, and final-row recovery requires exactly one unassigned printed code on that page. January and March 2025 require comparison-only whitespace compaction for character-spaced dates and accept the printed `Mon-YY` convention; raw date text remains unchanged. August 2024 features headerless continuation pages (7, 8, and 9 columns) which are normalized internally by carrying forward State and Sector text extracted from margins or prior pages.
4. `legacy-all-ongoing-nine-column-progress-only-v1` - November 2024. This narrowly scoped legacy variant prints `Progress (%)` instead of `Physical Progress (%)` while retaining the full verified positional header structure.
5. `table6-eight-column-approval-only-v1` - July 2025. This report legitimately omits Start Date; `start_date` must remain missing.
6. `table6-eight-column-v1` - August 2025-July 2026. This is the standard accepted eight-column Table 6 layout.

All layouts use `pdfplumber-lines-v1` extraction and the fail-closed `semantic-table6-header-v1` selector. Multiple detected tables on a page are allowed, but exactly one must match the verified positional project-table signature. The enclosing two-column `pdfplumber` detections seen in supported reports are ignored only after a logged semantic rejection; no fixed table index or size heuristic is used.

## June-July 2025 identifier redesign

June 2025 uses 1,595 legacy `N########`/nine-digit identifiers. July 2025 uses 791 six-digit project codes. Exact code overlap is zero, and neither report prints both identifier styles or an explicit OCMS/PMGID bridge.

The completed crosswalk investigation found:

- Explicit source mappings: **0**
- High-confidence analytical proposals: **137**
- Ambiguous June projects: **346** across 408 candidate edges
- Unmatched June projects: **1,112**
- Ambiguous July projects: **347**
- Unmatched July projects: **307**
- Possible one-to-many/split-shaped candidate structures: **41**
- Possible many-to-one/merger-shaped candidate structures: **44**

These relationships are **diagnostic only and are not integrated** into monthly CSVs or `projects_monthly.csv`. No stable ID has been assigned. Do not rewrite source `project_code`, automatically fuzzy-match, or use the proposals for ordinary exact-code longitudinal validation without explicit user authorization.

Detailed evidence and manual comparisons are in `reports/id_crosswalk_june_july_2025.md`. Candidate data are in `data/validation/id_crosswalk_june_july_2025.csv`, `data/validation/id_crosswalk_ambiguous_june_july_2025.csv`, and `data/validation/id_crosswalk_summary_june_july_2025.json`.

## Last completed task

The last completed task was April-June 2023 acceptance. All three full-monthly coded reports use the accepted milestones layout and produced 1,605, 1,681, and 1,643 rows with continuous serials, zero missing IDs, and zero duplicate keys. The rebuilt coded canonical dataset has 60,287 rows, 4,649 unique project identifiers, zero missing IDs, zero duplicate keys, and 107/107 tests passing. See `reports/extraction_acceptance_2023_04_to_2023_06.md`.

## Next planned task

No additional historical month is currently planned. Do not process a new report merely because it appears in `data/raw/`; wait for explicit user scope, snapshot hashes, and run the existing suite first.

## Read these files first

Recommended order for a new agent with no chat history:

1. `AGENTS.md` - durable repository rules and safe commands.
2. `README.md` - short pipeline overview.
3. `reports/extraction_acceptance_2023_04_to_2023_06.md` - April-June 2023 acceptance, milestones layout, agency headings, diagnostics, and hashes.
4. `reports/extraction_acceptance_2023_07_to_2023_09.md` - July-September 2023 acceptance, milestones layout, footer filter, diagnostics, and hashes.
5. `reports/extraction_acceptance_2023_10_to_2023_11.md` - October-November 2023 acceptance and December gap.
6. `reports/source_structure_assessment_2023_10_to_12.md` - late-2023 source classifications and quarterly-source boundary.
7. `reports/extraction_acceptance_2024_01_to_2024_03.md` - 2024 milestones layout acceptance.
8. `reports/extraction_acceptance_2024_04_to_2024_06.md` - uncoded April/May Annexure XVIII boundary and June Table 7 acceptance.
9. `reports/id_crosswalk_june_july_2025.md` - identifier redesign investigation and limitations.
10. `reports/data_dictionary.md` and `schemas/project_month.schema.json` - canonical fields. Note that the JSON schema's six-digit `project_code` regex predates the accepted legacy IDs; production validation in `src/validation/core.py` accepts all source formats.
11. `reports/validation_rules.md` - cross-field warning meanings and QC-only metrics.
12. `reports/manual_validation.md` and `tests/fixtures/manual_verified_records.csv` - source-checked records.
13. `reports/extraction_comparison.md` - why native `pdfplumber` extraction was selected.
14. `reports/longitudinal_warning_diagnostic_2026_01_07.md` and `data/validation/diagnostics/longitudinal_warning_diagnostic_2026_01_07.json` - diagnosis of later warning spikes.
15. `reports/zero_expenditure_positive_progress_diagnostic_2026_06_07.md` - the focused zero-expenditure diagnostic.
16. `src/extraction/pipeline.py`, `src/cleaning/parsers.py`, `src/validation/core.py`, and `src/build_dataset/monthly.py` - production implementation.
17. The relevant `data/validation/manifest_YYYY_MM.json`, `quality_YYYY_MM.json`, `warnings_YYYY_MM.csv`, `rejected_YYYY_MM.csv`, `duplicates_YYYY_MM.csv`, and `qc_metrics_YYYY_MM.csv` before changing any accepted month.

Earlier acceptance reports remain useful for incremental history:

- `reports/extraction_acceptance_2024_10_to_2026_07.md`
- `reports/extraction_acceptance_2025_07_to_2026_07.md`
- `reports/extraction_acceptance_2025_10_to_2026_07.md`
- `reports/longitudinal_warning_diagnostic_2026_01_07.md`

Do not copy their large tables into new reports; link to them and record only new deltas.

## Useful facts for new reports

- Serial continuity is reported per monthly manifest and is an invariant across normal tables.
- A duplicate key in the source data is preserved and written to `duplicates_YYYY_MM.csv`. It is not silently deduplicated.
- A project at 100% progress may still appear in the ongoing table; the validator flags but retains it.
- `qc_metrics` contains derived financial progress and physical-financial gap only for validation. Those fields are deliberately absent from canonical data.
- `src/build_dataset/monthly.py` has an old default month list of January-July 2026. Always pass the complete explicit ordered month list.
- The extraction CLI combines only PDFs processed in that invocation. Running it against a single PDF would replace `projects_monthly.csv` with that invocation's rows; use `process_pdf` directly for single-month acceptance work.
- The repository has an unrelated untracked archive `IRIS_data_2025_2026.7z`. Preserve it and do not stage, modify, or delete it without instruction.

## Known source and implementation quirks

- April-May 2024 use a six-column Annexure XVIII with no project code, agency, ministry, Start Date, or physical progress. Keep them under `data/cleaned_uncoded/`; serial numbers are provenance, not identity.
- Other April/May report sections do print legacy project identifiers (1,899/1,906 distinct identifier strings across those full Part-II PDFs), but Annexure XVIII does not print a relationship to them. Linking would require a separate entity-resolution investigation and is not an explicit source bridge.
- May Annexure XVIII has source/rendering defects at 175, 919/920, 1353, and 1785. They are preserved in raw extraction and rejected with exact reasons; do not reconstruct them or use nearby serials as identity.
- June 2024-June 2025 are legacy Table 7 reports, not the later Table 6 layout.
- June 2024 project-code bleed recovery cannot borrow a neighboring code: adjacent recovery requires serial continuity plus a second independent code, and last-row recovery requires exactly one source-printed page code not already assigned.
- November 2024 uniquely prints `Progress (%)`; its narrow adapter still requires the complete verified legacy header signature.
- January and March embed some date strings with spaces between characters and use `Mon-YY`. Parser-only compaction is covered by regression tests; `*_raw` values remain source faithful.
- Legacy reports omit Start Date and Ministry. Missing values are intentional and must not be inferred.
- Legacy cells can contain original, parenthesized revised, and braced anticipated values. Anticipated is not revised.
- July 2025 is an approval-only layout and legitimately lacks Start Date.
- June-July 2025 has a source identifier redesign, so ordinary exact-code overlap is zero.
- Some pages produce an extra enclosing two-column table with implausible geometry. It is logged and ignored only because it fails the semantic header signature.
- Fourteen accepted non-project rows from October 2025-May 2026 are rejected as `empty_table_row`; these counts are stable. June 2024 has six rejected non-project rows. April and May uncoded extractions have 22 and 32 rejected rows respectively. April, May, June, July, August, September, October, and November 2023 each have exactly 1 rejected `empty_table_row`.
- Project names, agency labels, sector labels, state strings, revised costs, expenditure, progress, and dates can change between reports. Preserve them and emit warnings; do not normalize the source layer.
- May-June and June-July 2026 have large longitudinal warning counts, particularly agency/name label changes. These were diagnosed rather than corrected; read the longitudinal diagnostic report.
- Positive expenditure can become zero and physical progress can decrease in later reports. These are retained source states, not imputation/correction requests.
- A project at 100% progress may still appear in the ongoing table; the validator flags but retains it.
- `qc_metrics` contains derived financial progress and physical-financial gap only for validation. Those fields are deliberately absent from canonical data.
- `src/build_dataset/monthly.py` has an old default month list of January-July 2026. Always pass the complete explicit ordered month list.
- The extraction CLI combines only PDFs processed in that invocation. Running it against a single PDF would replace `projects_monthly.csv` with that invocation's rows; use `process_pdf` directly for single-month acceptance work.
- The repository has an unrelated untracked archive `IRIS_data_2025_2026.7z`. Preserve it and do not stage, modify, or delete it without instruction.

## First health checks

From the repository root:

```powershell
git status --short
python -m unittest discover -v
Get-FileHash data/processed/projects_monthly.csv -Algorithm SHA256
Get-Content -Raw data/validation/combined_summary.json
Get-Content -Raw data/validation/id_crosswalk_summary_june_july_2025.json
```

Expected test result: **107 tests, OK**.

Expected combined SHA-256:

```text
2301524D9A7AF597672716FB6D483FBBCCCBCAA9B9A57E0A154AC7E42F4878FA
```

Before any new extraction, also capture all accepted monthly CSV hashes:

```powershell
Get-FileHash data/cleaned/projects_*.csv -Algorithm SHA256 | Sort-Object Path
```

To rebuild only after every new month has passed individual acceptance, use the complete explicit month list, extending it at the beginning as authorized:

```powershell
python -m src.build_dataset.monthly --months 2023-04 2023-05 2023-06 2023-07 2023-08 2023-09 2023-10 2023-11 2024-01 2024-02 2024-03 2024-06 2024-07 2024-08 2024-09 2024-10 2024-11 2024-12 2025-01 2025-02 2025-03 2025-04 2025-05 2025-06 2025-07 2025-08 2025-09 2025-10 2025-11 2025-12 2026-01 2026-02 2026-03 2026-04 2026-05 2026-06 2026-07
```

Do not run this rebuild merely as a health check because it writes generated data. Tests and hashes are the non-mutating health checks.

## Safety boundary

The current phase prohibits ML, normalization, feature engineering, target creation, imputation, dashboard work, and canonical integration of the diagnostic identifier crosswalk. Preserve exact source values and provenance. Stop on unsupported schemas and wait for an explicit next extraction instruction.
