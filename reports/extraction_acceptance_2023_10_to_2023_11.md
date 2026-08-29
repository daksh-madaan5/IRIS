# October-November 2023 extraction acceptance

## Decision

October and November 2023 are accepted as coded, full-population monthly ongoing-project datasets. Both use the source-verified `legacy-detail-ongoing-nine-column-milestones-v1` layout. December 2023 remains `SUMMARY_ONLY` and contributes no canonical rows. The nearby Q3 quarterly report remains separate and was not extracted or used as a December substitute.

## Monthly acceptance

| Month | Source pages | Rows | Missing IDs | Duplicate IDs | Rejected rows | Warnings | Monthly SHA-256 |
|---|---:|---:|---:|---:|---:|---:|---|
| 2023-10 | 92-215 | 1,788 | 0 | 0 | 1 `empty_table_row` | 76 | `113C29BA846F2138640C86BE32B90B1CD7EC3798874BCF49384D30D8B287624A` |
| 2023-11 | 417-541 | 1,831 | 0 | 0 | 1 `empty_table_row` | 76 | `F4682A5CF8EA54C79D8717D06DC5EEAF4D8E43C10A7DEC9B14E27FABD2330337` |

Both months have continuous serials from 1 through the accepted row count, zero serial gaps or duplicates, 100% parsing of source-present approval dates, cost values, and cumulative expenditure, and complete project code/name/agency/sector/state population. `ministry`, `start_date`, and `physical_progress` are structurally absent. Milestone achieved/total values are preserved only in raw/intermediate extraction, as required.

Source-present completion/revision coverage is:

| Month | Original completion | Revised completion | Revised cost |
|---|---:|---:|---:|
| 2023-10 | 1,746 / 1,788 | 612 / 1,788 | 414 / 1,788 |
| 2023-11 | 1,789 / 1,831 | 618 / 1,831 | 424 / 1,831 |

Each month has 74 `REVISED_COST_BELOW_ORIGINAL` and 2 `EXTREME_EXPENDITURE_COST_MISMATCH` source warnings. Values were retained unchanged. The selector remained semantic and fail closed: normal project pages require the verified title/header structure, while October's final identity-only wrapped continuation is accepted only after the milestones layout has already been established and exactly one explicit project identity is present.

## Manual source verification

Visual comparisons covered first and last records, multiline names, missing revised fields, unusual cost/expenditure values, and multiple page boundaries. Representative verified serials include October 1, 27, 972, 974, and 1788, plus November 1, 12, 1041, 1825, and 1831. October serial 1788 spans pages 214-215 and retains the source code and missing revised values. November serial 1041 preserves the unusual source project-name ending. Milestone text such as October serial 1's `85/87` remains in raw cells while canonical physical progress remains empty.

## Longitudinal diagnostics

October to November 2023 has 1,773 exact-code overlaps, 15 October-only codes, and 58 November-only codes. The transition emits 47 warnings: 40 cumulative-expenditure decreases and 7 state changes; all other existing longitudinal rules emit zero warnings for this pair.

November 2023 to January 2024 is not adjacent because December is unavailable. A boundary-only diagnostic finds 1,786 exact-code overlaps, 45 November-only codes, and 35 January-only codes. It is not written or described as an adjacent-month transition.

## Combined acceptance and regression protection

The explicit 31-month coded rebuild contains 50,187 project-month rows, 4,472 unique source codes, zero missing IDs, and zero duplicate `(project_code, report_month)` keys. The month list contains `2023-10` and `2023-11` and explicitly omits `2023-12`, `2024-04`, and `2024-05`.

- New combined SHA-256: `A0704D145006CB153FB8D5E07F3AF970103A833214BDC753B09655295428206B`
- Previously accepted coded monthly CSVs: 29/29 byte-for-byte unchanged
- Previously accepted uncoded monthly CSVs: 2/2 byte-for-byte unchanged
- Regression suite: 98/98 passing

No normalization, interpolation, surrogate identity, quarterly substitution, crosswalk integration, feature engineering, target creation, or model training was performed.
