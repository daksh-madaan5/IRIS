# IRIS Risk Dashboard Handoff

**Updated:** 2026-08-30  
**Status:** First polished dashboard complete  
**Target:** `target_effective_schedule_ext_3m`

## Delivered product

The dashboard is a desktop-first React/Vite monitoring surface under `dashboard/`.
Its hierarchy is portfolio → ranked risks → exact project explanation → exact-ID
history. The default landing state uses the latest month exposed by
`GET /risk/options` (currently April 2026).

The dashboard includes:

- report-month selection and Legacy/Modern regime indication;
- total population, risk-probability quantiles, and sector summary;
- ranked, paginated projects with exact metadata filters and code/name search;
- risk probability, percentile, rank/population, model, and calibration state;
- positive and negative predictive contributors with source values and signed
  raw-margin/logit contribution magnitudes;
- chronological history from `GET /risk/project/{project_code}/history`;
- loading, empty/no-match, service-unavailable, and invalid-detail states;
- explicit non-causal, no-threshold, no-crosswalk, and no-completion-inference
  interpretation boundaries.

No red/amber/green class or operational alert threshold is implemented.

## Architecture and source of truth

```text
React/Vite dashboard
        |
        | HTTP /api proxy
        v
FastAPI src/serving/api.py
        |
        v
read-only data/serving/iris_risk_serving_v1.sqlite3
```

The frontend never reads canonical CSVs and never calculates a prediction,
calibration transform, contribution, rank, percentile, or project continuity.
Portfolio filtering and summaries are API-owned. React only formats values and
renders the records returned by FastAPI.

Serving contract 1.1 adds `project_name`, `agency`, `ministry`, `sector`, and
`state` as nullable display metadata. The builder copies them from the immutable
ongoing panel by exact `(project_code, report_month)`. Source spelling and nulls
are preserved. `project_name` is explicitly not a model feature. Completed-project
data and analytical June–July crosswalk proposals remain excluded.

Key frontend files:

- `dashboard/src/App.tsx`: data orchestration and application states;
- `dashboard/src/api.ts`: the only HTTP boundary;
- `dashboard/src/components/PortfolioOverview.tsx`: quantiles and sector view;
- `dashboard/src/components/RiskTable.tsx`: authoritative server-ranked table;
- `dashboard/src/components/ProjectDetail.tsx`: metadata, contributors, history;
- `dashboard/src/styles.css`: visual system and responsive layout.

## Setup and run

From the repository root, rebuild the serving artifact after a fresh checkout:

```powershell
D:\AppInstall\python.exe -m src.serving.builder --root .
```

Start FastAPI in one terminal:

```powershell
D:\AppInstall\python.exe -m uvicorn src.serving.api:app --host 127.0.0.1 --port 8000
```

Install and start the dashboard in a second terminal:

```powershell
cd dashboard
npm install
npm run dev
```

Open `http://127.0.0.1:5173/`. Vite proxies `/api` to the local FastAPI service.
For a different API origin, set `VITE_IRIS_API_BASE` before building. A deployed
static frontend still requires an accessible FastAPI deployment; it cannot operate
from the SQLite artifact directly.

## Two-to-three minute demo flow

1. Open the latest month and establish portfolio size, regime, probability spread,
   and sector summary.
2. Use the ranked table to identify rank 1 or filter by an exact source sector,
   agency, ministry, or state.
3. Open a project and show probability, percentile, rank/population, model, and
   calibration state.
4. Compare the strongest positive and negative predictive contributors, including
   their exact at-T feature values.
5. Show the exact-code risk history and call out that no Legacy/Modern identifier
   crosswalk or disappearance-as-completion inference is made.

## Tests and build

Backend/API tests:

```powershell
D:\AppInstall\python.exe -m unittest tests.test_serving_api -v
```

Frontend tests and production build:

```powershell
cd dashboard
npm test
npm run build
```

The frontend suite covers API request ownership, report-month/filter forwarding,
server ranking order, project detail, literal-ID history, null metadata, the
explanation disclaimer, and absence of invented threshold/risk-band language.

Final verification on 2026-08-30:

- full Python regression suite: **215/215 passing**;
- serving/API suite: **13/13 passing**;
- frontend suite: **6/6 passing**;
- TypeScript and Vite production build: **passing**;
- canonical ongoing SHA-256:
  `9512A9881E17DFDED6E182D87A8DFB1C4EDBD36C0D9B8A7DA9FD1ABB7E002FBF`;
- canonical completed SHA-256:
  `89BEA84FD68A22E327090C1E4E4533F5BCD745ADCA61EB4E66172EE9023BB910`;
- serving v1.1 SHA-256:
  `5D4574319F258328FF106C9B51AC4963D8CD6A3464DCE4A5AF4AD6210DEADC42`.

## Frozen boundaries

- Do not recompute or rerank risk content in JavaScript.
- Do not use `raw_probability` instead of `risk_probability` when calibration is
  active.
- Do not compare ranks outside their recorded month/regime/model population.
- Do not normalize, infer, or backfill display metadata.
- Do not connect June 2025 Legacy codes to July 2025 Modern codes.
- Do not infer completion from a missing later observation.
- Do not add LLM narratives, new targets, model training, or operational thresholds
  without a new explicitly scoped phase.
