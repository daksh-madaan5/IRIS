# July-September 2023 extraction acceptance

## Decision

July, August, and September 2023 are accepted as coded, full-population monthly ongoing-project datasets. All three use the source-verified `legacy-detail-ongoing-nine-column-milestones-v1` layout. The December 2023 gap remains preserved. April and May 2024 remain separate uncoded extractions.

## Monthly acceptance

| Month | Source pages | Rows | Missing IDs | Duplicate IDs | Rejected rows | Warnings | Monthly SHA-256 |
|---|---:|---:|---:|---:|---:|---:|---|
| 2023-07 | 108-218 | 1,646 | 0 | 0 | 1 `empty_table_row` | 84 | `51E7D808DEDFC16B1D0A91E4F71B08D443F2B2D5005D3262D6D9E4410DB71190` |
| 2023-08 | 118-237 | 1,762 | 0 | 0 | 1 `empty_table_row` | 81 | `AD64956F75188247FFA83F2E17E647B5A197C23049EECE007AE231C408A6B3A8` |
| 2023-09 | 89-207 | 1,763 | 0 | 0 | 1 `empty_table_row` | 74 | `B24EF26AFBB6C3D272C054380FD2830D1A9E38260FB0EE067F44D05B546A3B2E` |

All three months feature continuous serial numbers from 1 through the accepted row count, zero serial gaps or duplicates, 100% parsing of source-present approval dates, original costs, revised costs, and cumulative expenditure. `ministry`, `start_date`, and `physical_progress` are structurally absent and remain empty. Milestone achieved/total text is preserved in raw/intermediate extraction.

One genuinely source-missing state value exists in July 2023 for project `N28000147` (agency `CPWD FOR`); it remains empty as reported.

Source-present completion and revision coverage:

| Month | Original completion | Revised completion | Revised cost |
|---|---:|---:|---:|
| 2023-07 | 1,598 / 1,646 | 569 / 1,646 | 407 / 1,646 |
| 2023-08 | 1,714 / 1,762 | 586 / 1,762 | 425 / 1,762 |
| 2023-09 | 1,716 / 1,763 | 615 / 1,763 | 406 / 1,763 |

Warning breakdowns:
- 2023-07: 82 `REVISED_COST_BELOW_ORIGINAL`, 2 `EXTREME_EXPENDITURE_COST_MISMATCH` (`N18000335`, `220100205`). Total: 84 across 82 rows.
- 2023-08: 79 `REVISED_COST_BELOW_ORIGINAL`, 2 `EXTREME_EXPENDITURE_COST_MISMATCH` (`N18000335`, `220100205`). Total: 81 across 79 rows.
- 2023-09: 72 `REVISED_COST_BELOW_ORIGINAL`, 2 `EXTREME_EXPENDITURE_COST_MISMATCH` (`N18000335`, `220100205`). Total: 74 across 72 rows.

## Source artifacts and fixes

- **July 2023 footer overprint exclusion:** In July 2023 page 108 (and similar bottom rows), a centered footer page number overprinted the bottom table cell, appending digits to `original_completion_date_raw`. Scoped char filtering in `_without_centered_footer_page_number` excluded the footer artifact without modifying source table text. Regression test `test_july_2023_footer_page_number_does_not_corrupt_bottom_date` verifies serial 13 has `original_completion_date_raw = 9/2021`.
- **Rejected non-project rows:** Each month rejected exactly 1 structural empty table row (July p.218 row 12, August p.237 row 11, September p.207 row 8).

## Manual source verification

Representative visual checks verified:
- First projects: `020100044` (serial 1 across all 3 months).
- Last projects: `N30000004` (serials 1646, 1762, 1763 respectively).
- Multi-page boundary crossings: July `N04000078` across pages 108-109; August `N04000079` across pages 118-119; September `N04000077` across pages 89-90.
- Raw milestone cells: July serial 1 raw milestone `83/87` preserved in intermediate JSONL with canonical `physical_progress` empty.
- Source-missing state: July serial `N28000147` confirmed to omit state text in PDF; kept empty.

## Longitudinal diagnostics

### July 2023 → August 2023
- Both months: 1,630 projects
- July only: 16 projects
- August only: 132 projects
- Warnings (19 total):
  - `cumulative_expenditure_decreased`: 12
  - `state_changed`: 6
  - `agency_changed`: 1
- Numeric transitions:
  - Cumulative expenditure: 882 increased, 12 decreased, 736 unchanged
  - Revised cost: 6 increased, 0 decreased, 392 unchanged, 1,232 missing
- Expenditure states: 1,566 positive→positive, 7 zero→positive, 57 zero→zero

### August 2023 → September 2023
- Both months: 1,708 projects
- August only: 54 projects
- September only: 55 projects
- Warnings (32 total):
  - `cumulative_expenditure_decreased`: 11
  - `state_changed`: 8
  - `positive_to_zero_expenditure`: 7
  - `revised_cost_decreased`: 4
  - `project_name_changed`: 2
- Numeric transitions:
  - Cumulative expenditure: 936 increased, 11 decreased, 761 unchanged
  - Revised cost: 5 increased, 4 decreased, 380 unchanged, 1,319 missing
- Expenditure states: 1,567 positive→positive, 7 positive→zero, 30 zero→positive, 104 zero→zero

### September 2023 → October 2023
- Both months: 1,728 projects
- September only: 35 projects
- October only: 60 projects
- Warnings (36 total):
  - `cumulative_expenditure_decreased`: 18
  - `project_name_changed`: 10
  - `state_changed`: 8
- Numeric transitions:
  - Cumulative expenditure: 953 increased, 18 decreased, 757 unchanged
  - Revised cost: 2 increased, 0 decreased, 400 unchanged, 1,326 missing
- Expenditure states: 1,595 positive→positive, 29 zero→positive, 104 zero→zero

## Combined acceptance and regression protection

The explicit 34-month coded rebuild contains 55,358 project-month rows, 4,574 unique source project identifiers, zero missing project codes, and zero duplicate `(project_code, report_month)` keys.

- New combined SHA-256: `9733A05BE6DC63340E713128F7BE3EE1FF77B3F2661287DBAF0580A715F9AD67`
- All 31 previously accepted coded monthly CSVs: 31/31 byte-for-byte unchanged
- All 2 previously accepted uncoded monthly CSVs: 2/2 byte-for-byte unchanged
- Regression suite: 103/103 passing
