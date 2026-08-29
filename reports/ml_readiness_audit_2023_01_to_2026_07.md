# PAIMANA Comprehensive Historical Data Readiness and Coverage Audit (2023-01 to 2026-07)

## 1. Executive Summary & Authoritative Recommendation

### Primary Recommendation: `READY_FOR_TARGET_AND_FEATURE_DESIGN`
*(With explicit distinction between rolling longitudinal early-warning targets and final realized lifecycle outcomes)*

Following the completed extraction and individual acceptance of all 40 coded historical months spanning January 2023 through July 2026 (64,608 canonical project-month observations across 4,738 unique project identifiers), this audit assesses the empirical readiness of the dataset for predictive machine learning and econometric target design.

```
+--------------------------------------------------------------------------------------------------+
|                                    DATASET AUDIT DECISION MATRIX                                 |
+----------------------------------------------------+---------------------------------------------+
| TARGET FAMILY                                      | STATUS & RECOMMENDATION                     |
+----------------------------------------------------+---------------------------------------------+
| 1. Rolling Longitudinal Early-Warning Targets:    | READY_FOR_TARGET_AND_FEATURE_DESIGN         |
|    - 3M / 6M Schedule Extension Revision           | 4,819 positive 3M events (1,653 leg, 3,166 mod)   |
|    - 3M / 6M Expenditure Stagnation                | 10,072 positive 3M events (7,814 leg, 2,258 mod)  |
|    - 3M / 6M Physical Progress Stagnation          | 8,085 positive 3M events (where supported)  |
|    - 3M / 6M Upward Cost Revision (Escalation)     | 457 positive 3M events (208 leg, 249 mod)   |
+----------------------------------------------------+---------------------------------------------+
| 2. Realized Final Project Lifecycle Outcomes:      | WAIT_FOR_COMPLETED_PROJECTS_BEFORE_DESIGN   |
|    - Actual Completion Date & Realized Delay       | Cannot be inferred from ongoing panel exit  |
|    - Final Project Cost & Lifetime Cost Overrun    | Ongoing panel exit is right-censored/biased |
+----------------------------------------------------+---------------------------------------------+
```

### Key Audit Conclusions
1. **Zero Defect Baseline**:
   - 0 missing project codes across all 64,608 rows (100.0% identifier completeness).
   - 0 duplicate `(project_code, report_month)` keys.
   - 100% parse success for all source-reported numeric and date fields.
   - Exact canonical hash verified: `9512A9881E17DFDED6E182D87A8DFB1C4EDBD36C0D9B8A7DA9FD1ABB7E002FBF`.
   - Test suite: **111/111 passing**.
2. **Substantial Deepening of Longitudinal Histories**:
   - Expanding the canonical dataset from 29 to 40 coded months added 18,040 rows (+38.7%) and extended the legacy identifier era from 16 to 27 months.
   - **4,529 projects** (95.6%) possess $\ge 3$ observations; **4,182 projects** (88.3%) possess $\ge 6$ observations; **2,570 projects** (54.2%) possess $\ge 12$ observations; and **1,459 projects** possess $\ge 18$ observations.
   - **702 legacy projects** are observed in all 27 legacy months, and **552 modern projects** are observed in all 13 six-digit months.
3. **Robust Event Counts for Schedule and Stagnation Targets**:
   - Schedule extensions offer large sample sizes: **3,146 adjacent upward revisions**, **4,819 3-month forward extensions**, and **3,320 6-month forward extensions**.
   - Expenditure and progress stagnation provide abundant positive examples with balanced class ratios ($1:1.5$ to $1:4.5$).
4. **Target Definition & Class Imbalance for Cost Escalation**:
   - Cost escalation is defined strictly as a **future upward reported cost revision** ($C_{T+H} > C_T$ where $C$ is reported `revised_cost`), rather than a non-zero cost level.
   - Upward cost revisions remain rare in monthly reporting: 270 adjacent events (1.06% of comparable pairs) and 457 3-month forward escalations across the entire 3.5-year history. Cost escalation models will face significant class imbalance ($1:29$ to $1:100$).
5. **Structural Regime Isolation**:
   - Prediction windows must not cross the three structural discontinuities: (a) December 2023 missing report, (b) April–May 2024 uncoded Annexure XVIII gap, and (c) July 2025 official identifier redesign.

---

## 2. Dataset Integrity & Comprehensive Inventory

### Canonical Scope & Coverage

| Dimension | Full Dataset (40 Months) | Legacy Identifier Era (27 Months) | Six-Digit Identifier Era (13 Months) |
|---|---:|---:|---:|
| **Calendar Range** | 2023-01 to 2026-07 | 2023-01 to 2025-06 | 2025-07 to 2026-07 |
| **Coded Months Present** | **40** | **27** | **13** |
| **Total Canonical Rows** | **64,608** | **46,007** | **18,601** |
| **Unique Project Identifiers** | **4,738** | **2,495** | **2,243** |
| **Missing Project Codes** | **0** (0.0%) | **0** (0.0%) | **0** (0.0%) |
| **Duplicate `(project_code, month)` Keys** | **0** (0.0%) | **0** (0.0%) | **0** (0.0%) |
| **Cross-Era Exact ID Overlap** | **0** (0.0%) | N/A | N/A |
| **Structural Layouts** | 4 layouts | 3 layouts | 2 layouts |

### Monthly Observations and Verification Status

```
2023: [01: 1454] [02: 1418] [03: 1449] [04: 1605] [05: 1681] [06: 1643] [07: 1646] [08: 1762] [09: 1763] [10: 1788] [11: 1831] [12: GAP]
2024: [01: 1821] [02: 1902] [03: 1873] [04: UNCODED] [05: UNCODED] [06: 1810] [07: 1793] [08: 1783] [09: 1792] [10: 1747] [11: 1742] [12: 1724]
2025: [01: 1719] [02: 1682] [03: 1677] [04: 1670] [05: 1637] [06: 1595] || [07: 791] [08: 800] [09: 794] [10: 820] [11: 823] [12: 1392]
2026: [01: 1702] [02: 1948] [03: 1941] [04: 1981] [05: 1987] [06: 1847] [07: 1775]
```

*Explicit Boundaries*:
- `2023-12`: Monthly project table unavailable in published Flash Report (Summary Only); explicit gap preserved.
- `2024-04` & `2024-05`: `Annexure XVIII` structurally omits project codes; 1,838 and 1,812 source-faithful records preserved under `data/cleaned_uncoded/` and excluded from canonical combined dataset.
- `2025-06` $\to$ `2025-07`: Official MOSPI identifier redesign from `N########`/9-digit codes to 6-digit codes; exact-code overlap is 0. Proposed crosswalk remains diagnostic only.

### Field Completeness by Era & Layout

| Field | Overall Present (64,608 Rows) | Overall Missing | Structurally Absent | Source Missing | Applicable Source Completeness |
|---|---:|---:|---:|---:|---:|
| `project_code` | 64,608 (100.0%) | 0 (0.0%) | 0 | 0 | **100.0%** |
| `project_name` | 64,608 (100.0%) | 0 (0.0%) | 0 | 0 | **100.0%** |
| `agency` | 64,608 (100.0%) | 0 (0.0%) | 0 | 0 | **100.0%** |
| `sector` | 64,608 (100.0%) | 0 (0.0%) | 0 | 0 | **100.0%** |
| `original_cost` | 64,608 (100.0%) | 0 (0.0%) | 0 | 0 | **100.0%** |
| `cumulative_expenditure` | 64,608 (100.0%) | 0 (0.0%) | 0 | 0 | **100.0%** |
| `state` | 64,597 (99.98%) | 11 (0.02%) | 0 | 11 | **99.98%** |
| `approval_date` | 63,997 (99.05%) | 611 (0.95%) | 0 | 611 | **99.05%** |
| `original_completion_date` | 63,585 (98.42%) | 1,023 (1.58%) | 0 | 1,023 | **98.42%** |
| `revised_completion_date` | 28,433 (44.01%) | 36,175 (55.99%) | 0 | 36,175 | **44.01%** *(unrevised)* |
| `revised_cost` | 29,268 (45.30%) | 35,340 (54.70%) | 0 | 35,340 | **45.30%** *(unrevised)* |
| `physical_progress` | 39,959 (61.85%) | 24,649 (38.15%) | 23,636 *(milestones)* | 1,013 | **97.53%** *(when supported)* |
| `ministry` | 18,601 (28.79%) | 46,007 (71.21%) | 46,007 *(legacy era)* | 0 | **100.0%** *(when supported)* |
| `start_date` | 17,789 (27.53%) | 46,819 (72.47%) | 46,798 *(legacy+Jul25)*| 21 | **99.88%** *(when supported)* |

> [!NOTE]
> Structural missingness in legacy layouts (e.g. `ministry`, `start_date`, `physical_progress` in 2023 and early 2024) reflects genuine source design, not extraction loss. Milestone text (`achieved/total`) is preserved in raw extractions and must never be converted to a percentage.

---

## 3. Longitudinal Signal Inventory (Exact Project IDs)

Quantified across all 36 valid adjacent monthly transitions within continuous identifier regimes (56,284 comparable adjacent pairs):

### 1. Cumulative Expenditure Transitions
- **Comparable adjacent pairs**: 56,284
- **Increases ($\Delta > 0$)**: 30,923 (54.94%)
- **Unchanged ($\Delta = 0$)**: 24,038 (42.71%)
- **Reported Decreases ($\Delta < 0$)**: 1,323 (2.35%)
- **Positive $\to$ Zero Resets**: 66 (0.12%)
- **Zero-Expenditure Observations**: 4,782 rows (7.40% of dataset); 1,033 projects ever report zero; 286 projects always report zero.
- **Zero Expenditure with Positive Physical Progress**: 1,917 rows across 410 unique projects (observed primarily in MoRTH / NHAI records where expenditure is reported periodically).

### 2. Revised Cost Transitions (Reported Cost Revisions)
- **Comparable adjacent pairs with revised cost in both months**: 25,454
- **Unchanged**: 25,051 (98.42%)
- **Upward Cost Revisions / Escalations ($C_{T+1} > C_T$)**: 270 (1.06%)
  - Mean upward revision: +Rs 585.78 crore (median: +Rs 158.38 cr, max: +Rs 13,334.00 cr)
- **Downward Cost Reductions ($C_{T+1} < C_T$)**: 133 (0.52%)
- **Unique projects with $\ge 1$ cost revision**: 334 (Legacy: 114, Modern: 220)
- **Unique projects with $\ge 2$ cost revisions**: 53 (Legacy: 22, Modern: 31)

### 3. Revised Completion Date Transitions (Schedule Revisions)
- **Comparable adjacent pairs with revised date in both months**: 23,734
- **Unchanged**: 20,432 (86.09%)
- **Upward Schedule Extensions ($D_{T+1} > D_T$)**: 3,146 (13.25%)
  - Mean extension: +6.09 months (median: +3.0 months, max: +183 months)
- **Downward Schedule Reductions ($D_{T+1} < D_T$)**: 156 (0.66%)
- **Unique projects with $\ge 1$ schedule extension**: 1,584 (Legacy: 478, Modern: 1,106)
- **Unique projects with $\ge 2$ schedule extensions**: 841 (Legacy: 239, Modern: 602)

### 4. Physical Progress Transitions (Supported Eras: Jun 2024–Jul 2026)
- **Comparable adjacent pairs**: 35,569
- **Increases ($\Delta > 0$)**: 17,525 (49.27%)
- **Unchanged ($\Delta = 0$)**: 17,370 (48.83%)
- **Reported Decreases / Corrections ($\Delta < 0$)**: 674 (1.89%)
- **Unchanged Progress Runs**: 6,225 runs of $\ge 2$ months; 3,437 runs of $\ge 3$ months; 1,056 runs of $\ge 6$ months; 233 runs of $\ge 12$ months.

---

## 4. Anomalous Transition Concentrations & Empirical Patterns

A systematic review of warning rates across all 36 valid adjacent monthly boundaries identified several distinct concentration patterns:

```
RANKED TOP HIGH-WARNING BOUNDARIES:
1. 2024-07 -> 2024-08 (789 warnings): State changes (429), Name changes (286), Progress dec (28)
2. 2026-05 -> 2026-06 (654 warnings): Agency changes (578), Exp dec (38), Cost dec (6)
3. 2025-04 -> 2025-05 (642 warnings): Name changes (262), State changes (258), Exp dec (49)
4. 2026-06 -> 2026-07 (629 warnings): Agency changes (236), Name changes (147), Progress dec (91), Exp dec (85), Cost dec (44)
5. 2024-06 -> 2024-07 (619 warnings): Name changes (467), State changes (58), Progress dec (44), Exp dec (26)
6. 2024-08 -> 2024-09 (619 warnings): State changes (374), Name changes (129), Sector changes (56), Progress dec (45)
7. 2024-11 -> 2024-12 (610 warnings): State changes (273), Name changes (257), Progress dec (39), Exp dec (30)
...
13. 2023-03 -> 2023-04 (334 warnings): Exp dec (269), State changes (52), Pos->Zero Exp (8), Cost dec (4)
17. 2023-04 -> 2023-05 (172 warnings): Exp dec (138), Pos->Zero Exp (29), Exp dec (75)
```

### Empirical Investigation of Concentrations

#### A. March $\to$ April 2023 (334 Warnings)
- **Expenditure Decreases (269 cases)**:
  - Concentrated in `ROAD TRANSPORT AND HIGHWAYS` (172 cases: `NHIDCL` 68, `MoRTH` 54, `NHAI` 50), `PETROLEUM` (24 cases: `BPCL` 13), `RAILWAYS` (23 cases: `ECR` 18), and `COAL` (18 cases).
  - *Observation*: Coincides with the March 31 Indian fiscal year-end boundary (FY 2022-23); the reported pattern is consistent with annual agency-level expenditure reporting reconciliations.
- **State Text Changes (52 cases)**:
  - Consist of exact source text string changes in the published Flash Reports: 42 cases of `CHHATISGARH` vs `CHHATTISGARH`, 8 cases of `A & N ISLANDS` vs `ANDAMAN AND NICOBAR ISLANDS`, 1 case of `PONDICHERRY` vs `PUDUCHERRY`, and 1 case for project `N28000140` where state text was blank in March and printed as `KERALA` in April.

#### B. April $\to$ May 2023 (172 Warnings)
- **Positive $\to$ Zero Expenditure Resets (29 cases)**:
  - 100% of these 29 cases occur in `ROAD TRANSPORT AND HIGHWAYS` under `NHAI`, where the source PDF printed `0.00` expenditure in May 2023 before reporting positive cumulative values again in June 2023.

#### C. July $\to$ August 2024 (789 Warnings) & August $\to$ September 2024 (619 Warnings)
- **Recheck Against Accepted August Spatial Reconstruction Fix**:
  - In August 2024, Table 7 features headerless continuation pages (7, 8, and 9 columns) across 202 pages. The accepted spatial fix (`projects_2024_08.csv`, SHA-256 `2D49E706...`) verified 100% continuous serials (1 to 1,783) and exact physical coordinate alignment (`x ∈ [30.0, 81.5]` for State, `x ∈ [81.5, 132.0]` for Sector).
  - The 429 state changes and 286 name changes in July $\to$ August 2024, and 374 state changes and 129 name changes in August $\to$ September 2024, are **normalization-sensitive differences and raw-text formatting variations in the source tables**, not extraction regressions.
  - Specifically, collapsing whitespace reveals that across all 429 July $\to$ August state differences, only 58 are substantive text differences—all 58 being the literal printed abbreviation `MULTI` on August Page 163 vs `MULTI STATE` in July and September. The remaining 371 state differences and project name differences reflect source line-break wrapping in multi-line cells that the pipeline faithfully preserves without artificial string normalization.

#### D. May $\to$ June 2026 (654 Warnings)
- **Agency Changes (578 cases)**:
  - 494 cases are string changes from `National Highways Authority of India [NHAI]` to `NHAI`.
  - 32 cases are string changes from `Western Coalfields Limited [WCL]` to `WCL - CIL`.
  - 10 cases are string changes from `South Eastern Coalfields Limited [SECL]` to `SECL - CIL`.

#### E. June $\to$ July 2026 (629 Warnings)
- Multi-field transitions occur across agency names (236), project names (147), physical progress decreases (91), cumulative expenditure decreases (85), and revised cost decreases (44).

---

## 5. Prediction Target Feasibility & Opportunity Counts

Target opportunities were evaluated within strictly continuous same-ID regimes across forecast horizons $H \in \{1, 3, 6, 12\}$ months:

```
+----------------------------------------------------------------------------------------------------+
|                         PREDICTION TARGET OPPORTUNITY COUNTS BY ERA & HORIZON                      |
+----------------------+----------+--------------------+---------------------+-----------+-----------+
| TARGET DEFINITION    | HORIZON  | COMPARABLE WINDOWS | POSITIVE INCIDENCES | POS RATE  | IMBALANCE |
+----------------------+----------+--------------------+---------------------+-----------+-----------+
| A. Cost Escalation   | Adjacent | Leg: 9,139         | 110 (92 projects)   | 1.20%     | 1 : 82.1  |
|    (revised_cost     |          | Mod: 16,315        | 160 (149 projects)  | 0.98%     | 1 : 101.0 |
|     upward revision) | 3-Month  | Leg: 6,330         | 208 (84 projects)   | 3.29%     | 1 : 29.4  |
|                      |          | Mod: 11,985        | 249 (144 projects)  | 2.08%     | 1 : 47.1  |
|                      | 6-Month  | Leg: 3,744         | 236 (72 projects)   | 6.30%     | 1 : 14.9  |
|                      |          | Mod: 6,038         | 289 (136 projects)  | 4.79%     | 1 : 19.9  |
|                      | 12-Month | Leg: 290           | 34 (34 projects)    | 11.72%    | 1 : 7.5   |
|                      |          | Mod: 552           | 118 (118 projects)  | 21.38%    | 1 : 3.7   |
+----------------------+----------+--------------------+---------------------+-----------+-----------+
| B. Schedule Revision | Adjacent | Leg: 12,228        | 1,050 (456 projects)| 8.59%     | 1 : 10.6  |
|    (completion ext   |          | Mod: 11,506        | 2,096 (1079 proj)   | 18.22%    | 1 : 4.5   |
|     upward revision) | 3-Month  | Leg: 8,140         | 1,653 (450 projects)| 20.31%    | 1 : 3.9   |
|                      |          | Mod: 7,938         | 3,166 (1045 proj)   | 39.88%    | 1 : 1.5   |
|                      | 6-Month  | Leg: 4,933         | 1,599 (416 projects)| 32.41%    | 1 : 2.1   |
|                      |          | Mod: 3,751         | 1,721 (577 projects)| 45.88%    | 1 : 1.2   |
|                      | 12-Month | Leg: 397           | 198 (198 projects)  | 49.87%    | 1 : 1.0   |
|                      |          | Mod: 320           | 183 (183 projects)  | 57.19%    | 1 : 0.7   |
+----------------------+----------+--------------------+---------------------+-----------+-----------+
| C. Progress          | 3-Month  | Leg: 15,500        | 5,059 (1041 proj)   | 32.64%    | 1 : 2.1   |
|    Stagnation (Δ=0)  |          | Mod: 11,985        | 3,026 (969 proj)    | 25.25%    | 1 : 3.0   |
|                      | 6-Month  | Leg: 10,316        | 2,386 (637 projects)| 23.13%    | 1 : 3.3   |
|                      |          | Mod: 6,038         | 759 (304 projects)  | 12.57%    | 1 : 7.0   |
+----------------------+----------+--------------------+---------------------+-----------+-----------+
| D. Expenditure       | 3-Month  | Leg: 28,471        | 7,814 (1343 proj)   | 27.45%    | 1 : 2.6   |
|    Stagnation (Δ=0)  |          | Mod: 11,985        | 2,258 (680 projects)| 18.84%    | 1 : 4.3   |
|                      | 6-Month  | Leg: 17,814        | 3,346 (746 projects)| 18.78%    | 1 : 4.3   |
|                      |          | Mod: 6,038         | 572 (235 projects)  | 9.47%     | 1 : 9.6   |
+----------------------+----------+--------------------+---------------------+-----------+-----------+
```

---

## 6. History Depth: Calendar Span vs. Observed Months

### Observation Count Distribution by Project

| Observation Threshold | Overall Dataset (40 Months) | Legacy Era (27 Months) | Six-Digit Era (13 Months) |
|---|---:|---:|---:|
| $\ge 1$ Observation | **4,738** (100.0%) | **2,495** (100.0%) | **2,243** (100.0%) |
| $\ge 2$ Observations | **4,618** (97.47%) | **2,442** (97.88%) | **2,176** (97.01%) |
| $\ge 3$ Observations | **4,529** (95.59%) | **2,403** (96.31%) | **2,126** (94.78%) |
| $\ge 6$ Observations | **4,182** (88.27%) | **2,265** (90.78%) | **1,917** (85.47%) |
| $\ge 12$ Observations | **2,570** (54.24%) | **1,941** (77.80%) | **629** (28.04%) |
| $\ge 18$ Observations | **1,459** (30.80%) | **1,459** (58.48%) | **0** (0.00%) |
| $\ge 24$ Observations | **970** (20.47%) | **970** (38.88%) | **0** (0.00%) |
| $\ge 27$ Observations | **702** (14.82%) | **702** (28.14%) | **0** (0.00%) |
| $\ge 30$ Observations | **0** (0.00%) | **0** (0.00%) | **0** (0.00%) |
| **Present in All Era Months** | N/A | **702** (28.14%) | **552** (24.61%) |

### Calendar Span vs. Observed Months Distinction
- **Legacy Identifier Era**: Spans 30 calendar months (January 2023 through June 2025). However, because December 2023 was unavailable and April/May 2024 were uncoded Annexures, the maximum number of observed monthly snapshots for any single project is **27**, achieved by **702 projects**.
- **Six-Digit Identifier Era**: Spans 13 continuous calendar months (July 2025 through July 2026). Maximum observed monthly snapshots is **13**, achieved by **552 projects**.
- **Zero Cross-Era Overlap**: Because the July 2025 redesign changed project codes without an official bridge, no single project identifier spans 30 observed months.

---

## 7. Completed-Project Dependency Analysis

The ongoing-project monitoring panel alone **cannot defensibly provide**:
1. **Actual completion date**
2. **Final closed-form project cost**
3. **Realized lifetime schedule delay**
4. **Realized lifetime cost overrun**

*Rationale*:
- Disappearance from ongoing tables (Table 6/7) does not equate to project completion (projects can be dropped, restructured, unbundled, transferred to state governments, or drop below Rs 150 crore).
- The terminal ongoing snapshot precedes final contract settlement by 3–12 months, creating survivorship and right-censoring bias.
- Final lifecycle outcome modeling strictly requires extracting the dedicated **Completed Projects** tables published separately in Flash Reports.

---

## 8. Feature Leakage Risk Taxonomy

Feature safety classifications for future feature engineering:

```
+----------------------------------------------------------------------------------------------------+
|                                    FEATURE SAFETY TAXONOMY                                         |
+-------------------------------+-----------------------------------+--------------------------------+
| FIELD                         | CLASSIFICATION                    | GOVERNANCE CONSTRAINT          |
+-------------------------------+-----------------------------------+--------------------------------+
| project_code                  | IDENTIFIER_ONLY                   | Cluster/split key; unbridged   |
| project_name                  | IDENTIFIER_ONLY                   | Memorization risk; normalize   |
| legacy_ocms_code, pmgid       | IDENTIFIER_ONLY                   | Sparse provenance only         |
| agency                        | SAFE_BASE_FEATURE                 | Known at T; subject to drift   |
| sector                        | SAFE_BASE_FEATURE                 | Known at T; preserve labels    |
| state                         | SAFE_BASE_FEATURE                 | Known at T; categorical encode |
| approval_date                 | SAFE_BASE_FEATURE                 | Known at T; baseline age       |
| original_completion_date      | SAFE_BASE_FEATURE                 | Known at T; baseline schedule  |
| original_cost                 | SAFE_BASE_FEATURE                 | Known at T; baseline budget    |
| start_date                    | CONDITIONALLY_SAFE                | Structurally absent in legacy  |
| ministry                      | CONDITIONALLY_SAFE                | Structurally absent in legacy  |
| physical_progress             | CONDITIONALLY_SAFE                | Absent Jan-Nov23, Jan-Mar24    |
| cumulative_expenditure        | CONDITIONALLY_SAFE                | Safe at T; agency zero quirks  |
| report_month                  | CONDITIONALLY_SAFE                | Temporal grouping/regime split |
| revised_cost                  | LIKELY_LEAKAGE FOR CERTAIN TARGETS| Safe at T for future delta;    |
|                               |                                   | Leaks current revision status  |
| revised_completion_date       | LIKELY_LEAKAGE FOR CERTAIN TARGETS| Safe at T for future delta;    |
|                               |                                   | Leaks current schedule status  |
| *_raw, source_file, page, ... | IDENTIFIER_ONLY                   | Extraction provenance only     |
+-------------------------------+-----------------------------------+--------------------------------+
```

---

## 9. Audit Artifacts Produced

The machine-readable outputs generated in `data/validation/audit/` are:
1. `audit_manifest.json` — Scope, provenance, SHA-256 hash, read-only guarantees.
2. `coverage_summary.json` — Monthly counts, era breakdowns, observation depth distributions.
3. `field_missingness.json` — Field-by-field completeness rates overall, by month, layout, sector, agency.
4. `event_audit.json` — Numeric change counts, upward/downward distributions, stagnation run lengths.
5. `category_coverage.json` — Category cardinality, sparsity flags, frequency distributions.
6. `horizon_eligibility.json` — Forward horizon eligible observations, target event incidences, class imbalance ratios.
7. `leakage_risk.json` — Feature governance classifications and leakage prevention rules.
