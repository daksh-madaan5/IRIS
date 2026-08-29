import type { HistoryResponse, RiskRecord } from "../types";

export const riskRecord = (overrides: Partial<RiskRecord> = {}): RiskRecord => ({
  project_code: "617936",
  report_month: "2026-04",
  project_name: "National Highway Capacity Expansion",
  agency: "MoRTH",
  ministry: "Ministry of Road Transport & Highways",
  sector: "Roads & Highways",
  state: "Telangana",
  regime: "MODERN",
  target: "target_effective_schedule_ext_3m",
  model_id: "logistic_static_only__unweighted",
  raw_probability: 0.91,
  risk_probability: 0.94,
  calibration_active: true,
  risk_percentile: 1,
  risk_rank: 1,
  population_size: 1625,
  top_positive_contributors: [{
    feature: "months_to_effective_schedule",
    display_name: "Months to effective schedule",
    value: "-18",
    contribution: 1.25,
    direction: "POSITIVE",
    rank: 1,
  }],
  top_negative_contributors: [{
    feature: "sector",
    display_name: "Sector",
    value: "Roads & Highways",
    contribution: -0.31,
    direction: "NEGATIVE",
    rank: 1,
  }],
  source_feature_values: { months_to_effective_schedule: "-18", sector: "Roads & Highways" },
  version_metadata: {
    serving_contract_version: "1.1",
    serving_artifact_version: "iris_serving_v1_1",
    explanation_version: "schedule_extension_3m_locked_models_explainability_v1",
    explanation_manifest_sha256: "A".repeat(64),
    model_id: "logistic_static_only__unweighted",
    explanation_method: "LOGISTIC_COEFFICIENT_TIMES_TRANSFORMED_VALUE",
    contribution_space: "RAW_MARGIN_LOGIT",
    ranking_score_type: "OPERATIONAL_PROBABILITY",
  },
  ...overrides,
});

export const history: HistoryResponse = {
  project_code: "617936",
  regime_filter: null,
  count: 2,
  items: [
    riskRecord({ report_month: "2026-03", risk_probability: 0.72, risk_rank: 8 }),
    riskRecord(),
  ],
};
