# PAIMANA Feature Specification

**Version**: 1.1 (Corrected Design)  
**Date**: 2026-08-29  
**Status**: Design document — no models trained, no canonical CSVs modified.  
**Prerequisite**: Read `docs/model_target_spec.md` before this document.

---

## Part D: Leakage-Safe Feature Framework

### D.1 Governing Principle

Every feature must be computable **exclusively from information available at or before reference snapshot time $T$**. A feature that incorporates information from $T+1$ or later — including future states of the target variable or administrative outcomes published after $T$ — constitutes **target leakage** and invalidates model evaluation.

Critical leakage boundaries in PAIMANA:
1. **Target Boundary**: At reference month $T$, `eff_date(p, T)` is a safe baseline feature. Any comparison against `eff_date(p, t)` for $t > T$ is strictly the target variable, never a feature.
2. **Trajectory Lookback**: Past trajectory features (e.g. `exp_delta_3m`, `n_prior_extensions`) must look strictly backward from $T$ ($T-K$ through $T$) within the same continuous segment.
3. **Completed Dataset Boundary**: No field from `projects_completed.csv` may be used as a feature, as completion records are published only after a project exits ongoing monitoring.

---

### D.2 Feature Classification Taxonomy

#### Tier 1: SAFE_AT_T — Known directly at prediction time $T$

These features are read directly from `Obs(p, T)` without derivation:

| Feature | Source Column | Availability / Constraints | Treatment |
|---|---|---|---|
| `sector` | `sector` | 100% present | Categorical; frequency or one-hot encode on training fold |
| `agency` | `agency` | 100% present | High cardinality (~600 raw strings); frequency encode on training fold |
| `state` | `state` | 99.98% present (11 source-missing rows) | Categorical; binary `state_is_missing` flag for nulls |
| `original_cost` | `original_cost` | 100% present | Numeric (Rs crore); `log1p(original_cost)` |
| `cumulative_expenditure_t` | `cumulative_expenditure` | 100% present | Numeric (Rs crore); `log1p(cumulative_expenditure_t)` |
| `revised_cost_t` | `revised_cost` | 45.30% present (54.70% source-missing) | Leave null + binary indicator `revised_cost_is_present` |
| `original_completion_date` | `original_completion_date` | 98.42% present | Date parsing baseline for schedule features |
| `revised_completion_date_t` | `revised_completion_date` | 44.01% present (55.99% source-missing) | Leave null + binary indicator `revised_date_is_present` |
| `physical_progress_t` | `physical_progress` | Present only Jun 2024–Jul 2026 (97.53% when supported) | Leave null in unsupported eras + binary indicator |
| `approval_date` | `approval_date` | 99.05% present (0.95% source-missing) | Date baseline for project age; null + indicator |
| `start_date` | `start_date` | **Present ONLY Aug 2025–Jul 2026** (27.53% overall) | Structurally absent in legacy & Jul 2025; null + indicator |

> [!IMPORTANT]
> **Start Date Availability Correction**: `start_date` is structurally absent from all 27 legacy months (Jan 2023–Jun 2025) and from July 2025 (`table6-eight-column-approval-only-v1`). It is reported **only from August 2025 through July 2026** (`table6-eight-column-v1`). It cannot be used in legacy models and must not be imputed.

> [!NOTE]
> `ministry` is structurally absent from all 27 legacy months (Jan 2023–Jun 2025). It is present only in the modern era (Jul 2025–Jul 2026).

---

#### Tier 2: SAFE_IF_DERIVED — Engineered features derived from $T$ and historical lookback

##### D.2.1 Time and Schedule Elapsed Features (Computed at $T$)

| Feature Name | Formulation | Handling of Missing Inputs |
|---|---|---|
| `project_age_months` | $\text{months\_between}(\text{approval\_date}, T)$ | Null if `approval_date` absent; binary flag `approval_date_is_missing` |
| `months_to_original_schedule` | $\text{months\_between}(T, \text{original\_completion\_date})$ | Positive = deadline in future; negative = past original deadline |
| `months_to_effective_schedule` | $\text{months\_between}(T, \text{eff\_date}(p, T))$ | Uses $\text{eff\_date}(p, T)$; reflects current operational deadline |
| `schedule_revision_lag_months` | $\text{months\_between}(\text{original\_completion\_date}, \text{revised\_completion\_date}(p, T))$ | Null if `revised_completion_date` is absent (unrevised project) |
| `schedule_has_been_revised` | $1 \text{ if } \text{revised\_completion\_date}(p, T) \text{ is not null else } 0$ | Binary indicator |
| `months_since_start` | $\text{months\_between}(\text{start\_date}, T)$ | **Modern Aug 2025–Jul 2026 only**; null in all other months |

##### D.2.2 Cost-Ratio Features (Computed at $T$)

| Feature Name | Formulation | Handling of Missing Inputs |
|---|---|---|
| `expenditure_to_original_cost_ratio` | $\text{cumulative\_expenditure}(p, T) / \text{original\_cost}(p, T)$ | 100% available (both inputs complete) |
| `revised_to_original_cost_ratio` | $\text{revised\_cost}(p, T) / \text{original\_cost}(p, T)$ | Null if `revised_cost` absent; indicates sanctioned escalation level |
| `cost_has_been_revised` | $1 \text{ if } \text{revised\_cost}(p, T) \text{ is not null else } 0$ | Binary indicator |

##### D.2.3 Longitudinal Trajectory Features (Lookback $T-K$ through $T$)

Lookback features require prior snapshots of project $p$ **within the same continuous segment**. If any required prior month is outside the continuous segment or unobserved for project $p$, the feature evaluates to null:

| Feature Name | Lookback $K$ | Formulation | Transform / Representation |
|---|---|---|---|
| `exp_delta_1m` | 1 month | $\text{exp}(p, T) - \text{exp}(p, T-1)$ | **Signed-log**: $\text{sign}(x) \cdot \ln(1 + |x|)$ or raw |
| `exp_delta_3m` | 3 months | $\text{exp}(p, T) - \text{exp}(p, T-3)$ | **Signed-log**: $\text{sign}(x) \cdot \ln(1 + |x|)$ or raw |
| `past_exp_stagnant_3m` | 3 months | $1 \text{ if } \text{exp}(p, T) == \text{exp}(p, T-3) \text{ else } 0$ | Binary indicator (past predictor, NOT target) |
| `past_progress_delta_3m` | 3 months | $\text{prog}(p, T) - \text{prog}(p, T-3)$ | Signed-log or raw; null in unsupported eras |
| `past_progress_stagnant_3m` | 3 months | $1 \text{ if } \text{prog}(p, T) == \text{prog}(p, T-3) \text{ else } 0$ | Binary indicator |
| `n_prior_schedule_extensions` | Segment history | Count of upward $\text{eff\_date}$ revisions observed up to $T$ | Integer count |
| `n_prior_cost_revisions` | Segment history | Count of upward $\text{revised\_cost}$ revisions observed up to $T$ | Integer count |
| `observed_tenure_months` | Segment history | Total observed snapshots for project $p$ within current segment | Integer count |

> [!CAUTION]
> **No Plain Log on Delta Features**: Delta features such as `exp_delta_1m` and `progress_delta_3m` can take negative values (due to reported decreases or audit reconciliations). Applying plain `log1p(x)` will result in `NaN` on negative values. Use the **signed-log transform** $\text{sign}(x) \cdot \ln(1 + |x|)$ or leave values raw.

##### D.2.4 Optional Drift / Seasonality Features (Ablation Candidates)

These temporal features capture calendar patterns and reporting seasonality, but must be evaluated via **explicit ablation studies** rather than included as unquestioned core predictors:

| Feature Name | Definition | Evaluation Policy |
|---|---|---|
| `month_of_fiscal_year` | 1 to 12 (Apr=1 ... Mar=12) | Optional; test whether fiscal seasonality aids generalization |
| `is_fiscal_yearend` | $1 \text{ if month } \in \{\text{Feb, Mar}\} \text{ else } 0$ | Optional; captures fiscal year-end reconciliation periods |
| `report_month_index` | Monotonic integer index of `report_month` | **High risk of overfitting to sample-period trends**; ablation only |
| `identifier_regime` | Binary (`LEGACY` vs `MODERN`) | **Relevant ONLY for pooled cross-era models**; constant and omitted in per-regime models |

---

#### Tier 3: LEAKAGE_DO_NOT_USE — Strictly Prohibited

| Feature / Column | Leakage Mechanism |
|---|---|
| Any target variable at $T+k$ ($k > 0$) | Future target outcome |
| `actual_completion_date` (from completed data) | Outcome published post-exit |
| `eventually_completed` / `completion_report_month` | Encodes future panel exit status |
| `source_file`, `source_page`, `source_row_number` | Extraction artifact provenance |
| `*_raw` representation columns | Redundant unparsed strings |
| `project_code` / `project_name` | Entity memorization risk |
| `legacy_ocms_code`, `pmgid` | Sparse provenance keys |

---

### D.3 Categorical Encoding and Imputation Standards for v1

#### 1. Categorical Encoding Protocol
- **Training-Fold Only**: All categorical encoders (frequency encoders, one-hot encoders, or target encoders) **must be fit strictly on the training fold**. Applying encoders across the full dataset before splitting constitutes data leakage.
- **v1 Recommendation**: Use **frequency encoding** (mapping categories to their training-set prevalence) or **simple one-hot encoding** (for top-N categories, with an `OTHER` bucket for infrequent categories).
- **Target Encoding**: Target encoding is deferred as an optional later technique; if used, it must be computed strictly out-of-fold on training data only.

#### 2. Missing Value Imputation Policy
- **Structurally Absent Fields** (`ministry`, `start_date` in legacy; `physical_progress` in early legacy): Leave null; provide a binary `<field>_is_missing = 1` indicator. **Do NOT impute zeros or artificial dates.**
- **Source-Missing Revision Fields** (`revised_cost`, `revised_completion_date`): Null represents an unrevised state. Encode via binary indicators (`schedule_has_been_revised = 0`, `cost_has_been_revised = 0`). **Do NOT impute.**
- **Source-Missing Baseline Dates** (`approval_date` missing in 0.95% of rows): **Do NOT impute with median project age in v1.** Leave null and provide `approval_date_is_missing = 1`.

---

## Part E: Regime-Specific Feature Sets

Because the legacy and modern eras differ structurally in column presence, model development should maintain **two parallel, regime-specific feature sets**:

### Feature Set A: Legacy Regime (Segments 1–3, Jan 2023 – Jun 2025)
- **Included Base Features**: `sector`, `agency`, `state`, `original_cost`, `cumulative_expenditure`, `original_completion_date`, `revised_completion_date` (with indicator), `revised_cost` (with indicator), `approval_date` (with indicator).
- **Included Trajectory Features**: `exp_delta_1m`, `exp_delta_3m`, `past_exp_stagnant_3m`, `n_prior_schedule_extensions`, `n_prior_cost_revisions`, `observed_tenure_months`.
- **Excluded**: `ministry` (absent), `start_date` (absent), `physical_progress` (absent in Segments 1 & 2; restricted to Segment 3 if analyzed separately).

### Feature Set B: Modern Regime (Segment 4, Jul 2025 – Jul 2026)
- **Included Base Features**: All Feature Set A features plus `ministry`, `start_date` (Aug 2025–Jul 2026), and `physical_progress`.
- **Included Trajectory Features**: All Feature Set A trajectory features plus `past_progress_delta_3m` and `past_progress_stagnant_3m`.

---

*Next: see `docs/validation_strategy.md` for expanding-origin walk-forward evaluation design.*
