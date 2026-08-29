# IRIS Deterministic Explanation Contract

**Version**: 1.0

**Target**: `target_effective_schedule_ext_3m`

**Status**: Machine-readable contract for the first locked-model explanation layer.

## 1. Scope and interpretation

This contract defines the generated records that a future API, dashboard, or
language-model consumer may read. Explanations describe predictive association
with a fitted model output. They are not causal attribution and must not be
presented as intervention advice or a statement about real-world mechanisms.

The model family, target, feature lists, folds, and calibration policy are closed:

| Regime | Model | Explanation method | Contribution space |
|---|---|---|---|
| Legacy | `catboost_full_v1__unweighted` | CatBoost-native TreeSHAP | Raw CatBoost margin/logit |
| Modern | `logistic_static_only__unweighted` | Fold-local transformed value multiplied by fitted Logistic coefficient | Raw Logistic logit |

For both regimes, every complete local vector satisfies:

`expected_base_value + sum(feature_contribution) = raw_decision_score`

within the tolerance declared in `explainability_manifest.json`. Contributions
do not sum to probability. Probability is obtained by applying the model link
function to the raw decision score.

Modern Platt calibration is a separate monotonic score transformation. It may
change the reported calibrated probability, but Platt parameters never appear as
model features and never enter a feature-contribution vector.

## 2. Shared identifiers and score semantics

The stable project-month explanation key is:

`(project_code, report_month, regime, model_identifier)`

- `project_code` is metadata only. It is never a model feature.
- `report_month` is the evaluation origin and ranking scope. It is never a model
  feature.
- `regime` is `LEGACY` or `MODERN` and identifies the locked model family.
- `model_identifier` is the exact locked model specification.
- `raw_decision_score` is the additive explanation space: CatBoost raw margin or
  Logistic raw logit.
- `raw_predicted_probability` is the locked model probability before any Platt
  transformation.
- `calibrated_probability` is populated only when approved temporal Platt
  calibration is active; otherwise it is empty.
- `calibration_active` states whether `calibrated_probability` is populated.
- `ranking_probability` is the operational probability used for rank ordering:
  raw for Legacy and inactive Modern folds, calibrated for an active Modern fold.

Blank feature values represent source/derived-feature absence. Consumers must
not replace a blank with zero or invent a descriptive explanation. Support and
missingness indicators are interpreted only by their literal names and values.

## 3. Risk rank and percentile

Ranks are computed independently inside each `(report_month, regime,
model_identifier)` population. No project from another month or regime enters the
comparison.

- `risk_rank_within_month = 1` is the highest operational probability.
- Equal scores use `project_code` ascending as the deterministic tie-break.
- `risk_percentile_within_month = (month_population - rank + 1) / month_population`.
- The highest-ranked row therefore has percentile `1.0`; the lowest-ranked row
  has percentile `1 / month_population`.

Ranks and percentiles are relative portfolio positions, not calibrated event
probabilities.

## 4. `local_explanations.csv`

This is the complete machine-readable contribution vector. It contains one row
per explained project-month and native/encoded model-input component.

| Column | Type | Contract |
|---|---|---|
| `project_code` | string | Metadata-only source identifier. |
| `report_month` | `YYYY-MM` | Evaluation origin and within-month ranking scope. |
| `regime` | enum | `LEGACY` or `MODERN`. |
| `model_identifier` | string | Exact locked model name. |
| `raw_predicted_probability` | float | Pre-calibration model probability. |
| `calibrated_probability` | nullable float | Populated only when temporal Platt is active. |
| `calibration_active` | boolean | Whether the calibrated score is active. |
| `raw_decision_score` | float | Raw additive model output. |
| `risk_rank_within_month` | integer | Descending operational-score rank in the same month/regime. |
| `risk_percentile_within_month` | float | Within-month percentile defined in Section 3. |
| `month_population` | integer | Number of projects in the ranking population. |
| `source_feature_name` | string | Approved human-readable at-T feature name. |
| `source_feature_value_at_t` | nullable string | Feature value visible at prediction time. Categorical spelling is preserved. |
| `encoded_feature_name` | string | Native feature name or exact fold-local transformed component name. |
| `model_input_value` | nullable string/float | Value passed to the fitted model component after fold-local transformation. |
| `encoding` | enum | `CATBOOST_NATIVE`, `TRAIN_FREQUENCY`, `TRAIN_STANDARDIZED`, or `MISSING_INDICATOR`. |
| `contribution_method` | enum | TreeSHAP or Logistic coefficient-product method. |
| `contribution_space` | enum | `RAW_MARGIN_LOGIT`. |
| `feature_contribution` | float | Signed additive contribution to `raw_decision_score`. |
| `contribution_direction` | enum | `POSITIVE`, `NEGATIVE`, or `ZERO`, determined only by contribution sign. |
| `contribution_rank` | integer | Rank by absolute component contribution within the complete local vector; encoded name breaks ties. |
| `expected_base_value` | float | CatBoost expected value or fitted Logistic intercept. |

For Modern numeric inputs, `TRAIN_STANDARDIZED` and `MISSING_INDICATOR` are two
separate encoded components mapped to the same `source_feature_name`. Summing all
components for one source feature gives its source-level local contribution.
Categorical Logistic inputs use the training-fold frequency for the exact source
category; both the source category and transformed frequency remain available.

## 5. `top_contributors.csv`

This is a configurable view derived from the complete vector. The default is the
five largest positive and five largest negative source-feature contributions per
project-month. Encoded components are summed to their source feature before
selection.

In addition to the shared score and ranking fields, it contains:

- `source_feature_name` and `source_feature_value_at_t`;
- `feature_contribution` and `contribution_direction`;
- `direction_rank`, where 1 is strongest within the positive or negative side;
- `configured_direction_limit`;
- `contribution_space`.

Consumers must use predictive wording such as “increased the model's predicted
risk,” “reduced the model's predicted risk,” or “was among the strongest
contributors to this prediction.”

## 6. `risk_rankings.csv`

This artifact contains exactly one record per explained project-month. It carries
all shared model, calibrated-score, and ranking fields plus:

- `ranking_probability`;
- `ranking_score_type`, fixed to `OPERATIONAL_PROBABILITY`;
- `month_population`.

It is the authoritative source for display ordering. Feature-contribution rows
must not be independently reranked across months.

## 7. `global_feature_contributions.csv`

This artifact aggregates encoded components to source features inside each
regime. It reports:

- model, method, contribution space, evaluation fold and row counts;
- mean signed and mean absolute contribution;
- standard deviation, minimum, p05, p25, median, p75, p95, and maximum;
- positive, negative, and zero counts and frequencies;
- deterministic global feature rank by mean absolute contribution;
- for Legacy only, previous CatBoost feature-importance value/rank, rank
  difference, and comparison label.

TreeSHAP mean absolute contribution and CatBoost's previously exported global
importance are distinct measures. Their rankings are compared, not forced to
match.

## 8. `fold_explanation_stability.csv`

This artifact contains one record per evaluation fold and source feature. It
reports fold-local contribution distribution summaries, fold and global feature
ranks, absolute rank difference, top-10 membership, and the fold top-10 Jaccard
overlap with the regime-global top 10.

Legacy February 2025 remains present. Modern folds remain separate. Variation is
reported without an inferred real-world explanation.

## 9. `explainability_manifest.json`

The manifest is the authoritative execution audit. It records:

- runtime versions, locked models/features, target, and exact origins;
- source manifest and canonical hashes;
- contribution methods, score space, ranking formula, and top-N configuration;
- fold-level embargo and reconciliation audits;
- global rankings and fold stability summaries;
- Legacy TreeSHAP versus prior importance comparison;
- explicit Legacy February 2025 and Modern fold inspections;
- generated artifact row counts and SHA-256 hashes;
- prohibited-feature, metadata separation, calibration separation, model-family,
  target-scope, and canonical-immutability validation.

## 10. Consumer invariants

Any future consumer must preserve these invariants:

1. Never present predictive contributions as causal attribution.
2. Never treat `project_code`, project name, target-event fields, completed-project
   information, or extraction provenance as model features.
3. Never merge calibrated-score transformation terms into the feature vector.
4. Never compare ranks across different report months or regimes.
5. Never manufacture a feature value or explanation for a blank value.
6. Never discard zero or negative contributions from the complete local artifact.
7. Never infer an operational threshold, alert policy, or recommended action from
   an explanation record alone.
