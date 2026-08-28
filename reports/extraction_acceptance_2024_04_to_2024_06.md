# PAIMANA April-June 2024 extraction acceptance

## Decision

April and May 2024 are accepted as source-faithful **uncoded** extractions and remain separate under `data/cleaned_uncoded/`. Their Annexure XVIII source table has no project identifier, agency, ministry, Start Date, or physical progress. Serial numbers were retained only as provenance and were not converted into identity.

June 2024 is accepted as a coded Table 7 extraction and has been integrated into the canonical coded history. The combined canonical dataset now covers `2024-06 -> 2026-07`. No normalization, crosswalk, feature, target, or model was created.

## Monthly acceptance

| Month | Source table | Layout | Pages | Accepted rows | Missing codes | Warnings | Rejected rows | Canonical integration |
|---|---|---|---:|---:|---:|---:|---:|---|
| 2024-04 | Annexure XVIII: Details of On-going Projects | `legacy-annexure-xviii-six-column-v1` | 462-571 | 1,838 | 1,838 structural | 81 | 22 | No |
| 2024-05 | Annexure XVIII: Details of Ongoing Projects | `legacy-annexure-xviii-six-column-v1` | 462-570 | 1,812 | 1,812 structural | 93 | 32 | No |
| 2024-06 | Table 7: Ongoing Projects | `legacy-all-ongoing-nine-column-v1` | 35-304 | 1,810 | 0 | 357 | 6 | Yes |

April serials are continuous from 1 through 1,838. June serials are continuous from 1 through 1,810, with 1,810 unique source project codes and no duplicate codes. May's accepted serials span 1 through 1,817 with five source-defect gaps: 175, 919, 920, 1353, and 1785.

State and Sector hierarchy propagation is complete without inventing labels: all accepted rows in all three months retain a non-missing source State and Sector. April and May contain 33 exact State strings and 21 exact Sector strings; June contains 33 and 20 respectively.

Rejected-row reasons:

| Month | Reason | Count |
|---|---|---:|
| April | `unclassified_non_project_row` | 21 |
| April | `empty_table_row` | 1 |
| May | `unclassified_non_project_row` | 26 |
| May | `empty_table_row` | 2 |
| May | `source_omitted_serial_project_row` | 2 |
| May | `multiple_source_projects_merged_in_one_detected_row` | 1 |
| May | `serial_project_cell_bleed` | 1 |
| June | `empty_table_row` | 5 |
| June | `unclassified_non_project_row` | 1 |

May 175 and 1353 have data in the date/cost/expenditure cells but no printed serial or project name. The source rendering merges 919/920 into one detected row, while 1785 bleeds project text into the serial cell. Raw rows and exact reasons are retained; none was reconstructed from context.

## Parsing and source-quality validation

April parsed 100% of 1,838 reported original costs, 426 revised costs, 1,838 cumulative-expenditure values, and 4,251 dates. Physical progress is structurally absent. Its 81 warnings comprise 80 `REVISED_COST_BELOW_ORIGINAL` and one `EXTREME_EXPENDITURE_COST_MISMATCH`.

May parsed 1,806/1,809 reported original costs, 426/429 revised costs, 1,803/1,803 expenditures, and 4,178/4,185 dates. The six numeric and seven date parse warnings retain the exact unusual source strings. Its other warnings comprise 78 `REVISED_COST_BELOW_ORIGINAL` and two `EXTREME_EXPENDITURE_COST_MISMATCH`.

June parsed 100% of 1,810 original costs, 444 revised costs, 1,810 expenditures, 1,808 reported progress values, and 4,237 dates. Its 357 warnings are source-quality signals: 103 `EXPENDITURE_WITH_ZERO_PROGRESS`, 139 `FULL_PROGRESS_STILL_ONGOING`, four `EXTREME_EXPENDITURE_COST_MISMATCH`, 84 `REVISED_COST_BELOW_ORIGINAL`, and 27 `ZERO_EXPENDITURE_POSITIVE_PROGRESS`.

## Semantic selection and code-bleed safety

The Annexure adapter starts only when the report contains standalone semantic heading lines equivalent to `Annexure XVIII` and `Details of On-going Projects`, followed by exactly one candidate matching the six-column Annexure signature. A contents-page mention does not qualify. This does not broaden the Table 6/Table 7 selectors.

June code-cell bleed recovery is conservative. An apparent leading code is moved to the immediately preceding serial only when adjacent serial continuity and another independent code establish the shift. A final row receives a code only when exactly one source-printed page code remains unassigned. The former unsafe fallback to the last code on a page was removed. Page 45 was visually checked: serials 66, 67, 68, 69, 70, and 71 map respectively to `N24002124`, `N24002125`, `N24002126`, `N24002139`, `N24002140`, and `N24002141`; serial 72 on the following page is `N24002142`.

## Manual PDF verification

- April page 462: serial 1, multiline Port Blair terminal project, approval `10/2013`, original/revised cost `417.23`/`707.73`, expenditure `697.52`, State `ANDAMAN AND NICOBAR ISLANDS`, Sector `Civil Aviation`.
- April page 571: serial 1,838, Barrackpore sewerage project, cost `272.32`/`341.68`, expenditure `311.62`; no project code or physical-progress column is printed.
- May pages 472, 516, 541, and 568: visually confirmed the four malformed regions covering 175, 919/920, 1353, and 1785; none was silently resolved.
- May page 570: final printed serial 1,817, Barrackpore sewerage project, expenditure `302.82`.
- June page 35: serial 1, `N04000073`, Port Blair terminal project, agency `AAI`, cost `417.23`/`707.73`, expenditure `697.52`, progress `100`.
- June page 45: visually confirmed the multi-row bleed chain and the unique final-row code described above.
- June page 304: serial 1,810, `N30000049`, Bally STP project, agency `KMDA`, original cost `164.93`, expenditure `45.45`, progress `100`.

## Identifier presence outside Annexure XVIII

The April and May Part-II PDFs do contain legacy identifiers in other tables and annexures before page 449: 1,899 distinct identifier strings in April and 1,906 in May. However, Annexure XVIII itself contains no code column, no embedded code, and no explicit relationship to those other occurrences. The Part-I synopsis PDFs also contain no identifier labels or legacy code patterns.

Therefore the reports do **not** provide an explicit, row-level source bridge from the uncoded Annexure XVIII records to June. Linking names/attributes to identifiers printed in other sections would be a separate entity-resolution investigation, not extraction, and is not integrated here.

## Combined coded dataset and June-July transition

- Range: `2024-06 -> 2026-07` (26 months)
- Rows: 40,972
- Unique source codes: 4,238
- Missing IDs: 0
- Duplicate `(project_code, report_month)` keys: 0
- Projects with at least 3/6/10/12 observations: 4,052 / 3,691 / 2,301 / 2,090
- Combined SHA-256: `D4641D225009F8890DD144DC165A42597F9CE28777A462FBD60D8B34AB7B5D40`

June to July 2024 has 1,789 projects in both months, 21 June-only projects, and four July-only projects. Longitudinal warnings total 619: revised cost decreased 1, cumulative expenditure decreased 26, physical progress decreased 44, positive expenditure to zero 3, project name changed 467, agency changed 0, ministry changed 0, sector changed 20, and state changed 58. These are retained diagnostics, not corrections.

## Regression and hash protection

The full suite passes: **86 tests, OK**. Artifact-tool verification confirmed the header, final boundary, absence of trailing records, and zero spreadsheet error tokens for both uncoded CSVs, June's coded CSV, and the combined CSV.

All 25 previously accepted monthly CSV hashes for `2024-07 -> 2026-07` remain unchanged. New file hashes are:

- April uncoded: `BDE92BE33D2B41E494ECFF9BC7BAB2F961146B9CD7DD8317AF3C4D55FA8F6389`
- May uncoded: `AB485E959E000F5605A821DFABDCAC596A6D409441213B6674506C58F934951E`
- June coded: `4ACE40FB0D5F8DED6923A42E385A5BDEFB2C45349AFF8A016958F27D0A811DA9`

Detailed machine-readable metrics remain in the monthly manifests and `data/validation/longitudinal_summary_2024_06_2026_07.json`.
