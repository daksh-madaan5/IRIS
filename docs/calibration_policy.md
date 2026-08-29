# IRIS v1 Calibration & Operational Decision-Policy Specification

**Version**: 1.0  
**Date**: 2026-08-29  
**Status**: Formal Design Document — no code implemented, no canonical data modified.  
**Prerequisites**: Read `docs/MODELING_HANDOFF.md` Sections 8–11, `docs/validation_strategy.md`, and `docs/feature_spec.md`.

---

## 1. Formal Record of Model-Family Decisions

Following the completion of the controlled CatBoost nonlinear challenger evaluation across all 17 walk-forward origins (MODELING_HANDOFF §9), the model-family selections for IRIS v1 are formally recorded:

| Regime | Model Decision | Selected Specification | Key Empirical Evidence |
|---|---|---|---|
| **Legacy** (Jan 2023 – Jun 2025) | **`PREFER_CATBOOST`** | `catboost_full_v1__unweighted` | AP = **0.4071** (95% project-cluster CI: 0.3541–0.4578). Paired $\Delta\text{AP}$ vs balanced Logistic = **+0.0674** (95% project-cluster CI: **+0.0376 to +0.0955**; **CI strictly excludes zero**). Resolves severe probability distortion without class weighting: Brier = **0.0720**, ECE = **0.0287** (vs 0.1957 and 0.3340 in balanced Logistic). |
| **Modern** (Jul 2025 – Jul 2026) | **`KEEP_LOGISTIC`** | `logistic_static_only__unweighted` | AP = **0.7587** (95% project-cluster CI: 0.7340–0.7861). CatBoost best challenger $\Delta\text{AP} = +0.0090$ (95% project-cluster CI: **−0.0196 to +0.0338**; **CI spans zero**). **No statistically distinguishable CatBoost improvement was demonstrated; Logistic is preferred for parsimony.** |

**Policy Boundary**: Model-family selection is closed for IRIS v1. No further model families (XGBoost, LightGBM, Random Forest, Neural Networks) and no secondary targets shall be introduced in this phase.

---

## 2. Legacy CatBoost Calibration Strategy

### 2.1 Empirical Probability Quality
Legacy `catboost_full_v1__unweighted` pooled evaluation across 12 walk-forward origins demonstrates:
- **Mean predicted probability**: 0.1020 vs empirical positive prevalence 0.0945 (mean delta of only +0.0075).
- **Expected Calibration Error (ECE, 10-bin)**: **0.0287**.
- **Brier Score**: **0.0720** (substantially outperforming the training prevalence baseline Brier of 0.0859).

### 2.2 Calibration Decision
The unweighted CatBoost model naturally produces reliable, well-calibrated risk probabilities on the ~9.5% prevalence legacy portfolio.

**Decision**: Legacy CatBoost does **not** require an active post-hoc calibration layer for IRIS v1. Its native probabilities are directly usable as operational risk scores.

### 2.3 Diagnostic Protocol & Provisional Monitoring Heuristic
- **Diagnostic Check**: A diagnostic Platt scaling fit (and secondary isotonic fit) must be computed strictly on historical nested out-of-fold predictions to audit fold-level stability prior to operational deployment.
- **Provisional Monitoring Heuristic**: If a future deployment fold exhibits a diagnostic hold-out ECE substantially exceeding the historical baseline (e.g., ECE > 3× the 0.0287 baseline), the diagnostic calibration output must be investigated before operational alerting. This is a provisional monitoring heuristic, not an empirically established structural threshold.

---

## 3. Modern Logistic — Leakage-Safe Temporal Calibration Scheme

### 3.1 Empirical Miscalibration State
Modern `logistic_static_only__unweighted` achieves high discriminative ranking (AP 0.7587, ROC-AUC 0.8419) but suffers from systematic underprediction:
- **Mean predicted probability**: ~0.38 vs empirical positive prevalence 0.4493.
- **Expected Calibration Error (ECE, 10-bin)**: **0.1405**.
- **Fold-level underprediction**: Observed across all 5 Modern evaluation origins, with mean predicted-minus-observed ranging from −0.042 to −0.215.

Post-hoc probability calibration is necessary to align decision scores with true empirical risk.

### 3.2 Strict Embargo Arithmetic ($T_{\text{train}} + H < E$)
All training, calibration, and threshold-tuning data must satisfy the non-negotiable strict embargo rule:
$$\text{month\_index}(T_{\text{train}} + H) < \text{month\_index}(E)$$

For horizon $H=3$, any training snapshot $T_{\text{train}}$ whose label window ends at $T_{\text{train}}+3 \ge E$ is strictly unobserved and unverified at evaluation origin $E$.

#### Actual Embargo-Safe Modern Training Pools:
- **Fold M1** ($E = \text{2025-12}$): $T_{\text{train}} \in \{\text{2025-07}, \text{2025-08}\}$ ($T_{\max} = \text{2025-08} \to T_{\max}+3 = \text{2025-11} < \text{2025-12}$; 1,447 rows).
- **Fold M2** ($E = \text{2026-01}$): $T_{\text{train}} \in \{\text{2025-07} \dots \text{2025-09}\}$ ($T_{\max} = \text{2025-09} \to T_{\max}+3 = \text{2025-12} < \text{2026-01}$; 2,178 rows).
- **Fold M3** ($E = \text{2026-02}$): $T_{\text{train}} \in \{\text{2025-07} \dots \text{2025-10}\}$ ($T_{\max} = \text{2025-10} \to T_{\max}+3 = \text{2026-01} < \text{2026-02}$; 2,937 rows).
- **Fold M4** ($E = \text{2026-03}$): $T_{\text{train}} \in \{\text{2025-07} \dots \text{2025-11}\}$ ($T_{\max} = \text{2025-11} \to T_{\max}+3 = \text{2026-02} < \text{2026-03}$; 3,709 rows).
- **Fold M5** ($E = \text{2026-04}$): $T_{\text{train}} \in \{\text{2025-07} \dots \text{2025-12}\}$ ($T_{\max} = \text{2025-12} \to T_{\max}+3 = \text{2026-03} < \text{2026-04}$; 5,047 rows).

### 3.3 Nested Temporal Out-of-Fold (OOF) Calibration Scheme

To calibrate without leaking label information, calibration models must be fit on **historical out-of-fold predictions generated under a recursive sub-embargo**.

```
For each Modern Evaluation Origin E (H=3):

  1. Define Main Training Pool:
     T_pool = { T in Segment 4 : T + 3 < E }

  2. Construct Nested Temporal OOF Calibration Pool:
     For each target month T in T_pool (in chronological order):
       Sub-training Pool: sub_train(T) = { T' in T_pool : T' + 3 < T }
       
       If sub_train(T) is non-empty:
         a. Fit sub-model (unweighted static Logistic) on sub_train(T).
         b. Predict raw decision scores (logits z = w^T x + b_0) for observations at T.
         c. Append (z_i, y_i) pairs for month T to calibration_pool(E).
       Else:
         Month T cannot be predicted out-of-fold under strict sub-embargo; skip.

  3. Calibration Fitting & Activation:
     If |calibration_pool(E)| >= N_cal_min (minimum chronological threshold):
       Fit Platt scaling on logits: P(Y=1 | z) = sigma(a * z + b).
       Apply frozen (a, b) to main model predictions at E.
       Mark calibration_active = True.
     Else:
       Leave evaluation fold E UNCALIBRATED.
       Emit raw logistic probabilities.
       Mark calibration_active = False.
```

### 3.4 Embargo-Safe Calibration Pool Availability

Evaluating the sub-embargo $T' + 3 < T$ on Segment 4 (starting 2025-07):
- For $T = \text{2025-11}$, sub-training on $T' = \text{2025-07}$ satisfies $\text{2025-07}+3 = \text{2025-10} < \text{2025-11}$ (valid).
- For $T \le \text{2025-10}$, no $T' \ge \text{2025-07}$ satisfies $T' + 3 < T$.

| Origin $E$ | $T_{\text{pool}}$ ($T+3 < E$) | Sub-Embargo OOF Target Months ($T' + 3 < T$) | Calibration Sample Size | Calibration Status |
|---|---|---|---|---|
| **M1** (2025-12) | {07, 08} | None | 0 rows | **UNCALIBRATED** (Insufficient history) |
| **M2** (2026-01) | {07, 08, 09} | None | 0 rows | **UNCALIBRATED** (Insufficient history) |
| **M3** (2026-02) | {07, 08, 09, 10} | None | 0 rows | **UNCALIBRATED** (Insufficient history) |
| **M4** (2026-03) | {07, 08, 09, 10, 11} | {2025-11} (sub-trained on {2025-07}) | ~820 rows | **PROVISIONAL PLATT** (Subject to $N_{\text{cal\_min}}$) |
| **M5** (2026-04) | {07, 08, 09, 10, 11, 12} | {2025-11, 2025-12} (sub-trained on {07} and {07, 08}) | ~1,580 rows | **PLATT CALIBRATED** |

> [!IMPORTANT]
> **Temporal Validity Over Artificial Calibration**: Early Modern origins (M1–M3) structurally lack sufficient mature chronological history for out-of-fold calibration under strict label embargo. These folds **must remain uncalibrated**. Under no circumstances should the label embargo be relaxed to manufacture calibration data.

### 3.5 Calibration Method: Platt Scaling on Logits vs. Isotonic Regression

1. **Primary Method: Platt Scaling on Raw Logits**  
   Platt scaling fits a 1D logistic regression over the raw logit / decision function score $z_i = w^T x_i + b_0$:
   $$P(Y=1 \mid z_i) = \frac{1}{1 + \exp(-(a \cdot z_i + b))}$$
   - **Rationale**: Modern Logistic underprediction reflects systematic log-odds translation and scale distortion. A 2-parameter parametric fit $(a, b)$ is well-regularized and robust against thin chronological sample pools (800–1,600 rows).

2. **Secondary Diagnostic: Isotonic Regression**  
   Isotonic regression fits a non-parametric piecewise-constant isotonic step function.
   - **Constraint**: Isotonic regression is prone to overfitting and step-function artifacts when chronological calibration samples are limited.
   - **Status**: Diagnostic comparator only. Isotonic outputs shall not be deployed operationally in IRIS v1 unless Platt scaling exhibits severe residual miscalibration ($ECE > 0.05$) and isotonic demonstrates smooth, non-degenerate reliability curves.

---

## 4. Operational Threshold Policies for Infrastructure Early Warning

### 4.1 Operational Problem Definition
In PAIMANA infrastructure monitoring, the model emits continuous risk scores to alert oversight authorities regarding impending 3-month schedule push-outs.
- **Population**: ~800 to 1,980 active projects monitored monthly.
- **Alert Consequence**: Flagged projects trigger administrative review and site verifications.
- **Error Asymmetry**: Missed push-outs (false negatives) allow unnoticed project slippage; excessive false alerts (false positives) exhaust monitoring capacity.

### 4.2 Invariant: No In-Sample Training Fallback

> [!CAUTION]
> Thresholds must be selected exclusively from chronological, embargo-safe out-of-fold (OOF) operating curves.
> 
> **If strict embargo-safe nested OOF history is insufficient to construct an empirical operating curve (e.g. origins M1–M3), the operational threshold must be marked UNAVAILABLE for that fold, and the system shall report threshold-free evaluation metrics only (AP, ROC-AUC, Brier, ECE).**
> 
> Selecting operational thresholds from optimistic in-sample training predictions is strictly prohibited.

### 4.3 Candidate Threshold Policies

```
                               OPERATIONAL POLICIES
                                       |
    +------------------+---------------+------------------+------------------+
    |                  |                                  |                  |
[Policy A]         [Policy B]                         [Policy C]         [Policy D]
Fixed Recall       Fixed Precision                    Top-K Alert        Cost-Sensitive
Floor (PRIMARY)    Floor (SECONDARY)                  Budget (SUPPL.)    (DEFERRED)
tau = max{tau:     tau = min{tau:                     Flag top K by      tau = argmin Cost
      Rec >= r}          Prec >= p}                   ranked score       on OOF
```

#### Policy A: Fixed Recall Floor (RECOMMENDED PRIMARY for IRIS v1)
- **Mathematical Definition**: Select the **highest** decision threshold $\tau^*$ such that empirical recall on historical OOF data meets or exceeds the target recall floor $r_{\min}$:
  $$\tau^*(E) = \max \left\{ \tau \in [0, 1] : \text{Recall}_{\text{OOF}}(\tau) \ge r_{\min} \right\}$$
  *(Choosing the maximum threshold maximizes precision among all thresholds satisfying the recall requirement).*
- **Essential Operational Principle**:
  > [!IMPORTANT]
  > **A recall-floor threshold targets $r_{\min}$ on historical OOF data and does NOT guarantee achieved recall on the future evaluation fold.** Realized recall will fluctuate with temporal drift, portfolio composition, and base-rate variation. The pipeline must **always report achieved recall** on the evaluation fold alongside the target floor.
- **Candidate Operating Points**: Evaluate $r_{\min} \in \{0.50, 0.60, 0.70, 0.80\}$ across historical OOF curves.
- **Provisional Alert Volume Indications** (subject to implementation verification on OOF data):
  - *Legacy ($r_{\min}=0.60$)*: At historical precision ~0.22–0.25, estimated alert volume is ~130–250 projects/month (~8–16% of active portfolio).
  - *Modern ($r_{\min}=0.70$)*: At historical precision ~0.72–0.75, estimated alert volume is ~600–650 projects/month (~35–38% of active portfolio).
- **Candidate Capacity Constraint (Alert Cap)**:
  - If oversight agencies impose an operational constraint (e.g. alert rate cannot exceed $C_{\max} = 25\%$ of active projects), a hard cap may be applied.
  - **Priority Rule**: When a capacity cap is enforced, **the capacity cap takes priority over the recall target**. As a direct consequence, **achieved recall will fall below $r_{\min}$**. The pipeline must explicitly report:
    1. Cap activation status (`alert_cap_triggered = True`),
    2. Number of suppressed alerts,
    3. Post-cap achieved recall, and
    4. Shortfall relative to $r_{\min}$.

#### Policy B: Fixed Precision Floor (Secondary Alternative)
- **Mathematical Definition**: Select the lowest threshold satisfying the precision floor, maximizing recall:
  $$\tau^*(E) = \min \left\{ \tau \in [0, 1] : \text{Precision}_{\text{OOF}}(\tau) \ge p_{\min} \right\}$$
- **Candidate Operating Points**: $p_{\min} \in \{0.30, 0.40, 0.50\}$.
- **Trade-off**: Protects reviewer bandwidth but risks severe recall collapse in low-prevalence regimes (Legacy ~9.5%).

#### Policy C: Top-$K$ / Alert-Budget Policy (Supplemental Reporting)
- **Mathematical Definition**: Rank projects by calibrated risk score and flag the top $K$ projects ($K \in \{50, 100, 150, 200\}$).
- **Primary Metric**: Precision@$K$.
- **Role**: Emitted as a mandatory supplemental metric alongside Policy A to provide capacity-bounded visibility.

#### Policy D: Cost-Sensitive Threshold Optimization (Deferred)
- **Mathematical Definition**: Minimize total expected misclassification cost:
  $$\tau^*(E) = \arg\min_{\tau} \left[ C_{\text{FP}} \cdot \text{FP}_{\text{OOF}}(\tau) + C_{\text{FN}} \cdot \text{FN}_{\text{OOF}}(\tau) \right]$$
- **Status**: Deferred until rigorous stakeholder cost elicitation establishes the empirical cost ratio $C_{\text{FN}} / C_{\text{FP}}$.

---

## 5. Frozen Threshold Execution Protocol

For each evaluation origin $E$ at horizon $H=3$:

```
Step 1: Training Pool Assembly
  Assemble all eligible observations with T_train + 3 < E into T_pool(E).

Step 2: Nested OOF Generation
  Generate sub-model out-of-fold decision scores z_i for all T in T_pool where sub_train(T) is non-empty.

Step 3: Calibration & Operating Curve Construction
  If |calibration_pool(E)| >= N_cal_min:
    Fit Platt parameters (a, b) on calibration_pool(E) logits.
    Calibrate all OOF scores: p_hat_i = sigma(a * z_i + b).
    Construct calibrated OOF precision-recall curve.
    Select tau*(E) = max { tau : Recall_OOF(tau) >= r_min }.
    Set threshold_available = True.
  Else:
    Set threshold_available = False.
    tau*(E) = None.

Step 4: Threshold Freezing
  Persist tau*(E), (a, b), and threshold_available in the fold configuration audit BEFORE scoring E.

Step 5: Evaluation Fold Scoring
  Fit main model on T_pool(E).
  Score evaluation origin E:
    If threshold_available == True:
      Compute calibrated probabilities p_hat(E) = sigma(a * z_eval + b).
      Flag projects where p_hat(E) >= tau*(E).
      Apply capacity cap if configured; record post-cap alerts.
      Evaluate achieved recall, precision, F1, alert count, and alert rate.
    Else:
      Emit raw scores; report threshold-free metrics (AP, ROC-AUC, Brier, ECE) only.
```

---

## 6. Metric Reporting Standard

For every walk-forward evaluation origin $E$, the evaluation suite shall record:

### 6.1 Score-Level (Threshold-Free) Metrics
- **Average Precision (PR-AUC)** [Primary Criterion]
- **ROC-AUC**
- **Brier Score**
- **Expected Calibration Error (ECE, 10-bin)**
- **Deterministic 95% Project-Cluster Bootstrap CIs** (1,000 resamples clustered on `project_code`)

### 6.2 Threshold-Level Operational Metrics (where `threshold_available == True`)
- `applied_threshold`: Frozen $\tau^*(E)$
- `target_recall_floor`: $r_{\min}$
- `achieved_recall`: Realized recall on evaluation fold $E$
- `achieved_precision`: Realized precision on evaluation fold $E$
- `achieved_f1`: Harmonic mean of realized precision and recall
- `alert_count`: Total projects flagged ($N_{\text{flagged}}$)
- `alert_rate`: $N_{\text{flagged}} / N_{\text{eligible}}$
- `confusion_matrix`: Counts for TP, FP, FN, TN
- `alert_cap_applied`: Boolean
- `post_cap_achieved_recall`: Realized recall after cap truncation
- `precision_at_k`: Precision@50, Precision@100, Precision@200

### 6.3 Diagnostic & Stability Metrics
- `calibration_active`: Boolean
- `platt_parameters`: $(a, b)$ values where fitted
- `calibration_sample_size`: Number of nested OOF rows in calibration fit
- `feb_2025_diagnostic_isolation`: Separate reporting for the February 2025 reporting discontinuity
- `sector_disaggregated_performance`: Operational metrics broken down by Roads, Railways, Petroleum, Power
- `reliability_diagram_bins`: 10-bin empirical vs mean predicted probabilities

---

## 7. Open Commitments & Invariants

1. **Non-Negotiable Embargo**: $T_{\text{train}} + 3 < E$ holds for all training and calibration operations. No future data or contemporary label windows are ever accessed.
2. **No In-Sample Threshold Tuning**: All operational thresholds derive strictly from out-of-fold curves. Origins lacking mature OOF history remain unthresholded.
3. **Canonical Data Immutability**: All calibration and policy operations read strictly from feature matrices generated from immutable canonical datasets:
   - `projects_monthly.csv`: `9512A9881E17DFDED6E182D87A8DFB1C4EDBD36C0D9B8A7DA9FD1ABB7E002FBF`
   - `projects_completed.csv`: `89BEA84FD68A22E327090C1E4E4533F5BCD745ADCA61EB4E66172EE9023BB910`
