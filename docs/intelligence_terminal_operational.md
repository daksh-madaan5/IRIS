# Intelligence Terminal Operational Investigation Reference (PR-16)

## 1. Executive Summary & Purpose

PR-16 establishes the **Operational Investigation Terminal** at `/intelligence` and `/intelligence?project={projectCode}` as an institutional-grade workstation for infrastructure monitoring specialists, risk analysts, and oversight officers evaluating public-sector infrastructure projects in the PAIMANA system.

Prior implementations focused on high-level visual charts and summaries. PR-16 upgrades this interface into a disciplined operational investigative tool centered around authentic machine-learning model outputs, deterministic factual tracking, and strict governance boundaries.

### Core Non-Negotiables & Invariants
1. **Frontend-Only Scope**: The implementation introduces zero modifications to backend routes, database schemas, canonical datasets, or machine-learning artifacts.
2. **Single Analytical Request**: An investigation of any given project issues exactly one API call (`GET /api/v1/projects/{projectCode}/risk-intelligence`), completely eliminating N+1 request loops.
3. **No Artificial Risk Classifications**: The system strictly prohibits manufactured categories (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`), derived percentage bands (`TOP 5%`, `TOP 10%`, `TOP 20%`), synthetic trend scores, momentum metrics, or fabricated health scores.
4. **Calibrated Probability vs Raw Model Score**: Operational probabilities are Platt-calibrated probabilities on the served model architecture; pre-calibration logit scores are preserved and displayed distinctly as raw model probabilities.
5. **Strict Semantic Comparability**:
   - `calibration_active === true` alone does **not** establish that two evaluations are directly comparable.
   - Two evaluations are comparable only when they share identical `model_id`, identical `regime`, and compatible calibration state.
6. **Adjacent-Only Movement Calculation**: Probability, rank, and percentile movement is computed only between immediately consecutive, semantically comparable historical observations. Non-adjacent observations (e.g., historical point vs current assessment separated by unobserved months) receive no automatic delta and are displayed separately with `COMPARISON NOT ESTABLISHED (NON-ADJACENT OBSERVATIONS)`.
7. **Strictly Observed Historical Trajectory**: Gaps between reporting months are preserved truthfully. No synthetic months, linear interpolation, smoothing algorithms, or zero-filling are permitted.
8. **Explicit Explainability Governance**: Signed feature contributions reflect model logit margin shifts, not real-world causal mechanisms. The disclaimer *"Signed contributions are model evidence, not causal effects"* is mandatory.
9. **Unserved Specifications Disclosure**: Target specifications for unserved domains (`cost_overrun`, `progress_stagnation`) are explicitly disclosed as `DATA PENDING`.
10. **Canonical Navigation Graph**: Only canonical application routes are linked (`/projects`, `/projects/:projectCode`, `/analytics`). The route `/intelligence/projects` is strictly forbidden.

---

## 2. Canonical Information Architecture (8-Level Hierarchy)

The terminal workspace is structured according to a strict eight-level investigative hierarchy:

```
┌────────────────────────────────────────────────────────────────────────┐
│ LEVEL 1: PROJECT CONTEXT & CANONICAL IDENTITY                          │
│ Project Code | Name | Ministry | Agency | Sector | State | OCMS | PMGID│
│ Snapshot Month (2026-07) vs Assessment Month (2026-04) Boundary        │
├────────────────────────────────────────────────────────────────────────┤
│ LEVEL 2: CURRENT OPERATIONAL RISK ASSESSMENT                           │
│ Platt-Calibrated Risk Probability (%) | Raw Model Probability (%)     │
│ Active Target: target_effective_schedule_ext_3m                        │
├────────────────────────────────────────────────────────────────────────┤
│ LEVEL 3: CROSS-SECTIONAL PORTFOLIO POSITION                            │
│ Authoritative Rank (#42) | Monitored Population (1,625) | Percentile P82.5 │
├────────────────────────────────────────────────────────────────────────┤
│ LEVEL 4: DRIVER EVIDENCE & MODEL DECOMPOSITION                         │
│ Signed Margin Logit Contributions | TreeSHAP / Logistic Coefficients   │
│ Mandatory Causal Disclaimer                                            │
├────────────────────────────────────────────────────────────────────────┤
│ LEVEL 5: HISTORICAL TRAJECTORY & OBSERVATION INSPECTION                │
│ Real Served Months | Transition Boundaries | Adjacent Movement deltas │
│ Inspection Drawer: Isolated Observation Record & Non-Adjacent Separation│
├────────────────────────────────────────────────────────────────────────┤
│ LEVEL 6: MODEL GOVERNANCE & PIPELINE PROVENANCE                        │
│ Dynamic Model ID | Algorithm Family | Coverage Period | Platt Policy    │
├────────────────────────────────────────────────────────────────────────┤
│ LEVEL 7: DATA AVAILABILITY & UNSERVED SPECIFICATIONS                   │
│ Served: Schedule Extension Risk | Pending: Cost Overrun & Stagnation   │
├────────────────────────────────────────────────────────────────────────┤
│ LEVEL 8: CANONICAL NAVIGATION & RETURN ACTIONS                         │
│ View Project Detail | Project Portfolio | Back to Analytics (PR-15 Context)│
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Authoritative Contract Specification

The workstation operates against the `ProjectRiskIntelligenceResponse` contract:

```typescript
export interface ProjectRiskIntelligenceResponse {
  project: ProjectIntelligenceIdentity;
  snapshot: ProjectIntelligenceSnapshot | null;
  risk: ProjectIntelligenceRisk | null;
  model: ProjectIntelligenceModelGovernance | null;
  history: ProjectRiskHistoryPoint[];
  drivers: ProjectRiskDrivers;
  signals: ProjectSignals;
  recent_changes: ProjectRecentChanges;
  data_availability: ProjectDataAvailability;
}
```

### Component Roles & Invariants
- **`project`**: Authoritative identifiers (`project_code`, `project_name`, `agency`, `ministry`, `sector`, `state`, `legacy_ocms_code`, `pmgid`).
- **`snapshot`**: Deterministic monthly operational figures from PAIMANA infrastructure monitoring records (`report_month`, `physical_progress`, `cumulative_expenditure`, `original_cost`, `revised_cost`, completion dates).
- **`risk`**: Production risk evaluation (`risk_probability`, `raw_probability`, `risk_rank`, `population_size`, `risk_percentile`, `regime`, `model_id`, `target`, `calibration_active`).
- **`model`**: Dynamic model metadata (`model_id`, `model_family`, `status`, `coverage_period`, `calibration_policy`, `explanation_method`).
- **`history`**: Chronological sequence of prior risk assessments across served months.
- **`drivers`**: Signed feature contributions decomposed into `top_positive` and `top_negative` vectors.
- **`signals`**: Deterministic observation deltas (`cost_revised`, `schedule_revised`, `cost_revision_ratio`, `reporting_months_count`).
- **`recent_changes`**: Month-over-month differentials relative to the immediately preceding monitoring month.
- **`data_availability`**: Explicit flags indicating serving coverage and pending specifications.

---

## 4. Probability & Calibration Semantics

The terminal enforces clear separation between calibrated probability and raw model decision output:

### Platt Scaling Calibration
- When `calibration_active === true`, the primary risk probability (`risk_probability`) is presented under the label `CALIBRATED PROBABILITY`.
- The raw pre-calibration probability is displayed beneath it as `RAW: {val}%`.
- When `calibration_active === false`, the value is labeled `RAW MODEL PROBABILITY`, and an explicit note informs the analyst: *"Evaluation origin was served uncalibrated"*.

### Dynamic Architecture Adaptation
- The interface does not hardcode model names or regimes.
- If the served model is `logistic_static_only__unweighted`, the explanation method is displayed as `"Logistic coefficient times transformed value"`.
- If the served model is `catboost_full_v1__unweighted`, the method is displayed as `"CatBoost-native TreeSHAP"`.
- The regime is displayed dynamically (`MODERN` vs `LEGACY`) as provided in the serving payload.

---

## 5. Cross-Sectional Portfolio Position

Risk position is communicated strictly through authentic cross-sectional distribution metrics:
- **Authoritative Rank**: Displayed as `#42 OF 1,625 MONITORED`.
- **Authoritative Percentile**: Displayed as `P82.5`, indicating that the project's risk probability equals or exceeds 82.5% of evaluated projects in the corresponding portfolio month.
- **Visual Analytical Position**: Rendered on a continuous percentile track with markings at P0.0, P50.0 (Median), and P100.0.
- **Prohibited Derivations**: The terminal never groups projects into artificial tiers such as "Top 5%", "Top 10%", or "Critical Risk".

---

## 6. Model Explainability & Driver Governance

Driver evidence decomposition operates under strict mathematical and governance guidelines:

### Margin Logit Space
- Contributions are reported in model logit margin space (e.g. `+0.412 logit`, `-0.285 logit`).
- They are grouped by directional impact:
  - **Risk-Increasing Contributors**: Positive margin additions that increase predicted delay likelihood.
  - **Risk-Reducing Contributors**: Negative margin offsets that decrease predicted delay likelihood.

### Mandatory Causal Disclaimer
All explainability surfaces include the explicit institutional disclaimer:
> *"Signed contributions describe model decision shifts, not causal real-world mechanisms. They indicate statistical association with the prediction, not real-world causality or intervention advice."*

### Truthful Missing Fallback
When a project has zero served drivers or the feature vector is unavailable:
- The UI renders `NO MODEL DRIVER EVIDENCE AVAILABLE`.
- No synthetic or inferred features are ever fabricated.

---

## 7. Historical Comparability & Movement Governance

PR-16 implements two crucial semantic corrections governing longitudinal analysis:

### Semantic Correction 1: Calibration Comparability Boundary
```typescript
export function areObservationsSemanticallyComparable(
  a: RiskObservationLike | null | undefined,
  b: RiskObservationLike | null | undefined
): boolean {
  if (!a || !b) return false;
  if (a.model_id !== b.model_id) return false;
  if (a.regime !== b.regime) return false;
  if (a.calibration_active !== b.calibration_active) return false;
  return true;
}
```
`calibration_active === true` alone does not imply comparability across different model architectures or regimes. If two evaluations differ in `model_id`, `regime`, or calibration state, direct comparability is suppressed and marked as `COMPARABILITY LIMITED`.

### Semantic Correction 2: Adjacency Requirement for Movement Calculation
Movement deltas are calculated **only** between immediately consecutive observations:
- **Adjacent Historical Observations**: If observation $T_i$ and preceding observation $T_{i-1}$ share identical model, regime, and calibration states, the signed probability delta (in percentage points `pp`), raw probability delta, rank delta, and percentile delta are rendered.
- **Transition Points**: If $T_i$ and $T_{i-1}$ cross a boundary, the table and inspection drawer show `LIMITED (REGIME / MODEL / CALIBRATION)`.
- **Non-Adjacent Observations**: If an analyst inspects an older historical observation (e.g., `2024-06`) against the current assessment (`2026-04`), the system suppresses an automated delta and displays:
  ```
  COMPARISON NOT ESTABLISHED (NON-ADJACENT OBSERVATIONS)
  ```
  Both observations are shown side-by-side with their original values, regime, and model architecture, preventing the illusion of a continuous trajectory across unobserved or non-consecutive intervals.

### Trajectory Charting Invariants
- Only verified, observed evaluation months are plotted on the longitudinal chart.
- Gaps between observation periods are rendered linearly without synthetic points.
- If a project possesses only a single historical observation, the system displays a discrete evaluation card rather than a misleading horizontal trend line.

---

## 8. Factual Observational Signals & Recent Changes

Alongside predictive risk evaluations, the terminal presents factual monitoring deltas:
- **Cost Revision Ratio**: Exact multiplier (e.g. `1.84x`) and revision event count.
- **Schedule Extensions**: Exact cumulative extension count.
- **Reporting Span**: Chronological monitoring span (e.g. `2024-06 → 2026-07`, `24 MONTHS`).
- **Recent Month-over-Month Deltas**: Progress delta (`+0.8 pp`), expenditure delta (`+₹350 CR`), and cost delta compared strictly with the immediately preceding observation month.

---

## 9. Unserved Specification Disclosures

In accordance with IRIS system transparency rules, domains lacking deployed models are surfaced with truthful status badges:
- **Schedule Extension Risk**: `SERVED` (operational Platt-calibrated model active).
- **Cost Overrun Risk**: `DATA PENDING` (target specification exists in governance; model unserved).
- **Progress Stagnation Risk**: `DATA PENDING` (target specification exists in governance; model unserved).

---

## 10. Workspace Navigation & Cross-Workspace Context

Navigation maintains strict canonical routing boundaries:

### Canonical Routes
- `/projects`: Project portfolio directory.
- `/projects/:projectCode`: Institutional project detail dossier.
- `/analytics`: Cross-project risk analytics and distribution workspace.
- `/intelligence?project={projectCode}`: Operational investigation workstation.

### Prohibited Route
- `/intelligence/projects` is strictly forbidden and never generated by any link, redirect, or action.

### PR-15 Return Context Preservation
When an investigator navigates from Analytics to Intelligence, Analytics encodes its current filter state into `location.state.analyticsUrl` (e.g. `/analytics?sector=RAILWAYS&state=MAHARASHTRA`).
- If this context exists, `BACK TO ANALYTICS` returns to that exact filtered URL.
- If no Analytics context exists, `BACK TO ANALYTICS` routes cleanly to `/analytics`.

---

## 11. Verification & Test Suite Structure

The PR-16 test suite (`src/test/components/intelligence/IntelligenceTerminalOperational.test.tsx`) validates all 50 operational semantics:

| Group | Test Range | Scope |
|---|---|---|
| Group 1 | Tests 1–5 | Authoritative Identity, Temporal Month Separation, Target Discipline, Single-Request (No N+1) |
| Group 2 | Tests 6–11 | Calibrated vs Raw Probability, Dynamic Model/Regime, Prohibition of Risk Tiers |
| Group 3 | Tests 12–17 | Authoritative Rank, Population Size, Percentile, No Top-X%, No Synthetic Scores |
| Group 4 | Tests 18–23 | Signed Logit Contributions, Causal Disclaimer, Architecture Explanation, Missing Driver Fallback |
| Group 5 | Tests 24–28 | Factual Signals, Recent Changes, Unserved ML Disclosures (DATA PENDING), Provenance |
| Group 6 | Tests 29–35 | Longitudinal History, Regime/Model/Calibration Transitions, Single Observation, Inspection Drawer |
| Group 7 | Tests 36–41 | URL Param Synchronization, Canonical Links (`/projects`, `/projects/:code`, `/analytics`), No Forbidden Routes |
| Group 8 | Tests 42–48 | Empty State, Search Autocomplete, Loading State, Error Handling, Keyboard & Focus Accessibility |
| Group 9 | Tests 49–50 | Semantic Correction 1 (Calibration Comparability) & Correction 2 (Non-Adjacent Separation) |
