# Ongoing ↔ Completed Linkage Audit (Exact Project Identifiers)

**Audit date**: 2026-08-29  
**Method**: Read-only exact identifier join. No fuzzy matching, no crosswalk integration.  
**Canonical inputs** (hashes verified before and after — unchanged):

| File | Rows | SHA-256 |
|---|---:|---|
| `data/processed/projects_monthly.csv` | 64,608 | `9512A9881E17DFDED6E182D87A8DFB1C4EDBD36C0D9B8A7DA9FD1ABB7E002FBF` |
| `data/processed/projects_completed.csv` | 876 | `89BEA84FD68A22E327090C1E4E4533F5BCD745ADCA61EB4E66172EE9023BB910` |

---

## 1. Summary Findings

| Metric | Value |
|---|---:|
| Unique ongoing project codes | 4,738 |
| Unique completed project codes | 876 (all distinct — pure cross-section) |
| **Exact-ID matches (ongoing ∩ completed)** | **876 (100.0%)** |
| Completed projects absent from ongoing panel | **0 (0.0%)** |
| Ongoing codes never appearing in completed | 3,862 (81.5%) |

Every completed project has at least one ongoing snapshot in the panel.
The two datasets are fully linkable by exact `project_code` with no omissions on the completed side.

---

## 2. Linkage by Identifier Regime

| Regime | Completed projects | Ongoing codes | Exact matches | Match rate |
|---|---:|---:|---:|---:|
| Legacy `N########` + 9-digit | 617 | 2,495 | 617 | **100.0%** |
| Modern 6-digit | 259 | 2,243 | 259 | **100.0%** |
| **Total** | **876** | **4,738** | **876** | **100.0%** |

The identifier regime split does not create any linkage gap within each regime.
The zero cross-era overlap in the ongoing panel is preserved: no legacy completed
project appears under a modern code or vice versa.

---

## 3. Longitudinal Observation Depth for Matched Projects

Each of the 876 matched projects has a known number of monthly snapshots in the
ongoing panel before disappearance:

| Depth bucket | Projects | % of 876 |
|---|---:|---:|
| 1–2 observations | 19 | 2.2% |
| 3–5 observations | 162 | 18.5% |
| 6–11 observations | 303 | 34.6% |
| 12–17 observations | 143 | 16.3% |
| 18–26 observations | 249 | 28.4% |
| 27 (full legacy era) | 0 | 0.0% |

**Summary**: Min = 1, Max = 26, Median = 10, Mean = 11.99 months of history per completed project.

- 97.8% of completed projects have >= 3 ongoing snapshots.
- 79.3% have >= 6 ongoing snapshots.
- 44.7% have >= 12 ongoing snapshots.
- No completed project has a full 27-month legacy history (max = 26, one gap month excluded).

---

## 4. Reporting Chronology: Completion Month vs. Last Ongoing Month

The completed projects table uses `report_month` to record when the Flash Report
announcing completion was published, not the physical completion date.

| Lag (completed `report_month` − last ongoing `report_month`) | Projects | % |
|---|---:|---:|
| −5 (completion published 5 months BEFORE last ongoing) | 1 | 0.1% |
| −3 (completion published 3 months BEFORE last ongoing) | 1 | 0.1% |
| **+1 (completion published 1 month after last ongoing)** | **836** | **95.4%** |
| +2 | 20 | 2.3% |
| +3 | 18 | 2.1% |

**Dominant pattern**: 95.4% of projects disappear from the ongoing table in month T
and appear in the completed table in month T+1. The two-step construction
`terminal_ongoing_snapshot → completed_record` is reliable for 836/876 projects.

### 4.1 Two Anomalous Projects (Negative Lag)

> [!WARNING]
> Two projects have `completed.report_month < last ongoing.report_month` —
> they appear in the completed table *before* their final ongoing appearance.

| `project_code` | Completed month | Last ongoing month | Lag | Observation |
|---|---|---|---:|---|
| `N24001682` | 2025-03 | 2025-06 | −3 | Progress reported as 15.1% at last ongoing; actual_completion_date absent; re-listed Apr–Jun 2025 in ongoing tables following completed table appearance. Consistent with phased contract reporting or administrative adjustment. |
| `705635` | 2026-02 | 2026-07 | −5 | Progress reported as 59% at 2026-07; actual_completion_date reported as 2026-03. Consistent with partial-section completion reporting (Trivandrum–Kanyakumari). |

**Governance**: These are source-faithful anomalies, not extraction errors.
Flag both as `COMPLETION_REAPPEAR_ANOMALY`. Do not use as "never completed"
negatives and review carefully before using as positives.

---

## 5. Terminal Ongoing Snapshot Distribution

The last ongoing month for each of the 876 matched projects spans the full panel:

```
2023-03:  20    2024-01:  20    2025-01:  41    2026-01:   8
2023-04:  10    2024-02:  32    2025-02:  16    2026-02:  25
2023-05:  54    2024-03:  18    2025-03:  34    2026-03:   9
2023-06:   7    2024-06:  21    2025-04:  40    2026-04:  16
2023-07:  15    2024-07:  16    2025-05:  42    2026-05: 137
2023-08:  48    2024-08:  13    2025-06:   1    2026-06:  18
2023-09:  29    2024-09:  62    2025-08:   6    2026-07:   1
2023-10:  11    2024-10:  12    2025-09:   6
2023-11:  13    2024-11:  22    2025-10:  13
                2024-12:  20    2025-11:  17
                                2025-12:   3
```

Large concentrations at 2024-09 (62) and 2026-05 (137) reflect high-completion-
announcement months. Temporal validation splits must be based on calendar time,
not project count, to avoid leakage.

---

## 6. Completed Dataset Field Availability for Linked Records

| Field | Available | Notes |
|---|---:|---|
| `original_cost` | 851 (97.1%) | Primary cost baseline |
| `original_completion_date` | 828 (94.5%) | Scheduled completion baseline |
| `cumulative_expenditure` | ~875 (see note) | Interim disbursement proxy only |
| `revised_completion_date` | 256 (29.2%) | Revised schedule at completion announcement |
| `actual_completion_date` | **107 (12.2%)** | **Critical gap: 87.8% absent** |
| `revised_cost` | **170 (19.4%)** | **Critical gap: 80.6% absent in legacy** |

> [!CAUTION]
> `actual_completion_date` is structurally absent from all legacy layout records (table2 and table3-legacy-six-column), covering 617/876 projects. It cannot serve as a general ground-truth label without restricting scope to modern-layout (Sept 2025–Jul 2026) projects only.

> [!CAUTION]
> `cumulative_expenditure` in the completed table mirrors the terminal ongoing expenditure for most projects and reflects an interim disbursement at reporting time — not an audited final settled cost. 72.15% of completed projects show expenditure < original_cost (median ratio 0.8353).

---

## 7. Sector and Agency Coverage

### Sector distribution of 876 matched completed projects

| Sector | Count | % |
|---|---:|---:|
| ROAD TRANSPORT AND HIGHWAYS | 292 | 33.3% |
| Roads & Highways | 154 | 17.6% |
| PETROLEUM | 97 | 11.1% |
| RAILWAYS | 81 | 9.2% |
| POWER | 78 | 8.9% |
| HEALTH AND FAMILY WELFARE | 22 | 2.5% |
| WATER RESOURCES | 21 | 2.4% |
| Transmission & Distribution | 19 | 2.2% |
| Oil & Gas | 18 | 2.1% |
| Railways | 15 | 1.7% |
| COAL | 11 | 1.3% |
| Other (22 sectors) | 68 | 7.8% |

"ROAD TRANSPORT AND HIGHWAYS" and "Roads & Highways" are source-faithful distinct
labels from different layout eras and must not be silently merged for encoding.
Road-sector dominance (>=50%) means any completion-labelled training set is
implicitly road-sector biased unless sector stratification is applied.

### Top agencies (completed projects)
NHAI (177), MoRTH (142), MoRTH-State PWDs (64), NHIDCL (51), NHAI-legacy-label (50)

---

## 8. Conclusions for ML Design

### What the linkage enables

1. **Exact-ID terminal snapshot retrieval**: For any completed project, its full
   time series can be retrieved by exact `project_code` join — no fuzzy matching needed.

2. **Trajectory feature construction**: The full series of `cumulative_expenditure`,
   `physical_progress`, `revised_completion_date`, and `revised_cost` up to the
   terminal snapshot is available for 97.8% of completed projects (>= 3 observations).

3. **Bounded training windows**: Last ongoing month is known exactly for all 876
   matched projects, enabling strict data cutoffs that prevent completion-outcome leakage.

4. **Qualified class label availability**:
   - Schedule slippage proxy: `original_completion_date` (94.5%), `revised_completion_date` (29.2%)
   - Actual delay: `actual_completion_date` is available for only 12.2% (107 records) and is structurally absent in legacy layouts. These 107 records cannot serve as direct evaluation labels for whether a 3M revision occurred in the ongoing panel, but may be used in separate construct-validity / downstream delay-risk sanity analysis.
   - Cost outcome: no audited final cost field exists in either canonical dataset

### What the linkage does NOT enable

- Definitive ground-truth "completed on time / late" labels for >87.8% of projects
- Ground-truth evaluation labels for whether an interim 3M schedule revision occurred
- Definitive "cost overrun / within budget" labels for >80.6% of projects
- Realized outcomes for 3,862 ongoing-only projects (right-censored)
- Any cross-era (legacy <-> modern) linkage (zero overlap is structural)

### Governance flags for ML use

| Flag | Projects | Recommended disposition |
|---|---:|---|
| `COMPLETION_REAPPEAR_ANOMALY` | 2 | Exclude from "never completed" negatives; review before using as positives |
| `ACTUAL_DATE_ABSENT` | 769 | Cannot use `actual_completion_date` as label; proxy metrics only |
| `REVISED_COST_ABSENT_AT_COMPLETION` | 706 | Cannot compute formal cost escalation from completed table |
| `LOW_OBSERVATION_DEPTH` (1–2 obs) | 19 | Exclude from feature-dependent trajectory models |
| `CROSS_ERA_ISOLATION` | all 876 | Legacy and modern completed must not be pooled without regime indicator |

---

*Both canonical dataset hashes verified unchanged after audit execution.*  
*See `docs/model_target_spec.md` for formal target definitions using this linkage structure.*
