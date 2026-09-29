"""Integration tests for IRIS risk intelligence endpoints."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import Any
import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import settings
from backend.app.main import app
from backend.app.services.risk_service import get_serving_repository, reset_cached_repository
from src.serving.builder import _create_schema
from src.serving.repository import ServingRepository


def _compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _populate_test_serving_db(db_path: Path) -> dict[str, Any]:
    connection = sqlite3.connect(db_path)
    try:
        _create_schema(connection)
        # 1. Insert Features
        features = [
            (1, "ratio_cost_revised_to_orig", "Cost Revision Ratio (Revised / Original)"),
            (2, "physical_progress", "Reported Physical Progress (%)"),
            (3, "months_to_effective_schedule", "Months to effective schedule"),
            (4, "expenditure_to_original_cost_ratio", "Expenditure to original cost ratio"),
        ]
        connection.executemany(
            "INSERT INTO feature_catalog (id, feature, display_name) VALUES (?, ?, ?)",
            features,
        )

        # 2. Insert Risk Records
        records = [
            (
                1, "201234", "2026-04", "Mumbai Metro Line 4", "MMRDA",
                "HOUSING AND URBAN AFFAIRS", "URBAN DEVELOPMENT", "MAHARASHTRA",
                "MODERN", "target_effective_schedule_ext_3m", "logistic_static_only__unweighted",
                0.812, 0.892, 1, 1.0, 1, 2, 1.45,
                "LOGISTIC_COEFFICIENT_TIMES_TRANSFORMED_VALUE", "RAW_MARGIN_LOGIT",
            ),
            (
                2, "201235", "2026-04", "Delhi-Meerut RRTS", "NCRTC",
                "HOUSING AND URBAN AFFAIRS", "RAILWAYS", "DELHI",
                "MODERN", "target_effective_schedule_ext_3m", "logistic_static_only__unweighted",
                0.412, 0.450, 1, 0.5, 2, 2, -0.21,
                "LOGISTIC_COEFFICIENT_TIMES_TRANSFORMED_VALUE", "RAW_MARGIN_LOGIT",
            ),
            (
                3, "201234", "2026-03", "Mumbai Metro Line 4", "MMRDA",
                "HOUSING AND URBAN AFFAIRS", "URBAN DEVELOPMENT", "MAHARASHTRA",
                "MODERN", "target_effective_schedule_ext_3m", "logistic_static_only__unweighted",
                0.780, 0.780, 0, 1.0, 1, 1, 1.25,
                "LOGISTIC_COEFFICIENT_TIMES_TRANSFORMED_VALUE", "RAW_MARGIN_LOGIT",
            ),
            (
                4, "N24001001", "2024-06", "Legacy Highway Expansion", "NHAI",
                "ROAD TRANSPORT AND HIGHWAYS", "ROAD TRANSPORT AND HIGHWAYS", "UTTAR PRADESH",
                "LEGACY", "target_effective_schedule_ext_3m", "catboost_full_v1__unweighted",
                0.650, 0.650, 0, 1.0, 1, 1, 0.85,
                "CATBOOST_NATIVE_TREESHAP", "RAW_MARGIN_LOGIT",
            ),
        ]
        connection.executemany(
            """
            INSERT INTO risk_records (
                id, project_code, report_month, project_name, agency, ministry, sector,
                state, regime, target, model_id, raw_probability, risk_probability,
                calibration_active, risk_percentile, risk_rank, population_size,
                raw_decision_score, explanation_method, contribution_space
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            records,
        )

        # 3. Insert Contributors
        contributors = [
            (1, 1, "1.27", 0.642, "POSITIVE", 1),
            (1, 2, "57.0", -0.318, "NEGATIVE", 1),
            (2, 3, "12.0", 0.210, "POSITIVE", 1),
            (2, 4, "0.85", -0.150, "NEGATIVE", 1),
            (3, 1, "1.20", 0.580, "POSITIVE", 1),
            (4, 1, "1.15", 0.420, "POSITIVE", 1),
        ]
        connection.executemany(
            """
            INSERT INTO contributors (
                risk_record_id, feature_id, value, contribution, direction, rank
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            contributors,
        )
        connection.commit()
    finally:
        connection.close()

    db_hash = _compute_sha256(db_path)
    manifest = {
        "serving_artifact_version": "iris_serving_v1_1",
        "serving_contract_version": "1.1",
        "target": "target_effective_schedule_ext_3m",
        "explanation_version": "schedule_extension_3m_locked_models_explainability_v1",
        "sources": {
            "explainability_manifest": {
                "sha256": "5D4574319F258328FF106C9B51AC4963D8CD6A3464DCE4A5AF4AD6210DEADC42"
            }
        },
        "database": {
            "filename": "iris_risk_serving_v1.sqlite3",
            "sha256": db_hash,
        },
        "record_counts": {
            "project_months": len(records),
        },
    }
    return manifest


@pytest.fixture
def test_serving_repo() -> Generator[ServingRepository, None, None]:
    """Create a temporary test serving repository with manifest and SQLite database."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        db_path = temp_path / "iris_risk_serving_v1.sqlite3"
        manifest_path = temp_path / "serving_manifest.json"

        manifest = _populate_test_serving_db(db_path)
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        reset_cached_repository()
        repo = ServingRepository(temp_path)

        def override_get_serving_repository() -> ServingRepository:
            return repo

        app.dependency_overrides[get_serving_repository] = override_get_serving_repository
        yield repo
        app.dependency_overrides.pop(get_serving_repository, None)
        reset_cached_repository()


def test_risk_options_default(client: TestClient, test_serving_repo: ServingRepository) -> None:
    response = client.get("/api/v1/risk/options")
    assert response.status_code == 200
    data = response.json()
    assert data["report_months"] == ["2024-06", "2026-03", "2026-04"]
    assert data["default_report_month"] == "2026-04"
    assert data["selected_report_month"] == "2026-04"
    assert data["regimes"] == ["MODERN"]
    assert "URBAN DEVELOPMENT" in data["sectors"]
    assert "RAILWAYS" in data["sectors"]
    assert "MMRDA" in data["agencies"]


def test_risk_options_specific_month(client: TestClient, test_serving_repo: ServingRepository) -> None:
    response = client.get("/api/v1/risk/options", params={"report_month": "2024-06"})
    assert response.status_code == 200
    data = response.json()
    assert data["selected_report_month"] == "2024-06"
    assert data["regimes"] == ["LEGACY"]
    assert data["sectors"] == ["ROAD TRANSPORT AND HIGHWAYS"]


def test_risk_options_invalid_month(client: TestClient, test_serving_repo: ServingRepository) -> None:
    res_422 = client.get("/api/v1/risk/options", params={"report_month": "invalid-month"})
    assert res_422.status_code == 422

    res_404 = client.get("/api/v1/risk/options", params={"report_month": "2099-01"})
    assert res_404.status_code == 404


def test_risk_summary_success(client: TestClient, test_serving_repo: ServingRepository) -> None:
    response = client.get("/api/v1/risk/summary", params={"report_month": "2026-04"})
    assert response.status_code == 200
    data = response.json()
    assert data["report_month"] == "2026-04"
    assert data["project_count"] == 2
    assert "score_distribution" in data
    dist = data["score_distribution"]
    assert dist["minimum"] == 0.450
    assert dist["maximum"] == 0.892
    assert len(data["top_risk_projects"]) == 2
    assert data["top_risk_projects"][0]["risk_rank"] == 1
    assert data["top_risk_projects"][0]["project_code"] == "201234"
    assert len(data["sector_summary"]) == 2


def test_risk_summary_filters(client: TestClient, test_serving_repo: ServingRepository) -> None:
    response = client.get(
        "/api/v1/risk/summary",
        params={"report_month": "2026-04", "sector": "URBAN DEVELOPMENT"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["project_count"] == 1
    assert data["top_risk_projects"][0]["project_code"] == "201234"


def test_risk_summary_404_on_no_match(client: TestClient, test_serving_repo: ServingRepository) -> None:
    response = client.get(
        "/api/v1/risk/summary",
        params={"report_month": "2026-04", "sector": "NONEXISTENT"},
    )
    assert response.status_code == 404


def test_risk_projects_listing_and_pagination(client: TestClient, test_serving_repo: ServingRepository) -> None:
    response = client.get(
        "/api/v1/risk/projects",
        params={"report_month": "2026-04", "page": 1, "page_size": 1},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert data["page"] == 1
    assert data["page_size"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["risk_rank"] == 1
    assert data["items"][0]["project_code"] == "201234"
    assert len(data["items"][0]["top_positive_contributors"]) == 1
    assert len(data["items"][0]["top_negative_contributors"]) == 1


def test_risk_projects_search(client: TestClient, test_serving_repo: ServingRepository) -> None:
    response = client.get(
        "/api/v1/risk/projects",
        params={"report_month": "2026-04", "search": "Metro"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["project_name"] == "Mumbai Metro Line 4"


def test_risk_projects_invalid_probability_bounds(client: TestClient, test_serving_repo: ServingRepository) -> None:
    response = client.get(
        "/api/v1/risk/projects",
        params={
            "report_month": "2026-04",
            "min_risk_probability": 0.8,
            "max_risk_probability": 0.2,
        },
    )
    assert response.status_code == 422


def test_risk_project_detail_success(client: TestClient, test_serving_repo: ServingRepository) -> None:
    response = client.get(
        "/api/v1/risk/project/201234",
        params={"report_month": "2026-04"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["project_code"] == "201234"
    assert data["report_month"] == "2026-04"
    assert data["project_name"] == "Mumbai Metro Line 4"
    assert data["raw_probability"] == 0.812
    assert data["risk_probability"] == 0.892
    assert data["calibration_active"] is True
    assert data["risk_rank"] == 1
    assert data["risk_percentile"] == 1.0
    assert len(data["top_positive_contributors"]) == 1
    assert data["top_positive_contributors"][0]["feature"] == "ratio_cost_revised_to_orig"
    assert data["top_positive_contributors"][0]["direction"] == "POSITIVE"
    assert data["version_metadata"]["model_id"] == "logistic_static_only__unweighted"


def test_risk_project_detail_404(client: TestClient, test_serving_repo: ServingRepository) -> None:
    response = client.get(
        "/api/v1/risk/project/NONEXISTENT",
        params={"report_month": "2026-04"},
    )
    assert response.status_code == 404


def test_risk_project_history_success(client: TestClient, test_serving_repo: ServingRepository) -> None:
    response = client.get("/api/v1/risk/project/201234/history")
    assert response.status_code == 200
    data = response.json()
    assert data["project_code"] == "201234"
    assert data["count"] == 2
    assert len(data["items"]) == 2
    assert data["items"][0]["report_month"] == "2026-03"
    assert data["items"][1]["report_month"] == "2026-04"


def test_risk_project_history_404(client: TestClient, test_serving_repo: ServingRepository) -> None:
    response = client.get("/api/v1/risk/project/NONEXISTENT/history")
    assert response.status_code == 404


def test_risk_model_info(client: TestClient, test_serving_repo: ServingRepository) -> None:
    response = client.get("/api/v1/risk/model-info")
    assert response.status_code == 200
    data = response.json()
    assert data["serving_artifact_version"] == "iris_serving_v1_1"
    assert data["target"] == "target_effective_schedule_ext_3m"
    assert data["horizon_months"] == 3
    assert data["status"] == "READY"
    assert len(data["models"]) == 2
    assert data["models"][0]["regime"] == "LEGACY"
    assert data["models"][1]["regime"] == "MODERN"


def test_direct_risk_routes_for_frontend_proxy(client: TestClient, test_serving_repo: ServingRepository) -> None:
    """Verify that /risk routes mounted at root for Vite proxy work identically to /api/v1/risk."""
    res_direct = client.get("/risk/options")
    res_v1 = client.get("/api/v1/risk/options")
    assert res_direct.status_code == 200
    assert res_v1.status_code == 200
    assert res_direct.json() == res_v1.json()


def test_missing_serving_artifact_returns_503(client: TestClient) -> None:
    """Verify that accessing risk endpoints without a valid artifact returns HTTP 503."""
    reset_cached_repository()
    # Point settings to non-existent directory
    original = settings.SERVING_DIR
    settings.SERVING_DIR = "nonexistent/serving/dir"
    try:
        response = client.get("/api/v1/risk/options")
        assert response.status_code == 503
    finally:
        settings.SERVING_DIR = original
        reset_cached_repository()


def test_zero_future_label_exposure(client: TestClient, test_serving_repo: ServingRepository) -> None:
    """Audit all responses to ensure realized target labels and completion evidence are absent."""
    prohibited_substrings = [
        "actual_completion_date",
        "target_effective_schedule_ext_3m_realized",
        "future_label",
        "is_completed",
    ]

    record = client.get("/api/v1/risk/project/201234", params={"report_month": "2026-04"}).json()
    record_str = json.dumps(record)
    for prohibited in prohibited_substrings:
        assert prohibited not in record_str, f"Prohibited label {prohibited} found in response"


def test_optional_report_month_defaults_to_latest_cycle(
    client: TestClient, test_serving_repo: ServingRepository
) -> None:
    """Verify that omitting report_month defaults to the authoritative default cycle instead of failing with 422."""
    # 1. Summary endpoint without report_month
    res_summary = client.get("/api/v1/risk/summary", params={"top_n": 5})
    assert res_summary.status_code == 200
    data_summary = res_summary.json()
    assert data_summary["report_month"] == "2026-04"
    assert len(data_summary["top_risk_projects"]) <= 5

    # Direct mounted route
    res_summary_direct = client.get("/risk/summary", params={"top_n": 5})
    assert res_summary_direct.status_code == 200
    assert res_summary_direct.json()["report_month"] == "2026-04"

    # 2. Projects list endpoint without report_month
    res_projects = client.get("/api/v1/risk/projects", params={"page": 1, "page_size": 2})
    assert res_projects.status_code == 200
    data_projects = res_projects.json()
    assert data_projects["report_month"] == "2026-04"
    assert len(data_projects["items"]) == 2

    # 3. Project detail endpoint without report_month
    res_project = client.get("/api/v1/risk/project/201234")
    assert res_project.status_code == 200
    assert res_project.json()["report_month"] == "2026-04"

