# Completed Projects Extraction Acceptance Report

## 1. Executive Summary

This report documents the completed extraction and validation for **Completed Projects** across 36 accepted Flash Report monthly datasets spanning **April 2023 through July 2026** (Batch 1: April–June 2023 [+84 rows], Batch 2: July–September 2023 [+70 rows], Batch 3: October–December 2023 [+40 rows], Batch 4: January–March 2024 [+65 rows], Phase 2: 10 historical reports from FY 2024-25, plus 14 reports from Phase 1).

The extraction strictly enforces source-faithfulness, positional header matching, fail-closed candidate selection, additive dataset extension, and exact source-issued project code preservation. All previously accepted Completed Projects records (811 rows) remain 100% byte-identical, and existing monthly extraction pipelines, schemas, validation outputs, and canonical monthly datasets remain completely untouched and byte-identical.

- **Output dataset**: `data/processed/projects_completed.csv`
- **Output SHA-256**: `89BEA84FD68A22E327090C1E4E4533F5BCD745ADCA61EB4E66172EE9023BB910`
- **Total completed project records**: **876** (811 baseline + 65 Batch 4)
- **Unique completed projects**: **876** (zero duplicate keys)
- **Missing project codes**: **0**
- **Duplicate `(project_code, report_month)` keys**: **0**
- **Serial continuity**: **100% continuous** within each report month (serials 1..20 for April 2023, 21..30 for May 2023, 31..84 for June 2023, 85..91 for July 2023, 92..106 for August 2023, 107..154 for September 2023, 155..183 for October 2023, 184..194 for November 2023, 217..229 for January 2024, 230..249 for February 2024, 250..281 for March 2024, and 1..N for subsequent months)
- **Parse rate for present values**: **100%** across dates and numerics
- **Dedicated test suite**: **Passing** (`tests/test_completed_projects.py`: 15/15 tests OK)
- **Combined monthly dataset integrity**: `data/processed/projects_monthly.csv` and all 16 monthly CSVs are **byte-for-byte identical** to pre-implementation baselines.

---

## 2. Reports Processed & Completed Projects Inventory

| Report Month | PDF Filename | Table Presence & Status | Pages Used | Layout Variant | Project Rows Extracted |
|---|---|---|---|---|---:|
| **2023-04** | `2023/FR_APril_2023.pdf` | **Yes** (Table 2) | Pages 24–25 (serials 1–20) | `table2-completed-legacy-five-column-v1` | 20 |
| **2023-05** | `2023/FR_may_2023.pdf` | **Yes** (Table 2) | Pages 25–27 (serials 21–30) | `table2-completed-legacy-five-column-v1` | 10 |
| **2023-06** | `2023/FR_june_2023.pdf` | **Yes** (Table 2) | Pages 25–29 (serials 31–84) | `table2-completed-legacy-five-column-v1` | 54 |
| **2023-07** | `2023/FR_july1_2023.pdf` | **Yes** (Table 2) | Pages 25–30 (serials 85–91 on pp. 29–30) | `table2-completed-legacy-five-column-v1` | 7 |
| **2023-08** | `2023/FR_august_2023.pdf` | **Yes** (Table 2) | Pages 26–32 (serials 92–106 on pp. 31–32) | `table2-completed-legacy-five-column-v1` | 15 |
| **2023-09** | `2023/FR_sept_2023.pdf` | **Yes** (Table 2) | Pages 24–33 (serials 107–154 on pp. 30–33) | `table2-completed-legacy-five-column-v1` | 48 |
| **2023-10** | `2023/FR_oct_2023.pdf` | **Yes** (Table 2) | Pages 24–35 (serials 155–183 on pp. 33–34; p. 35 blank continuation) | `table2-completed-legacy-five-column-v1` | 29 |
| **2023-11** | `2023/FR_nov_2023.pdf` | **Yes** (Table 2) | Pages 25–36 (serials 184–194 on p. 36) | `table2-completed-legacy-five-column-v1` | 11 |
| **2023-12** | `2023/FR_dec_2023.pdf` | **Absent** (Executive synopsis only) | N/A | Absent | 0 |
| **2024-01** | `2023/FR_jan_2024.pdf` | **Yes** (Table 2) | Pages 25–39 (serials 217–229 on p. 38) | `table2-completed-legacy-five-column-v1` | 13 |
| **2024-02** | `2023/FR_feb_2024.pdf` | **Yes** (Table 2) | Pages 26–41 (serials 230–249 on pp. 40–41) | `table2-completed-legacy-five-column-v1` | 20 |
| **2024-03** | `2023/FR_mar_2024.pdf` | **Yes** (Table 2) | Pages 23–40 (serials 250–281 on pp. 38–40) | `table2-completed-legacy-five-column-v1` | 32 |
| **2024-04** | `April_Part-II_List_of_tables.pdf` | **DEFERRED** (Completed Projects in Table 2, 5-col) | N/A | Table 2 (Future Task) | 0 |
| **2024-05** | `May_Part-2.pdf` | **DEFERRED** (Completed Projects in Table 2, 5-col) | N/A | Table 2 (Future Task) | 0 |
| **2024-06** | `2024/June.pdf` | **Yes** (Table 3) | Pages 7–9 | `table3-completed-legacy-six-column-v1` | 18 |
| **2024-07** | `2024/July_Part-II.pdf` | **Yes** (Table 3) | Pages 7–9 | `table3-completed-legacy-six-column-v1` | 21 |
| **2024-08** | `2024/August_Part-2(List_of_tables).pdf` | **Yes** (Table 3) | Pages 8–10 | `table3-completed-legacy-six-column-v1` | 16 |
| **2024-09** | `2024/September_Part-2(List_of_tables).pdf` | **Yes** (Table 3) | Pages 8–9 | `table3-completed-legacy-six-column-v1` | 13 |
| **2024-10** | `2024/October.pdf` | **Yes** (Table 3) | Pages 12–18 | `table3-completed-legacy-six-column-v1` | 62 |
| **2024-11** | `2024/November.pdf` | **Yes** (Table 3) | Pages 12–13 | `table3-completed-legacy-six-column-v1` | 12 |
| **2024-12** | `2024/December.pdf` | **Yes** (Table 3) | Pages 11–13 | `table3-completed-legacy-six-column-v1` | 22 |
| **2025-01** | `2025/FRJanuary2025.pdf` | **Yes** (Table 3) | Pages 11–13 | `table3-completed-legacy-six-column-v1` | 20 |
| **2025-02** | `2025/FRFebruary2025.pdf` | **Yes** (Table 3) | Pages 12–16 | `table3-completed-legacy-six-column-v1` | 41 |
| **2025-03** | `2025/FRMarch2025.pdf` | **Yes** (Table 3) | Pages 11–12 | `table3-completed-legacy-six-column-v1` | 17 |
| **2025-04** | `2025/FR_April_2025.pdf` | **Yes** (Table 3) | Pages 11–14 | `table3-completed-legacy-six-column-v1` | 34 |
| **2025-05** | `2025/FR_May2025.pdf` | **Yes** (Table 3) | Pages 11–15 | `table3-completed-legacy-six-column-v1` | 40 |
| **2025-06** | `2025/FR_JUNE_2025.pdf` | **Yes** (Table 3) | Pages 11–15 | `table3-completed-legacy-six-column-v1` | 42 |
| **2025-07** | `2025/FlashReport_July_2025.pdf` | **Absent** (Table 3 is *North-East Ongoing*) | N/A | Absent | 0 |
| **2025-08** | `2025/FlashReport_August_2025.pdf` | **Absent** (Table 3 is *North-East Ongoing*) | N/A | Absent | 0 |
| **2025-09** | `2025/FlashReport_September_2025.pdf` | **Yes** (Table 3) | Pages 32–33 (p. 33 data) | `table3-completed-seven-column-v1` | 6 |
| **2025-10** | `2025/FlashReport_October_2025.pdf` | **Yes** (Table 3) | Pages 32–33 (p. 33 data) | `table3-completed-seven-column-v1` | 6 |
| **2025-11** | `2025/FlashReport_November_2025.pdf` | **Yes** (Table 3) | Pages 32–33 (p. 33 data) | `table3-completed-seven-column-v1` | 13 |
| **2025-12** | `2025/FlashReport_December_2025.pdf` | **Yes** (Table 3) | Pages 34–36 (pp. 35–36 data) | `table3-completed-seven-column-v1` | 17 |
| **2026-01** | `FlashReport_January_2026.pdf` | **Yes** (Table 3) | Pages 35–36 (p. 36 data) | `table3-completed-seven-column-v1` | 3 |
| **2026-02** | `FlashReport_February_2026.pdf` | **Yes** (Table 3) | Pages 35–36 (p. 36 data) | `table3-completed-seven-column-v1` | 9 |
| **2026-03** | `FlashReport_March_2026.pdf` | **Yes** (Table 3) | Pages 35–37 (pp. 36–37 data) | `table3-completed-seven-column-v1` | 25 |
| **2026-04** | `FlashReport_April2026.pdf` | **Yes** (Table 3) | Pages 34–35 (p. 35 data) | `table3-completed-seven-column-v1` | 9 |
| **2026-05** | `FlashReport_May2026.pdf` | **Yes** (Table 3) | Pages 34–35 (p. 35 data) | `table3-completed-seven-column-v1` | 16 |
| **2026-06** | `FlashReport_June_2026.pdf` | **Yes** (Table 3) | Pages 35–42 (pp. 36–42 data) | `table3-completed-seven-column-v1` | 130 |
| **2026-07** | `FlashReport_July_2026.pdf` | **Yes** (Table 3) | Pages 35–37 (pp. 36–37 data) | `table3-completed-seven-column-v1` | 25 |
| **TOTAL** | | | | | **876** |

### Supporting-Only Synopses (No Completed Project Tables)
The following 6 files were inspected and verified as narrative/executive summaries containing no completed projects tables:
- `data/raw/2023/FR_dec_2023.pdf` (20-page executive summary with Tables A–F only)
- `data/raw/2024/April_Part-I_Synopsis.pdf`
- `data/raw/2024/May_Part-1.pdf`
- `data/raw/2024/July_Part-I.pdf`
- `data/raw/2024/August_Part-1(synopsis).pdf`
- `data/raw/2024/September_Part-1(synopsis).pdf`

### Deferred Reports: April & May 2024 (Table 2)
In `data/raw/2024/April_Part-II_List_of_tables.pdf` and `data/raw/2024/May_Part-2.pdf`, Completed Projects are located in **Table 2**, not Table 3.
- **Table 2 Title**: `Table 2: Projects Completed During ...` (e.g. April 2024 pp. 9–11; May 2024 pp. 9–11)
- **Structure**: 5 columns (`Sl. No.`, `Project Name (Agency) (Project Code)`, `Original Cost`, `Original Date of Commissioning`, `Cumulative Expenditure`)
- **Key differences**: No `Sector` column or band rows; no `State` identifier in composite cells; project codes printed as bracketed `[N########]`; Table 3 in these reports is *Deleted Projects*.
- Per project instructions, April and May 2024 are left unresolved and documented as a separate future task requiring a dedicated Table 2 adapter.

---

## 3. Technical Discoveries & Layout Adapters

### Layout 0: `table2-completed-legacy-five-column-v1` (Batch 1, 2, 3, & 4: April 2023–March 2024)
* **Header text**: `Month wise List of Completed Projects Costing Rs. 150 crore and above during 2023-2024`
* **Columns (5)**:
  1. `Sl. No.`
  2. `Project Name [(Agency)] - [<Project Code>]` (Composite cell)
  3. `Original Cost (Rs. crore)`
  4. `Original Date of commissioning`
  5. `Cumulative Expenditure (Rs. crore)`
* **Cumulative Financial-Year Ledger Semantics**:
  - The 2023-24 Table 2 is a cumulative FY ledger. April reports serials 1–20, May reports serials 1–30, June reports serials 1–84, July reports serials 1–91, August reports serials 1–106, September reports serials 1–154, October reports serials 1–183, November reports serials 1–194, January 2024 reports serials 1–229, February 2024 reports serials 1–249, and March 2024 reports serials 1–281.
  - Section banners within the table indicate completion months (`April,2023`, `May,2023`, `June,2023`, `July, 2023`, `August, 2023`, `September, 2023`, `October,2023`, `November,2023`, `December,2023`, `January,2024`, `February,2024`, `March,2024`).
  - The extraction assigns each project row to its reported completion month banner, extracting only newly completed projects per month:
    - 20 in April (serials 1–20)
    - 10 in May (serials 21–30)
    - 54 in June (serials 31–84)
    - 7 in July (serials 85–91)
    - 15 in August (serials 92–106)
    - 48 in September (serials 107–154)
    - 29 in October (serials 155–183)
    - 11 in November (serials 184–194)
    - 13 in January 2024 (serials 217–229)
    - 20 in February 2024 (serials 230–249)
    - 32 in March 2024 (serials 250–281)
    This prevents duplication while preserving exact cumulative ledger serial continuity (1..20, 21..30, 31..84, 85..91, 92..106, 107..154, 155..183, 184..194, 217..229, 230..249, 250..281).
  - Note on December 2023: `FR_dec_2023.pdf` had no Table 2 (synopsis only). In the January, February, and March 2024 reports, the cumulative ledger includes December 2023 projects (serials 195–216, 22 rows). Per batch boundary instructions, only January, February, and March 2024 records were extracted in Batch 4.
  - Sector banners appear as structural rows (`PETROLEUM`, `POWER`, `STEEL`, `ROAD TRANSPORT AND HIGHWAYS`, `DEPARTMENT OF HIGHER EDUCATION`, `COAL`, `HEALTH AND FAMILY WELFARE`, etc.) and are carried forward into `sector`. State and Ministry are source-absent (stored as `None`).
* **Trailing Blank Continuation Page Handling (October 2023)**:
  - In `FR_oct_2023.pdf`, Table 2 ends on page 34 at serial 183. MoSPI generated page 35 with the Table 2 header and 4 empty table rows before transitioning to Table 3 (*Deleted Projects*) on page 36.
  - `table_candidate_audit` checks `has_content` before rejecting candidate tables for `no rows with numeric serial in serial column`. Trailing blank pages with zero non-header content match cleanly as empty continuation tables, allowing page 35 to be audited and processed without false-alarm schema change aborts.
* **Table 2 vs. Table 20 Isolation**:
  - Reports in FY 2023-24 contain `TABLE-20 Month wise List of Completed Projects Costing Rs. 1000 crore and above during 2023-2024` on pages 70–73.
  - `is_table2_page` explicitly rejects `"1000 crore"` and `"table-20"` to maintain strict isolation of the 150 crore Completed Projects table.

### Layout 1: `table3-completed-legacy-six-column-v1`
* **Header text**: `Table:-3. Project List: Completed during <Month> <Year>`
* **Columns (6)**:
  1. `Sector`
  2. `Sl. No.`
  3. `Project Name / (Agency Name) / (Project Code) / (State Name)` (Composite cell)
  4. `Original Cost in Rs. Crore`
  5. `Date of Commissioning Original (MM/YYYY)`
  6. `Cumulative Expenditure in Rs. Crore`

#### Legacy Sector Column Ruling Quirk & Resolution
In several 2024 reports (July 2024, August 2024, October 2024, December 2024), MoSPI PDF generation omitted the vertical ruling line separating Column 0 (`Sector`) and Column 1 (`Sl. No.`) for body rows or sector band rows. Consequently, `pdfplumber.find_tables()` returned `row[0] = None`, while the sector name was printed in the left margin within Column 0's x-span.
- **Resolution**: `_get_page_sector_headings` scans margin words in Column 0 (`x0` from `hdr.x0 - 10` to `hdr.x1 + 10`) and groups them into vertical bands. Project rows match against the active sector heading at or above their `top` coordinate, carrying the sector forward until the next sector header.

#### Robust Semantic Page Detection
`is_table3_page` checks `project list: completed during` or `completed projects during month`. To avoid false rejections when project names contain regional descriptors (such as Project 7 in December 2024: `NORTH EASTERN REGION STRENGTHENING SCHEME-XII`), ongoing table exclusion requires both `"ongoing projects"` and a Table 3 heading label.

---

## 4. Final CSV Schema (`projects_completed.csv`)

The output schema preserves source representation and provenance:

1. **Identity & Source Labels**: `project_code`, `project_name`, `agency`, `ministry`, `sector`, `state`
2. **Parsed Dates** (`YYYY-MM`): `approval_date`, `start_date`, `original_completion_date`, `revised_completion_date`, `actual_completion_date`
3. **Parsed Numerics** (Rs. crore, float): `original_cost`, `revised_cost`, `cumulative_expenditure`
4. **Time**: `report_month`
5. **Source Representations**: `approval_date_raw`, `start_date_raw`, `original_completion_date_raw`, `revised_completion_date_raw`, `actual_completion_date_raw`, `original_cost_raw`, `revised_cost_raw`, `cumulative_expenditure_raw`
6. **Provenance**: `source_file`, `source_page`, `source_row_number`, `source_serial_number`, `extraction_method`

---

## 5. Dataset Integrity & Hash Verification

### Baseline & Re-Verification of Monthly Dataset Files

Before and after the Phase 2, Batch 1, Batch 2, and Batch 3 Completed Projects processing, SHA-256 hashes of all canonical ongoing datasets and monthly cleaned CSVs were verified. All files are **byte-for-byte identical**:

| File | Status | SHA-256 Hash |
|---|---|---|
| `data/processed/projects_monthly.csv` | **MATCH** | `73E47AA487E70A28FE3C984E532A6E23D21897B60C176BEEA80FB1C06F73E191` |
| `data/cleaned/projects_2025_04.csv` | **MATCH** | `9870B39CB353B4DDF870566908E21BC000322FED65B2DB1E94E50C3A78A000FD` |
| `data/cleaned/projects_2025_05.csv` | **MATCH** | `ED45BC78FE9B12E00A9EC9D914D38A347F7A6CBB29F0264F85F1ADE14982B843` |
| `data/cleaned/projects_2025_06.csv` | **MATCH** | `987459F23C0E479B80F7E647F4062BE1B73FA3BA9451BFECFB9DFA29A4B4334F` |
| `data/cleaned/projects_2025_07.csv` | **MATCH** | `AFEDC251C8F55CB27034938FA9681E823BC00F8ECD062E50E44E9B802A9A1A58` |
| `data/cleaned/projects_2025_08.csv` | **MATCH** | `FB9296DCD192FB591B726717BF83DCF78269DF86E797FC85B5FFD6296F9FBD61` |
| `data/cleaned/projects_2025_09.csv` | **MATCH** | `6045C5274077A7CBE7EC948F3C966BFF12BA089C3924434FB4E3CB487F8AA5D3` |
| `data/cleaned/projects_2025_10.csv` | **MATCH** | `241F26EA0FA3465DD83AA2E3BDEA3548BB40EE8457ED3BFADD5B396B40A1F01E` |
| `data/cleaned/projects_2025_11.csv` | **MATCH** | `E07EBD3630C34F6795BCCA0FD269DCAF11E944EBE7F14410A790B9FE34111016` |
| `data/cleaned/projects_2025_12.csv` | **MATCH** | `1195FBB10AFB31E68A3B13B7FDDE953FEA4771301ABBF76D361233F85A1A36FB` |
| `data/cleaned/projects_2026_01.csv` | **MATCH** | `B48F69745B4BD97253761825F5BF143B0FAD7C51AF326C1A1F73D394F05DA4D6` |
| `data/cleaned/projects_2026_02.csv` | **MATCH** | `E6D2EA35AB40EAF8B2DCB091760EFCA0F3847EACC9C904D8CEEB366EA6511E3B` |
| `data/cleaned/projects_2026_03.csv` | **MATCH** | `8A99484E353FBF50437B92C6842DDE8FE0BBC9112A5331B2637600873DF4C512` |
| `data/cleaned/projects_2026_04.csv` | **MATCH** | `EDD50D32FC179611D217BEFADE8B5903AE17ABFE014F164199F37C2DDF02AB3A` |
| `data/cleaned/projects_2026_05.csv` | **MATCH** | `85C04A73B7978935B47244351E52382C6A96F7DE41CB5863557085BD4787C802` |
| `data/cleaned/projects_2026_06.csv` | **MATCH** | `829E7B8A7A6C9611AB7C3A228CCA97C25A0FE7E4AF043FAFF27C560D77ACE289` |
| `data/cleaned/projects_2026_07.csv` | **MATCH** | `05BF807B4C4E8C0A93D5952EC963141F4AC246A22C9BCD5BF0A70C68544DDC17` |

### Completed Projects Dataset Hash Comparison

| Stage | Row Count | SHA-256 Hash | Notes |
|---|---:|---|---|
| **Baseline (April 2025–July 2026)** | 375 | `CDE695898623FAEE380B834DCE764BE1A79F7681760B99A18F2C911C4C045456` | 14 active months |
| **Phase 2 (June 2024–July 2026)** | 617 | `D8A06675FBDCA847A2B12D02665679AD4077402FDBE741C461C6FB369A8A8C2E` | 24 active months (+242 rows) |
| **Batch 1 (April 2023–July 2026)** | 701 | `47D1A82F234A4144E68410302B624315E96567DF0C1FC5541C4A9296A5489BAF` | 27 active months (+84 rows) |
| **Batch 2 (April 2023–July 2026)** | 771 | `2650E56E107170E0BE5248D25B47ABBEB03A641E7A63EBA7398630879475BFDA` | 30 active months (+70 rows) |
| **Batch 3 (April 2023–July 2026)** | 811 | `C8CB9672551827E91832682B9877012A1FA0F48F880EC5C917EBE8476C2F0D3C` | 32 active months (+40 rows) |
| **Batch 4 (April 2023–July 2026)** | **876** | `89BEA84FD68A22E327090C1E4E4533F5BCD745ADCA61EB4E66172EE9023BB910` | 35 active months (+65 rows) |

---

## 6. Summary of Validation Checks

- `total_records`: **876**
- `unique_projects`: **876**
- `missing_project_codes`: **0**
- `duplicate_keys`: **0**
- `serial_continuity_all_months`: **True** (serials 1..20 for 2023-04, 21..30 for 2023-05, 31..84 for 2023-06, 85..91 for 2023-07, 92..106 for 2023-08, 107..154 for 2023-09, 155..183 for 2023-10, 184..194 for 2023-11, 217..229 for 2024-01, 230..249 for 2024-02, 250..281 for 2024-03, and 1..N across all subsequent active months)
- `warnings_count`: **0**
- `tests.test_completed_projects`: **15/15 OK**
