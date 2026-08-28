# PAIMANA Second ML-Readiness and Data-Coverage Audit (2024-01 to 2026-07)

## 1. Decision & Single Recommendation

**Recommendation: `EXTRACT_2023_AND_COMPLETED_PROJECTS`**

### Rationale Based on Event Rarity, Horizon Depth, and Censoring Bias

While expanding the canonical history from 19 to 29 coded months (46,568 rows across Jan–Mar 2024 and Jun 2024–Jul 2026) has significantly deepened longitudinal observation windows, the data remain **insufficient for training robust predictive models on project cost escalation**:

1. **Extreme Event Sparsity for Cost Escalation**:
   - Out of 40,359 adjacent month-to-month observation pairs, only **224 upward cost escalation events** occur (1.02% of 21,911 comparable pairs).
   - Across the entire 2.5-year history, only **289 unique projects** ever experience an upward or downward cost revision, and only **42 projects** experience multiple revisions.
   - At a 3-month forecast horizon ($H=3$), only **370 upward cost escalation events** are observable across 15,736 comparable windows (**2.35% incidence**).
   - At a 6-month forecast horizon ($H=6$), only **438 upward cost escalation events** are observable across 8,445 comparable windows (**5.19% incidence**).
2. **Structural Longitudinal Discontinuities**:
   - **April and May 2024**: Structurally uncoded in Annexure XVIII (0% project codes), creating a 3-month project-level continuity break between Q1 2024 and June 2024.
   - **Jan–Mar 2024**: Structurally lack physical progress, Start Date, and Ministry.
   - **June $\to$ July 2025**: Unbridged identifier redesign (zero exact code overlap).
3. **Severe Survivorship & Right-Censoring Bias in Ongoing Tables**:
   - The ongoing project tables (Table 6/7) only track active projects. When a project finishes or is commissioned, it drops out of the table without recording final closed-form cost overruns or total lifetime delay.
   - **Completed Projects** tables (published separately in Flash Reports) contain the exact ground-truth outcomes needed for lifecycle modeling (original cost vs actual final cost, original completion date vs actual completion date).
4. **Why Both 2023 and Completed Projects are Required**:
   - Extracting **2023** will add 12 continuous pre-2024 monthly snapshots to the legacy era, doubling legacy longitudinal depth and providing much-needed historical baseline observations.
   - Extracting **Completed Projects** provides un-censored, closed-form targets for total cost escalation and schedule delay, solving the fundamental limitation of ongoing-only monitoring tables.

---

## 2. Comparison: First Audit (19 Months) vs. Second Audit (29 Months)

| Dimension / Metric | 1st Audit (19 Months: Jan 2025–Jul 2026) | 2nd Audit (29 Months: Jan–Mar 2024, Jun 2024–Jul 2026) | Delta / Trend |
|---|---:|---:|---|
| **Coded Months** | 19 | 29 | +10 months (+52.6%) |
| **Project-Month Rows** | 28,581 | 46,568 | +17,987 rows (+62.9%) |
| **Unique Project Identifiers** | 4,029 | 4,412 | +383 projects (+9.5%) |
| **Missing Project Codes** | 0 | 0 | 0 (source-faithful) |
| **Duplicate Keys** | 0 | 0 | 0 (strictly unique) |
| **Legacy Era Rows** | 9,980 (6 months) | 27,967 (16 months) | +17,987 rows (+180.2%) |
| **Six-Digit Era Rows** | 18,601 (13 months) | 18,601 (13 months) | 0 |
| **Projects with $\ge 3$ Observations** | 4,052 (4,029 unique) | 4,220 (4,412 unique) | +168 projects |
| **Projects with $\ge 6$ Observations** | 3,691 | 3,796 | +105 projects |
| **Projects with $\ge 12$ Observations** | 2,090 | 2,186 | +96 projects |
| **Projects with $\ge 16$ Observations** | 0 | 1,253 (all 16 legacy months) | +1,253 projects |
| **Projects with $\ge 18$ Observations** | 0 | 0 | 0 (bounded by ID redesign) |
| **Comparable Adjacent Pairs** | 18,175 | 40,359 | +22,184 pairs (+122.1%) |
| **Adjacent Cost Escalations ($>0$)** | 180 (0.99%) | 224 (1.02% of 21,911 comparable) | +44 events (+24.4%) |
| **Projects with $\ge 1$ Cost Change** | 244 | 289 | +45 projects |
| **Projects with $\ge 2$ Cost Changes** | 34 | 42 | +8 projects |
| **Adjacent Schedule Extensions ($>0$)** | 2,281 (16.29%) | 2,737 (14.72% of 18,597 comparable) | +456 events (+20.0%) |
| **Projects with $\ge 1$ Schedule Change** | 1,209 | 1,428 | +219 projects |
| **Projects with $\ge 2$ Schedule Changes** | 639 | 748 | +109 projects |
| **1-Month Forward Trajectories ($H=1$)** | 23,723 | 40,359 | +16,636 trajectories (+70.1%) |
| **3-Month Forward Trajectories ($H=3$)** | 16,738 | 28,463 | +11,725 trajectories (+70.0%) |
| **3-Month Cost Escalations ($T \to T+3$)** | ~249 (modern only) | 370 (121 legacy, 249 modern) | +121 events |
| **3-Month Schedule Extensions ($T \to T+3$)** | ~3,166 (modern only) | 4,072 (906 legacy, 3,166 modern) | +906 events |
| **6-Month Forward Trajectories ($H=6$)** | 6,038 (0 legacy) | 17,052 (11,014 legacy, 6,038 modern) | +11,014 trajectories (+182.4%) |
| **6-Month Cost Escalations ($T \to T+6$)** | 289 (modern only) | 438 (149 legacy, 289 modern) | +149 events |
| **6-Month Schedule Extensions ($T \to T+6$)** | 1,721 (modern only) | 2,642 (921 legacy, 1,721 modern) | +921 events |
| **12-Month Forward Trajectories ($H=12$)** | 552 (0 legacy) | 1,963 (1,411 legacy, 552 modern) | +1,411 trajectories (+255.6%) |
| **12-Month Cost Escalations ($T \to T+12$)** | 118 (modern only) | 152 (34 legacy, 118 modern) | +34 events |
| **12-Month Schedule Extensions ($T \to T+12$)** | 183 (modern only) | 381 (198 legacy, 183 modern) | +198 events |

---

## 3. Project History-Length Distribution

### Distribution Across Eras

| Statistic | Overall (29 Months) | Legacy Era (16 Months) | Six-Digit Era (13 Months) |
|---|---:|---:|---:|
| **Total Rows** | 46,568 | 27,967 | 18,601 |
| **Unique Project Identifiers** | 4,412 | 2,169 | 2,243 |
| **Minimum Observations / Project** | 1 | 1 | 1 |
| **25th Percentile (p25)** | 6 | 13 | 6 |
| **Median Observations** | 12 | 16 | 8 |
| **Mean Observations** | 10.55 | 12.90 | 8.29 |
| **75th Percentile (p75)** | 16 | 16 | 12 |
| **Maximum Observations** | 16 | 16 | 13 |

### Project Observation Thresholds

| Threshold | Overall Dataset | Legacy Era Alone | Six-Digit Era Alone |
|---|---:|---:|---:|
| $\ge 1$ Observation | 4,412 (100.0%) | 2,169 (100.0%) | 2,243 (100.0%) |
| $\ge 2$ Observations | 4,317 (97.8%) | 2,141 (98.7%) | 2,176 (97.0%) |
| $\ge 3$ Observations | 4,220 (95.6%) | 2,094 (96.5%) | 2,126 (94.8%) |
| $\ge 6$ Observations | 3,796 (86.0%) | 1,879 (86.6%) | 1,917 (85.5%) |
| $\ge 10$ Observations | 2,385 (54.1%) | 1,666 (76.8%) | 719 (32.1%) |
| $\ge 12$ Observations | 2,186 (49.5%) | 1,557 (71.8%) | 629 (28.0%) |
| $\ge 13$ Observations | 2,089 (47.3%) | 1,537 (70.9%) | 552 (24.6%) |
| $\ge 16$ Observations | 1,253 (28.4%) | 1,253 (57.8%) | 0 (N/A) |
| $\ge 18$ Observations | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) |
| $\ge 24$ Observations | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) |
| **Present in All Era Months** | N/A | **1,253** (57.8%) | **552** (24.6%) |

> [!IMPORTANT]
> Because the June $\to$ July 2025 redesign changed project identifiers without an explicit source mapping, **no project can exceed 16 consecutive observations in the legacy era or 13 in the six-digit era**. Zero projects achieve 18 or 24 observations.

---

## 4. Field Missingness & Structural Absence

### Overall Canonical Dataset (46,568 Rows)

| Field | Present | Structurally Absent | Source Missing | Overall Completeness | Source Completeness When Applicable |
|---|---:|---:|---:|---:|---:|
| `project_code` | 46,568 | 0 | 0 | 100.00% | 100.00% |
| `project_name` | 46,568 | 0 | 0 | 100.00% | 100.00% |
| `agency` | 46,568 | 0 | 0 | 100.00% | 100.00% |
| `sector` | 46,568 | 0 | 0 | 100.00% | 100.00% |
| `original_cost` | 46,568 | 0 | 0 | 100.00% | 100.00% |
| `cumulative_expenditure` | 46,568 | 0 | 0 | 100.00% | 100.00% |
| `state` | 46,562 | 0 | 6 | 99.99% | 99.99% |
| `original_completion_date` | 46,133 | 0 | 435 | 99.07% | 99.07% |
| `approval_date` | 45,957 | 0 | 611 | 98.69% | 98.69% |
| `physical_progress` | 39,959 | 5,596 | 1,013 | 85.81% | 97.53% |
| `revised_cost` | 25,190 | 0 | 21,378 | 54.09% | 54.09% |
| `revised_completion_date` | 22,513 | 0 | 24,055 | 48.34% | 48.34% |
| `ministry` | 18,601 | 27,967 | 0 | 39.94% | 100.00% |
| `start_date` | 17,789 | 28,758 | 21 | 38.20% | 99.88% |

### Breakdown by Layout Adapter

1. **`legacy-detail-ongoing-nine-column-milestones-v1`** (Jan–Mar 2024, 5,596 rows):
   - `ministry`: **5,596 structurally absent** (100%)
   - `start_date`: **5,596 structurally absent** (100%)
   - `physical_progress`: **5,596 structurally absent** (100%)
   - `revised_cost`: 1,288 present (23.02%), 4,308 source missing (76.98%)
   - `revised_completion_date`: 2,429 present (43.41%), 3,167 source missing (56.59%)
2. **`legacy-all-ongoing-nine-column-v1`** (Jun–Oct 2024, Dec 2024, Jan–Jun 2025, 20,629 rows):
   - `ministry`: **20,629 structurally absent** (100%)
   - `start_date`: **20,629 structurally absent** (100%)
   - `physical_progress`: 20,539 present (99.56%), 90 source missing (0.44%)
   - `revised_cost`: 6,298 present (30.53%), 14,331 source missing (69.47%)
   - `revised_completion_date`: 7,858 present (38.09%), 12,771 source missing (61.91%)
3. **`legacy-all-ongoing-nine-column-progress-only-v1`** (Nov 2024, 1,742 rows):
   - `ministry`: **1,742 structurally absent** (100%)
   - `start_date`: **1,742 structurally absent** (100%)
   - `physical_progress`: 1,738 present (99.77%), 4 source missing (0.23%)
   - `revised_cost`: 505 present (28.99%), 1,237 source missing (71.01%)
   - `revised_completion_date`: 645 present (37.03%), 1,097 source missing (62.97%)
4. **`table6-eight-column-approval-only-v1`** (Jul 2025, 791 rows):
   - `start_date`: **791 structurally absent** (100%)
   - `ministry`: 791 present (100%)
   - `physical_progress`: 777 present (98.23%), 14 source missing (1.77%)
   - `revised_cost`: 791 present (100%)
   - `revised_completion_date`: 363 present (45.89%), 428 source missing (54.11%)
5. **`table6-eight-column-v1`** (Aug 2025–Jul 2026, 17,810 rows):
   - Standard 8-column layout with no structurally absent fields.
   - `start_date`: 17,789 present (99.88%), 21 source missing (0.12%)
   - `ministry`: 17,810 present (100%)
   - `physical_progress`: 16,882 present (94.79%), 928 source missing (5.21%)
   - `revised_cost`: 15,798 present (88.70%), 2,012 source missing (11.30%)
   - `revised_completion_date`: 11,218 present (62.99%), 6,592 source missing (37.01%)

### Inspection of Uncoded Datasets (April & May 2024)

- **April 2024 (`data/cleaned_uncoded/projects_2024_04.csv`)**: 1,838 rows.
  - Structurally absent: `project_code` (100%), `agency` (100%), `ministry` (100%), `start_date` (100%), `physical_progress` (100%).
  - Present: `project_name` (1,838), `sector` (1,838), `state` (1,838), `approval_date` (1,838), `original_cost` (1,838), `cumulative_expenditure` (1,838).
  - Sparse: `revised_cost` (426 / 23.18%), `revised_completion_date` (608 / 33.08%).
- **May 2024 (`data/cleaned_uncoded/projects_2024_05.csv`)**: 1,812 rows.
  - Same structural absence. Retains source defect rows as explicit rejects.
- **Analytical Treatment**: These uncoded months provide aggregate volume context but **cannot provide project-level continuity**. They must not be linked using synthetic surrogate keys or fuzzy name heuristics.

---

## 5. Observable Event Counts & Longitudinal Change Rates

### Adjacent Month-to-Month Change Events (40,359 Pairs)

| Target Field | Comparable Pairs | Increases / Extensions | Decreases / Reductions | Unchanged Pairs | Positive-to-Zero Resets |
|---|---:|---:|---:|---:|---:|
| **`revised_cost`** | 21,911 | **224** (1.02%) | **115** (0.52%) | 21,572 (98.45%) | N/A |
| **`revised_completion_date`** | 18,597 | **2,737** (14.72%) | **121** (0.65%) | 15,739 (84.63%) | N/A |
| **`physical_progress`** | 35,569 | **17,525** (49.27%) | **674** (1.89%) | 17,370 (48.83%) | N/A |
| **`cumulative_expenditure`** | 40,359 | **22,158** (54.90%) | **750** (1.86%) | 17,451 (43.24%) | 20 (0.05%) |

### Project-Level Concentration of Revisions

- **Revised Cost**:
  - Projects with $\ge 1$ cost change: **289** (6.55% of unique projects)
  - Projects with $\ge 2$ cost changes: **42** (0.95% of unique projects)
  - Projects with $\ge 3$ cost changes: **8** (0.18% of unique projects)
  - Upward magnitude: median = **Rs 167.19 crore**, mean = **Rs 616.42 crore**, max = **Rs 13,334.00 crore**.
- **Schedule Revisions**:
  - Projects with $\ge 1$ schedule change: **1,428** (32.37% of unique projects)
  - Projects with $\ge 2$ schedule changes: **748** (16.95% of unique projects)
  - Projects with $\ge 3$ schedule changes: **368** (8.34% of unique projects)
  - Upward extension magnitude: median = **3 months**, mean = **6.08 months**, max = **183 months**.

---

## 6. Forward Horizon Eligibility & Observable Event Rates

Evaluated strictly within same-era consecutive calendar months:

| Horizon | Dimension / Metric | Legacy Era (16 Months) | Six-Digit Era (13 Months) | Combined Canonical History |
|---|---|---:|---:|---:|
| **$H=1$** | **Calendar Coverage Ceiling** | 24,499 | 16,826 | **41,325** |
| | **Complete Project Trajectories** | 24,044 | 16,315 | **40,359** |
| | Cost Escalation ($T \to T+1$) | 64 / 5,596 (1.14%) | 160 / 16,315 (0.98%) | **224 / 21,911 (1.02%)** |
| | Schedule Extension ($T \to T+1$) | 641 / 7,091 (9.04%) | 2,096 / 11,506 (18.22%) | **2,737 / 18,597 (14.72%)** |
| | Progress Stagnation (End = Start) | 9,179 / 19,254 (47.67%) | 8,191 / 16,315 (50.21%) | **17,370 / 35,569 (48.83%)** |
| | Expenditure Stagnation (End = Start) | 11,402 / 24,044 (47.42%) | 6,049 / 16,315 (37.08%) | **17,451 / 40,359 (43.24%)** |
| **$H=3$** | **Calendar Coverage Ceiling** | 17,469 | 12,992 | **30,461** |
| | **Complete Project Trajectories** | 16,478 | 11,985 | **28,463** |
| | Cost Escalation ($T \to T+3$ Endpoint) | 121 / 3,751 (3.23%) | 249 / 11,985 (2.08%) | **370 / 15,736 (2.35%)** |
| | Cost Escalation (Any in Window) | 125 | 249 | **374** |
| | Schedule Extension ($T \to T+3$ Endpoint) | 906 / 4,429 (20.46%) | 3,166 / 7,938 (39.88%) | **4,072 / 12,367 (32.93%)** |
| | Schedule Extension (Any in Window) | 1,113 | 3,604 | **4,717** |
| | Progress Stagnation (End = Start) | 5,059 / 15,500 (32.64%) | 3,026 / 11,985 (25.25%) | **8,085 / 27,485 (29.42%)** |
| | Expenditure Stagnation (End = Start) | 5,034 / 16,478 (30.55%) | 2,258 / 11,985 (18.84%) | **7,292 / 28,463 (25.62%)** |
| **$H=6$** | **Calendar Coverage Ceiling** | 12,391 | 7,122 | **19,513** |
| | **Complete Project Trajectories** | 11,014 | 6,038 | **17,052** |
| | Cost Escalation ($T \to T+6$ Endpoint) | 149 / 2,407 (6.19%) | 289 / 6,038 (4.79%) | **438 / 8,445 (5.19%)** |
| | Cost Escalation (Any in Window) | 169 | 289 | **458** |
| | Schedule Extension ($T \to T+6$ Endpoint) | 921 / 2,952 (31.20%) | 1,721 / 3,751 (45.88%) | **2,642 / 6,703 (39.42%)** |
| | Schedule Extension (Any in Window) | 1,212 | 2,158 | **3,370** |
| | Progress Stagnation (End = Start) | 2,386 / 10,316 (23.13%) | 759 / 6,038 (12.57%) | **3,145 / 16,354 (19.23%)** |
| | Expenditure Stagnation (End = Start) | 2,425 / 11,014 (22.02%) | 572 / 6,038 (9.47%) | **2,997 / 17,052 (17.58%)** |
| **$H=12$** | **Calendar Coverage Ceiling** | 1,810 | 791 | **2,601** |
| | **Complete Project Trajectories** | 1,411 | 552 | **1,963** |
| | Cost Escalation ($T \to T+12$ Endpoint) | 34 / 290 (11.72%) | 118 / 552 (21.38%) | **152 / 842 (18.05%)** |
| | Cost Escalation (Any in Window) | 42 | 118 | **160** |
| | Schedule Extension ($T \to T+12$ Endpoint) | 198 / 397 (49.87%) | 183 / 320 (57.19%) | **381 / 717 (53.14%)** |
| | Schedule Extension (Any in Window) | 266 | 213 | **479** |
| | Progress Stagnation (End = Start) | 180 / 1,311 (13.73%) | 32 / 552 (5.80%) | **212 / 1,863 (11.38%)** |
| | Expenditure Stagnation (End = Start) | 208 / 1,411 (14.74%) | 19 / 552 (3.44%) | **227 / 1,963 (11.56%)** |

---

## 7. Trajectory Depth: Progress & Expenditure Dynamics

### Physical Progress Trajectories

- **Reported Observations**: 39,959 rows.
- **Projects with $\ge 1$ progress observation**: 4,203 (95.26%).
- **Projects with $\ge 6$ progress observations**: 3,643 (82.57%).
- **Projects with $\ge 12$ progress observations**: 1,970 (44.65%).
- **Progress Decreases / Downward Revisions**: **674 adjacent pairs** (1.89%). These represent real source data corrections and scope reassessments, not data corruption.
- **Unchanged Progress Runs (Stagnation)**:
  - 6,225 runs of $\ge 2$ consecutive months
  - 3,437 runs of $\ge 3$ consecutive months
  - 1,056 runs of $\ge 6$ consecutive months
  - 411 runs of $\ge 9$ consecutive months
  - 233 runs of $\ge 12$ consecutive months
  - Maximum continuous stagnation run: **13 months**.

### Cumulative Expenditure Trajectories & Zero-Expenditure Anomaly

- **Reported Observations**: 46,568 rows (100.00%).
- **Zero-Expenditure Observations**: **3,721 rows** (7.99% of total dataset).
- **Projects Ever Reporting Zero Expenditure**: **748 projects** (16.95%).
- **Projects Always Reporting Zero Expenditure**: **288 projects** (6.53%).
- **Zero Expenditure with Positive Physical Progress**: **1,917 rows** across **410 projects**.
- **Agency Concentration of Zero Expenditure**:
  - MoRTH: 1,520 zero expenditure rows (18.8%), 1,172 zero exp + positive progress (14.5%).
  - NHIDCL: 659 zero expenditure rows (15.2%), 442 zero exp + positive progress (10.2%).
  - PGCIL: 147 zero expenditure rows (17.8%), 55 zero exp + positive progress (6.7%).
  - MoRTH and NHIDCL account for **84.2%** of all zero-expenditure-with-positive-progress observations, reflecting distinct agency accounting conventions where contractors are reimbursed in milestone tranches rather than monthly book expenditure.

---

## 8. Categorical Coverage & Sparsity

| Dimension | Non-Missing Categories | Missing Rows | Extremely Sparse Categories (<10 Rows or <3 Projects) | Top Categories (% of Present Rows) |
|---|---:|---:|---:|---|
| **`ministry`** | 17 | 27,967 (60.06%) | 0 | MoRTH (42.88%), Railways (17.40%), Coal (8.69%), Petroleum (7.56%), Power (6.85%) |
| **`sector`** | 54 | 0 (0.00%) | 5 | Road Transport & Highways (52.22%), Railways (14.65%), Petroleum (4.15%), Power (3.86%) |
| **`agency`** | 369 | 0 (0.00%) | 92 | NHAI (18.70%), MoRTH (17.40%), NHIDCL (9.34%), NHAI Full Label (6.34%), PGCIL (1.77%) |
| **`state`** | 163 | 6 (0.01%) | 17 | Uttar Pradesh (4.55%), Maharashtra (3.88%), Andhra Pradesh (3.63%), Bihar (3.16%), Gujarat (3.12%) |

> [!NOTE]
> `ministry` is structurally absent in 100% of the legacy era (Jan 2024–Jun 2025). Any model incorporating `ministry` directly would experience 100% structural missingness on pre-July 2025 data. Sector labels exhibit casing and naming evolution across eras (e.g. `ROAD TRANSPORT AND HIGHWAYS` vs `Roads & Highways`).

---

## 9. Potential Feature Leakage Risk Classification

| Field | Classification | Leakage Rationale & Usage Boundary |
|---|---|---|
| `project_code` | `IDENTIFIER_ONLY` | Grouping key only. Not a predictive feature. |
| `legacy_ocms_code` | `IDENTIFIER_ONLY` | Provenance identifier; sparse and era-specific. |
| `pmgid` | `IDENTIFIER_ONLY` | Provenance identifier. |
| `project_name` | `IDENTIFIER_ONLY` | High-cardinality text that memorizes individual projects; requires grouped evaluation. |
| `agency` | `SAFE_BASE_FEATURE` | Source-reported category known at snapshot $T$. |
| `sector` | `SAFE_BASE_FEATURE` | Source-reported category known at snapshot $T$. |
| `state` | `SAFE_BASE_FEATURE` | Source-reported geography known at snapshot $T$. |
| `approval_date` | `SAFE_BASE_FEATURE` | Historical date known at $T$. (Project age derived from $T$ is safe). |
| `original_cost` | `SAFE_BASE_FEATURE` | Baseline budget set at approval; fully known at $T$. |
| `original_completion_date` | `SAFE_BASE_FEATURE` | Baseline schedule set at approval; fully known at $T$. |
| `ministry` | `CONDITIONALLY_SAFE` | Safe when present, but 100% structurally absent in legacy era. Encodes era boundary. |
| `start_date` | `CONDITIONALLY_SAFE` | Safe when present, but structurally absent through July 2025 (61.75% of dataset). |
| `cumulative_expenditure` | `CONDITIONALLY_SAFE` | Snapshot value at $T$ is safe. Future expenditure or future deltas are direct target leakage. |
| `physical_progress` | `CONDITIONALLY_SAFE` | Snapshot value at $T$ is safe. Future progress is direct target leakage. Structurally absent in Jan–Mar 2024. |
| `report_month` | `CONDITIONALLY_SAFE` | Essential for temporal slicing/evaluation; must not be used for random cross-validation. |
| `revised_cost` | `LIKELY_LEAKAGE_FOR_CERTAIN_TARGETS` | Safe as predictor at $T$ for *future* escalation, but direct target leakage if target is current cost revision. |
| `revised_completion_date` | `LIKELY_LEAKAGE_FOR_CERTAIN_TARGETS` | Safe as predictor at $T$ for *future* delay, but direct target leakage if target is current delay. |
| `*_raw` | `IDENTIFIER_ONLY` | Provenance representations; use parsed canonical values for modeling. |
| `source_*` metadata | `IDENTIFIER_ONLY` | Provenance only; encodes PDF page order and layout rather than project characteristics. |

---

## 10. Target Feasibility Summary

### Target 1: Future Cost Escalation ($T \to T+H$)
- **Feasibility**: **POOR / NOT RECOMMENDED FOR PRODUCTION MODELING YET**.
- **Key Limitations**: Extreme event rarity (only 224 adjacent events, 370 events at 3-month horizon, 438 at 6-month horizon). Low revision reporting rate in legacy era (revised cost missing in ~70–77% of rows). Severe right-censoring / survivorship bias in ongoing tables.
- **Remedy**: Extract **2023** to double legacy event counts, and extract **Completed Projects** tables to capture final ground-truth cost overruns.

### Target 2: Future Schedule Revision ($T \to T+H$)
- **Feasibility**: **MODERATE / FEASIBLE FOR EXPERIMENTAL PROTOTYPES**.
- **Key Characteristics**: High event density (2,737 adjacent events, 4,072 at 3-month horizon, 2,642 at 6-month horizon). Schedule revisions occur regularly across 1,428 unique projects.
- **Key Limitations**: Reporting regime shifts (average extension frequency is significantly higher in 2026 Table 6 than in 2024 Table 7).

### Target 3: Project Progress Stagnation ($\Delta \text{Progress} = 0$ over $H$ Months)
- **Feasibility**: **HIGH / FULLY FEASIBLE**.
- **Key Characteristics**: Very frequent and well-distributed (17,370 adjacent unchanged observations, 8,085 at 3-month horizon, 3,145 at 6-month horizon).
- **Key Limitations**: Jan–Mar 2024 structurally omit physical progress. Agency-specific zero-expenditure conventions require separate handling.

---

## 11. Safety Boundary & Next Actions

- **Prohibitions**: No final feature engineering, no label generation, no synthetic imputation, no model training, and no identifier crosswalk integration was performed.
- **Canonical Protection**: Canonical dataset [`data/processed/projects_monthly.csv`](file:///d:/coding/PAIMANA/data/processed/projects_monthly.csv) (`FE115E5FE71CC70552669FC4E0ACC2699B14CFE7545A319EEAEAF577E4DB95C3`) was accessed **strictly read-only**.
- **Generated Audit Artifacts**: Output JSON summaries are persisted under `data/validation/audit/` (`coverage_summary.json`, `field_missingness.json`, `event_audit.json`, `horizon_eligibility.json`, `category_coverage.json`, `leakage_risk.json`, `audit_manifest.json`).
- **Regression Suite**: **91/91 tests passing** (`python -m unittest discover -v`).
