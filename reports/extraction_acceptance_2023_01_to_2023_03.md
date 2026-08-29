# January-March 2023 extraction acceptance

## Decision

January, February, and March 2023 are accepted as coded, full-population monthly ongoing-project datasets. All three use the source-verified `legacy-detail-ongoing-nine-column-milestones-v1` layout. The December 2023 gap remains preserved. April and May 2024 remain separate uncoded extractions.

## Monthly acceptance

| Month | Source pages | Rows | Missing IDs | Duplicate IDs | Rejected rows | Warnings | Monthly SHA-256 |
|---|---:|---:|---:|---:|---:|---:|---|
| 2023-01 | 133-227 | 1,454 | 0 | 0 | 1 `empty_table_row` | 65 | `ADA1498C5771DBE58770732BB6E8410D101C1ACA70490CD7226640168FC3FC79` |
| 2023-02 | 125-217 | 1,418 | 0 | 0 | 1 `empty_table_row` | 62 | `9C191739FC97AC0948BB54D120545423650803E9E2F2B4BE6C11C7B97BD86398` |
| 2023-03 | 133-227 | 1,449 | 0 | 0 | 1 `empty_table_row` | 63 | `AC1CCA529AE5C78F934EE6DA3C60A66E9E8ADCD77A71500B3E6F512EEF7FAC65` |

All three months feature continuous serial numbers from 1 through the accepted row count, zero serial gaps or duplicates, 100% parsing of source-present approval dates, original costs, revised costs, and cumulative expenditure. `ministry`, `start_date`, and `physical_progress` are structurally absent and remain empty. Milestone achieved/total text is preserved in raw/intermediate extraction.

One genuinely source-missing state value exists in February and March 2023 for project `N28000140` (`CPWD`); it legitimately lacks state text in the printed source PDF cells and remains empty as reported.

Source-present completion and revision coverage:

| Month | Original completion | Revised completion | Revised cost |
|---|---:|---:|---:|
| 2023-01 | 1,388 / 1,454 | 439 / 1,454 | 302 / 1,454 |
| 2023-02 | 1,353 / 1,418 | 448 / 1,418 | 294 / 1,418 |
| 2023-03 | 1,387 / 1,449 | 466 / 1,449 | 301 / 1,449 |

Warning breakdowns:
- 2023-01: 63 `REVISED_COST_BELOW_ORIGINAL`, 2 `EXTREME_EXPENDITURE_COST_MISMATCH` (`N18000335`, `220100205`). Total: 65 across 63 rows.
- 2023-02: 60 `REVISED_COST_BELOW_ORIGINAL`, 2 `EXTREME_EXPENDITURE_COST_MISMATCH` (`N18000335`, `220100205`). Total: 62 across 60 rows.
- 2023-03: 61 `REVISED_COST_BELOW_ORIGINAL`, 2 `EXTREME_EXPENDITURE_COST_MISMATCH` (`N18000335`, `220100205`). Total: 63 across 61 rows.

## Source artifacts and fixes

- **Agency group headings:** January, February, and March 2023 each contain 3 standalone agency headings filtered as non-project material.
- **Rejected non-project rows:** Each month rejected exactly 1 structural empty table row on its final page (Jan p.227 row 10, Feb p.217 row 10, Mar p.227 row 10).

## Manual source verification

Representative visual checks verified:
- First projects: `020100044` (serial 1 across all 3 months).
- Last projects: `N30000004` (serial 1454 in January, 1418 in February, 1449 in March).
- Multi-page boundary crossings: January `N04000081` across pages 133-134; February `N04000082` across pages 126-127; March `N04000082` across pages 134-135.
- Raw milestone cells: January serial 1 raw milestone `83/87` preserved in intermediate JSONL with canonical `physical_progress` empty.
- Source-missing states: February and March `N28000140` confirmed to omit state text in PDF; kept empty.

## Longitudinal diagnostics

### January 2023 → February 2023
- Both months: 1,406 projects
- January only: 48 projects
- February only: 12 projects
- Warnings (29 total):
  - `cumulative_expenditure_decreased`: 21
  - `agency_changed`: 3
  - `revised_cost_decreased`: 2
  - `state_changed`: 2
  - `project_name_changed`: 1
- Numeric transitions:
  - Cumulative expenditure: 783 increased, 21 decreased, 602 unchanged
  - Revised cost: 3 increased, 2 decreased, 274 unchanged, 1,127 missing
- Expenditure states: 1,351 positive→positive, 9 zero→positive, 46 zero→zero

### February 2023 → March 2023
- Both months: 1,398 projects
- February only: 20 projects
- March only: 51 projects
- Warnings (16 total):
  - `cumulative_expenditure_decreased`: 14
  - `revised_cost_decreased`: 2
- Numeric transitions:
  - Cumulative expenditure: 833 increased, 14 decreased, 551 unchanged
  - Revised cost: 2 increased, 2 decreased, 284 unchanged, 1,110 missing
- Expenditure states: 1,346 positive→positive, 12 zero→positive, 40 zero→zero

### March 2023 → April 2023
- Both months: 1,428 projects
- March only: 21 projects
- April only: 177 projects
- Warnings (334 total):
  - `cumulative_expenditure_decreased`: 269
  - `state_changed`: 52
  - `positive_to_zero_expenditure`: 8
  - `revised_cost_decreased`: 4
  - `agency_changed`: 1
- Numeric transitions:
  - Cumulative expenditure: 590 increased, 269 decreased, 569 unchanged
  - Revised cost: 5 increased, 4 decreased, 287 unchanged, 1,132 missing
- Expenditure states: 1,344 positive→positive, 8 positive→zero, 36 zero→positive, 40 zero→zero

## Combined acceptance and regression protection

The explicit 40-month coded rebuild contains 64,608 project-month rows, 4,738 unique source project identifiers, zero missing project codes, and zero duplicate `(project_code, report_month)` keys.

- New combined SHA-256: `9512A9881E17DFDED6E182D87A8DFB1C4EDBD36C0D9B8A7DA9FD1ABB7E002FBF`
- All 37 previously accepted coded monthly CSVs: 37/37 byte-for-byte unchanged
- All 2 previously accepted uncoded monthly CSVs: 2/2 byte-for-byte unchanged
- Regression suite: 111/111 passing
