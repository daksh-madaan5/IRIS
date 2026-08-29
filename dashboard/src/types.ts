export type Regime = "LEGACY" | "MODERN";

export interface Contributor {
  feature: string;
  display_name: string;
  value: string | null;
  contribution: number;
  direction: "POSITIVE" | "NEGATIVE";
  rank: number;
}

export interface RiskRecord {
  project_code: string;
  report_month: string;
  project_name: string | null;
  agency: string | null;
  ministry: string | null;
  sector: string | null;
  state: string | null;
  regime: Regime;
  target: "target_effective_schedule_ext_3m";
  model_id: string;
  raw_probability: number;
  risk_probability: number;
  calibration_active: boolean;
  risk_percentile: number;
  risk_rank: number;
  population_size: number;
  top_positive_contributors: Contributor[];
  top_negative_contributors: Contributor[];
  source_feature_values: Record<string, string | null>;
  version_metadata: {
    serving_contract_version: string;
    serving_artifact_version: string;
    explanation_version: string;
    explanation_manifest_sha256: string;
    model_id: string;
    explanation_method: string;
    contribution_space: "RAW_MARGIN_LOGIT";
    ranking_score_type: "OPERATIONAL_PROBABILITY";
  };
}

export interface DashboardFilters {
  regime: Regime | "";
  sector: string;
  agency: string;
  ministry: string;
  state: string;
  search: string;
}

export interface DashboardOptions {
  report_months: string[];
  default_report_month: string;
  selected_report_month: string;
  regimes: Regime[];
  sectors: string[];
  agencies: string[];
  ministries: string[];
  states: string[];
}

export interface ProjectListResponse {
  report_month: string;
  page: number;
  page_size: number;
  total: number;
  items: RiskRecord[];
}

export interface ScoreDistribution {
  minimum: number;
  p25: number;
  median: number;
  p75: number;
  p90: number;
  p95: number;
  maximum: number;
  mean: number;
}

export interface SectorSummary {
  sector: string | null;
  project_count: number;
  mean_risk_probability: number;
  highest_risk_probability: number;
}

export interface SummaryResponse {
  report_month: string;
  project_count: number;
  score_distribution: ScoreDistribution;
  top_risk_projects: Array<Pick<
    RiskRecord,
    | "project_code"
    | "project_name"
    | "agency"
    | "ministry"
    | "sector"
    | "state"
    | "regime"
    | "model_id"
    | "raw_probability"
    | "risk_probability"
    | "calibration_active"
    | "risk_rank"
    | "risk_percentile"
    | "population_size"
  >>;
  regimes: Array<{
    regime: Regime;
    model_id: string;
    project_count: number;
    calibration_active: boolean;
  }>;
  sector_summary: SectorSummary[];
}

export interface HistoryResponse {
  project_code: string;
  regime_filter: Regime | null;
  count: number;
  items: RiskRecord[];
}

export interface ApiErrorShape {
  detail?: string;
}
