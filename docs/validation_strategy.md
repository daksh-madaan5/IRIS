# PAIMANA Validation Strategy

**Version**: 1.1 (Corrected Design)  
**Date**: 2026-08-29  
**Status**: Design document — no models trained, no canonical CSVs modified.  
**Prerequisite**: Read `docs/model_target_spec.md` and `docs/feature_spec.md` before this document.

---

## Part F: Temporal Validation Architecture

### F.1 Continuous Reporting Segments (Ground Truth Timeline)

The 40 coded historical months in `projects_monthly.csv` are partitioned into **four continuous reporting segments** separated by explicit historical gaps and administrative discontinuities:

```
[SEGMENT 1: 11 Coded Months]
2023-01, 2023-02, 2023-03, 2023-04, 2023-05, 2023-06, 2023-07, 2023-08, 2023-09, 2023-10, 2023-11
  |--- [GAP: 2023-12 Summary Only]

[SEGMENT 2: 3 Coded Months]
2024-01, 2024-02, 2024-03
  |--- [GAP: 2024-04 & 2024-05 Uncoded Annexure XVIII]

[SEGMENT 3: 13 Coded Months]
2024-06, 2024-07, 2024-08, 2024-09, 2024-10, 2024-11, 2024-12, 2025-01, 2025-02, 2025-03, 2025-04, 2025-05, 2025-06
  |=== [BOUNDARY: 2025-06 -> 2025-07 MOSPI Identifier Redesign (Zero Exact ID Overlap)]

[SEGMENT 4: 13 Coded Months]
2025-07, 2025-08, 2025-09, 2025-10, 2025-11, 2025-12, 2026-01, 2026-02, 2026-03, 2026-04, 2026-05, 2026-06, 2026-07
```

**Total Legacy Coded Months** (Segments 1–3): $11 + 3 + 13 = \mathbf{27}$ coded months.  
*(Note: A nominal calendar span of Jan 2023 to Sep 2024 contains $11 + 3 + 4 = \mathbf{18}$ coded months, not 20).*  
**Total Modern Coded Months** (Segment 4): $\mathbf{13}$ coded months.

---

### F.2 Hard Rules of Longitudinal Validation

> [!CAUTION]
> Violating any of these rules introduces structural leakage or evaluates across unbridgeable data regimes:

1. **Rule 1: No Random Splitting**: Never use random row-level or project-level train/test splits. Evaluation must follow strict chronological order.
2. **Rule 2: Segment Containment**: Every prediction window $[T, T+H]$ and every training target realization window $[T_{\text{train}}, T_{\text{train}}+H]$ **must reside entirely within a single continuous segment**. No window may cross `2023-12`, `2024-04/05`, or `2025-06` $\to$ `2025-07`.
3. **Rule 3: Label Embargo ($H$-Month Lag)**: When training a model to evaluate at decision origin $T_{\text{eval}}$, the training set may only contain reference snapshots $T_{\text{train}} \le T_{\text{eval}} - H$. Training labels realized during $(T_{\text{eval}} - H, T_{\text{eval}}]$ are unobserved at decision time $T_{\text{eval}}$ and must not be used for model fitting.
4. **Rule 4: Historical Lookback Containment**: Trajectory features (e.g. `exp_delta_3m`) must look back strictly within the current segment. If a project was not observed at $T-3$ within the same segment, the feature is null.

---

### F.3 Recommended Strategy: Walk-Forward (Expanding-Origin) Evaluation

Rather than an arbitrary fixed split, model performance must be evaluated using **expanding-origin walk-forward validation**.

#### Mechanism
At each evaluation origin $T_{\text{eval}}$:
1. **Training Pool**: All eligible historical windows $[T_{\text{train}}, T_{\text{train}}+H]$ from prior segments and from the current segment where $T_{\text{train}} \le T_{\text{eval}} - H$.
2. **Feature Fitting**: All categorical encoders and numeric scalers are fit **strictly on the training pool**.
3. **Model Fitting**: Models are trained on the training pool.
4. **Prediction**: The trained model generates risk scores for all eligible projects observed at $T_{\text{eval}}$.
5. **Evaluation**: Predictions are compared against the true realization occurring over $[T_{\text{eval}}+1, \dots, T_{\text{eval}}+H]$.

---

### F.4 Concrete Walk-Forward Evaluation Origins for $H=3$

#### 1. Legacy Regime (Segments 1–3)

- **Segment 1** (`2023-01` to `2023-11`, 11 months):
  - Available $H=3$ origins: `2023-01` through `2023-08` (8 origins).
  - *Warm-Up Training*: Origins `2023-01` through `2023-04` (labels mature by `2023-04` $\dots$ `2023-07`).
  - *Evaluation Folds in Segment 1*:
    - **Fold L1.1**: $T_{\text{eval}} = \text{2023-07}$ (Train: $T_{\text{train}} \in [\text{2023-01} \dots \text{2023-04}]$)
    - **Fold L1.2**: $T_{\text{eval}} = \text{2023-08}$ (Train: $T_{\text{train}} \in [\text{2023-01} \dots \text{2023-05}]$)
- **Segment 2** (`2024-01` to `2024-03`, 3 months):
  - Length is 3 months; requires $\ge 4$ months for $H=3$. **Cannot host $H=3$ evaluation or training windows.**
- **Segment 3** (`2024-06` to `2025-06`, 13 months):
  - Available $H=3$ origins: `2024-06` through `2025-03` (10 origins).
  - *Training Pool*: All 8 mature origins from Segment 1 (`2023-01` $\dots$ `2023-08`) plus mature Segment 3 origins ($T_{\text{train}} \le T_{\text{eval}} - 3$).
  - *Evaluation Folds in Segment 3*:
    - **Fold L3.1**: $T_{\text{eval}} = \text{2024-06}$ (Train: all 8 Segment 1 origins; 0 Segment 3 origins)
    - **Fold L3.2**: $T_{\text{eval}} = \text{2024-07}$ (Train: Segment 1 origins)
    - **Fold L3.3**: $T_{\text{eval}} = \text{2024-08}$ (Train: Segment 1 origins)
    - **Fold L3.4**: $T_{\text{eval}} = \text{2024-09}$ (Train: Segment 1 + `2024-06`)
    - **Fold L3.5**: $T_{\text{eval}} = \text{2024-10}$ (Train: Segment 1 + `2024-06` $\dots$ `2024-07`)
    - **Fold L3.6**: $T_{\text{eval}} = \text{2024-11}$ (Train: Segment 1 + `2024-06` $\dots$ `2024-08`)
    - **Fold L3.7**: $T_{\text{eval}} = \text{2024-12}$ (Train: Segment 1 + `2024-06` $\dots$ `2024-09`)
    - **Fold L3.8**: $T_{\text{eval}} = \text{2025-01}$ (Train: Segment 1 + `2024-06` $\dots$ `2024-10`)
    - **Fold L3.9**: $T_{\text{eval}} = \text{2025-02}$ (Train: Segment 1 + `2024-06` $\dots$ `2024-11`)
    - **Fold L3.10**: $T_{\text{eval}} = \text{2025-03}$ (Train: Segment 1 + `2024-06` $\dots$ `2024-12`)

#### 2. Modern Regime (Segment 4)

- **Segment 4** (`2025-07` to `2026-07`, 13 months):
  - Available $H=3$ origins: `2025-07` through `2026-04` (10 origins).
  - *Warm-Up Training*: Origins `2025-07` through `2025-09` (labels mature by `2025-10` $\dots$ `2025-12`).
  - *Evaluation Folds in Modern Regime*:
    - **Fold M1**: $T_{\text{eval}} = \text{2025-12}$ (Train: $T_{\text{train}} \in [\text{2025-07} \dots \text{2025-09}]$)
    - **Fold M2**: $T_{\text{eval}} = \text{2026-01}$ (Train: $T_{\text{train}} \in [\text{2025-07} \dots \text{2025-10}]$)
    - **Fold M3**: $T_{\text{eval}} = \text{2026-02}$ (Train: $T_{\text{train}} \in [\text{2025-07} \dots \text{2025-11}]$)
    - **Fold M4**: $T_{\text{eval}} = \text{2026-03}$ (Train: $T_{\text{train}} \in [\text{2025-07} \dots \text{2025-12}]$)
    - **Fold M5**: $T_{\text{eval}} = \text{2026-04}$ (Train: $T_{\text{train}} \in [\text{2025-07} \dots \text{2026-01}]$)

---

### F.5 Severe Constraints on Longer Horizons ($H=6$ and $H=12$)

Longer forecasting horizons are heavily constrained by continuous segment lengths:

| Segment | Coded Months | Available Origins for $H=1$ | Available Origins for $H=3$ | Available Origins for $H=6$ | Available Origins for $H=12$ |
|---|---:|---:|---:|---:|---:|
| **Segment 1** (2023-01 $\to$ 2023-11) | 11 | 10 | 8 | 5 | **0** (length < 13) |
| **Segment 2** (2024-01 $\to$ 2024-03) | 3 | 2 | **0** | **0** | **0** |
| **Segment 3** (2024-06 $\to$ 2025-06) | 13 | 12 | 10 | 7 | **1** (`2024-06` only) |
| **Segment 4** (2025-07 $\to$ 2026-07) | 13 | 12 | 10 | 7 | **1** (`2025-07` only) |

#### Operational Implications:
- **$H=12$ is practically unviable**: Across the entire 40-month repository history, only **2 total origins** can evaluate a 12-month forward window (`2024-06` in legacy and `2025-07` in modern). With zero training history prior to these origins within their respective segments, $H=12$ cannot be evaluated via walk-forward validation.
- **$H=6$ is severely restricted in the Modern Regime**: Segment 4 has only 7 eligible origins (`2025-07` $\dots$ `2026-01`). With an $H=6$ label embargo, the first test fold cannot occur until `2026-01` ($T_{\text{train}} = \text{2025-07}$ only), leaving only **1 single test evaluation fold** (`2026-01`).
- **Conclusion**: **$H=3$ is the primary robust operational horizon** supported by the dataset structure.

---

## Part G: Evaluation Metrics and Baseline Requirements

### G.1 Primary Metric: Precision-Recall AUC (PR-AUC)

Due to class imbalance across all target families (ranging from 1:1.7 to 1:105), raw accuracy and ROC-AUC can be misleading:
- **Primary Metric**: **PR-AUC (Average Precision)**, evaluated out-of-fold across walk-forward test folds.
- **Secondary Operational Metrics**:
  - Precision at Recall Floors: $\text{Precision @ Recall} \ge 0.50$ and $\text{Precision @ Recall} \ge 0.70$.
  - Brier Score: measures probability calibration $\frac{1}{N} \sum (\hat{p}_i - y_i)^2$.
  - Expected Calibration Error (ECE): grouped into 10 reliability bins.

> [!IMPORTANT]
> **No Arbitrary Absolute Thresholds**: Do not declare a model "acceptable" based on arbitrary thresholds like "PR-AUC > 0.45". Model performance must be evaluated strictly **relative to empirical baselines** and supported by **bootstrap confidence intervals**.

---

### G.2 Mandatory Benchmark Baselines

Every model must be compared against four standardized baselines evaluated on identical test folds:

| Baseline | Description | Expected Performance / Floor |
|---|---|---|
| **1. Prevalence / Random-Score Baseline** | Emits random scores or uniform positive prevalence $\pi = P(Y=1)$ | $\text{PR-AUC} = \pi$ (positive prevalence on test fold) |
| **2. Always-Negative Baseline** | Predicts $\hat{y} = 0$ for all observations | $\text{Recall} = 0.0$; **Precision is undefined** (0/0); $\text{Brier} = \pi$ |
| **3. Lagged-Rule Baseline** | Predicts $\hat{y} = 1$ if the project experienced an upward revision in the prior interval ($T-H$ to $T$) | Tests whether model adds value beyond simple persistence heuristic |
| **4. Regularized Logistic Baseline** | Linear logistic regression trained on Tier 1 base features only | Establishes standard linear performance floor |

---

### G.3 Statistical Rigor and Bootstrap Confidence Intervals

- **Bootstrap Confidence Intervals**: For all test metrics (PR-AUC, Brier score, ECE), compute **95% bootstrap confidence intervals** using 1,000 resamples stratified by target label.
- **Disaggregation Requirements**: Report walk-forward evaluation metrics disaggregated by:
  1. **Regime** (Legacy vs Modern)
  2. **Top Sectors** (Road Transport & Highways, Railways, Petroleum, Power)
  3. **Evaluation Fold** (to monitor performance stability across time)

---

*Both canonical dataset hashes verified unchanged.*  
*See `docs/model_target_spec.md` for target definitions and `docs/feature_spec.md` for feature taxonomy.*
