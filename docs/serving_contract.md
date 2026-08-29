# IRIS Deterministic Model-Serving Contract

**Version**: 1.0

**Serving artifact**: `iris_serving_v1`

**Target**: `target_effective_schedule_ext_3m`

**Status**: Locked consumer contract for the first deterministic serving/API layer.

## 1. Scope

This contract defines the JSON read by a future IRIS dashboard or grounded
language-model layer. The service copies accepted model scores, calibration state,
ranks, percentiles, and configured source-level top contributors from the locked
explainability outputs. It does not train, refit, recalibrate, rerank, create a
label, infer completion, or resolve project identities.

The only served target value is the target **name**
`target_effective_schedule_ext_3m`. The realized future target label is never
served. Completed-project fields, target-event evidence, project names, extraction
provenance, and June-July crosswalk proposals are excluded.

The strict machine schema is emitted by FastAPI at `GET /openapi.json` from the
Pydantic models in `src/serving/schemas.py`. Those models reject extra response
fields. This document records the same contract in consumer-facing terms.

## 2. Locked score and explanation semantics

| Concept | JSON field | Exact meaning |
|---|---|---|
| Raw score probability | `raw_probability` | Locked model probability before any approved Platt transformation. Legacy uses the native CatBoost probability; Modern uses the native Logistic probability. |
| Calibrated risk probability | `risk_probability` | Operational probability copied from `ranking_probability`. It equals `raw_probability` when calibration is inactive and equals the approved temporal-Platt probability when calibration is active. It is never recomputed by serving code. |
| Calibration state | `calibration_active` | `true` only where the approved temporal Platt transform was active. In the current artifact this is Modern 2026-04 only. Legacy is always uncalibrated. |
| Rank | `risk_rank` | Rank copied from the explainability artifact inside the same report month, regime, and model. Rank 1 is highest risk. |
| Percentile | `risk_percentile` | Copied within-month relative position `(population_size - risk_rank + 1) / population_size`. It is not an event probability. |
| Predictive contribution | `contribution` | Signed source-feature contribution in raw margin/logit space. Positive raises and negative lowers the fitted raw score relative to its base value. It is predictive, not causal, and does not sum to probability. |
| Source value | contributor `value` and `source_feature_values` | Exact at-T value already attached to the accepted top-contributor artifact. Missing remains JSON `null`; it is never replaced with zero or inferred. |
| Regime/model identity | `regime`, `model_id` | `LEGACY` uses `catboost_full_v1__unweighted`; `MODERN` uses `logistic_static_only__unweighted`. Records are never pooled or crosswalked. |

`source_feature_values` contains the relevant at-T values for the configured top
positive and negative source features in that record. The same value is repeated
inside each contributor object so a contributor remains self-contained.

## 3. Compact risk record JSON Schema

The following JSON Schema is normative for every full project-month item. All
objects set `additionalProperties` to `false`, except
`source_feature_values`, whose keys are reviewed model feature names.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://iris.local/schemas/risk-record-v1.json",
  "title": "IRIS RiskRecord v1",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "project_code", "report_month", "regime", "target", "model_id",
    "raw_probability", "risk_probability", "calibration_active",
    "risk_percentile", "risk_rank", "population_size",
    "top_positive_contributors", "top_negative_contributors",
    "source_feature_values", "version_metadata"
  ],
  "properties": {
    "project_code": {"type": "string", "minLength": 1},
    "report_month": {"type": "string", "pattern": "^[0-9]{4}-(0[1-9]|1[0-2])$"},
    "regime": {"enum": ["LEGACY", "MODERN"]},
    "target": {"const": "target_effective_schedule_ext_3m"},
    "model_id": {"type": "string", "minLength": 1},
    "raw_probability": {"type": "number", "minimum": 0, "maximum": 1},
    "risk_probability": {"type": "number", "minimum": 0, "maximum": 1},
    "calibration_active": {"type": "boolean"},
    "risk_percentile": {"type": "number", "exclusiveMinimum": 0, "maximum": 1},
    "risk_rank": {"type": "integer", "minimum": 1},
    "population_size": {"type": "integer", "minimum": 1},
    "top_positive_contributors": {
      "type": "array", "maxItems": 5,
      "items": {"$ref": "#/$defs/contributor"}
    },
    "top_negative_contributors": {
      "type": "array", "maxItems": 5,
      "items": {"$ref": "#/$defs/contributor"}
    },
    "source_feature_values": {
      "type": "object",
      "additionalProperties": {"type": ["string", "null"]}
    },
    "version_metadata": {"$ref": "#/$defs/versionMetadata"}
  },
  "$defs": {
    "contributor": {
      "type": "object",
      "additionalProperties": false,
      "required": ["feature", "display_name", "value", "contribution", "direction", "rank"],
      "properties": {
        "feature": {"type": "string", "minLength": 1},
        "display_name": {"type": "string", "minLength": 1},
        "value": {"type": ["string", "null"]},
        "contribution": {"type": "number"},
        "direction": {"enum": ["POSITIVE", "NEGATIVE"]},
        "rank": {"type": "integer", "minimum": 1}
      }
    },
    "versionMetadata": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "serving_contract_version", "serving_artifact_version",
        "explanation_version", "explanation_manifest_sha256", "model_id",
        "explanation_method", "contribution_space", "ranking_score_type"
      ],
      "properties": {
        "serving_contract_version": {"const": "1.0"},
        "serving_artifact_version": {"const": "iris_serving_v1"},
        "explanation_version": {"const": "schedule_extension_3m_locked_models_explainability_v1"},
        "explanation_manifest_sha256": {"type": "string", "pattern": "^[A-F0-9]{64}$"},
        "model_id": {"type": "string"},
        "explanation_method": {
          "enum": [
            "CATBOOST_NATIVE_TREESHAP",
            "LOGISTIC_COEFFICIENT_TIMES_TRANSFORMED_VALUE"
          ]
        },
        "contribution_space": {"const": "RAW_MARGIN_LOGIT"},
        "ranking_score_type": {"const": "OPERATIONAL_PROBABILITY"}
      }
    }
  }
}
```

Within each contributor array, `rank` is consecutive from 1 and array order is
ascending rank. Positive and negative ranks are independent. Feature name is the
deterministic tie-break already applied by the explanation layer.

## 4. Endpoint contracts

### `GET /health`

Returns HTTP 200 when the manifest and read-only SQLite artifact load and the
database is queryable:

```json
{
  "status": "ok",
  "serving_artifact_version": "iris_serving_v1",
  "target": "target_effective_schedule_ext_3m",
  "project_month_records": 25189
}
```

Missing or hash-invalid serving data returns HTTP 503.

### `GET /risk/projects?report_month=YYYY-MM`

Query parameters:

- `report_month` is required and must be a real `YYYY-MM` representation.
- `page` defaults to 1 and must be at least 1.
- `page_size` defaults to 25 and must be 1-100.
- `regime` is optional and is `LEGACY` or `MODERN`.
- `min_risk_probability` and `max_risk_probability` are optional inclusive
  bounds in `[0, 1]`; minimum may not exceed maximum.

The response is:

```json
{
  "report_month": "2026-04",
  "filters": {
    "regime": "MODERN",
    "min_risk_probability": null,
    "max_risk_probability": null
  },
  "page": 1,
  "page_size": 25,
  "total": 1625,
  "items": ["RiskRecord v1 objects in ascending risk_rank order"]
}
```

`items` contains full objects conforming to Section 3, not the illustrative
string shown above. No matching month/filter population returns HTTP 404.

### `GET /risk/project/{project_code}?report_month=YYYY-MM`

Returns exactly one Section 3 `RiskRecord` for the literal source
`project_code` and month. There is no normalized, fuzzy, legacy, PMGID, or
June-July crosswalk lookup. Unknown keys return HTTP 404.

### `GET /risk/project/{project_code}/history`

Optional `regime=LEGACY|MODERN` may narrow the exact-code history. Response:

```json
{
  "project_code": "400160",
  "regime_filter": null,
  "count": 5,
  "items": ["chronological RiskRecord v1 objects for exact code 400160 only"]
}
```

Items are ordered by `report_month`. A proposed legacy/new crosswalk counterpart
is never included. Disappearance creates no synthetic history row and is never
interpreted as completion.

### `GET /risk/summary?report_month=YYYY-MM`

Optional parameters are `regime=LEGACY|MODERN` and `top_n=1..50` (default 10).
The response schema is:

```json
{
  "report_month": "2026-04",
  "regime_filter": "MODERN",
  "project_count": 1625,
  "score_distribution": {
    "minimum": 0.0,
    "p25": 0.0,
    "median": 0.0,
    "p75": 0.0,
    "p90": 0.0,
    "p95": 0.0,
    "maximum": 0.0,
    "mean": 0.0
  },
  "top_risk_projects": [
    {
      "project_code": "string",
      "regime": "MODERN",
      "model_id": "logistic_static_only__unweighted",
      "raw_probability": 0.0,
      "risk_probability": 0.0,
      "calibration_active": true,
      "risk_rank": 1,
      "risk_percentile": 1.0,
      "population_size": 1625
    }
  ],
  "regimes": [
    {
      "regime": "MODERN",
      "model_id": "logistic_static_only__unweighted",
      "project_count": 1625,
      "calibration_active": true
    }
  ]
}
```

The numeric zeros above are type placeholders, not actual values. Distribution
quantiles use deterministic linear interpolation at probabilities 0.25, 0.50,
0.75, 0.90, and 0.95 over `risk_probability`. Summary aggregation does not alter
or reinterpret any individual score.

## 5. Errors

- HTTP 404: syntactically valid request with no matching project, history, month,
  or filter population.
- HTTP 422: missing/malformed month, invalid enum, invalid pagination, probability
  outside `[0, 1]`, reversed probability bounds, or invalid `top_n`.
- HTTP 503: serving artifact missing or its recorded database hash fails.

FastAPI error envelopes use `{"detail": ...}`.

## 6. Artifact and execution contract

Build the ignored serving artifact from repository root:

```powershell
D:\AppInstall\python.exe -m src.serving.builder --root .
```

Generated files are:

- `data/serving/iris_risk_serving_v1.sqlite3`: indexed compact records and top
  contributors;
- `data/serving/serving_manifest.json`: source hashes, database hash, locked
  identities, counts, and validation attestations.

The builder reads only `risk_rankings.csv`, `top_contributors.csv`, and
`explainability_manifest.json`. It validates source hashes before copying. It
does not read `local_explanations.csv`; that complete ~1M-row vector remains
offline and authoritative for audit.

Run the API from repository root:

```powershell
D:\AppInstall\python.exe -m uvicorn src.serving.api:app --host 127.0.0.1 --port 8000
```

The service opens a short-lived read-only SQLite connection per operation. It
does not load either the complete explanation vector or the compact contributor
table into memory for each request.

## 7. Consumer invariants

1. Contributions are predictive associations with a fitted raw score, not causal
   explanations, root causes, or recommended interventions.
2. `risk_probability` is the display/ordering probability. Never substitute
   `raw_probability` where `calibration_active` is true.
3. Rank and percentile are relative positions, never probability estimates.
4. Compare ranks only inside their recorded month, regime, and model population.
5. Preserve literal project codes. Never infer continuity across the June-July
   2025 redesign or merge Legacy and Modern identities.
6. Missing source values remain `null`. Do not infer, impute, or relabel them.
7. Absence from a later history month does not imply completion.
8. Do not infer a threshold, alert, causal narrative, or action recommendation
   from this contract.
