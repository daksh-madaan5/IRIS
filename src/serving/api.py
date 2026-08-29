"""FastAPI application for deterministic IRIS risk-serving records."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import FastAPI, HTTPException, Query

from src.serving.repository import ServingRepository, score_distribution
from src.serving.schemas import (
    DashboardOptionsResponse,
    HealthResponse,
    HistoryResponse,
    ProjectListResponse,
    RiskRecord,
    SummaryResponse,
)


MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
Regime = Literal["LEGACY", "MODERN"]


def _month(value: str) -> str:
    if not MONTH_PATTERN.fullmatch(value):
        raise HTTPException(
            status_code=422, detail="report_month must use a valid YYYY-MM value"
        )
    return value


def create_app(
    root: Path | None = None, artifact_dir: Path | None = None
) -> FastAPI:
    repository_root = (root or Path.cwd()).resolve()
    serving_dir = (artifact_dir or repository_root / "data/serving").resolve()
    repository: ServingRepository | None = None

    def store() -> ServingRepository:
        nonlocal repository
        if repository is None:
            try:
                repository = ServingRepository(serving_dir)
            except (FileNotFoundError, RuntimeError) as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
        return repository

    app = FastAPI(
        title="IRIS deterministic risk service",
        version="1.1.0",
        description=(
            "Read-only access to locked IRIS project-month scores and predictive "
            "contributors. Contributions are predictive, not causal."
        ),
    )

    @app.get("/health", response_model=HealthResponse)
    def health() -> dict[str, Any]:
        return store().health()

    @app.get("/risk/projects", response_model=ProjectListResponse)
    def projects(
        report_month: Annotated[str, Query(description="Evaluation month as YYYY-MM")],
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int, Query(ge=1, le=100)] = 25,
        regime: Regime | None = None,
        min_risk_probability: Annotated[float | None, Query(ge=0.0, le=1.0)] = None,
        max_risk_probability: Annotated[float | None, Query(ge=0.0, le=1.0)] = None,
        sector: str | None = None,
        agency: str | None = None,
        ministry: str | None = None,
        state: str | None = None,
        search: Annotated[str | None, Query(max_length=200)] = None,
    ) -> dict[str, Any]:
        month = _month(report_month)
        if (
            min_risk_probability is not None
            and max_risk_probability is not None
            and min_risk_probability > max_risk_probability
        ):
            raise HTTPException(
                status_code=422,
                detail="min_risk_probability cannot exceed max_risk_probability",
            )
        total, items = store().list_records(
            report_month=month,
            regime=regime,
            min_probability=min_risk_probability,
            max_probability=max_risk_probability,
            sector=sector,
            agency=agency,
            ministry=ministry,
            state=state,
            search=search.strip() if search and search.strip() else None,
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
                "sector": sector,
                "agency": agency,
                "ministry": ministry,
                "state": state,
                "search": search.strip() if search and search.strip() else None,
            },
            "page": page,
            "page_size": page_size,
            "total": total,
            "items": items,
        }

    @app.get("/risk/options", response_model=DashboardOptionsResponse)
    def options(
        report_month: Annotated[
            str | None, Query(description="Optional evaluation month as YYYY-MM")
        ] = None,
    ) -> dict[str, Any]:
        month = _month(report_month) if report_month is not None else None
        try:
            return store().dashboard_options(month)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/risk/project/{project_code}", response_model=RiskRecord)
    def project(
        project_code: str,
        report_month: Annotated[str, Query(description="Evaluation month as YYYY-MM")],
    ) -> dict[str, Any]:
        record = store().get_record(project_code, _month(report_month))
        if record is None:
            raise HTTPException(status_code=404, detail="Project-month risk record not found")
        return record

    @app.get("/risk/project/{project_code}/history", response_model=HistoryResponse)
    def history(project_code: str, regime: Regime | None = None) -> dict[str, Any]:
        records = store().history(project_code, regime)
        if not records:
            raise HTTPException(status_code=404, detail="Project risk history not found")
        return {
            "project_code": project_code,
            "regime_filter": regime,
            "count": len(records),
            "items": records,
        }

    @app.get("/risk/summary", response_model=SummaryResponse)
    def summary(
        report_month: Annotated[str, Query(description="Evaluation month as YYYY-MM")],
        regime: Regime | None = None,
        top_n: Annotated[int, Query(ge=1, le=50)] = 10,
        sector: str | None = None,
        agency: str | None = None,
        ministry: str | None = None,
        state: str | None = None,
        search: Annotated[str | None, Query(max_length=200)] = None,
    ) -> dict[str, Any]:
        month = _month(report_month)
        normalized_search = search.strip() if search and search.strip() else None
        rows = store().month_scores(
            month,
            regime,
            sector=sector,
            agency=agency,
            ministry=ministry,
            state=state,
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
                "sector": sector,
                "agency": agency,
                "ministry": ministry,
                "state": state,
                "search": normalized_search,
            },
            "project_count": len(rows),
            "score_distribution": score_distribution(
                [float(row["risk_probability"]) for row in rows]
            ),
            "top_risk_projects": top,
            "regimes": [regimes[key] for key in sorted(regimes)],
            "sector_summary": store().sector_summary(rows),
        }

    return app


app = create_app()
