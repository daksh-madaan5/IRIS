from __future__ import annotations

import csv
import json
import tempfile
import unittest
import warnings
from pathlib import Path

from fastapi.testclient import TestClient

from src.ml.dataset_builder import COMPLETED_SHA256, ONGOING_SHA256, sha256
from src.serving.api import create_app
from src.serving.builder import build


ROOT = Path(__file__).resolve().parents[1]
EXPLANATION_DIR = (
    ROOT / "data/ml/schedule_extension_3m/evaluation/explainability"
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


class ServingApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.artifact_dir = Path(cls.temporary.name) / "serving"
        cls.manifest = build(ROOT, cls.artifact_dir)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            cls.client = TestClient(create_app(ROOT, cls.artifact_dir))
        cls.rankings = read_csv(EXPLANATION_DIR / "risk_rankings.csv")
        cls.ranking_index = {
            (row["project_code"], row["report_month"]): row for row in cls.rankings
        }
        cls.top_rows = read_csv(EXPLANATION_DIR / "top_contributors.csv")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        cls.temporary.cleanup()

    def test_health_endpoint_and_deterministic_builder(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(response.json()["project_month_records"], 25_189)
        first_hash = self.manifest["database"]["sha256"]
        rebuilt = build(ROOT, self.artifact_dir)
        self.assertEqual(rebuilt["database"]["sha256"], first_hash)
        self.assertFalse(rebuilt["validation"]["complete_local_explanations_read"])
        self.assertFalse(rebuilt["validation"]["risk_recomputed"])

    def test_api_probabilities_ranks_and_percentiles_match_locked_artifacts(self) -> None:
        # Modern 2026-04 is the single active temporal-Platt fold.
        source = next(
            row
            for row in self.rankings
            if row["report_month"] == "2026-04"
            and row["risk_rank_within_month"] == "1"
        )
        response = self.client.get(
            f"/risk/project/{source['project_code']}",
            params={"report_month": source["report_month"]},
        )
        self.assertEqual(response.status_code, 200)
        record = response.json()
        self.assertEqual(record["raw_probability"], float(source["raw_predicted_probability"]))
        self.assertEqual(record["risk_probability"], float(source["ranking_probability"]))
        self.assertTrue(record["calibration_active"])
        self.assertEqual(record["risk_rank"], int(source["risk_rank_within_month"]))
        self.assertEqual(
            record["risk_percentile"], float(source["risk_percentile_within_month"])
        )
        self.assertEqual(record["population_size"], int(source["month_population"]))

    def test_contributor_order_values_and_schema_are_deterministic(self) -> None:
        project_code = "020100044"
        month = "2023-07"
        record = self.client.get(
            f"/risk/project/{project_code}", params={"report_month": month}
        ).json()
        expected = [
            row
            for row in self.top_rows
            if row["project_code"] == project_code and row["report_month"] == month
        ]
        for direction, field in (
            ("POSITIVE", "top_positive_contributors"),
            ("NEGATIVE", "top_negative_contributors"),
        ):
            expected_direction = sorted(
                [row for row in expected if row["contribution_direction"] == direction],
                key=lambda row: (int(row["direction_rank"]), row["source_feature_name"]),
            )
            actual = record[field]
            self.assertEqual([item["rank"] for item in actual], list(range(1, len(actual) + 1)))
            self.assertEqual(
                [item["feature"] for item in actual],
                [row["source_feature_name"] for row in expected_direction],
            )
            self.assertEqual(
                [item["contribution"] for item in actual],
                [float(row["feature_contribution"]) for row in expected_direction],
            )
            self.assertTrue(all(item["direction"] == direction for item in actual))
            self.assertTrue(all(set(item) == {
                "feature", "display_name", "value", "contribution", "direction", "rank"
            } for item in actual))

    def test_no_future_or_completed_metadata_leaks_into_responses(self) -> None:
        response = self.client.get(
            "/risk/projects", params={"report_month": "2026-04", "page_size": 5}
        )
        self.assertEqual(response.status_code, 200)
        serialized = json.dumps(response.json())
        for prohibited in (
            "eventually_completed",
            "completion_report_month",
            "target_event_month",
            "target_event_revised_completion_date",
            "target_window_end_month",
            "extension_type",
            "project_name",
            "source_file",
            "source_page",
        ):
            self.assertNotIn(f'"{prohibited}"', serialized)

    def test_history_uses_exact_source_code_and_never_crosswalks_regimes(self) -> None:
        # This pair is an analytical June-July proposal. Each endpoint must stay
        # on its literal source code and must not return the other code's rows.
        legacy_code = "N06000087"
        modern_code = "400160"
        legacy = self.client.get(f"/risk/project/{legacy_code}/history")
        modern = self.client.get(f"/risk/project/{modern_code}/history")
        self.assertEqual(legacy.status_code, 200)
        self.assertEqual(modern.status_code, 200)
        self.assertTrue(all(row["project_code"] == legacy_code for row in legacy.json()["items"]))
        self.assertTrue(all(row["regime"] == "LEGACY" for row in legacy.json()["items"]))
        self.assertNotIn(modern_code, json.dumps(legacy.json()))
        self.assertTrue(all(row["project_code"] == modern_code for row in modern.json()["items"]))
        self.assertTrue(all(row["regime"] == "MODERN" for row in modern.json()["items"]))
        months = [row["report_month"] for row in modern.json()["items"]]
        self.assertEqual(months, sorted(months))

    def test_missing_source_values_serialize_as_json_null(self) -> None:
        response = self.client.get(
            "/risk/project/060100093", params={"report_month": "2023-07"}
        )
        self.assertEqual(response.status_code, 200)
        record = response.json()
        self.assertIsNone(record["source_feature_values"]["schedule_revision_lag_months"])
        contributor = next(
            item
            for side in ("top_positive_contributors", "top_negative_contributors")
            for item in record[side]
            if item["feature"] == "schedule_revision_lag_months"
        )
        self.assertIsNone(contributor["value"])

    def test_ranked_list_pagination_filters_and_summary(self) -> None:
        first = self.client.get(
            "/risk/projects",
            params={"report_month": "2026-04", "regime": "MODERN", "page_size": 2},
        )
        second = self.client.get(
            "/risk/projects",
            params={
                "report_month": "2026-04",
                "regime": "MODERN",
                "page": 2,
                "page_size": 2,
            },
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual([item["risk_rank"] for item in first.json()["items"]], [1, 2])
        self.assertEqual([item["risk_rank"] for item in second.json()["items"]], [3, 4])
        summary = self.client.get(
            "/risk/summary", params={"report_month": "2026-04", "regime": "MODERN"}
        )
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.json()["project_count"], 1_625)
        self.assertEqual(summary.json()["top_risk_projects"][0]["risk_rank"], 1)
        self.assertTrue(summary.json()["regimes"][0]["calibration_active"])
        self.assertLessEqual(
            summary.json()["score_distribution"]["minimum"],
            summary.json()["score_distribution"]["maximum"],
        )

    def test_unknown_project_and_month_return_clean_404(self) -> None:
        self.assertEqual(
            self.client.get(
                "/risk/project/DOES_NOT_EXIST", params={"report_month": "2026-04"}
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get("/risk/projects", params={"report_month": "2099-01"}).status_code,
            404,
        )

    def test_malformed_month_and_filters_return_validation_errors(self) -> None:
        for params in (
            {"report_month": "2026-13"},
            {"report_month": "April-2026"},
            {"report_month": "2026-04", "regime": "MIDDLE"},
            {"report_month": "2026-04", "page": 0},
            {
                "report_month": "2026-04",
                "min_risk_probability": 0.9,
                "max_risk_probability": 0.1,
            },
        ):
            with self.subTest(params=params):
                self.assertEqual(
                    self.client.get("/risk/projects", params=params).status_code, 422
                )

    def test_canonical_hashes_remain_unchanged(self) -> None:
        self.assertEqual(sha256(ROOT / "data/processed/projects_monthly.csv"), ONGOING_SHA256)
        self.assertEqual(
            sha256(ROOT / "data/processed/projects_completed.csv"), COMPLETED_SHA256
        )


if __name__ == "__main__":
    unittest.main()
