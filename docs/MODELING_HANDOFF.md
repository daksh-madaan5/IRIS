# PAIMANA Modeling Handoff

**Updated**: 2026-08-30
**Version**: 1.9 (Deterministic Locked-Model Explainability Complete)
**Phase**: Model-family selections remain closed (Legacy PREFER_CATBOOST, Modern KEEP_LOGISTIC). Calibration and operational-policy evaluation remains unchanged. The first deterministic predictive-explanation layer is complete; no dashboard, generated narratives, counterfactuals, new target, model family, or threshold selection was added.

---

## 1. Canonical Dataset Hashes (Verified Unchanged)

| File | Rows | SHA-256 |
|---|---:|---|
| `data/processed/projects_monthly.csv` | 64,608 | `9512A9881E17DFDED6E182D87A8DFB1C4EDBD36C0D9B8A7DA9FD1ABB7E002FBF` |
| `data/processed/projects_completed.csv` | 876 | `89BEA84FD68A22E327090C1E4E4533F5BCD745ADCA61EB4E66172EE9023BB910` |

The explainability pre-implementation regression baseline was **191/191 passing**.
Eleven deterministic-explanation tests were added; see Section 13 for the current
full-suite result (**202/202 passing**).

---

## 2. Completed Design Sections Summary

### Part A — Ongoing ↔ Completed Linkage Audit ✓
- **File**: [`reports/ongoing_completed_linkage_audit.md`](file:///d:/coding/PAIMANA/reports/ongoing_completed_linkage_audit.md)
- **Key Findings**:
  - 876/876 completed projects (100.0%) link by exact `project_code` to the ongoing panel.
  - 95.4% (836 projects) transition cleanly: last ongoing at $T$, completed table at $T+1$.
  - 2 source-faithful reappearance anomalies (`N24001682` lag −3, `705635` lag −5) flagged as `COMPLETION_REAPPEAR_ANOMALY`.
  - `actual_completion_date` present in only 107 records (12.21%); structurally absent in legacy era.

### Part B & C — Target Selection and Formal Definitions ✓
- **File**: [`docs/model_target_spec.md`](file:///d:/coding/PAIMANA/docs/model_target_spec.md)
- **Flagship Target**: **Schedule Push-Out over Horizon $H=3$** (`target_effective_schedule_ext_3m`).
- **Two Evaluated Schedule Formulations**:
  1. *Variant A (Revised-Only)*: Evaluates already-revised projects (`revised_completion_date(T)` non-null; ~44% of observations). 4,930 positive events at $H=3$ interval (28.98% rate).
  2. *Variant B (Effective Commitment) — RECOMMENDED FLAGSHIP*: Baseline $\text{eff\_date}(p, T) = \text{revised\_date if present else original\_date}$. Covers 98.42% of ongoing observations; captures both first-time and subsequent extensions. **7,845 positive events at $H=3$ interval (19.65% positive rate)**.
- **Event Timing Formulation**: **Interval-Based** ($\exists t \in [T+1 \dots T+H]: \text{eff\_date}(t) > \text{eff\_date}(T)$) is recommended as the primary operational target over endpoint-only comparison.
- **Cost Escalation**: Evaluated analogously with Variant A (revised-only, 461 events at 3M) and Variant B (effective cost, 1,094 events at 3M).
- **Stagnation vs. Non-Improvement**:
  - Strict Stagnation ($\Delta = 0$): 10,072 positive events at $H=3$ for expenditure; 8,085 for progress.
  - Reported Decreases ($\Delta < 0$): 1,432 events for expenditure; 647 for progress.
  - Non-Improvement ($\Delta \le 0$): 11,504 positive events for expenditure; 8,732 for progress.
- **Zero-Expenditure Reporting Policy**: Base dataset retains all valid observations; zero-reporter exclusions are specified as sensitivity / ablation analyses.

### Part D & E — Leakage-Safe Feature Framework & Missingness ✓
- **File**: [`docs/feature_spec.md`](file:///d:/coding/PAIMANA/docs/feature_spec.md)
- **Three-Tier Taxonomy**: `SAFE_AT_T`, `SAFE_IF_DERIVED`, `LEAKAGE_DO_NOT_USE`.
- **Start Date Correction**: `start_date` is reported **strictly from August 2025 through July 2026**; structurally absent in legacy (Jan 2023–Jun 2025) and July 2025.
- **Imputation Standards**: Nulls in baseline dates (`approval_date`, missing in 0.95%) remain null with binary `<col>_is_missing` indicators; no median imputation in v1.
- **Numeric Transforms**: Signed-log $\text{sign}(x) \cdot \ln(1 + |x|)$ or raw values for delta features with potential negative values; plain `log1p` restricted to strictly non-negative fields.
- **Encoding Standards**: Frequency or one-hot encoding fit strictly on training folds. Target encoding deferred.
- **Ablation Features**: Calendar and drift features (`report_month_index`, `fiscal_year`, `month_of_fiscal_year`) designated as optional ablation candidates. `identifier_regime` used only in pooled models.

### Part F & G — Temporal Validation & Evaluation Metrics ✓
- **File**: [`docs/validation_strategy.md`](file:///d:/coding/PAIMANA/docs/validation_strategy.md)
- **Continuous Reporting Segments**:
  - Segment 1: `2023-01` $\to$ `2023-11` (11 coded months)
  - Segment 2: `2024-01` $\to$ `2024-03` (3 coded months)
  - Segment 3: `2024-06` $\to$ `2025-06` (13 coded months)
  - Segment 4: `2025-07` $\to$ `2026-07` (13 coded months)
- **Legacy Coded Months Correction**: Jan-2023 to Sep-2024 contains **18 coded months** (not 20).
- **Validation Architecture**: **Walk-Forward (Expanding-Origin) Validation with an $H$-Month Label Embargo** ($T_{\text{train}} \le T_{\text{eval}} - H$).
- **Concrete $H=3$ Folds**:
  - Legacy: 2 evaluation folds in Segment 1 (`2023-07`, `2023-08`); 0 in Segment 2; 10 sequential folds in Segment 3 (`2024-06` $\dots$ `2025-03`).
  - Modern: 5 sequential test folds in Segment 4 (`2025-12` $\dots$ `2026-04`).
- **Horizon Constraints**: $H=12$ is unviable (only 2 total origins across repository history); $H=6$ is severely restricted in the modern era (only 1 test fold). $H=3$ is the primary operational horizon.
- **Evaluation Metrics**: PR-AUC is primary; no arbitrary absolute thresholds. All models must be evaluated against 4 baselines (Prevalence, Always-Negative with undefined precision, Lagged-Rule, Logistic Regression) with 95% bootstrap confidence intervals.

### Part H — Role of Completed Projects Dataset ✓
- **Policy**: `projects_completed.csv` is **NOT** used for training or as ground-truth labels for early warning.
- **Construct-Validity Role**: The 107 records with `actual_completion_date` may be used in a separate, post-hoc analysis to evaluate whether model risk scores emitted during ongoing monitoring correlate with downstream realized physical delay.

---

## 3. Files Created / Modified

| File | Status | Description |
|---|---|---|
| [`reports/ongoing_completed_linkage_audit.md`](file:///d:/coding/PAIMANA/reports/ongoing_completed_linkage_audit.md) | Corrected | Objective language, construct validity framing for 107 records |
| [`docs/model_target_spec.md`](file:///d:/coding/PAIMANA/docs/model_target_spec.md) | Corrected | Target semantics, 2 variants, interval vs endpoint, non-improvement distinction, objective language |
| [`docs/feature_spec.md`](file:///d:/coding/PAIMANA/docs/feature_spec.md) | Corrected | `start_date` scope resolved, signed-log, training-only encoding, null+indicator policy |
| [`docs/validation_strategy.md`](file:///d:/coding/PAIMANA/docs/validation_strategy.md) | Rebuilt | Walk-forward evaluation across 4 continuous segments with label embargo |
| [`docs/MODELING_HANDOFF.md`](file:///d:/coding/PAIMANA/docs/MODELING_HANDOFF.md) | Updated | Comprehensive handoff reflecting post-correction design state |
| [`src/ml/dataset_builder.py`](file:///d:/coding/PAIMANA/src/ml/dataset_builder.py) | Added | Conservative H=3 target and leakage-safe at-T feature construction |
| [`src/ml/evaluate_baselines.py`](file:///d:/coding/PAIMANA/src/ml/evaluate_baselines.py) | Added | Regime-separated strict-embargo walk-forward baseline evaluation |
| [`src/ml/robustness_audit.py`](file:///d:/coding/PAIMANA/src/ml/robustness_audit.py) | Added | Fold stability, aggregation, cluster uncertainty, ablation, and calibration diagnostics |
| [`src/ml/refine_logistic.py`](file:///d:/coding/PAIMANA/src/ml/refine_logistic.py) | Added | Regime-specific manual feature set and class-weight Logistic refinement |
| [`src/ml/challenger_catboost.py`](file:///d:/coding/PAIMANA/src/ml/challenger_catboost.py) | Added | First controlled nonlinear challenger (CatBoost) with native categoricals |
| [`requirements.txt`](file:///d:/coding/PAIMANA/requirements.txt) | Modified | Pinned `catboost==1.2.10` dependency |
| [`tests/test_ml_dataset_builder.py`](file:///d:/coding/PAIMANA/tests/test_ml_dataset_builder.py) | Added | Builder semantics and generated-data regression tests |
| [`tests/test_ml_evaluate_baselines.py`](file:///d:/coding/PAIMANA/tests/test_ml_evaluate_baselines.py) | Added | Embargo, preprocessing, leakage, regime, determinism, lagged-rule, and output tests |
| [`tests/test_ml_robustness_audit.py`](file:///d:/coding/PAIMANA/tests/test_ml_robustness_audit.py) | Added | Feature partition, clustered bootstrap, aggregation, ablation-fold, output, and hash tests |
| [`tests/test_ml_refine_logistic.py`](file:///d:/coding/PAIMANA/tests/test_ml_refine_logistic.py) | Added | Manual feature definitions, class-weight fits, cluster bootstrap, and hash tests |
| [`tests/test_ml_challenger_catboost.py`](file:///d:/coding/PAIMANA/tests/test_ml_challenger_catboost.py) | Added | CatBoost data preparation, sentinels, paired cluster bootstrap, and regression tests |

---

## 4. Dataset Builder Implementation Completed

Implementation: `src/ml/dataset_builder.py`  
Generated directory: `data/ml/schedule_extension_3m/`

Only the approved flagship target, `target_effective_schedule_ext_3m`, is built.
No H=6/H=12, cost, progress, or expenditure targets were generated. No encoder,
imputer, random split, feature fitter, or model was created.

### Generated eligible rows and event balance

| Identifier regime | Eligible rows | Positives | Negatives | Positive rate | First revisions | Subsequent revisions |
|---|---:|---:|---:|---:|---:|---:|
| Legacy | 25,406 | 2,634 | 22,772 | 10.37% | 886 | 1,748 |
| Modern | 11,899 | 4,327 | 7,572 | 36.36% | 1,145 | 3,182 |
| **Total** | **37,305** | **6,961** | **30,344** | **18.66%** | **2,031** | **4,930** |

The generated manifest records the complete feature list, metadata list, source
hashes, target rules, exclusion reasons, output hashes, and validation results.
`eventually_completed` and `completion_report_month` are attached by exact ID only
and explicitly classified `METADATA_ONLY_LEAKAGE_DO_NOT_USE`; neither is in the
feature list. `project_code` remains metadata, and `project_name` is excluded.

### Corrected effective-commitment persistence semantics

The required pre-label audit found material non-null-to-null behavior:

| Field | Regime | Projects affected | Later null project-months | Adjacent non-null→null transitions |
|---|---|---:|---:|---:|
| Revised completion date | Legacy | 693 | 1,336 | 741 |
| Revised completion date | Modern | 57 | 96 | 57 |
| Revised cost | Legacy | 89 | 484 | 89 |
| Revised cost | Modern | 0 | 0 | 0 |

Consequently, the builder never interprets a later null as a return to the
original completion date or original cost. A positive schedule event requires an
actually reported future revised completion date later than the usable commitment
at T. If a revision was previously reported but is null at T, the baseline is
ambiguous and the row is ineligible. If a future null follows an observed revision
inside a would-be negative window, that window is also ineligible. A directly
reported qualifying extension remains a positive even if another future snapshot
in the window is null.

This conservative correction yields **37,305 eligible / 6,961 positive** rows,
versus the design estimate of **39,932 / 7,845**. The difference is **−2,627
eligible rows and −884 positives**, caused by requiring actually reported future
revised values and excluding unresolved null-return windows rather than converting
them to effective-original states.

### Ineligibility audit

The builder writes every excluded reference observation with a single deterministic
reason. Across both regimes, 27,303 observations are ineligible, including segment
ends/gap crossings, project disappearance or missing future months, missing baseline
commitments, and revised-value persistence ambiguity. Counts by regime and reason
are in `ineligible_reason_counts.csv`; case-level evidence is retained in
`ineligible_window_audit.csv`.

The encoded embargo helper enforces the strict rule `T + 3 < E`. In particular,
a January training reference is not usable for an April evaluation reference, but
is usable for May. No train/test splits have been generated.

## 5. Verification and Exact Next Step

The builder validates unique prediction keys, reproducible reported evidence for
every positive, complete same-segment three-month windows for negatives, no gap or
identifier-regime crossings, no future-derived feature columns, and no completed
field in the feature matrix. Generated CSVs were also imported and inspected as
tabular artifacts after construction.

Post-implementation regression result: **139/139 passing** (the 126-test baseline
plus 13 dataset-builder unit/regression tests). Both canonical inputs were hashed
again after generation and remain immutable at the exact hashes in Section 1.

The dataset-builder handoff originally identified walk-forward baseline evaluation
as the next step. That step is now complete and documented below.

## 6. First Walk-Forward Baseline Evaluation Completed

Evaluation implementation: `src/ml/evaluate_baselines.py`  
Generated results: `data/ml/schedule_extension_3m/evaluation/`

The evaluator reads its 36 inputs exclusively from
`manifest.json["feature_columns"]`. Legacy and Modern are fitted and evaluated
separately. No pooled cross-era model, random split, row shuffle, target encoding,
class weighting, test-fold threshold tuning, completed-project metadata, project
identifier, project name, or target/reproducibility metadata enters the feature
matrix.

### Exact folds evaluated

All advertised origins contained sufficient eligible training and evaluation rows;
none were skipped. The training maximum below reflects the strict rule
`T_train + 3 < E`, so a label window ending in E is excluded.

| Regime | E | Maximum training T | Training rows | Evaluation rows | Positives | Base rate |
|---|---|---|---:|---:|---:|---:|
| Legacy | 2023-07 | 2023-03 | 3,906 | 1,480 | 144 | 9.73% |
| Legacy | 2023-08 | 2023-04 | 5,372 | 1,590 | 130 | 8.18% |
| Legacy | 2024-06 | 2023-08 | 11,477 | 1,706 | 141 | 8.26% |
| Legacy | 2024-07 | 2023-08 | 11,477 | 1,633 | 160 | 9.80% |
| Legacy | 2024-08 | 2023-08 | 11,477 | 1,623 | 166 | 10.23% |
| Legacy | 2024-09 | 2023-08 | 11,477 | 1,613 | 169 | 10.48% |
| Legacy | 2024-10 | 2024-06 | 13,183 | 1,611 | 135 | 8.38% |
| Legacy | 2024-11 | 2024-07 | 14,816 | 1,092 | 94 | 8.61% |
| Legacy | 2024-12 | 2024-08 | 16,439 | 1,113 | 133 | 11.95% |
| Legacy | 2025-01 | 2024-09 | 18,052 | 1,109 | 135 | 12.17% |
| Legacy | 2025-02 | 2024-10 | 19,663 | 983 | 43 | 4.37% |
| Legacy | 2025-03 | 2024-11 | 20,755 | 1,446 | 156 | 10.79% |
| Modern | 2025-12 | 2025-08 | 1,447 | 1,338 | 608 | 45.44% |
| Modern | 2026-01 | 2025-09 | 2,178 | 1,630 | 739 | 45.34% |
| Modern | 2026-02 | 2025-10 | 2,937 | 1,867 | 947 | 50.72% |
| Modern | 2026-03 | 2025-11 | 3,709 | 1,730 | 724 | 41.85% |
| Modern | 2026-04 | 2025-12 | 5,047 | 1,625 | 662 | 40.74% |

Aggregate evaluation populations are **16,999 Legacy rows / 1,606 positives
(9.45%)** and **8,190 Modern rows / 3,680 positives (44.93%)**.

### Aggregate baseline results by regime

Metrics pool predictions from the non-overlapping evaluation origins within each
regime. Average Precision is the primary metric. Precision is intentionally `NA`
for baselines with zero predicted positives; their recall and F1 are zero.

| Regime | Baseline | AP / PR-AUC | ROC-AUC | Precision | Recall | F1 | Brier |
|---|---|---:|---:|---:|---:|---:|---:|
| Legacy | Training prevalence | 0.0928 | 0.4940 | NA | 0.0000 | 0.0000 | 0.0859 |
| Legacy | Always negative | 0.0945 | 0.5000 | NA | 0.0000 | 0.0000 | 0.0945 |
| Legacy | Latest-transition lagged rule | 0.1512 | 0.5636 | 0.4925 | 0.1426 | 0.2211 | 0.0949 |
| Legacy | Logistic L2, unweighted | **0.2906** | **0.7360** | 0.4157 | 0.1843 | 0.2554 | **0.0838** |
| Modern | Training prevalence | 0.4479 | 0.5061 | NA | 0.0000 | 0.0000 | 0.3152 |
| Modern | Always negative | 0.4493 | 0.5000 | NA | 0.0000 | 0.0000 | 0.4493 |
| Modern | Latest-transition lagged rule | 0.4961 | 0.5636 | 0.6681 | 0.2139 | 0.3240 | 0.4010 |
| Modern | Logistic L2, unweighted | **0.7091** | **0.8072** | 0.7444 | 0.3609 | 0.4861 | **0.2111** |

Deterministic, label-stratified 1,000-resample 95% bootstrap intervals for all
aggregate metrics are in `regime_aggregate_metrics.csv`. Core Logistic intervals:

- Legacy AP 0.2906 (95% CI 0.2714–0.3125), ROC-AUC 0.7360
  (0.7230–0.7493).
- Modern AP 0.7091 (95% CI 0.6949–0.7251), ROC-AUC 0.8072
  (0.7970–0.8169).

### Baseline definitions and preprocessing

- **Training prevalence:** a deterministic constant probability equal to the
  training-fold prevalence. It replaces noisy random scores while preserving the
  intended prevalence baseline. Because the constant changes by fold, pooled AP
  need not equal pooled evaluation prevalence exactly.
- **Always negative:** score and label zero. Precision is `NA` because no positive
  is predicted.
- **Lagged rule:** predicts positive only when the approved cumulative prior-
  extension count at T exceeds its value in the exact same-project, same-segment
  T-1 feature row. Missing T-1 rows fall back to zero. Coverage is 85.05% Legacy
  and 85.01% Modern; fallback coverage is explicitly recorded per prediction.
- **Logistic:** unweighted L2 Logistic Regression, `C=1.0`, `lbfgs`, maximum 2,000
  iterations, fixed seed 20260829, decision threshold 0.5. No balanced variant or
  threshold search was run.
- **Categoricals:** training-fold frequency encoding; unseen evaluation values map
  safely to zero.
- **Numerics:** training-fold mean/standard-deviation scaling on reported values.
  Matrix-only missing placeholders are standardized zero and are paired with an
  explicit per-input missingness bit. No canonical or generated feature value is
  imputed or modified.

Calibration artifacts include 10 equal-width-bin reliability summaries for every
fold and pooled regime. The unweighted Logistic model has Legacy ECE 0.0529 and
mean score 0.1473 versus a 0.0945 base rate. Modern ECE is 0.1664 and mean score
0.2986 versus a 0.4493 base rate, showing material underprediction; no Platt or
isotonic calibration was applied.

### Extension-type metadata clarification

The stored `FIRST_REVISION` value means only that no revised completion date was
reported at T. For evaluation documentation it is interpreted as
`FIRST_REVISION_FROM_UNREVISED_BASELINE`. It does **not** prove that the event is
the first revision in the project's entire pre-observation history. Labels and
generated dataset rows were not changed.

### Unresolved issues

- Fold performance is not temporally stable. Legacy February 2025 is the clearest
  warning: Logistic AP is 0.0341 and ROC-AUC 0.3919, despite stronger surrounding
  folds. This must be diagnosed before treating aggregate results as deployable.
- The fixed 0.5 threshold has low recall, especially in Legacy. Threshold selection
  and class-weight comparisons must occur using training/validation history only,
  not these test folds.
- Modern probabilities are materially under-calibrated. Calibration methods are
  deferred and must be trained within each future walk-forward fold.
- The lagged rule has about 15% deterministic fallback due to unavailable exact
  prior eligible feature rows.
- Frequency encoding is intentionally conservative; one-hot encoding remains an
  approved training-fold-only comparison, not yet evaluated.

### Outputs, tests, and next step

Generated artifacts include fold metrics, regime aggregates, predictions,
calibration bins, skipped-fold records, preprocessing fit audits, configuration,
and `evaluation_manifest.json`. Generated files remain Git-ignored.

The evaluator adds 11 regression tests covering strict embargo enforcement,
train-only preprocessing, prohibited metadata, regime separation, deterministic
bootstrap and Logistic output, lagged-rule temporal direction, generated fold
integrity, and canonical hashes. Final full-suite status and post-run hashes are
**150/150 passing** (the accepted 139-test baseline plus 11 evaluator tests).
Post-evaluation hashes remain:

- `projects_monthly.csv`: `9512A9881E17DFDED6E182D87A8DFB1C4EDBD36C0D9B8A7DA9FD1ABB7E002FBF`
- `projects_completed.csv`: `89BEA84FD68A22E327090C1E4E4533F5BCD745ADCA61EB4E66172EE9023BB910`

That baseline-stability investigation is now complete and documented in Section 7.

## 7. Baseline Robustness and Diagnostic Audit Completed

Implementation: `src/ml/robustness_audit.py`  
Generated results: `data/ml/schedule_extension_3m/evaluation/robustness/`  
Human-readable diagnostic: `robustness_report.md`

The audit reuses all 17 accepted walk-forward origins, their strict embargo, the
same unweighted L2 Logistic configuration, and fold-local preprocessing. Full-v1
probabilities reconcile with the accepted evaluation to machine precision. Labels
were not rebuilt, no defect was found, and no advanced model was implemented.

### Fold stability and February 2025

The complete fold table is in `fold_stability.csv`. Performance is materially
time-varying. Legacy Logistic AP ranges from 0.0341 to 0.8058; Modern ranges from
0.5678 to 0.8151. Early Modern folds also contain substantial exact categorical
novelty (30.4%–39.9% of sector/agency/state cells unseen in training), falling to
0.6% by April 2026.

Legacy February 2025 has 983 rows and only 43 positives (4.37%), versus 135/1,109
(12.17%) in January and 156/1,446 (10.79%) in March. Its Logistic AP/ROC are
0.0341/0.3919. Observed diagnostic differences are:

- all 43 positives are `FIRST_REVISION_FROM_UNREVISED_BASELINE`; there are no
  subsequent-revision positives, versus 79.3% subsequent in January and 85.3% in
  March;
- `revised_date_is_present` and `n_prior_schedule_extensions` are both zero for
  every eligible February row, versus revised-date presence of 9.65% in January
  and 34.85% in March;
- physical-progress and expenditure-delta support rates remain close to adjacent
  folds; the exact categorical unseen-cell rate is only 0.20%;
- sector total-variation distances are 0.030 (Jan→Feb) and 0.069 (Feb→Mar), while
  agency distances are 0.062 and 0.148.

These are observed reporting-state, target-composition, and distribution shifts;
the audit makes no causal claim. The accepted target semantics remain internally
reproducible, but this fold prevents treating the pooled result as temporally
stable.

### Micro, macro, and weighted metrics

| Regime | Metric | Concatenated OOF (micro) | Macro fold mean | Evaluation-row-weighted fold mean |
|---|---|---:|---:|---:|
| Legacy | AP | 0.2906 | 0.3904 | 0.3670 |
| Legacy | ROC-AUC | 0.7360 | 0.7435 | 0.7434 |
| Legacy | Brier | 0.0838 | 0.0813 | 0.0838 |
| Modern | AP | 0.7091 | 0.7221 | 0.7307 |
| Modern | ROC-AUC | 0.8072 | 0.8041 | 0.8113 |
| Modern | Brier | 0.2111 | 0.2122 | 0.2111 |

Concatenated AP/ROC pools score rankings from different fitted models and training
prevalences. It is an out-of-fold operational summary, not a single-model test
metric. Macro weights each origin equally; row-weighted metrics weight origins by
evaluation population. Micro and row-weighted Brier reconcile because Brier is
row-decomposable; AP and ROC generally do not.

### Cluster-aware confidence intervals

The robustness audit replaces independent-row bootstrap as the sole uncertainty
statement with 1,000 deterministic project-cluster resamples. Each sampled
`project_code` retains all of its out-of-fold observations. Evaluation-month block
resampling is also reported as a sensitivity analysis.

| Regime | Metric | Point | 95% project-cluster CI | Month-block sensitivity CI |
|---|---|---:|---:|---:|
| Legacy | AP | 0.2906 | 0.2440–0.3405 | 0.2470–0.3815 |
| Legacy | ROC-AUC | 0.7360 | 0.7107–0.7603 | 0.7111–0.7769 |
| Legacy | Brier | 0.0838 | 0.0787–0.0892 | 0.0723–0.0964 |
| Modern | AP | 0.7091 | 0.6835–0.7345 | 0.6196–0.7896 |
| Modern | ROC-AUC | 0.8072 | 0.7937–0.8205 | 0.7375–0.8515 |
| Modern | Brier | 0.2111 | 0.2027–0.2191 | 0.1952–0.2283 |

Modern month-block intervals are sensitivity-only because just five evaluation
months are available.

### Feature ablation and categorical dependence

| Regime | Logistic inputs | AP | ROC-AUC | Brier | ECE |
|---|---|---:|---:|---:|---:|
| Legacy | Static at T | 0.1960 | 0.7305 | 0.0830 | 0.0287 |
| Legacy | Trajectory only | 0.2936 | 0.6961 | 0.0884 | 0.0753 |
| Legacy | Full v1 | 0.2906 | 0.7360 | 0.0838 | 0.0529 |
| Legacy | Numeric-only full v1 | 0.2890 | 0.7398 | 0.0819 | 0.0458 |
| Modern | Static at T | 0.7587 | 0.8419 | 0.1916 | 0.1405 |
| Modern | Trajectory only | 0.6174 | 0.7137 | 0.3003 | 0.2741 |
| Modern | Full v1 | 0.7091 | 0.8072 | 0.2111 | 0.1664 |
| Modern | Numeric-only full v1 | 0.6983 | 0.8004 | 0.2239 | 0.1909 |

Historical trajectories add substantial Legacy AP versus static-only, but the
full set does not exceed trajectory-only AP. In Modern, static-at-T is clearly
stronger than trajectory-only or full v1. Removing sector/agency/state barely
changes Legacy AP and reduces Modern AP by only 0.0108 versus full v1; categorical
memorisation therefore does not dominate either pooled result.

### Calibration and threshold-free interpretation

Legacy mean probability is 0.1473 against a 0.0945 event rate (ECE 0.0529; Brier
0.0838), a pooled overprediction pattern. Modern mean probability is 0.2986
against a 0.4493 event rate (ECE 0.1664; Brier 0.2111). Every Modern fold
underpredicts on average, with predicted-minus-observed ranging from −0.042 to
−0.215. Modern's ECE therefore reflects systematic underprediction whose magnitude
also drifts by fold; in deciles 1–9 observed rates exceed mean scores, while the
top decile modestly overpredicts.

AP remains primary. Pooled precision-recall anchors are descriptive only: at about
50% recall, precision is 0.236 Legacy and 0.751 Modern; at about 80% recall, it is
0.145 and 0.690. No operational threshold was selected and no calibration was fit.

### Tests, hashes, and exact next step

Seven robustness tests cover exact manifest feature order, deterministic
project-cluster bootstrap, explicit aggregation semantics, identical ablation
fold populations, both cluster methods, accepted-score reconciliation, and
canonical hash immutability. Final full-suite status is **157/157 passing**.

Canonical hashes remain unchanged:

- `projects_monthly.csv`: `9512A9881E17DFDED6E182D87A8DFB1C4EDBD36C0D9B8A7DA9FD1ABB7E002FBF`
- `projects_completed.csv`: `89BEA84FD68A22E327090C1E4E4533F5BCD745ADCA61EB4E66172EE9023BB910`

**Exact next model stage, only after explicit approval:** remain regime-separated
and Logistic-first. Run a pre-specified training-fold-only one-hot encoding
comparison and a transparent unweighted-versus-balanced Logistic comparison, with
any threshold selected solely from training/validation history. Carry Legacy
trajectory/full-v1 and Modern static-at-T as distinct candidate specifications.
Do not calibrate or advance to tree, boosting, neural, or pooled production models
until the February reporting-state discontinuity, Modern categorical novelty, and
fold-specific calibration drift are incorporated into the validation plan.

## 8. Regime-Specific Logistic Refinement Completed

Implementation: `src/ml/refine_logistic.py`  
Tests: `tests/test_ml_refine_logistic.py`  
Generated results: `data/ml/schedule_extension_3m/evaluation/refinement/`

The refinement reuses exactly the accepted 12 Legacy and 5 Modern walk-forward
origins and the strict `T_train + 3 < E` embargo. All preprocessing remains
fold-local. Every candidate was fitted twice and reported separately: unweighted
L2 and `class_weight="balanced"` L2, with otherwise identical `C=1.0`, `lbfgs`,
2,000-iteration, and fixed-seed settings. The 0.5 threshold is descriptive only;
no threshold was tuned on a test fold. No calibration or nonlinear model was fit.

### Exact manually declared feature sets

No automated feature-selection search was performed. The candidate inputs are:

**Legacy trajectory-only (11 inputs)**

1. `exp_delta_1m`
2. `exp_delta_3m`
3. `past_exp_stagnant_3m`
4. `past_progress_delta_3m`
5. `past_progress_stagnant_3m`
6. `n_prior_schedule_extensions`
7. `n_prior_cost_revisions`
8. `observed_tenure_months`
9. `exp_delta_1m_is_supported`
10. `exp_delta_3m_is_supported`
11. `progress_delta_3m_is_supported`

**Legacy trajectory + minimal useful static numeric (16 inputs)** uses all 11
above plus:

12. `project_age_months`
13. `months_to_effective_schedule`
14. `schedule_revision_lag_months`
15. `expenditure_to_original_cost_ratio`
16. `revised_date_is_present`

These additions were pre-specified to represent project age, current schedule
distance, reported revision magnitude/presence, and expenditure scale. No Legacy
categorical field was added to this minimal candidate.

**Modern static-only (25 inputs)**

1. `sector`
2. `agency`
3. `state`
4. `original_cost`
5. `cumulative_expenditure_t`
6. `revised_cost_t`
7. `physical_progress_t`
8. `project_age_months`
9. `months_to_original_schedule`
10. `months_to_effective_schedule`
11. `schedule_revision_lag_months`
12. `schedule_has_been_revised`
13. `months_since_start`
14. `expenditure_to_original_cost_ratio`
15. `revised_to_original_cost_ratio`
16. `cost_has_been_revised`
17. `state_is_missing`
18. `approval_date_is_missing`
19. `original_completion_date_is_missing`
20. `revised_cost_is_present`
21. `revised_date_is_present`
22. `physical_progress_is_present`
23. `physical_progress_supported`
24. `start_date_is_present`
25. `start_date_supported`

**Modern static + selected trajectory (29 inputs)** uses all 25 above plus only:

26. `exp_delta_3m`
27. `past_progress_delta_3m`
28. `n_prior_schedule_extensions`
29. `observed_tenure_months`

This Modern candidate deliberately does not inherit all Legacy trajectory inputs.

**Full-v1 (36 inputs, both regimes)** contains the same 25 static inputs and the
complete 11-input trajectory set above in the accepted manifest's interleaved
order. It exactly matches `manifest.json["feature_columns"]`; the recomputed unweighted full-v1 scores
reconcile with the accepted baseline to maximum absolute difference
`4.996003610813204e-16`.

### Candidate comparison and winners

The primary criterion is concatenated out-of-fold AP within regime. Prevalence AP
is 0.0928 Legacy / 0.4479 Modern, and lagged-rule AP is 0.1512 / 0.4961.

| Regime | Feature set | Weighting | AP | ROC-AUC | Brier | ECE | Precision | Recall | F1 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| Legacy | Trajectory only | Balanced | **0.3397** | 0.7457 | 0.1957 | 0.3340 | 0.2518 | 0.6164 | 0.3575 |
| Legacy | Trajectory + minimal static | Balanced | 0.3128 | 0.7573 | 0.1990 | 0.3292 | 0.2015 | 0.6569 | 0.3084 |
| Legacy | Full-v1 | Balanced | 0.3031 | 0.7491 | 0.1944 | 0.3093 | 0.2039 | 0.6756 | 0.3133 |
| Legacy | Trajectory only | Unweighted | 0.2936 | 0.6961 | 0.0884 | 0.0753 | 0.4634 | 0.2092 | 0.2883 |
| Legacy | Full-v1 | Unweighted | 0.2906 | 0.7360 | 0.0838 | 0.0529 | 0.4157 | 0.1843 | 0.2554 |
| Legacy | Trajectory + minimal static | Unweighted | 0.2842 | 0.7178 | 0.0901 | 0.0742 | 0.3482 | 0.2335 | 0.2795 |
| Modern | Static only | Unweighted | **0.7587** | 0.8419 | 0.1916 | 0.1405 | 0.8083 | 0.3620 | 0.5000 |
| Modern | Static only | Balanced | 0.7567 | 0.8443 | 0.1796 | 0.1290 | 0.6430 | 0.9266 | 0.7592 |
| Modern | Full-v1 | Balanced | 0.7184 | 0.8186 | 0.1772 | 0.0811 | 0.6837 | 0.8457 | 0.7561 |
| Modern | Full-v1 | Unweighted | 0.7091 | 0.8072 | 0.2111 | 0.1664 | 0.7444 | 0.3609 | 0.4861 |
| Modern | Static + selected trajectory | Balanced | 0.6555 | 0.7824 | 0.1988 | 0.1147 | 0.6557 | 0.8639 | 0.7455 |
| Modern | Static + selected trajectory | Unweighted | 0.6526 | 0.7795 | 0.2250 | 0.1883 | 0.6696 | 0.3535 | 0.4627 |

The **winning Legacy configuration** is trajectory-only, balanced L2 Logistic:
AP 0.3397 (project-cluster 95% CI 0.2872–0.3884), ROC-AUC 0.7457
(0.7210–0.7704), and Brier 0.1957 (0.1910–0.2008). It improves AP by 0.0491
over the original unweighted full-v1 baseline and by 0.1885 over the lagged rule.

The **winning Modern configuration** is static-only, unweighted L2 Logistic: AP
0.7587 (project-cluster 95% CI 0.7340–0.7861), ROC-AUC 0.8419
(0.8285–0.8554), and Brier 0.1916 (0.1844–0.1990). It improves AP by 0.0496
over original unweighted full-v1 and by 0.2626 over the lagged rule. Adding the
selected trajectory subset materially reduces Modern AP, so the full Legacy
trajectory family should not be carried into Modern automatically.

### Class weighting, calibration, and stability

Class balancing helps Legacy AP for every feature set: +0.0461 trajectory-only,
+0.0286 trajectory-plus-static, and +0.0125 full-v1. This AP improvement is not
a calibration improvement: the winning balanced Legacy model has mean probability
0.4285 versus the 0.0945 event rate, Brier 0.1957, and ECE 0.3340. Balanced and
unweighted results must therefore remain separately identified; balanced weighting
is selected for Legacy only because AP is the declared primary criterion.

For Modern static-only, balancing slightly hurts AP by 0.0021 (0.7587 to 0.7567),
so the winning Modern model remains unweighted. Balancing improves Brier/ECE and
recall at the descriptive fixed threshold, but changes the mean probability to
0.5677 versus a 0.4493 event rate; this is not a reason to silently replace the
unweighted AP winner.

No calibration was fit. The unweighted Modern static-only winner naturally reduces
the pooled predicted-minus-observed gap from −0.1507 for original full-v1 to
−0.1319, an absolute reduction of 0.0188. It nevertheless underpredicts in all
five Modern folds, and pooled ECE remains 0.1405. Systematic underprediction is
therefore reduced modestly, not resolved; calibration remains a separate later
stage after final model-family selection.

Legacy remains unstable. The winning model's fold AP spans 0.0347–0.7739 with
fold mean 0.4026 and standard deviation 0.2349. February 2025 is retained and is
the minimum fold at AP 0.03475; pooled AP changes from 0.3397 to 0.3465 when shown
descriptively without it. This reports the fold's stability effect only and makes
no causal claim. Modern winner fold AP is materially tighter at 0.6916–0.8010
(mean 0.7516, standard deviation 0.0467).

Project-cluster 95% intervals use 1,000 deterministic whole-project resamples and
are provided for AP, ROC-AUC, Brier, ECE, precision, recall, and F1 for every
candidate and reference. Complete candidate, fold, aggregate, prediction, exact
feature-list, preprocessing-audit, configuration-manifest, and cluster-CI artifacts
are present in the refinement directory.

Nine refinement tests cover exact manual feature definitions, separate class-weight
fits, deterministic cluster bootstrap, accepted folds/populations, strict embargo,
full-v1 score reconciliation, calibration scope, February retention, generated
artifact counts, and canonical hash protection. Final full-suite status is
**166/166 passing**.

Canonical hashes remain unchanged:

- `projects_monthly.csv`: `9512A9881E17DFDED6E182D87A8DFB1C4EDBD36C0D9B8A7DA9FD1ABB7E002FBF`
- `projects_completed.csv`: `89BEA84FD68A22E327090C1E4E4533F5BCD745ADCA61EB4E66172EE9023BB910`

### Recommendation

Proceed to a separately authorized, regime-specific nonlinear model-family
comparison next, retaining these two Logistic winners as mandatory benchmarks and
reusing the same folds, embargo, fold-local preprocessing, cluster uncertainty,
and explicit February stability reporting. The recommendation is for controlled
model-family comparison, not deployment: Legacy's balanced AP gain comes with
poor probability quality, and Modern underprediction remains unresolved. Do not
fit calibration until the final model family has been selected. No CatBoost,
XGBoost, LightGBM, tree, boosting, or neural model has been implemented here.

## 9. Controlled CatBoost Nonlinear Challenger Evaluation Completed

Implementation: `src/ml/challenger_catboost.py`  
Tests: `tests/test_ml_challenger_catboost.py`  
Generated results: `data/ml/schedule_extension_3m/evaluation/catboost/`

The first controlled nonlinear challenger evaluation reuses exactly the 12 Legacy
and 5 Modern walk-forward origins, the strict `T_train + 3 < E` embargo, and
regime separation. No XGBoost, LightGBM, Random Forest, neural networks, stacking,
or automated hyperparameter search was performed.

### Exact CatBoost configuration and preprocessing

- **Model parameters**: `iterations=300` (fixed iteration count to avoid early-stopping validation leakage), `learning_rate=0.05`, `depth=5`, `l2_leaf_reg=3.0`, `random_seed=20260829`, `thread_count=4`, `verbose=False`.
- **Categorical handling**: Native CatBoost categorical handling with string missingness sentinel `__MISSING__`. All categorical mappings and target statistics are learned exclusively from the training fold; unseen evaluation categories are handled natively without error or data leakage.
- **Numeric missingness**: Preserved as `np.nan`; CatBoost's tree splitters evaluate missingness direction natively without artificial global or local imputation.
- **Class weighting**: Evaluated transparently in two variants: `unweighted` (`auto_class_weights=None`) and `balanced` (`auto_class_weights="Balanced"`, computed exclusively from the current walk-forward training fold).
- **Prohibited feature protection**: 0 prohibited features in any feature set.

### Evaluated feature sets

- **Legacy primary**: `trajectory_only` (11 features; matches the winning Legacy Logistic benchmark feature set).
- **Legacy secondary**: `full_v1` (36 features; full input feature set including static, categorical, and trajectory features).
- **Modern primary**: `static_only` (25 features; matches the winning Modern Logistic benchmark feature set).
- **Modern secondary**: `full_v1` (36 features; full input feature set).

### Aggregate candidate results and benchmark comparison

Primary metric is concatenated out-of-fold Average Precision (PR-AUC) within regime.

| Regime | Model | Feature Set | Weighting | AP / PR-AUC | ROC-AUC | Brier | ECE | Precision | Recall | F1 |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| Legacy | Prevalence | REFERENCE | REFERENCE | 0.0928 | 0.4940 | 0.0859 | 0.0180 | NA | 0.0000 | 0.0000 |
| Legacy | Lagged Rule | REFERENCE | REFERENCE | 0.1512 | 0.5636 | 0.0949 | 0.0949 | 0.4925 | 0.1426 | 0.2211 |
| Legacy | Winning Logistic Benchmark | `trajectory_only` | Balanced | 0.3397 | 0.7457 | 0.1957 | 0.3340 | 0.2518 | 0.6164 | 0.3575 |
| Legacy | CatBoost | `trajectory_only` | Unweighted | 0.2873 | 0.7417 | 0.0830 | 0.0335 | 0.3823 | 0.1800 | 0.2447 |
| Legacy | CatBoost | `trajectory_only` | Balanced | 0.3002 | 0.7263 | 0.1956 | 0.3249 | 0.2364 | 0.6108 | 0.3409 |
| Legacy | CatBoost | `full_v1` | Balanced | 0.3978 | 0.8022 | 0.1300 | 0.1636 | 0.2592 | 0.6202 | 0.3656 |
| Legacy | **CatBoost (Winner)** | `full_v1` | **Unweighted** | **0.4071** | **0.8064** | **0.0720** | **0.0287** | 0.5426 | 0.2540 | 0.3461 |
| Modern | Prevalence | REFERENCE | REFERENCE | 0.4479 | 0.5061 | 0.3152 | 0.2568 | NA | 0.0000 | 0.0000 |
| Modern | Lagged Rule | REFERENCE | REFERENCE | 0.4961 | 0.5636 | 0.4010 | 0.4010 | 0.6681 | 0.2139 | 0.3240 |
| Modern | Winning Logistic Benchmark | `static_only` | Unweighted | 0.7587 | 0.8419 | 0.1916 | 0.1405 | 0.8083 | 0.3620 | 0.5000 |
| Modern | CatBoost | `static_only` | Unweighted | 0.7567 | 0.8153 | 0.2129 | 0.1726 | 0.7953 | 0.4457 | 0.5712 |
| Modern | CatBoost | `static_only` | Balanced | 0.7629 | 0.8224 | 0.1842 | 0.1026 | 0.7507 | 0.6359 | 0.6885 |
| Modern | CatBoost | `full_v1` | Unweighted | 0.7602 | 0.8222 | 0.2137 | 0.1794 | 0.8010 | 0.4342 | 0.5632 |
| Modern | **CatBoost (Winner)** | `full_v1` | **Balanced** | **0.7677** | **0.8292** | **0.1816** | **0.1061** | 0.7606 | 0.6269 | 0.6873 |

### Statistical robustness and paired comparison vs Logistic benchmark

Deterministic 1,000-resample project-cluster bootstrap 95% confidence intervals were
computed for all candidates and for the paired difference $\Delta\text{AP} = \text{AP}_{\text{CatBoost}} - \text{AP}_{\text{Logistic}}$ on identical out-of-fold rows:

- **Legacy Winning Challenger (`catboost_full_v1__unweighted`)**:
  - CatBoost AP: **0.4071** (95% project-cluster CI: 0.3541–0.4578).
  - Logistic Benchmark AP: **0.3397** (95% project-cluster CI: 0.2872–0.3884).
  - Paired Difference $\Delta\text{AP}$: **+0.0674** (95% project-cluster CI: **+0.0376 to +0.0955**).
  - Statistical significance: **Statistically significant ($p < 0.05$)**. Zero is strictly outside the 95% confidence interval.
  - Calibration improvement: Brier score improves from 0.1957 to **0.0720** ($\Delta = -0.1238$, 95% CI: $-0.1285$ to $-0.1187$); ECE improves from 0.3340 to **0.0287** ($\Delta = -0.3053$, 95% CI: $-0.3133$ to $-0.2967$).
- **Modern Winning Challenger (`catboost_full_v1__balanced`)**:
  - CatBoost AP: **0.7677** (95% project-cluster CI: 0.7420–0.7937).
  - Logistic Benchmark AP: **0.7587** (95% project-cluster CI: 0.7340–0.7861).
  - Paired Difference $\Delta\text{AP}$: **+0.0090** (95% project-cluster CI: **−0.0196 to +0.0338**).
  - Statistical significance: **Not statistically significant**. The 95% confidence interval spans zero.
  - Calibration: Brier score improves slightly from 0.1916 to 0.1816; ECE improves from 0.1405 to 0.1061.

### Weighting effects and calibration analysis

- **Legacy**: Class balancing is not required for CatBoost to achieve high AP in Legacy. In fact, unweighted CatBoost achieves the highest AP (0.4071 vs 0.3978) while preserving natural probability calibration (mean score 0.1020 vs 0.0945 base rate, ECE 0.0287). This resolves the trade-off encountered in Logistic refinement, where balanced weighting was necessary for AP but severely degraded probability calibration.
- **Modern**: Class balancing modestly improves CatBoost AP (0.7677 balanced vs 0.7602 unweighted) and recall at the descriptive 0.5 threshold (0.6269 vs 0.4342), with mean predicted probability of 0.3785 vs 0.4493 base rate (ECE 0.1061).

### Stability checks and February 2025

- **February 2025**: Retained across all 12 Legacy folds. For `catboost_full_v1__unweighted`, Feb-2025 fold AP is **0.0711** (compared to 0.0347 in Logistic and 0.0437 in lagged rule). Pooled Legacy AP without Feb-2025 is **0.4162**.
- **Fold AP dispersion**:
  - Legacy CatBoost winner fold AP spans 0.0711 to 0.6328 (fold mean 0.4184, std 0.1628). The improvement over Logistic is broadly distributed across historical origins rather than isolated to a single fold.
  - Modern CatBoost winner fold AP spans 0.7238 to 0.8394 (fold mean 0.7696, std 0.0411), demonstrating tight temporal stability.

### Feature importance diagnostic

Feature importance averaged across walk-forward folds confirms:
1. `months_to_effective_schedule` is the primary predictor in both regimes (18.1–22.2% in Legacy, 27.5–31.5% in Modern).
2. Administrative identifiers / categoricals (`agency` 14.3–15.2%, `state` 14.4%, `sector` 6.5–11.5%) provide substantial predictive value in full-v1 CatBoost models through native decision-tree categorical splits.
3. Cost and schedule scale features (`months_to_original_schedule` 5.1–8.1%, `original_cost` 4.2–6.4%, `physical_progress_t` 5.6–6.9%) contribute balanced importance.
4. No single feature exhibits artificial or leakage-level dominance (>50%), and 0 prohibited metadata features entered any feature set.

### Tests, hashes, and final status

12 new CatBoost challenger unit/regression tests cover data preparation, string missingness sentinels, deterministic execution within tolerance, paired cluster bootstrap, fold alignment with Logistic benchmarks, and canonical hash protection.

- **Full regression suite**: **178/178 passing** (126 extraction/linkage baseline + 13 dataset builder + 11 baseline evaluation + 7 robustness audit + 9 Logistic refinement + 12 CatBoost challenger).
- **Canonical dataset hashes (immutable)**:
  - `projects_monthly.csv`: `9512A9881E17DFDED6E182D87A8DFB1C4EDBD36C0D9B8A7DA9FD1ABB7E002FBF`
  - `projects_completed.csv`: `89BEA84FD68A22E327090C1E4E4533F5BCD745ADCA61EB4E66172EE9023BB910`

### Explicit Regime Recommendations

- **Legacy Regime**: **`PREFER_CATBOOST`**  
  `catboost_full_v1__unweighted` outperforms the locked balanced Logistic benchmark ($\Delta\text{AP} = +0.0674$, 95% project-cluster CI: $+0.0376$ to $+0.0955$; the CI strictly excludes zero). Furthermore, it resolves the severe probability distortion of the balanced Logistic baseline, reducing ECE from 0.3340 to 0.0287 and Brier score from 0.1957 to 0.0720.
- **Modern Regime**: **`KEEP_LOGISTIC`**  
  `catboost_full_v1__balanced` achieves a minor point-estimate gain ($\Delta\text{AP} = +0.0089$), but the paired 95% project-cluster CI spans zero ($-0.0196$ to $+0.0338$). No statistically distinguishable CatBoost improvement was demonstrated; Logistic is preferred for parsimony.

---

## 10. Formal Record of Model-Family Decisions

| Regime | Model Decision | Selected Specification | Key Empirical Evidence |
|---|---|---|---|
| **Legacy** (Jan 2023 – Jun 2025) | **`PREFER_CATBOOST`** | `catboost_full_v1__unweighted` | AP = **0.4071** (95% project-cluster CI: 0.3541–0.4578). Paired $\Delta\text{AP}$ vs balanced Logistic = **+0.0674** (95% project-cluster CI: **+0.0376 to +0.0955**; CI strictly excludes zero). Resolves severe probability distortion without class weighting: Brier = **0.0720**, ECE = **0.0287** (vs 0.1957 and 0.3340 in balanced Logistic). |
| **Modern** (Jul 2025 – Jul 2026) | **`KEEP_LOGISTIC`** | `logistic_static_only__unweighted` | AP = **0.7587** (95% project-cluster CI: 0.7340–0.7861). CatBoost best challenger $\Delta\text{AP} = +0.0090$ (95% project-cluster CI: **−0.0196 to +0.0338**; CI spans zero). No statistically distinguishable CatBoost improvement was demonstrated; Logistic is preferred for parsimony. |

**Policy Boundary**: Model-family selection is closed for IRIS v1. No further model families (XGBoost, LightGBM, Random Forest, Neural Networks) and no secondary targets shall be introduced in this phase.

---

## 11. Calibration Strategy & Operational Decision-Policy Design

The approved design is fixed in `docs/calibration_policy.md`. It requires strict
main-fold embargo $T+3<E$, strict recursive nested embargo $T'+3<T$, raw-logit
Platt inputs, historical OOF-only threshold selection, and no early-fold or
in-sample fallback. Section 12 records its completed implementation and empirical
results.

## 12. Calibration and Operational Policy Evaluation Completed

Implementation: `src/ml/operational_policy.py`

Tests: `tests/test_ml_operational_policy.py`

Generated results: `data/ml/schedule_extension_3m/evaluation/operational_policy/`

### Locked models, chronology, and minimum-data rule

- Legacy remains `catboost_full_v1__unweighted`. No active calibration layer is
  introduced; raw CatBoost probabilities are the operational scores. Historical
  nested-OOF Platt fits are diagnostic only.
- Modern remains `logistic_static_only__unweighted`. Active calibration, when
  available, is a two-parameter Platt model fit directly to fold-local Logistic
  decision scores/logits.
- The main and nested embargoes are strict inequalities. Generated audits record
  zero main embargo violations, zero nested embargo violations, zero evaluation
  leakage rows, and zero in-sample threshold fallbacks.
- Three defensible calibration minimums were evaluated: 500 rows / 1 month / 50
  observations per class; 750 / 1 / 75; and 1,000 / 2 / 100. The selected rule is
  **1,000 rows spanning at least two chronological OOF target months with at least
  100 observations per class**. Temporal diversity is required for a temporal
  two-parameter calibrator; this deliberately prevents activation on one large
  historical month. The two looser rules remain sensitivity results and are not
  silently selected.

The exact Modern calibration state is:

| Fold | Evaluation origin | Nested OOF calibration pool | Positives | Calibration |
|---|---|---:|---:|---|
| M1 | 2025-12 | 0 rows / 0 months | 0 | Inactive |
| M2 | 2026-01 | 0 rows / 0 months | 0 | Inactive |
| M3 | 2026-02 | 0 rows / 0 months | 0 | Inactive |
| M4 | 2026-03 | 772 rows / 1 month (`2025-11`) | 117 | Inactive |
| M5 | 2026-04 | 2,110 rows / 2 months (`2025-11`, `2025-12`) | 725 | **Active Platt** |

Thus, the actual embargo-safe calculation leaves M1-M4 uncalibrated and activates
calibration only for M5. No embargo was weakened. Legacy has no active-calibration
folds; diagnostic Platt history meets the selected minimum from 2024-06 onward.

### Calibration findings

For Modern M5, the fitted Platt slope is **1.20633** and intercept is **0.45513**.
Brier improves from **0.18024** to **0.16710** and 10-bin ECE from **0.11217** to
**0.08535**. AP remains **0.69992** and ROC-AUC remains **0.83546**, as expected
from a monotonic transformation. The 1,000-resample project-cluster intervals are
0.17111-0.18915 raw versus 0.15905-0.17552 calibrated for Brier, and
0.10039-0.13431 raw versus 0.07245-0.10583 calibrated for ECE. The approved Platt
candidate therefore reduces Modern underprediction and improves probability error
on the one fold where it can be fit safely, without harming discrimination.

Legacy diagnostic Platt results are mixed and support the locked raw-score policy:
diagnostic Brier improves in 7 of 10 eligible folds but worsens materially in
2024-11 through 2025-01; diagnostic ECE improves in 8 of 10 folds but worsens in
2024-10 and 2024-11. Raw CatBoost probabilities remain operational throughout.

### Threshold availability and Policy A results

Thresholds are persisted with calibrator parameters before evaluation-fold model
scoring. Legacy 2023-07 and 2023-08 have `threshold_status=UNAVAILABLE`; the other
10 Legacy folds are available. Modern M1-M4 are unavailable and only M5 is
available. Unavailable folds emit threshold-free metrics only.

| Regime | Historical recall target | Available folds | Future precision | Future recall | F1 | Mean alerts | Mean alert rate | Fold recall std |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Legacy | 0.50 | 10 | **0.3288** | 0.5420 | **0.4093** | 219.6 | **14.90%** | 0.1521 |
| Legacy | 0.60 | 10 | 0.2610 | 0.6607 | 0.3741 | 337.2 | 22.74% | 0.1610 |
| Legacy | 0.70 | 10 | 0.2076 | 0.7500 | 0.3252 | 481.1 | 32.60% | 0.1720 |
| Legacy | 0.80 | 10 | 0.1739 | 0.8423 | 0.2883 | 645.1 | 44.25% | 0.1823 |
| Modern | 0.50 | 1 | 0.7937 | 0.6103 | 0.6900 | 509 | 31.32% | NA |
| Modern | 0.60 | 1 | 0.7472 | 0.7009 | 0.7233 | 621 | 38.22% | NA |
| Modern | 0.70 | 1 | 0.7060 | 0.7764 | **0.7396** | 728 | 44.80% | NA |
| Modern | 0.80 | 1 | 0.6536 | 0.8323 | 0.7322 | 843 | 51.88% | NA |

Legacy's February 2025 instability remains visible rather than removed: achieved
recall is 0.093, 0.163, 0.209, and 0.279 for the four recall-floor candidates,
respectively, far below the other future folds. No causal explanation is assigned.

The Legacy 0.50 candidate is the most defensible historical precision/volume
trade-off: it has the highest F1 and precision, its mean alert rate is just below
15%, and moving to 0.60 costs 6.8 precision points and adds about 118 alerts per
fold. It is recommended as the **Policy A candidate for operational review**, not
as a frozen production threshold. Modern 0.70 has the best single available-fold
F1, but one calibrated threshold fold provides no temporal stability evidence;
there is therefore **no supported final Modern operating-policy recommendation**.

Policy B precision floors are retained as secondary sensitivity results. In
Legacy, targets 0.30/0.40/0.50 yield pooled future precision 0.381/0.628/0.825 but
recall only 0.466/0.260/0.170. In Modern's single available fold they generate
very high alert rates (99.9%, 90.9%, and 76.1%), so they are not recommended.

### Alert volume, capacity caps, and Top-K

Capacity caps are sensitivity analyses only; none is frozen. For Legacy recall
targets 0.50/0.60/0.70/0.80, the 15% cap activates in 6/8/9/10 of 10 available
folds, the 20% cap in 2/6/9/10, and the 25% cap in 0/5/7/9. For Modern, every
15%, 20%, and 25% cap activates for every recall target in the sole available
fold. At Modern target 0.70, those caps reduce achieved recall from 0.7764 to
0.2779, 0.3927, and 0.5000, producing shortfalls of 0.4221, 0.3073, and 0.2000.
The results demonstrate that a cap cannot be chosen independently of recall and
workload; no candidate cap is adopted.

Top-K remains supplemental. Across all folds, mean precision at K=50/100/150/200
is 0.610/0.453/0.377/0.327 for Legacy. Modern mean precision at K=50/100/200 is
0.664/0.704/0.782. Full per-fold alert counts, rates, confusion matrices,
precision, recall, F1, precision@100, precision@200, cap overrides, target recall,
post-cap recall, and recall shortfall are in the generated CSV artifacts.

### Artifacts, tests, hashes, and limitations

The generated directory contains fold calibration metrics, calibration-pool and
nested-OOF audits, minimum-data sensitivity, reliability bins, threshold-policy
fold and aggregate metrics, alert-volume and cap sensitivity, Top-K and sector
metrics, predictions with raw logits and operational probabilities, frozen
threshold configuration, and 1,000-resample project-cluster confidence intervals.
Generated data remains untracked.

Thirteen new regression tests cover strict main and nested embargo equality,
evaluation leakage, no in-sample fallback, exact Modern early-fold inactivity,
raw-logit Platt inputs, threshold persistence before evaluation, cap/recall
accounting, deterministic contracts, locked models, and canonical hash protection.
The full suite is **191/191 passing**.

Canonical hashes remain unchanged:

- `projects_monthly.csv`: `9512A9881E17DFDED6E182D87A8DFB1C4EDBD36C0D9B8A7DA9FD1ABB7E002FBF`
- `projects_completed.csv`: `89BEA84FD68A22E327090C1E4E4533F5BCD745ADCA61EB4E66172EE9023BB910`

Unresolved limitations are the single safely calibrated Modern origin, temporal
base-rate drift between Modern calibration months, Legacy February instability,
and the absence of stakeholder capacity/cost inputs. These preclude freezing a
Modern threshold, a universal numerical threshold, or an alert-rate cap.

The calibration-policy next steps remain pending and unchanged: collect additional
mature Modern outcomes, and obtain stakeholder capacity and error-cost inputs
before freezing any production threshold or cap. The separately authorized first
explainability stage is recorded below.

## 13. Deterministic Locked-Model Explainability Completed

Implementation: `src/ml/explain_locked_models.py`

Contract: `docs/explanation_contract.md`

Tests: `tests/test_ml_explain_locked_models.py`

Generated results: `data/ml/schedule_extension_3m/evaluation/explainability/`

### Exact explanation methods and score separation

- Legacy `catboost_full_v1__unweighted` uses CatBoost-native TreeSHAP for the
  exact fold-fitted model. The expected value and 36 native feature contributions
  are in CatBoost raw-margin/logit space.
- Modern `logistic_static_only__unweighted` uses the exact fold-fitted frequency
  encoding, numeric standardization, missingness components, fitted intercept,
  and coefficients. Each encoded local contribution is transformed value
  multiplied by its fitted coefficient, in raw-logit space. Encoded components
  retain their human-readable source feature and at-T source/derived value.
- Platt calibration remains a separate score transformation. Local artifacts
  record raw model probability, raw decision score, calibrated probability when
  active, and calibration status. Platt terms never enter feature contributions.
- Feature contributions describe predictive association with the fitted output.
  They are not causal attribution.

For every row, the implemented invariant is:

`expected_base_value + sum(feature_contribution) = raw_decision_score`

The maximum reconciliation error is **1.33e-14** for Legacy TreeSHAP and
**3.55e-15** for Modern Logistic, against the declared `1e-10` tolerance. Refitted
raw scores reconcile with the locked operational-policy predictions to a maximum
absolute difference of **4.97e-14**.

### Local records, source values, and ranks

All 17 accepted evaluation origins and **25,189** project-month rows are
explained. `local_explanations.csv` preserves **996,894** native/encoded
contribution rows. `top_contributors.csv` contains a configurable source-feature
view, generated here with up to five positive and five negative contributors per
project-month; the complete vector remains authoritative.

Risk rank and percentile are computed only inside the same report month, regime,
and locked model. Rank 1 is highest operational probability; equal scores use
`project_code` ascending. Percentile is
`(month_population - rank + 1) / month_population`. Modern 2026-04 ranks use the
active calibrated probability, while its explanations remain tied to the raw
Logistic score. The Platt transformation is monotonic and does not alter ordering.

No feature value is manufactured for a missing input. Support/presence and
missingness components retain their literal model meaning. `project_code` appears
only as metadata. Project name, future target-event fields, completion metadata,
completed-project information, provenance, and unintended identifiers are absent
from the model feature vectors.

### Global contribution findings

Global rank is mean absolute source-feature contribution over concatenated OOF
rows within regime. The leading Legacy TreeSHAP features are:

| Rank | Legacy feature | Mean absolute contribution |
|---:|---|---:|
| 1 | `months_to_effective_schedule` | 0.7123 |
| 2 | `agency` | 0.4810 |
| 3 | `state` | 0.4260 |
| 4 | `months_to_original_schedule` | 0.1119 |
| 5 | `n_prior_schedule_extensions` | 0.1093 |
| 6 | `schedule_revision_lag_months` | 0.1092 |
| 7 | `project_age_months` | 0.0889 |
| 8 | `sector` | 0.0860 |
| 9 | `original_cost` | 0.0794 |
| 10 | `observed_tenure_months` | 0.0666 |

The leading Modern source-aggregated Logistic features are:

| Rank | Modern feature | Mean absolute contribution |
|---:|---|---:|
| 1 | `months_to_effective_schedule` | 0.9036 |
| 2 | `physical_progress_t` | 0.3239 |
| 3 | `sector` | 0.1983 |
| 4 | `months_to_original_schedule` | 0.1957 |
| 5 | `revised_cost_t` | 0.1747 |
| 6 | `months_since_start` | 0.1668 |
| 7 | `schedule_revision_lag_months` | 0.1310 |
| 8 | `original_cost` | 0.0946 |
| 9 | `start_date_supported` | 0.0758 |
| 10 | `project_age_months` | 0.0708 |

`global_feature_contributions.csv` also reports signed mean, standard deviation,
minimum, p05, p25, median, p75, p95, maximum, and positive/negative/zero
frequencies for every source feature.

### Legacy TreeSHAP versus prior CatBoost importance

The TreeSHAP and previously exported CatBoost importance top-10 sets are identical
(top-10 Jaccard **1.0**), and their full 36-feature rank Spearman correlation is
**0.9792**. They are not treated as interchangeable measures. The largest rank
disagreements are reported explicitly: `past_progress_stagnant_3m` is TreeSHAP
rank 21 versus prior rank 28; `n_prior_cost_revisions` is 25 versus 20;
`n_prior_schedule_extensions` is 5 versus 9; and
`revised_to_original_cost_ratio` is 18 versus 14. No ranking was adjusted to make
the measures agree.

### Fold-level stability and retained unstable origins

Legacy fold top-10 overlap with the global top 10 has mean Jaccard **0.685**,
range **0.538-0.818**. `months_to_effective_schedule`, `agency`, `state`, and
`project_age_months` are top-10 features in all 12 origins. February 2025 remains
in place and has Jaccard **0.538**, tied for the minimum. Its top 10 are
`months_to_effective_schedule`, `agency`, `state`, `physical_progress_t`,
`observed_tenure_months`, `schedule_has_been_revised`, `sector`,
`project_age_months`, `months_to_original_schedule`, and
`past_progress_stagnant_3m`. This variation is reported without a real-world
explanation.

Modern fold top-10 overlap has mean Jaccard **0.762**, range **0.538-0.818**.
Seven features are top 10 in every origin: `months_to_effective_schedule`,
`physical_progress_t`, `revised_cost_t`, `months_to_original_schedule`, `sector`,
`months_since_start`, and `schedule_revision_lag_months`. The first four Modern
origins each have Jaccard 0.818; 2026-04 has 0.538, with `agency`, `state`, and
`start_date_is_present` entering its top 10. No fold is removed and no source of
the variation is asserted.

The stable leading features support a reasonably consistent explanation layer,
while the February Legacy and April Modern changes require continued fold-level
reporting rather than a single timeless global narrative.

### Artifacts, tests, and immutable inputs

Generated artifacts are:

- `local_explanations.csv`: 996,894 complete native/encoded contribution rows;
- `top_contributors.csv`: 250,570 configured top-contributor rows;
- `global_feature_contributions.csv`: 61 regime-feature summaries;
- `fold_explanation_stability.csv`: 557 fold-feature summaries;
- `risk_rankings.csv`: 25,189 project-month rankings;
- `explainability_manifest.json`: methods, folds, hashes, reconciliation,
  feature-scope validation, global comparison, and stability audit.

Eleven new tests cover TreeSHAP/logit reconciliation, locked regime/model use,
within-month ranks, prohibited features, metadata separation, calibration
separation, deterministic explanation ordering, global/fold completeness,
artifact counts, and canonical hash protection. The full suite is **202/202
passing**.

Canonical hashes remain unchanged:

- `projects_monthly.csv`: `9512A9881E17DFDED6E182D87A8DFB1C4EDBD36C0D9B8A7DA9FD1ABB7E002FBF`
- `projects_completed.csv`: `89BEA84FD68A22E327090C1E4E4533F5BCD745ADCA61EB4E66172EE9023BB910`

### Exact next step

Perform a consumer-contract acceptance review of `docs/explanation_contract.md`
and manually audit representative high-, middle-, and low-ranked project records
against their complete contribution vectors. Any dashboard UI, generated
narrative, counterfactual recommendation, new target, model family, or threshold
work requires separate authorization. Continue collecting mature Modern outcomes
for the already documented calibration-policy stability step.

---

*Flagship H=3 model families, target, calibration policy, and canonical inputs remain unchanged. The first deterministic predictive-explanation layer is complete.*
