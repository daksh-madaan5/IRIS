# PAIMANA January-March 2024 extraction acceptance

## Decision

January, February, and March 2024 Flash Reports are accepted as source-faithful **coded** extractions from the full-population ongoing projects table titled `Detail of ongoing Projects Costing Rs 150 Crore and above.`. They have been integrated into the canonical coded history `projects_monthly.csv`.

All three months are fully coded with legacy `N########` or nine-digit numeric identifiers printed directly within each project cell along with agency and state labels. Hierarchical Sector group headings are faithfully carried forward across rows. `start_date`, `ministry`, and `physical_progress` are structurally absent from this table layout and remain intentionally missing/empty. Printed milestones (`Milestones Achieved / Total`) are preserved in the raw intermediate extraction and are not converted into physical progress.

The combined canonical dataset now covers 29 coded months: `2024-01 -> 2024-03` and `2024-06 -> 2026-07`. April and May 2024 remain separate as uncoded extractions under `data/cleaned_uncoded/`.

## Monthly acceptance

| Month | Source table | Layout | Pages | Accepted rows | Missing codes | Warnings | Rejected rows | Canonical integration |
|---|---|---|---:|---:|---:|---:|---:|---|
| 2024-01 | Detail of ongoing Projects Costing Rs 150 Crore and above | `legacy-detail-ongoing-nine-column-milestones-v1` | 96-220 (125) | 1,821 | 0 | 76 | 1 | Yes |
| 2024-02 | Detail of ongoing Projects Costing Rs 150 Crore and above | `legacy-detail-ongoing-nine-column-milestones-v1` | 104-234 (131) | 1,902 | 0 | 80 | 1 | Yes |
| 2024-03 | Detail of ongoing Projects Costing Rs 150 Crore and above | `legacy-detail-ongoing-nine-column-milestones-v1` | 104-233 (130) | 1,873 | 0 | 85 | 1 | Yes |

Serial numbers are strictly continuous from 1 to N in every month:
- 2024-01: 1 through 1,821 (0 gaps, 0 duplicates)
- 2024-02: 1 through 1,902 (0 gaps, 0 duplicates)
- 2024-03: 1 through 1,873 (0 gaps, 0 duplicates)

Every accepted project row has a valid non-empty project code, project name, agency, state, and sector. Exactly one non-project row in each month was rejected: the trailing `empty_table_row` following the summary `Total` row on the final table page.

## Parsing and source-quality validation

- **January 2024**:
  - Original cost: 1,821 / 1,821 parsed (100%)
  - Revised cost: 418 / 418 reported parsed (100%)
  - Cumulative expenditure: 1,821 / 1,821 parsed (100%)
  - Dates (approval & completion): 4,226 / 4,226 parsed (100%)
  - Warnings (76): 74 `REVISED_COST_BELOW_ORIGINAL`, 2 `EXTREME_EXPENDITURE_COST_MISMATCH`
- **February 2024**:
  - Original cost: 1,902 / 1,902 parsed (100%)
  - Revised cost: 430 / 430 reported parsed (100%)
  - Cumulative expenditure: 1,902 / 1,902 parsed (100%)
  - Dates (approval & completion): 4,388 / 4,388 parsed (100%)
  - Warnings (80): 78 `REVISED_COST_BELOW_ORIGINAL`, 2 `EXTREME_EXPENDITURE_COST_MISMATCH`
- **March 2024**:
  - Original cost: 1,873 / 1,873 parsed (100%)
  - Revised cost: 440 / 440 reported parsed (100%)
  - Cumulative expenditure: 1,873 / 1,873 parsed (100%)
  - Dates (approval & completion): 4,328 / 4,328 parsed (100%)
  - Warnings (85): 83 `REVISED_COST_BELOW_ORIGINAL`, 2 `EXTREME_EXPENDITURE_COST_MISMATCH`

No date or numeric parse failures occurred across any of the three months.

## Semantic selection and table boundary safety

1. **Semantic table identification**: The first page of the full-population table is detected semantically by searching leading text lines for `"detail of ongoing projects costing rs 150"` and verifying the 9-column header signature `LEGACY_DETAIL_MILESTONES_HEADER_SIGNATURE`. Narrower downstream annexures (e.g. state-wise/milestone-delayed lists) starting on later pages fail this header signature and are rejected.
2. **Table termination**: Continuation pages are processed until the final table page containing the explicit `Total` row with empty serial.
3. **Page-boundary wrapped records**: In each month, approximately 94–100 records span across page boundaries (bottom row of page $P$ carries project name and approval/original dates, while row 0 of page $P+1$ carries continuation text with bracketed `[project_code]`, agency, state, and anticipated values). Cells are merged into the logical record with provenance recorded as spanning pages (e.g. `96-97`).

## Manual PDF verification

- **January 2024**:
  - Page 96 (first record): Serial 1, `020100044`, `PROTOTYPE FAST BREEDER REACTOR (BHAVINI, 500 MWE)`, agency `BHAVNI`, state `TAMIL NADU`, sector `ATOMIC ENERGY`, approval `10/2003`, original DoC `09/2007`, original cost `3492.00`, revised cost `5677.00`, expenditure `6209.77`.
  - Page 96-97 (spanning boundary): Serial 12, `N04000074`, `MODERNIZATION OF CHENNAI AIRPORT PHASE II, CHENNAI`, agency `AAI`, state `TAMIL NADU`.
  - Page 220 (last record): Serial 1,821, `N30000004`, `INTERCEPTION AND DIVERSION WITH STP AT RISHIKESH`, agency `UKJalNigam`, state `UTTARAKHA ND`, sector `WATER RESOURCES`. Followed by source `Total` row.
- **February 2024**:
  - Page 104 (first record): Serial 1, `020100044`, Bhavini fast breeder reactor.
  - Page 104-105 (spanning boundary): Serial 12, `N04000102`, Prayagraj airport expansion, agency `AAI`, state `UTTAR PRADESH`.
  - Page 234 (last record): Serial 1,902, `N30000004`, Rishikesh STP.
- **March 2024**:
  - Page 104 (first record): Serial 1, `020100044`, Bhavini fast breeder reactor.
  - Page 104-105 (spanning boundary): Serial 12, `N04000085`, Dehradun airport terminal building, agency `AAI`, state `UTTARAKHAND`.
  - Page 233 (last record): Serial 1,873, `N30000004`, Rishikesh STP.

## Adjacent-month longitudinal continuity

Exact project code overlap confirms strong continuity across adjacent months:
- **Jan 2024 -> Feb 2024**:
  - Projects in both: **1,799** (22 earlier-only, 103 later-only)
  - Expenditure state transitions: 1,706 positive->positive, 14 zero->positive, 79 zero->zero, 0 positive->zero
  - Total longitudinal warnings: **8** (2 revised cost decreased, 4 cumulative expenditure decreased, 2 project name changed, 0 agency/state/sector changed)
- **Feb 2024 -> Mar 2024**:
  - Projects in both: **1,870** (32 earlier-only, 3 later-only)
  - Expenditure state transitions: 1,762 positive->positive, 15 zero->positive, 93 zero->zero, 0 positive->zero
  - Total longitudinal warnings: **21** (2 revised cost decreased, 17 cumulative expenditure decreased, 2 project name changed, 0 agency/state/sector changed)
- **Mar 2024 -> Apr 2024**:
  - March is coded (1,873 projects). April is structurally uncoded in Annexure XVIII (100% missing project code). Per repository rules, no surrogate key or name/serial match is permitted. Identity matching is structurally invalid across this boundary.
- **Mar 2024 -> Jun 2024** (adjacent coded months):
  - Projects in both: **1,753** (120 earlier-only, 57 later-only)
  - Reconciles across the April/May uncoded gap, proving that Jan-Mar 2024 shares the exact same legacy identifier system as June 2024 through June 2025.

## Combined coded dataset metrics

- Range: `2024-01 -> 2024-03` and `2024-06 -> 2026-07` (29 coded months)
- Total rows: **46,568**
- Unique source project codes: **4,412**
- Missing project codes: **0**
- Duplicate `(project_code, report_month)` keys: **0**
- Projects with at least 3 observations: **4,220**
- Projects with at least 6 observations: **3,796**
- Projects with at least 10 observations: **2,385**
- Projects with at least 12 observations: **2,186**
- Projects with at least 16 observations: **1,253**
- Projects with at least 18 observations: **0** (legacy-to-modern identifier boundary at June/July 2025)
- Combined file: `data/processed/projects_monthly.csv`
- Combined SHA-256: `FE115E5FE71CC70552669FC4E0ACC2699B14CFE7545A319EEAEAF577E4DB95C3`

## Regression and hash protection

- All 26 previously accepted monthly CSV SHA-256 hashes (`2024-06` through `2026-07`) remain **100% byte-for-byte identical**.
- Full test suite: **91/91 passing** (`python -m unittest discover -v`).

Accepted Q1 2024 monthly CSV SHA-256 hashes:
- `projects_2024_01.csv`: `31EF0C28DC14579A552C0A1FEB5E9551152D178654B3858880DBDA54384B51A4`
- `projects_2024_02.csv`: `2539B81042F40DE9BB08C8896D150D30949B37D8A869CFE8561BFFFA4BDBFF3D`
- `projects_2024_03.csv`: `7355DE5E4F916261F8B2F4EDB2E39EE2E746A545B7D58EBF298F55F030895DDD`
