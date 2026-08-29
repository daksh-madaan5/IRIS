# April-June 2023 extraction acceptance

## Decision

April, May, and June 2023 are accepted as coded, full-population monthly ongoing-project datasets. All three use the source-verified `legacy-detail-ongoing-nine-column-milestones-v1` layout. The December 2023 gap remains preserved. April and May 2024 remain separate uncoded extractions.

## Monthly acceptance

| Month | Source pages | Rows | Missing IDs | Duplicate IDs | Rejected rows | Warnings | Monthly SHA-256 |
|---|---:|---:|---:|---:|---:|---:|---|
| 2023-04 | 114-218 | 1,605 | 0 | 0 | 1 `empty_table_row` | 72 | `DB3A33FD9B476AAF4AA5EA46AC420EAE3DB562909FF5CCCC3AD020632367CF94` |
| 2023-05 | 106-218 | 1,681 | 0 | 0 | 1 `empty_table_row` | 72 | `F96E7ABC083D52613C3611AFDDED022CDF70BC479790714EF06022658758995A` |
| 2023-06 | 107-217 | 1,643 | 0 | 0 | 1 `empty_table_row` | 81 | `A2CDCEFC1BA837BA4C35E21E4416E702F96DEB13C2B3509F9F22086136AA8E7B` |

All three months feature continuous serial numbers from 1 through the accepted row count, zero serial gaps or duplicates, 100% parsing of source-present approval dates, original costs, revised costs, and cumulative expenditure. `ministry`, `start_date`, and `physical_progress` are structurally absent and remain empty. Milestone achieved/total text is preserved in raw/intermediate extraction.

Two genuinely source-missing state values exist in June 2023 for projects `N42000009` (agency `CPWD`) and `N28000148` (agency `PATNA METRO`); they legitimately lack state text in the source PDF and remain empty as reported.

Source-present completion and revision coverage:

| Month | Original completion | Revised completion | Revised cost |
|---|---:|---:|---:|
| 2023-04 | 1,545 / 1,605 | 501 / 1,605 | 345 / 1,605 |
| 2023-05 | 1,621 / 1,681 | 516 / 1,681 | 361 / 1,681 |
| 2023-06 | 1,595 / 1,643 | 550 / 1,643 | 399 / 1,643 |

Warning breakdowns:
- 2023-04: 70 `REVISED_COST_BELOW_ORIGINAL`, 2 `EXTREME_EXPENDITURE_COST_MISMATCH` (`N18000335`, `220100205`). Total: 72 across 70 rows.
- 2023-05: 71 `REVISED_COST_BELOW_ORIGINAL`, 1 `EXTREME_EXPENDITURE_COST_MISMATCH` (`220100205`). Total: 72 across 71 rows.
- 2023-06: 79 `REVISED_COST_BELOW_ORIGINAL`, 2 `EXTREME_EXPENDITURE_COST_MISMATCH` (`N18000335`, `220100205`). Total: 81 across 79 rows.

## Source artifacts and fixes

- **Agency group headings:** April 2023 contains 107 standalone agency headings (similar to October 2023), May contains 7, and June contains 6. These are filtered as structural non-project material.
- **Rejected non-project rows:** Each month rejected exactly 1 structural empty table row (April p.218 row 11, May p.218 row 11, June p.217 row 11).

## Manual source verification

Representative visual checks verified:
- First projects: `020100044` (serial 1 across all 3 months).
- Last projects: `N30000004` (serial 1605 in April, 1681 in May, 1643 in June).
- Multi-page boundary crossings: April `N04000079` across pages 114-115; May `N04000079` across pages 106-107; June `N04000078` across pages 107-108.
- Raw milestone cells: April serial 1 raw milestone `83/87` preserved in intermediate JSONL with canonical `physical_progress` empty.
- Source-missing states: June `N42000009` and `N28000148` confirmed to omit state text in PDF; kept empty.

## Longitudinal diagnostics

### April 2023 → May 2023
- Both months: 1,594 projects
- April only: 11 projects
- May only: 87 projects
- Warnings (172 total):
  - `cumulative_expenditure_decreased`: 138
  - `positive_to_zero_expenditure`: 29
  - `state_changed`: 5
- Numeric transitions:
  - Cumulative expenditure: 1,016 increased, 138 decreased, 440 unchanged
  - Revised cost: 3 increased, 0 decreased, 333 unchanged, 1,258 missing
- Expenditure states: 1,456 positive→positive, 29 positive→zero, 38 zero→positive, 71 zero→zero

### May 2023 → June 2023
- Both months: 1,626 projects
- May only: 55 projects
- June only: 17 projects
- Warnings (41 total):
  - `cumulative_expenditure_decreased`: 27
  - `state_changed`: 9
  - `revised_cost_decreased`: 3
  - `agency_changed`: 2
- Numeric transitions:
  - Cumulative expenditure: 888 increased, 27 decreased, 711 unchanged
  - Revised cost: 10 increased, 3 decreased, 337 unchanged, 1,276 missing
- Expenditure states: 1,515 positive→positive, 48 zero→positive, 63 zero→zero

### June 2023 → July 2023
- Both months: 1,634 projects
- June only: 9 projects
- July only: 12 projects
- Warnings (37 total):
  - `cumulative_expenditure_decreased`: 23
  - `state_changed`: 6
  - `revised_cost_decreased`: 3
  - `agency_changed`: 3
  - `positive_to_zero_expenditure`: 2
- Numeric transitions:
  - Cumulative expenditure: 905 increased, 23 decreased, 706 unchanged
  - Revised cost: 3 increased, 3 decreased, 387 unchanged, 1,241 missing
- Expenditure states: 1,563 positive→positive, 2 positive→zero, 9 zero→positive, 60 zero→zero

## Combined acceptance and regression protection

The explicit 37-month coded rebuild contains 60,287 project-month rows, 4,649 unique source project identifiers, zero missing project codes, and zero duplicate `(project_code, report_month)` keys.

- New combined SHA-256: `2301524D9A7AF597672716FB6D483FBBCCCBCAA9B9A57E0A154AC7E42F4878FA`
- All 34 previously accepted coded monthly CSVs: 34/34 byte-for-byte unchanged
- All 2 previously accepted uncoded monthly CSVs: 2/2 byte-for-byte unchanged
- Regression suite: 107/107 passing
