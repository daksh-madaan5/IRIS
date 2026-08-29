"""Build the compact, deterministic IRIS serving artifact.

The builder copies locked scores, ranks, percentiles, and configured source-level
top contributors from the accepted explainability outputs. It never refits a
model, recalibrates a score, recomputes a rank, or reads the complete local
contribution vector.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import sqlite3
from pathlib import Path
from typing import Any, Iterable


SERVING_ARTIFACT_VERSION = "iris_serving_v1_1"
SERVING_CONTRACT_VERSION = "1.1"
TARGET = "target_effective_schedule_ext_3m"
DATABASE_NAME = "iris_risk_serving_v1.sqlite3"
MANIFEST_NAME = "serving_manifest.json"

RANK_REQUIRED_FIELDS = {
    "project_code",
    "report_month",
    "regime",
    "model_identifier",
    "raw_predicted_probability",
    "calibrated_probability",
    "calibration_active",
    "raw_decision_score",
    "ranking_probability",
    "ranking_score_type",
    "risk_rank_within_month",
    "risk_percentile_within_month",
    "month_population",
}
TOP_REQUIRED_FIELDS = {
    "project_code",
    "report_month",
    "regime",
    "model_identifier",
    "raw_predicted_probability",
    "calibrated_probability",
    "calibration_active",
    "raw_decision_score",
    "risk_rank_within_month",
    "risk_percentile_within_month",
    "source_feature_name",
    "source_feature_value_at_t",
    "feature_contribution",
    "contribution_direction",
    "direction_rank",
    "configured_direction_limit",
    "contribution_space",
}

DISPLAY_METADATA_FIELDS = (
    "project_name",
    "agency",
    "ministry",
    "sector",
    "state",
)

DISPLAY_NAMES = {
    "sector": "Sector",
    "agency": "Agency",
    "state": "State",
    "original_cost": "Original cost",
    "cumulative_expenditure_t": "Cumulative expenditure",
    "revised_cost_t": "Revised cost",
    "physical_progress_t": "Physical progress",
    "project_age_months": "Project age (months)",
    "months_to_original_schedule": "Months to original schedule",
    "months_to_effective_schedule": "Months to effective schedule",
    "schedule_revision_lag_months": "Schedule revision lag (months)",
    "schedule_has_been_revised": "Schedule has been revised",
    "months_since_start": "Months since start",
    "expenditure_to_original_cost_ratio": "Expenditure to original cost ratio",
    "revised_to_original_cost_ratio": "Revised to original cost ratio",
    "cost_has_been_revised": "Cost has been revised",
    "exp_delta_1m": "Expenditure change (1 month)",
    "exp_delta_3m": "Expenditure change (3 months)",
    "past_exp_stagnant_3m": "Expenditure stagnant over prior 3 months",
    "past_progress_delta_3m": "Physical progress change (3 months)",
    "past_progress_stagnant_3m": "Physical progress stagnant over prior 3 months",
    "n_prior_schedule_extensions": "Prior schedule extensions",
    "n_prior_cost_revisions": "Prior cost revisions",
    "observed_tenure_months": "Observed tenure (months)",
    "state_is_missing": "State is missing",
    "approval_date_is_missing": "Approval date is missing",
    "original_completion_date_is_missing": "Original completion date is missing",
    "revised_cost_is_present": "Revised cost is present",
    "revised_date_is_present": "Revised completion date is present",
    "physical_progress_is_present": "Physical progress is present",
    "physical_progress_supported": "Physical progress is structurally supported",
    "start_date_is_present": "Start date is present",
    "start_date_supported": "Start date is structurally supported",
    "exp_delta_1m_is_supported": "One-month expenditure change is supported",
    "exp_delta_3m_is_supported": "Three-month expenditure change is supported",
    "progress_delta_3m_is_supported": "Three-month progress change is supported",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _read_csv(path: Path) -> tuple[list[str], Iterable[dict[str, str]]]:
    handle = path.open("r", encoding="utf-8-sig", newline="")
    reader = csv.DictReader(handle)
    fields = list(reader.fieldnames or [])

    def rows() -> Iterable[dict[str, str]]:
        try:
            yield from reader
        finally:
            handle.close()

    return fields, rows()


def _bool(value: str) -> bool:
    if value == "True":
        return True
    if value == "False":
        return False
    raise ValueError(f"Expected explicit boolean text, received {value!r}")


def _optional_text(value: str) -> str | None:
    return value if value != "" else None


def _require_finite_probability(value: str, field: str) -> float:
    result = float(value)
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise ValueError(f"{field} is not a finite probability: {value!r}")
    return result


def _validate_source_hashes(
    explanation_dir: Path, manifest: dict[str, Any]
) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for filename in ("risk_rankings.csv", "top_contributors.csv"):
        path = explanation_dir / filename
        actual = sha256(path)
        expected = manifest["generated_files"][filename]["sha256"].upper()
        if actual != expected:
            raise RuntimeError(
                f"Locked explainability artifact hash mismatch for {filename}: "
                f"expected {expected}, got {actual}"
            )
        hashes[filename] = actual
    return hashes


def _load_display_metadata(
    root: Path, explanation_manifest: dict[str, Any]
) -> tuple[dict[tuple[str, str], dict[str, str | None]], str]:
    """Load exact project-month display labels from the immutable canonical panel."""

    path = root / "data/processed/projects_monthly.csv"
    actual_hash = sha256(path)
    expected_hash = explanation_manifest["canonical_hashes"]["projects_monthly.csv"].upper()
    if actual_hash != expected_hash:
        raise RuntimeError(
            "Canonical project metadata hash mismatch: "
            f"expected {expected_hash}, got {actual_hash}"
        )
    fields, rows = _read_csv(path)
    required = {"project_code", "report_month", *DISPLAY_METADATA_FIELDS}
    if not required.issubset(fields):
        raise RuntimeError(
            f"Canonical metadata schema mismatch: missing {sorted(required - set(fields))}"
        )
    metadata: dict[tuple[str, str], dict[str, str | None]] = {}
    for row in rows:
        key = (row["project_code"], row["report_month"])
        if key in metadata:
            raise RuntimeError(f"Duplicate canonical project-month metadata key: {key}")
        metadata[key] = {
            field: _optional_text(row[field]) for field in DISPLAY_METADATA_FIELDS
        }
    return metadata, actual_hash


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA journal_mode = DELETE;
        PRAGMA synchronous = FULL;
        PRAGMA foreign_keys = ON;
        CREATE TABLE risk_records (
            id INTEGER PRIMARY KEY,
            project_code TEXT NOT NULL,
            report_month TEXT NOT NULL,
            project_name TEXT,
            agency TEXT,
            ministry TEXT,
            sector TEXT,
            state TEXT,
            regime TEXT NOT NULL CHECK (regime IN ('LEGACY', 'MODERN')),
            target TEXT NOT NULL,
            model_id TEXT NOT NULL,
            raw_probability REAL NOT NULL,
            risk_probability REAL NOT NULL,
            calibration_active INTEGER NOT NULL CHECK (calibration_active IN (0, 1)),
            risk_percentile REAL NOT NULL,
            risk_rank INTEGER NOT NULL,
            population_size INTEGER NOT NULL,
            raw_decision_score REAL NOT NULL,
            explanation_method TEXT NOT NULL,
            contribution_space TEXT NOT NULL,
            UNIQUE (project_code, report_month, regime, model_id)
        );
        CREATE TABLE feature_catalog (
            id INTEGER PRIMARY KEY,
            feature TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL
        );
        CREATE TABLE contributors (
            risk_record_id INTEGER NOT NULL REFERENCES risk_records(id),
            feature_id INTEGER NOT NULL REFERENCES feature_catalog(id),
            value TEXT,
            contribution REAL NOT NULL,
            direction TEXT NOT NULL CHECK (direction IN ('POSITIVE', 'NEGATIVE')),
            rank INTEGER NOT NULL,
            PRIMARY KEY (risk_record_id, direction, rank),
            UNIQUE (risk_record_id, feature_id)
        );
        CREATE TABLE artifact_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE INDEX risk_month_rank_idx
            ON risk_records(report_month, regime, risk_rank, project_code);
        CREATE INDEX risk_project_history_idx
            ON risk_records(project_code, report_month, regime);
        CREATE INDEX risk_month_metadata_idx
            ON risk_records(report_month, sector, agency, ministry, state);
        """
    )


def build(root: Path, output_dir: Path | None = None) -> dict[str, Any]:
    root = root.resolve()
    explanation_dir = (
        root / "data/ml/schedule_extension_3m/evaluation/explainability"
    )
    output_dir = (output_dir or root / "data/serving").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    database_path = output_dir / DATABASE_NAME
    manifest_path = output_dir / MANIFEST_NAME
    temporary_path = output_dir / f".{DATABASE_NAME}.tmp"

    explanation_manifest_path = explanation_dir / "explainability_manifest.json"
    explanation_manifest = json.loads(
        explanation_manifest_path.read_text(encoding="utf-8")
    )
    if explanation_manifest["target"] != TARGET:
        raise RuntimeError("Explainability target contradicts the locked serving target")
    if explanation_manifest["validation"]["canonical_hashes_unchanged"] is not True:
        raise RuntimeError("Explainability manifest does not attest immutable canonical inputs")
    source_hashes = _validate_source_hashes(explanation_dir, explanation_manifest)
    explanation_manifest_hash = sha256(explanation_manifest_path)
    display_metadata, canonical_monthly_hash = _load_display_metadata(
        root, explanation_manifest
    )

    if temporary_path.exists():
        temporary_path.unlink()
    connection = sqlite3.connect(temporary_path)
    try:
        _create_schema(connection)
        rank_fields, ranking_rows = _read_csv(explanation_dir / "risk_rankings.csv")
        if not RANK_REQUIRED_FIELDS.issubset(rank_fields):
            raise RuntimeError(
                f"risk_rankings.csv schema mismatch: missing "
                f"{sorted(RANK_REQUIRED_FIELDS - set(rank_fields))}"
            )

        key_to_id: dict[tuple[str, str, str, str], int] = {}
        rank_snapshot: dict[tuple[str, str, str, str], tuple[str, ...]] = {}
        regime_counts = {"LEGACY": 0, "MODERN": 0}
        calibration_active_rows = 0
        methods = {
            "LEGACY": "CATBOOST_NATIVE_TREESHAP",
            "MODERN": "LOGISTIC_COEFFICIENT_TIMES_TRANSFORMED_VALUE",
        }
        contribution_space = explanation_manifest["methods"]["contribution_space"]
        connection.executemany(
            "INSERT INTO feature_catalog(id, feature, display_name) VALUES (?, ?, ?)",
            [
                (index, feature, DISPLAY_NAMES[feature])
                for index, feature in enumerate(sorted(DISPLAY_NAMES), start=1)
            ],
        )
        feature_ids = {
            feature: index
            for index, feature in enumerate(sorted(DISPLAY_NAMES), start=1)
        }

        for row in ranking_rows:
            key = (
                row["project_code"],
                row["report_month"],
                row["regime"],
                row["model_identifier"],
            )
            if key in key_to_id:
                raise RuntimeError(f"Duplicate ranking key: {key}")
            if row["ranking_score_type"] != "OPERATIONAL_PROBABILITY":
                raise RuntimeError(f"Unsupported ranking score type for {key}")
            active = _bool(row["calibration_active"])
            raw_probability = _require_finite_probability(
                row["raw_predicted_probability"], "raw_predicted_probability"
            )
            risk_probability = _require_finite_probability(
                row["ranking_probability"], "ranking_probability"
            )
            calibrated = row["calibrated_probability"]
            if active:
                if calibrated == "" or float(calibrated) != risk_probability:
                    raise RuntimeError(f"Active calibrated probability mismatch for {key}")
            elif calibrated != "" or raw_probability != risk_probability:
                raise RuntimeError(f"Inactive calibration score mismatch for {key}")
            regime = row["regime"]
            if explanation_manifest["locked_models"].get(regime) != row["model_identifier"]:
                raise RuntimeError(f"Locked model mismatch for {key}")
            metadata_key = (row["project_code"], row["report_month"])
            if metadata_key not in display_metadata:
                raise RuntimeError(
                    f"Serving record has no exact canonical metadata match: {metadata_key}"
                )
            labels = display_metadata[metadata_key]
            cursor = connection.execute(
                """
                INSERT INTO risk_records (
                    project_code, report_month,
                    project_name, agency, ministry, sector, state,
                    regime, target, model_id,
                    raw_probability, risk_probability, calibration_active,
                    risk_percentile, risk_rank, population_size,
                    raw_decision_score, explanation_method, contribution_space
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["project_code"],
                    row["report_month"],
                    labels["project_name"],
                    labels["agency"],
                    labels["ministry"],
                    labels["sector"],
                    labels["state"],
                    regime,
                    TARGET,
                    row["model_identifier"],
                    raw_probability,
                    risk_probability,
                    int(active),
                    float(row["risk_percentile_within_month"]),
                    int(row["risk_rank_within_month"]),
                    int(row["month_population"]),
                    float(row["raw_decision_score"]),
                    methods[regime],
                    contribution_space,
                ),
            )
            key_to_id[key] = int(cursor.lastrowid)
            rank_snapshot[key] = (
                row["raw_predicted_probability"],
                row["calibrated_probability"],
                row["calibration_active"],
                row["raw_decision_score"],
                row["risk_rank_within_month"],
                row["risk_percentile_within_month"],
            )
            regime_counts[regime] += 1
            calibration_active_rows += int(active)

        top_fields, top_rows = _read_csv(explanation_dir / "top_contributors.csv")
        if not TOP_REQUIRED_FIELDS.issubset(top_fields):
            raise RuntimeError(
                f"top_contributors.csv schema mismatch: missing "
                f"{sorted(TOP_REQUIRED_FIELDS - set(top_fields))}"
            )
        contributor_rows = 0
        seen_contributors: set[tuple[int, str, int]] = set()
        for row in top_rows:
            key = (
                row["project_code"],
                row["report_month"],
                row["regime"],
                row["model_identifier"],
            )
            if key not in key_to_id:
                raise RuntimeError(f"Contributor has no ranking record: {key}")
            snapshot = (
                row["raw_predicted_probability"],
                row["calibrated_probability"],
                row["calibration_active"],
                row["raw_decision_score"],
                row["risk_rank_within_month"],
                row["risk_percentile_within_month"],
            )
            if snapshot != rank_snapshot[key]:
                raise RuntimeError(f"Contributor score/rank fields contradict ranking for {key}")
            feature = row["source_feature_name"]
            if feature not in DISPLAY_NAMES:
                raise RuntimeError(f"Missing reviewed display name for feature {feature!r}")
            direction = row["contribution_direction"]
            contribution = float(row["feature_contribution"])
            if direction not in {"POSITIVE", "NEGATIVE"}:
                raise RuntimeError(f"Unsupported top-contributor direction: {direction}")
            if (direction == "POSITIVE") != (contribution > 0.0):
                raise RuntimeError(f"Contributor sign/direction mismatch for {key}, {feature}")
            rank = int(row["direction_rank"])
            contributor_key = (key_to_id[key], direction, rank)
            if contributor_key in seen_contributors:
                raise RuntimeError(f"Duplicate contributor rank: {key}, {direction}, {rank}")
            seen_contributors.add(contributor_key)
            connection.execute(
                """
                INSERT INTO contributors (
                    risk_record_id, feature_id, value,
                    contribution, direction, rank
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    key_to_id[key],
                    feature_ids[feature],
                    _optional_text(row["source_feature_value_at_t"]),
                    contribution,
                    direction,
                    rank,
                ),
            )
            contributor_rows += 1

        records_without_contributors = connection.execute(
            """
            SELECT COUNT(*) FROM risk_records r
            WHERE NOT EXISTS (
                SELECT 1 FROM contributors c WHERE c.risk_record_id = r.id
            )
            """
        ).fetchone()[0]
        if records_without_contributors:
            raise RuntimeError(
                f"{records_without_contributors} risk records have no configured contributors"
            )

        metadata = {
            "serving_artifact_version": SERVING_ARTIFACT_VERSION,
            "serving_contract_version": SERVING_CONTRACT_VERSION,
            "target": TARGET,
            "explanation_version": explanation_manifest["explainability_name"],
            "explanation_manifest_sha256": explanation_manifest_hash,
            "risk_rankings_sha256": source_hashes["risk_rankings.csv"],
            "top_contributors_sha256": source_hashes["top_contributors.csv"],
            "projects_monthly_sha256": canonical_monthly_hash,
        }
        connection.executemany(
            "INSERT INTO artifact_metadata(key, value) VALUES (?, ?)",
            sorted(metadata.items()),
        )
        connection.commit()
        connection.execute("VACUUM")
        connection.commit()
    except Exception:
        connection.close()
        if temporary_path.exists():
            temporary_path.unlink()
        raise
    else:
        connection.close()

    # Windows cannot atomically replace an existing SQLite file in all runtime
    # configurations. Both paths are exact generated serving-artifact targets.
    database_path.unlink(missing_ok=True)
    os.replace(temporary_path, database_path)
    database_hash = sha256(database_path)
    manifest = {
        "serving_artifact_version": SERVING_ARTIFACT_VERSION,
        "serving_contract_version": SERVING_CONTRACT_VERSION,
        "runtime_versions": {
            "python": platform.python_version(),
            "sqlite": sqlite3.sqlite_version,
        },
        "target": TARGET,
        "database": {
            "path": str(database_path.relative_to(root))
            if database_path.is_relative_to(root)
            else str(database_path),
            "sha256": database_hash,
        },
        "sources": {
            "explainability_manifest": {
                "path": str(explanation_manifest_path.relative_to(root)),
                "sha256": explanation_manifest_hash,
            },
            "risk_rankings.csv": {
                "path": str((explanation_dir / "risk_rankings.csv").relative_to(root)),
                "sha256": source_hashes["risk_rankings.csv"],
            },
            "top_contributors.csv": {
                "path": str((explanation_dir / "top_contributors.csv").relative_to(root)),
                "sha256": source_hashes["top_contributors.csv"],
            },
            "projects_monthly.csv": {
                "path": "data/processed/projects_monthly.csv",
                "sha256": canonical_monthly_hash,
            },
        },
        "locked_models": explanation_manifest["locked_models"],
        "explanation_version": explanation_manifest["explainability_name"],
        "contribution_space": explanation_manifest["methods"]["contribution_space"],
        "record_counts": {
            "project_months": len(key_to_id),
            "contributors": contributor_rows,
            "by_regime": regime_counts,
            "calibration_active_project_months": calibration_active_rows,
        },
        "validation": {
            "risk_recomputed": False,
            "rank_recomputed": False,
            "calibration_recomputed": False,
            "complete_local_explanations_read": False,
            "future_target_values_included": False,
            "completed_project_metadata_included": False,
            "display_metadata_included": list(DISPLAY_METADATA_FIELDS),
            "project_name_included": True,
            "project_name_used_as_model_feature": False,
            "display_metadata_exact_key_match": True,
            "crosswalk_used": False,
            "records_without_contributors": records_without_contributors,
            "source_hashes_match_explainability_manifest": True,
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    result = build(args.root, args.output_dir)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
