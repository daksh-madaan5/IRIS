# PAIMANA Modeling Handoff

**Updated**: 2026-08-29  
**Version**: 1.4 (Baseline Robustness Audit Completed)  
**Phase**: Flagship H=3 baseline evaluation and robustness diagnostics complete — advanced models and production modeling not begun.

---

## 1. Canonical Dataset Hashes (Verified Unchanged)

| File | Rows | SHA-256 |
|---|---:|---|
| `data/processed/projects_monthly.csv` | 64,608 | `9512A9881E17DFDED6E182D87A8DFB1C4EDBD36C0D9B8A7DA9FD1ABB7E002FBF` |
| `data/processed/projects_completed.csv` | 876 | `89BEA84FD68A22E327090C1E4E4533F5BCD745ADCA61EB4E66172EE9023BB910` |

Pre-implementation regression baseline: **126/126 passing**. The post-implementation
suite adds 13 dataset-builder tests; see Section 5 for the final result.

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
| [`tests/test_ml_dataset_builder.py`](file:///d:/coding/PAIMANA/tests/test_ml_dataset_builder.py) | Added | Builder semantics and generated-data regression tests |
| [`tests/test_ml_evaluate_baselines.py`](file:///d:/coding/PAIMANA/tests/test_ml_evaluate_baselines.py) | Added | Embargo, preprocessing, leakage, regime, determinism, lagged-rule, and output tests |
| [`tests/test_ml_robustness_audit.py`](file:///d:/coding/PAIMANA/tests/test_ml_robustness_audit.py) | Added | Feature partition, clustered bootstrap, aggregation, ablation-fold, output, and hash tests |

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

---

*Flagship H=3 dataset construction, baseline evaluation, and robustness audit complete. No advanced model trained. Both canonical datasets preserved unchanged.*
