# PAIMANA Model Target Specification

**Version**: 1.1 (Corrected Design)  
**Date**: 2026-08-29  
**Status**: Design document — no models trained, no canonical CSVs modified.  
**Prerequisite**: Read `reports/ongoing_completed_linkage_audit.md` before this document.

---

## Part B: Flagship Early-Warning Target Selection

### Evaluation Matrix

Four candidate target families were evaluated against operational utility, empirical event frequency, and class balance across continuous reporting segments:

| # | Target family | 3M positive events (effective / interval) | Class balance (3M interval) | Operational utility | Structural constraints |
|---|---|---:|---|---|---|
| 1 | **Schedule push-out** (reported extension relative to current commitment) | **7,845** (effective) / **4,930** (revised-only) | ~1 : 4.1 (legacy) / ~1 : 1.7 (modern) | High — primary PAIMANA monitoring KPI; triggers review | Effective variant requires valid `original_completion_date` (98.4% present); revised-only requires `revised_completion_date` (44% present) |
| 2 | Expenditure non-improvement / stagnation (cumulative expenditure non-increasing over 3M) | 11,504 (non-improvement) / 10,072 (strict $\Delta=0$) | ~1 : 2.5 (legacy) / ~1 : 4.3 (modern) | High — signals stall in financial disbursement | 100% field completeness; zero-reporting observations present |
| 3 | Physical progress non-improvement / stagnation (progress non-increasing over 3M) | 8,732 (non-improvement) / 8,085 (strict $\Delta=0$) | ~1 : 2.1 (legacy) / ~1 : 3.0 (modern) | Medium — useful physical milestone tracking | Structurally absent Jan–Nov 2023 and Jan–Mar 2024; valid Jun 2024 onward |
| 4 | Cost escalation (reported upward cost revision over 3M) | 1,094 (effective) / 461 (revised-only) | ~1 : 32.7 (legacy) / ~1 : 47.1 (modern) | High — high fiscal impact | Severe class imbalance; requires specialized evaluation |

### Selection: **Schedule Extension / Push-Out as Flagship Target**

**Rationale**:
- **Operational Alignment**: Tracking schedule revisions is central to PAIMANA's mandate. Predicting whether a project will report an outward revision within the next 3 months provides actionable early warning for monitoring authorities.
- **Tractable Class Balance**: With 7,845 positive events (19.65% positive rate) for the effective schedule push-out target at $H=3$, class imbalance is well-behaved ($1:1.7$ to $1:7.0$ depending on era/segment), allowing robust statistical learning without extreme resampling.
- **Broad Population Coverage**: The effective schedule target covers over 98% of ongoing project-months, capturing both first-time schedule revisions (from original schedule) and subsequent revisions (from already-revised schedules).
- **Clear Objective Trigger**: Schedule revisions represent explicit administrative date changes recorded in published tables.

**Secondary targets** (to be phased in following flagship baseline verification):
1. **Expenditure non-improvement / stagnation** (abundant events, complementary financial trajectory signal)
2. **Physical progress non-improvement / stagnation** (available Jun 2024 onward)
3. **Cost escalation** (high fiscal impact, rare event requiring cost-sensitive methods)

---

## Part C: Formal Target Definitions

All targets are defined relative to a **reference snapshot** at time $T$ (a `(project_code, report_month)` row in `projects_monthly.csv`) and a **forward horizon** $H \in \{1, 3, 6\}$ months.

### Mathematical Notation

- $T$: reference month of the prediction snapshot
- $T+k$: the $k$-th calendar month following $T$
- $\text{Obs}(p, m)$: the canonical record for project $p$ in `report_month` $m$ ($\text{None}$ if absent from the panel)
- $\text{Segment}(m)$: the continuous coded reporting segment containing month $m$:
  - **Segment 1**: `2023-01` $\to$ `2023-11` (11 coded months)
  - **Segment 2**: `2024-01` $\to$ `2024-03` (3 coded months)
  - **Segment 3**: `2024-06` $\to$ `2025-06` (13 coded months)
  - **Segment 4**: `2025-07` $\to$ `2026-07` (13 coded months)
- $\text{Continuous}(p, T, H)$: $\text{True}$ if and only if:
  1. $T$ and $T+H$ belong to the **same continuous segment** ($\text{Segment}(T) = \text{Segment}(T+H)$).
  2. $\text{Obs}(p, m) \neq \text{None}$ for all $m \in \{T, T+1, \dots, T+H\}$.
  3. No gap month (`2023-12`, `2024-04`, `2024-05`, or the `2025-06` $\to$ `2025-07` identifier boundary) falls within $[T, T+H]$.

---

### C.1 Target 1: Schedule Push-Out (Flagship Target)

#### Target Semantics: Two Defensible Formulations

A key semantic distinction exists in how baseline schedule commitments are defined:

1. **Variant A: Conservative Revised-Only Target (`target_revised_only_schedule_ext_H`)**
   - **Scope**: Evaluates only projects where `revised_completion_date(p, T)` is **already non-null** at reference month $T$.
   - **Question Answered**: *"Among projects that have already undergone at least one schedule revision, will a subsequent extension be reported within $H$ months?"*
   - **Population**: ~44.0% of all ongoing observations.
   - **Pros**: Strictly adheres to the explicit `revised_completion_date` column without combining fields.
   - **Cons**: Excludes the ~56.0% unrevised population; cannot predict first-time schedule revisions from the original schedule.

2. **Variant B: Effective Schedule Push-Out Target (`target_effective_schedule_ext_H`) — RECOMMENDED FLAGSHIP**
   - **Scope**: Evaluates all projects with a valid baseline schedule commitment at $T$, defined as:
     $$\text{eff\_date}(p, m) = \begin{cases} \text{revised\_completion\_date}(p, m) & \text{if non-null and non-empty} \\ \text{original\_completion\_date}(p, m) & \text{otherwise} \end{cases}$$
   - **Question Answered**: *"Relative to the project's current official completion commitment at $T$ (whether original or previously revised), will a later completion date be reported within $H$ months?"*
   - **Population**: 98.42% of all ongoing observations (all records with valid `original_completion_date`).
   - **Source-Faithful Semantics Justification**: In PAIMANA / OCMS reporting, projects without an entry in the revised date column operate under their original sanctioned completion schedule. When an initial revision occurs, a `revised_completion_date` later than `original_completion_date` is published for the first time. If no revision occurs, the project remains committed to its original date. Constructing $\text{eff\_date}$ does not invent missing data or impute unobserved values; it represents the project's effective administrative commitment at month $m$.

#### Operational Event Timing: Interval-Based vs. Endpoint-Based

For a forward horizon of $H$ months, an upward revision event can be evaluated in two ways:

- **Interval-Based Event ($\exists t \in \{T+1, \dots, T+H\}: \text{eff\_date}(p, t) > \text{eff\_date}(p, T)$) — RECOMMENDED**:
  - A positive event occurs if an upward revision is reported **at any point** during the forward $H$-month window.
  - *Operational justification*: An early-warning alert generated at month $T$ is operationally validated if the project reports an extension in month $T+1$, $T+2$, or $T+H$. The alert succeeded in flagging near-term risk. Requiring the elevated date to persist specifically at the $T+H$ endpoint is unnecessarily restrictive and sensitive to downstream administrative adjustments.
- **Endpoint-Based Event ($\text{eff\_date}(p, T+H) > \text{eff\_date}(p, T)$)**:
  - Compares only the snapshot at $T+H$ against $T$.
  - *Limitation*: Fails to register extensions that occur at $T+1$ or $T+2$ if the project subsequently completes, adjusts reporting, or exits before $T+H$.

#### Formal Positive and Negative Rules for Variant B (Effective, Interval)

**Positive Rule ($Y = 1$)**:
```
Continuous(p, T, H) == True
AND original_completion_date(p, T) is not null
AND EXISTS t in {T+1, ..., T+H} such that:
    eff_date(p, t) is not null
    AND eff_date(p, t) > eff_date(p, T)
```

**Negative Rule ($Y = 0$)**:
```
Continuous(p, T, H) == True
AND original_completion_date(p, T) is not null
AND FOR ALL t in {T+1, ..., T+H}:
    eff_date(p, t) is not null
    AND eff_date(p, t) <= eff_date(p, T)
```

**Ineligibility / Exclusion (No Label Assigned)**:
```
Continuous(p, T, H) == False
OR original_completion_date(p, T) is null
OR Obs(p, t) is None for any t in {T+1, ..., T+H} (right-censoring / disappearance)
OR eff_date(p, t) cannot be computed for any t in {T+1, ..., T+H}
```

#### Empirical Event Counts Across Continuous Segments

Evaluated strictly within continuous segments (no gap crossings):

| Horizon $H$ | Formulation | Total Eligible | Total Positive | Positive Rate | Legacy Pos Rate | Modern Pos Rate | Imbalance |
|---|---|---:|---:|---:|---:|---:|---|
| **$H=1$** | Variant B (Effective, Interval) | 55,574 | 4,683 | 8.43% | 5.34% (2,096/39,270) | 15.87% (2,587/16,304) | 1 : 10.9 |
| $H=1$ | Variant A (Revised-Only, Interval) | 24,532 | 3,146 | 12.82% | 8.10% (1,050/12,969) | 18.13% (2,096/11,563) | 1 : 6.8 |
| **$H=3$** | **Variant B (Effective, Interval) [PRIMARY]** | **39,932** | **7,845** | **19.65%** | **12.46% (3,483/27,947)** | **36.40% (4,362/11,985)** | **1 : 4.1** |
| $H=3$ | Variant B (Effective, Endpoint) | 39,911 | 7,632 | 19.12% | 11.78% (3,290/27,926) | 36.23% (4,342/11,985) | 1 : 4.2 |
| $H=3$ | Variant A (Revised-Only, Interval) | 17,010 | 4,930 | 28.98% | 19.39% (1,748/9,015) | 39.80% (3,182/7,995) | 1 : 2.5 |
| $H=3$ | Variant A (Revised-Only, Endpoint) | 16,078 | 4,819 | 29.97% | 20.31% (1,653/8,140) | 39.88% (3,166/7,938) | 1 : 2.3 |
| **$H=6$** | Variant B (Effective, Interval) | 23,534 | 5,813 | 24.70% | 19.01% (3,326/17,496) | 41.19% (2,487/6,038) | 1 : 3.0 |
| $H=6$ | Variant A (Revised-Only, Interval) | 9,653 | 3,557 | 36.85% | 31.11% (1,822/5,856) | 45.69% (1,735/3,797) | 1 : 1.7 |

> [!NOTE]
> Modern-era positive rates are substantially higher (36.40% vs 12.46% at $H=3$). This reflects observed differences in project portfolio maturity and reporting frequency between eras. Models must account for regime differences during validation.

---

### C.2 Target 2: Expenditure Non-Improvement and Stagnation

#### Semantic Distinction: Strict Stagnation vs. Non-Improvement

- **Strict Stagnation ($\Delta = 0$)**: Cumulative expenditure reported at $T+H$ is **exactly equal** to cumulative expenditure at $T$.
- **Reported Decrease ($\Delta < 0$)**: Cumulative expenditure reported at $T+H$ is **less than** at $T$ (observed in 3.54% of $H=3$ pairs, reflecting accounting reconciliations or annual fiscal year-end adjustments).
- **Non-Improvement ($\Delta \le 0$)**: Combines stagnation and decreases into a unified binary outcome: *"project reported no net expenditure progress over $H$ months."*

#### Target Definitions

1. **`target_exp_stagnation_H` (Strict Stagnation)**:
   - Positive ($Y=1$): $\text{Continuous}(p, T, H) \land \text{exp}(p, T+H) = \text{exp}(p, T)$
   - Negative ($Y=0$): $\text{Continuous}(p, T, H) \land \text{exp}(p, T+H) > \text{exp}(p, T)$
   - *Note*: Rows with $\text{exp}(p, T+H) < \text{exp}(p, T)$ are excluded from the binary evaluation of strict stagnation.

2. **`target_exp_non_improvement_H` (Non-Improvement — RECOMMENDED COMPREHENSIVE FORM)**:
   - Positive ($Y=1$): $\text{Continuous}(p, T, H) \land \text{exp}(p, T+H) \le \text{exp}(p, T)$
   - Negative ($Y=0$): $\text{Continuous}(p, T, H) \land \text{exp}(p, T+H) > \text{exp}(p, T)$

#### Base Eligibility Rule and Zero-Reporting Policy

- **Base Eligibility**: All observations where $\text{Continuous}(p, T, H) == \text{True}$ and `cumulative_expenditure` is present (100% field completeness in canonical data).
- **Zero-Reporting Observations**: 286 projects in the canonical panel report zero cumulative expenditure across all observed months, and 410 unique projects exhibit the `ZERO_EXPENDITURE_POSITIVE_PROGRESS` pattern (predominantly in MoRTH/NHAI records).
  - *Policy*: Do **not** apply an ad-hoc hard deletion of zero-reporters from the base target dataset.
  - Instead, include all valid observations in the primary base dataset and define **zero-reporter exclusions as explicit sensitivity / ablation analyses** (e.g., evaluating model performance on the subset of records where $\text{exp}(p, T) > 0$).

#### Empirical Counts (Continuous Segments)

| Horizon $H$ | Metric | Eligible Windows | Positive Count | Positive Rate |
|---|---|---:|---:|---:|
| $H=3$ | Strict Stagnation ($\Delta = 0$) | 40,456 | 10,072 | 24.90% |
| $H=3$ | Reported Decrease ($\Delta < 0$) | 40,456 | 1,432 | 3.54% |
| **$H=3$** | **Non-Improvement ($\Delta \le 0$)** | **40,456** | **11,504** | **28.44%** |
| $H=6$ | Strict Stagnation ($\Delta = 0$) | 23,852 | 3,918 | 16.43% |
| $H=6$ | Reported Decrease ($\Delta < 0$) | 23,852 | 1,067 | 4.47% |
| **$H=6$** | **Non-Improvement ($\Delta \le 0$)** | **23,852** | **4,985** | **20.90%** |

---

### C.3 Target 3: Physical Progress Non-Improvement and Stagnation

#### Structural Scope

Physical progress is structurally absent in Segment 1 (Jan–Nov 2023, milestone format) and Segment 2 (Jan–Mar 2024). Target 3 is definable **only within Segments 3 and 4** (June 2024 through July 2026).

#### Target Definitions

1. **`target_progress_stagnation_H` (Strict Stagnation)**: $\text{prog}(p, T+H) == \text{prog}(p, T)$
2. **`target_progress_non_improvement_H` (Non-Improvement — RECOMMENDED)**: $\text{prog}(p, T+H) \le \text{prog}(p, T)$

#### Empirical Counts (Segments 3 & 4 Only)

| Horizon $H$ | Metric | Eligible Windows | Positive Count | Positive Rate |
|---|---|---:|---:|---:|
| $H=3$ | Strict Stagnation ($\Delta = 0$) | 27,485 | 8,085 | 29.42% |
| $H=3$ | Reported Decrease ($\Delta < 0$) | 27,485 | 647 | 2.35% |
| **$H=3$** | **Non-Improvement ($\Delta \le 0$)** | **27,485** | **8,732** | **31.77%** |
| $H=6$ | Strict Stagnation ($\Delta = 0$) | 16,354 | 3,145 | 19.23% |
| $H=6$ | Reported Decrease ($\Delta < 0$) | 16,354 | 402 | 2.46% |
| **$H=6$** | **Non-Improvement ($\Delta \le 0$)** | **16,354** | **3,547** | **21.69%** |

---

### C.4 Target 4: Cost Escalation

#### Target Formulations

1. **Variant A: Revised-Only Cost Escalation (`target_revised_only_cost_esc_H`)**
   - Requires `revised_cost(p, T)` to be non-null.
   - Evaluates upward revision among already-revised projects.
2. **Variant B: Effective Cost Escalation (`target_effective_cost_esc_H`) — RECOMMENDED**
   - Baseline: $\text{eff\_cost}(p, m) = \text{revised\_cost}(p, m) \text{ if non-null else } \text{original\_cost}(p, m)$.
   - Positive event (Interval): $\exists t \in \{T+1, \dots, T+H\}: \text{eff\_cost}(p, t) > \text{eff\_cost}(p, T)$.

#### Empirical Event Counts (Continuous Segments)

| Horizon $H$ | Formulation | Total Eligible | Positive Count | Positive Rate | Imbalance |
|---|---|---:|---:|---:|---|
| $H=1$ | Variant B (Effective, Interval) | 56,284 | 531 | 0.94% | 1 : 105.0 |
| $H=1$ | Variant A (Revised-Only, Interval) | 25,543 | 270 | 1.06% | 1 : 93.6 |
| **$H=3$** | **Variant B (Effective, Interval)** | **40,456** | **1,094** | **2.70%** | **1 : 36.0** |
| $H=3$ | Variant A (Revised-Only, Interval) | 18,510 | 461 | 2.49% | 1 : 39.2 |
| **$H=6$** | Variant B (Effective, Interval) | 23,852 | 1,308 | 5.48% | 1 : 17.2 |
| $H=6$ | Variant A (Revised-Only, Interval) | 10,038 | 532 | 5.30% | 1 : 17.9 |

> [!CAUTION]
> Due to significant class imbalance (~1:36 at $H=3$), cost escalation models must not use raw accuracy. They require precision-recall AUC as the primary metric, probability calibration, and bootstrap confidence intervals.

---

## Part H: Role of the Completed Projects Dataset in Model v1

### Summary Policy

> [!IMPORTANT]
> The 876-row completed projects dataset (`projects_completed.csv`) **shall NOT be used as training data or as a source of ground-truth labels for early-warning models**.

### Rationale and Permitted Scope

1. **No Ground Truth for Interim Early Warning**: A project appearing in the completed table months or years later does not constitute ground truth for whether an interim 3-month schedule revision occurred during an earlier monitoring window.
2. **Structural Omissions in Completed Data**:
   - `actual_completion_date` is reported in only **107 of 876 records (12.21%)** and is structurally absent from all legacy layouts.
   - `revised_cost` is reported in only **170 of 876 records (19.41%)**.
   - `cumulative_expenditure` in completed tables reflects interim disbursements at publication time, not audited final settled project costs (72.15% report expenditure < original cost).
3. **Permitted Construct-Validity Role for the 107 Records**:
   - The 107 completed records with verified `actual_completion_date` may be used exclusively in a **separate, post-hoc construct-validity / downstream delay-risk sanity analysis**: evaluating whether risk scores emitted during ongoing monitoring correlate with realized physical delay ($\text{actual\_completion\_date} - \text{original\_completion\_date}$).
   - This analysis is descriptive and exploratory; it must not be conflated with the evaluation of rolling early-warning models.
4. **Metadata Annotations**:
   - For auditing and survivorship analysis, flags such as `eventually_completed` and `completion_report_month` may be joined as read-only metadata, but must be strictly excluded from all feature sets.

---

*Next: see `docs/feature_spec.md` for leakage-safe feature definitions.*  
*Then: see `docs/validation_strategy.md` for expanding-origin temporal validation design.*
