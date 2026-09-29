"""Risk intelligence and model-serving endpoints."""

from __future__ import annotations

import re
from typing import Annotated, Any, Literal
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.services.risk_service import get_serving_repository
from src.serving.repository import ServingRepository, score_distribution
from src.serving.schemas import (
    DashboardOptionsResponse,
    HistoryResponse,
    ModelInfoResponse,
    ModelRegistryEntry,
    ModelRegistryListResponse,
    ProjectListResponse,
    RiskRecord,
    SummaryResponse,
    TargetRegistryEntry,
    TargetRegistryListResponse,
)

router = APIRouter()

MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
Regime = Literal["LEGACY", "MODERN"]


def _validate_month(value: str) -> str:
    cleaned = value.strip()
    if not MONTH_PATTERN.fullmatch(cleaned):
        raise HTTPException(
            status_code=422, detail="report_month must use a valid YYYY-MM value"
        )
    return cleaned


def _validate_project_code(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise HTTPException(
            status_code=422, detail="project_code cannot be empty or whitespace"
        )
    return cleaned


def _normalize_filter(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


@router.get(
    "/options",
    response_model=DashboardOptionsResponse,
    summary="Get Risk Dashboard Options",
    description="Retrieve available evaluation report months, default active month, available regimes, and distinct non-null metadata filter values.",
)
def get_risk_options(
    report_month: Annotated[
        str | None, Query(description="Optional evaluation month as YYYY-MM")
    ] = None,
    repo: ServingRepository = Depends(get_serving_repository),
) -> dict[str, Any]:
    month = _validate_month(report_month) if report_month is not None else None
    try:
        return repo.dashboard_options(month)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/summary",
    response_model=SummaryResponse,
    summary="Get Portfolio Risk Summary",
    description="Retrieve portfolio-level score distributions, quantiles, regime metadata, sector risk summaries, and top-N ranked projects.",
)
def get_risk_summary(
    report_month: Annotated[
        str | None, Query(description="Evaluation month as YYYY-MM")
    ] = None,
    regime: Regime | None = None,
    top_n: Annotated[int, Query(ge=1, le=50, description="Number of top risk projects to include")] = 10,
    sector: str | None = None,
    agency: str | None = None,
    ministry: str | None = None,
    state: str | None = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    repo: ServingRepository = Depends(get_serving_repository),
) -> dict[str, Any]:
    if report_month is not None:
        month = _validate_month(report_month)
    else:
        month = repo.dashboard_options()["default_report_month"]
    normalized_search = search.strip() if search and search.strip() else None
    norm_sector = _normalize_filter(sector)
    norm_agency = _normalize_filter(agency)
    norm_ministry = _normalize_filter(ministry)
    norm_state = _normalize_filter(state)
    rows = repo.month_scores(
        month,
        regime,
        sector=norm_sector,
        agency=norm_agency,
        ministry=norm_ministry,
        state=norm_state,
        search=normalized_search,
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Risk summary population not found")

    regimes: dict[str, dict[str, Any]] = {}
    for row in rows:
        item = regimes.setdefault(
            row["regime"],
            {
                "regime": row["regime"],
                "model_id": row["model_id"],
                "project_count": 0,
                "calibration_active": False,
            },
        )
        item["project_count"] += 1
        item["calibration_active"] = item["calibration_active"] or bool(
            row["calibration_active"]
        )

    top = [
        {
            "project_code": row["project_code"],
            "project_name": row["project_name"],
            "agency": row["agency"],
            "ministry": row["ministry"],
            "sector": row["sector"],
            "state": row["state"],
            "regime": row["regime"],
            "model_id": row["model_id"],
            "raw_probability": float(row["raw_probability"]),
            "risk_probability": float(row["risk_probability"]),
            "calibration_active": bool(row["calibration_active"]),
            "risk_rank": int(row["risk_rank"]),
            "risk_percentile": float(row["risk_percentile"]),
            "population_size": int(row["population_size"]),
        }
        for row in rows[:top_n]
    ]

    return {
        "report_month": month,
        "regime_filter": regime,
        "filters": {
            "regime": regime,
            "min_risk_probability": None,
            "max_risk_probability": None,
            "sector": norm_sector,
            "agency": norm_agency,
            "ministry": norm_ministry,
            "state": norm_state,
            "search": normalized_search,
        },
        "project_count": len(rows),
        "score_distribution": score_distribution(
            [float(row["risk_probability"]) for row in rows]
        ),
        "top_risk_projects": top,
        "regimes": [regimes[key] for key in sorted(regimes)],
        "sector_summary": repo.sector_summary(rows),
    }


@router.get(
    "/projects",
    response_model=ProjectListResponse,
    summary="List Ranked Risk Projects",
    description="Retrieve paginated list of evaluated projects strictly ordered by risk rank, including calibrated probabilities and signed feature contributors.",
)
def list_risk_projects(
    report_month: Annotated[
        str | None, Query(description="Evaluation month as YYYY-MM")
    ] = None,
    page: Annotated[int, Query(ge=1, description="Page number (1-indexed)")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page (max 100)")] = 25,
    regime: Regime | None = None,
    min_risk_probability: Annotated[float | None, Query(ge=0.0, le=1.0, description="Minimum risk probability")] = None,
    max_risk_probability: Annotated[float | None, Query(ge=0.0, le=1.0, description="Maximum risk probability")] = None,
    sector: str | None = None,
    agency: str | None = None,
    ministry: str | None = None,
    state: str | None = None,
    search: Annotated[str | None, Query(max_length=200, description="Substring search on project code or name")] = None,
    repo: ServingRepository = Depends(get_serving_repository),
) -> dict[str, Any]:
    if report_month is not None:
        month = _validate_month(report_month)
    else:
        month = repo.dashboard_options()["default_report_month"]
    if (
        min_risk_probability is not None
        and max_risk_probability is not None
        and min_risk_probability > max_risk_probability
    ):
        raise HTTPException(
            status_code=422,
            detail="min_risk_probability cannot exceed max_risk_probability",
        )

    normalized_search = search.strip() if search and search.strip() else None
    norm_sector = _normalize_filter(sector)
    norm_agency = _normalize_filter(agency)
    norm_ministry = _normalize_filter(ministry)
    norm_state = _normalize_filter(state)
    total, items = repo.list_records(
        report_month=month,
        regime=regime,
        min_probability=min_risk_probability,
        max_probability=max_risk_probability,
        sector=norm_sector,
        agency=norm_agency,
        ministry=norm_ministry,
        state=norm_state,
        search=normalized_search,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    if total == 0:
        raise HTTPException(status_code=404, detail="No risk records match the query")

    return {
        "report_month": month,
        "filters": {
            "regime": regime,
            "min_risk_probability": min_risk_probability,
            "max_risk_probability": max_risk_probability,
            "sector": norm_sector,
            "agency": norm_agency,
            "ministry": norm_ministry,
            "state": norm_state,
            "search": normalized_search,
        },
        "page": page,
        "page_size": page_size,
        "total": total,
        "items": items,
    }


@router.get(
    "/model-info",
    response_model=ModelInfoResponse,
    summary="Get Model Governance and Architecture Info",
    description="Retrieve model families, features, explainability methods, calibration policies, and target specifications.",
)
def get_model_info(
    repo: ServingRepository = Depends(get_serving_repository),
) -> dict[str, Any]:
    return repo.model_info()


@router.get(
    "/models",
    response_model=ModelRegistryListResponse,
    summary="List Production Models",
    description="Retrieve the complete authoritative model registry including active and historical models, coverage periods, calibration metadata, and metrics.",
)
def get_risk_models(
    repo: ServingRepository = Depends(get_serving_repository),
) -> dict[str, Any]:
    models = repo.models()
    active = repo.active_model()
    return {
        "total": len(models),
        "active_model_id": active["model_id"],
        "models": models,
    }


@router.get(
    "/models/active",
    response_model=ModelRegistryEntry,
    summary="Get Active Production Model",
    description="Retrieve the currently active production model for the schedule-risk target.",
)
def get_active_risk_model(
    repo: ServingRepository = Depends(get_serving_repository),
) -> dict[str, Any]:
    return repo.active_model()


@router.get(
    "/models/{model_id}",
    response_model=ModelRegistryEntry,
    summary="Get Model By ID",
    description="Retrieve an exact model registry entry by model ID.",
)
def get_risk_model_by_id(
    model_id: str,
    repo: ServingRepository = Depends(get_serving_repository),
) -> dict[str, Any]:
    cleaned = model_id.strip()
    if not cleaned:
        raise HTTPException(
            status_code=422, detail="model_id cannot be empty or whitespace"
        )
    model = repo.get_model(cleaned)
    if model is None:
        raise HTTPException(
            status_code=404, detail=f"Model '{cleaned}' not found in registry"
        )
    return model


@router.get(
    "/targets",
    response_model=TargetRegistryListResponse,
    summary="List ML Target Domains",
    description="Retrieve all registered ML target domains, distinguishing served production targets from unserved specifications.",
)
def get_risk_targets(
    repo: ServingRepository = Depends(get_serving_repository),
) -> dict[str, Any]:
    targets = repo.targets()
    return {
        "total": len(targets),
        "implemented_count": sum(1 for t in targets if t["is_served"]),
        "targets": targets,
    }



@router.get(
    "/project/{project_code}",
    response_model=RiskRecord,
    summary="Get Exact Project Risk Record",
    description="Retrieve the complete RiskRecord for a single project code in a specific report month, including signed TreeSHAP/logistic contributors.",
)
def get_project_risk_record(
    project_code: str,
    report_month: Annotated[
        str | None, Query(description="Evaluation month as YYYY-MM")
    ] = None,
    repo: ServingRepository = Depends(get_serving_repository),
) -> dict[str, Any]:
    valid_code = _validate_project_code(project_code)
    if report_month is not None:
        target_month = _validate_month(report_month)
    else:
        target_month = repo.dashboard_options()["default_report_month"]
    record = repo.get_record(valid_code, target_month)
    if record is None:
        raise HTTPException(status_code=404, detail="Project-month risk record not found")
    return record


@router.get(
    "/project/{project_code}/history",
    response_model=HistoryResponse,
    summary="Get Exact Project Risk History",
    description="Retrieve chronological risk history for an exact project code across all evaluated months. No crosswalk lookups or completion inferences.",
)
def get_project_risk_history(
    project_code: str,
    regime: Regime | None = None,
    repo: ServingRepository = Depends(get_serving_repository),
) -> dict[str, Any]:
    valid_code = _validate_project_code(project_code)
    records = repo.history(valid_code, regime)
    if not records:
        raise HTTPException(status_code=404, detail="Project risk history not found")
    return {
        "project_code": valid_code,
        "regime_filter": regime,
        "count": len(records),
        "items": records,
    }
