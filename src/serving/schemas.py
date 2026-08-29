"""Strict response schemas for the IRIS serving contract."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Contributor(StrictModel):
    feature: str
    display_name: str
    value: str | None
    contribution: float
    direction: Literal["POSITIVE", "NEGATIVE"]
    rank: int = Field(ge=1)


class VersionMetadata(StrictModel):
    serving_contract_version: str
    serving_artifact_version: str
    explanation_version: str
    explanation_manifest_sha256: str
    model_id: str
    explanation_method: Literal[
        "CATBOOST_NATIVE_TREESHAP",
        "LOGISTIC_COEFFICIENT_TIMES_TRANSFORMED_VALUE",
    ]
    contribution_space: Literal["RAW_MARGIN_LOGIT"]
    ranking_score_type: Literal["OPERATIONAL_PROBABILITY"]


class RiskRecord(StrictModel):
    project_code: str
    report_month: str
    project_name: str | None
    agency: str | None
    ministry: str | None
    sector: str | None
    state: str | None
    regime: Literal["LEGACY", "MODERN"]
    target: Literal["target_effective_schedule_ext_3m"]
    model_id: str
    raw_probability: float = Field(ge=0.0, le=1.0)
    risk_probability: float = Field(ge=0.0, le=1.0)
    calibration_active: bool
    risk_percentile: float = Field(gt=0.0, le=1.0)
    risk_rank: int = Field(ge=1)
    population_size: int = Field(ge=1)
    top_positive_contributors: list[Contributor]
    top_negative_contributors: list[Contributor]
    source_feature_values: dict[str, str | None]
    version_metadata: VersionMetadata


class HealthResponse(StrictModel):
    status: Literal["ok"]
    serving_artifact_version: str
    target: Literal["target_effective_schedule_ext_3m"]
    project_month_records: int = Field(ge=0)


class ProjectFilters(StrictModel):
    regime: Literal["LEGACY", "MODERN"] | None
    min_risk_probability: float | None
    max_risk_probability: float | None
    sector: str | None
    agency: str | None
    ministry: str | None
    state: str | None
    search: str | None


class ProjectListResponse(StrictModel):
    report_month: str
    filters: ProjectFilters
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=1)
    items: list[RiskRecord]


class HistoryResponse(StrictModel):
    project_code: str
    regime_filter: Literal["LEGACY", "MODERN"] | None
    count: int = Field(ge=1)
    items: list[RiskRecord]


class ScoreDistribution(StrictModel):
    minimum: float
    p25: float
    median: float
    p75: float
    p90: float
    p95: float
    maximum: float
    mean: float


class TopRiskProject(StrictModel):
    project_code: str
    project_name: str | None
    agency: str | None
    ministry: str | None
    sector: str | None
    state: str | None
    regime: Literal["LEGACY", "MODERN"]
    model_id: str
    raw_probability: float = Field(ge=0.0, le=1.0)
    risk_probability: float = Field(ge=0.0, le=1.0)
    calibration_active: bool
    risk_rank: int = Field(ge=1)
    risk_percentile: float = Field(gt=0.0, le=1.0)
    population_size: int = Field(ge=1)


class RegimeMetadata(StrictModel):
    regime: Literal["LEGACY", "MODERN"]
    model_id: str
    project_count: int = Field(ge=1)
    calibration_active: bool


class SectorSummary(StrictModel):
    sector: str | None
    project_count: int = Field(ge=1)
    mean_risk_probability: float = Field(ge=0.0, le=1.0)
    highest_risk_probability: float = Field(ge=0.0, le=1.0)


class DashboardOptionsResponse(StrictModel):
    report_months: list[str]
    default_report_month: str
    selected_report_month: str
    regimes: list[Literal["LEGACY", "MODERN"]]
    sectors: list[str]
    agencies: list[str]
    ministries: list[str]
    states: list[str]


class SummaryResponse(StrictModel):
    report_month: str
    regime_filter: Literal["LEGACY", "MODERN"] | None
    filters: ProjectFilters
    project_count: int = Field(ge=1)
    score_distribution: ScoreDistribution
    top_risk_projects: list[TopRiskProject]
    regimes: list[RegimeMetadata]
    sector_summary: list[SectorSummary]
