"""Read-only access to the compact IRIS serving database."""

from __future__ import annotations

import json
import math
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Sequence

from src.serving.builder import DATABASE_NAME, MANIFEST_NAME, sha256


RECORD_COLUMNS = (
    "id",
    "project_code",
    "report_month",
    "project_name",
    "agency",
    "ministry",
    "sector",
    "state",
    "regime",
    "target",
    "model_id",
    "raw_probability",
    "risk_probability",
    "calibration_active",
    "risk_percentile",
    "risk_rank",
    "population_size",
    "raw_decision_score",
    "explanation_method",
    "contribution_space",
)


class ServingRepository:
    def __init__(self, artifact_dir: Path) -> None:
        self.artifact_dir = artifact_dir.resolve()
        self.database_path = self.artifact_dir / DATABASE_NAME
        self.manifest_path = self.artifact_dir / MANIFEST_NAME
        if not self.database_path.is_file() or not self.manifest_path.is_file():
            raise FileNotFoundError(
                f"Serving artifact is missing under {self.artifact_dir}; "
                "run python -m src.serving.builder first"
            )
        self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        if sha256(self.database_path) != self.manifest["database"]["sha256"]:
            raise RuntimeError("Serving database hash does not match serving_manifest.json")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            f"file:{self.database_path.as_posix()}?mode=ro", uri=True
        )
        connection.row_factory = sqlite3.Row
        return connection

    def health(self) -> dict[str, Any]:
        with closing(self._connect()) as connection:
            connection.execute("SELECT 1").fetchone()
        return {
            "status": "ok",
            "serving_artifact_version": self.manifest["serving_artifact_version"],
            "target": self.manifest["target"],
            "project_month_records": self.manifest["record_counts"]["project_months"],
        }

    @staticmethod
    def _where(
        *,
        report_month: str | None = None,
        project_code: str | None = None,
        regime: str | None = None,
        min_probability: float | None = None,
        max_probability: float | None = None,
        sector: str | None = None,
        agency: str | None = None,
        ministry: str | None = None,
        state: str | None = None,
        search: str | None = None,
    ) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        values: list[Any] = []
        for clause, value in (
            ("report_month = ?", report_month),
            ("project_code = ?", project_code),
            ("regime = ?", regime),
            ("sector = ?", sector),
            ("agency = ?", agency),
            ("ministry = ?", ministry),
            ("state = ?", state),
        ):
            if value is not None:
                clauses.append(clause)
                values.append(value)
        if min_probability is not None:
            clauses.append("risk_probability >= ?")
            values.append(min_probability)
        if max_probability is not None:
            clauses.append("risk_probability <= ?")
            values.append(max_probability)
        if search:
            clauses.append(
                "(project_code LIKE ? ESCAPE '\\' COLLATE NOCASE OR "
                "project_name LIKE ? ESCAPE '\\' COLLATE NOCASE)"
            )
            escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            values.extend([f"%{escaped}%", f"%{escaped}%"])
        return (" WHERE " + " AND ".join(clauses) if clauses else ""), values

    def list_records(
        self,
        *,
        report_month: str,
        regime: str | None,
        min_probability: float | None,
        max_probability: float | None,
        sector: str | None,
        agency: str | None,
        ministry: str | None,
        state: str | None,
        search: str | None,
        limit: int,
        offset: int,
    ) -> tuple[int, list[dict[str, Any]]]:
        where, values = self._where(
            report_month=report_month,
            regime=regime,
            min_probability=min_probability,
            max_probability=max_probability,
            sector=sector,
            agency=agency,
            ministry=ministry,
            state=state,
            search=search,
        )
        with closing(self._connect()) as connection:
            total = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM risk_records{where}", values
                ).fetchone()[0]
            )
            rows = connection.execute(
                f"SELECT {', '.join(RECORD_COLUMNS)} FROM risk_records{where} "
                "ORDER BY risk_rank, project_code LIMIT ? OFFSET ?",
                [*values, limit, offset],
            ).fetchall()
            return total, self._hydrate(connection, rows)

    def get_record(self, project_code: str, report_month: str) -> dict[str, Any] | None:
        where, values = self._where(
            project_code=project_code, report_month=report_month
        )
        with closing(self._connect()) as connection:
            rows = connection.execute(
                f"SELECT {', '.join(RECORD_COLUMNS)} FROM risk_records{where} "
                "ORDER BY regime, model_id",
                values,
            ).fetchall()
            if not rows:
                return None
            if len(rows) > 1:
                raise RuntimeError(
                    "Exact project_code/report_month is ambiguous across locked regimes"
                )
            return self._hydrate(connection, rows)[0]

    def history(
        self, project_code: str, regime: str | None = None
    ) -> list[dict[str, Any]]:
        where, values = self._where(project_code=project_code, regime=regime)
        with closing(self._connect()) as connection:
            rows = connection.execute(
                f"SELECT {', '.join(RECORD_COLUMNS)} FROM risk_records{where} "
                "ORDER BY report_month, regime, model_id",
                values,
            ).fetchall()
            return self._hydrate(connection, rows)

    def month_scores(
        self,
        report_month: str,
        regime: str | None,
        *,
        sector: str | None = None,
        agency: str | None = None,
        ministry: str | None = None,
        state: str | None = None,
        search: str | None = None,
    ) -> list[sqlite3.Row]:
        where, values = self._where(
            report_month=report_month,
            regime=regime,
            sector=sector,
            agency=agency,
            ministry=ministry,
            state=state,
            search=search,
        )
        with closing(self._connect()) as connection:
            return connection.execute(
                "SELECT project_code, project_name, agency, ministry, sector, state, "
                "regime, model_id, raw_probability, "
                "risk_probability, calibration_active, risk_rank, risk_percentile, "
                f"population_size FROM risk_records{where} "
                "ORDER BY risk_rank, project_code",
                values,
            ).fetchall()

    def dashboard_options(self, report_month: str | None = None) -> dict[str, Any]:
        with closing(self._connect()) as connection:
            months = [
                row[0]
                for row in connection.execute(
                    "SELECT DISTINCT report_month FROM risk_records ORDER BY report_month"
                ).fetchall()
            ]
            selected = report_month or months[-1]
            if selected not in months:
                raise ValueError("Risk option population not found")

            def values(field: str) -> list[str]:
                return [
                    row[0]
                    for row in connection.execute(
                        f"SELECT DISTINCT {field} FROM risk_records "
                        f"WHERE report_month = ? AND {field} IS NOT NULL "
                        f"ORDER BY {field} COLLATE NOCASE, {field}",
                        (selected,),
                    ).fetchall()
                ]

            regimes = [
                row[0]
                for row in connection.execute(
                    "SELECT DISTINCT regime FROM risk_records "
                    "WHERE report_month = ? ORDER BY regime",
                    (selected,),
                ).fetchall()
            ]
            return {
                "report_months": months,
                "default_report_month": months[-1],
                "selected_report_month": selected,
                "regimes": regimes,
                "sectors": values("sector"),
                "agencies": values("agency"),
                "ministries": values("ministry"),
                "states": values("state"),
            }

    @staticmethod
    def sector_summary(rows: Sequence[sqlite3.Row]) -> list[dict[str, Any]]:
        grouped: dict[str | None, list[float]] = {}
        for row in rows:
            grouped.setdefault(row["sector"], []).append(float(row["risk_probability"]))
        result = [
            {
                "sector": sector,
                "project_count": len(values),
                "mean_risk_probability": math.fsum(values) / len(values),
                "highest_risk_probability": max(values),
            }
            for sector, values in grouped.items()
        ]
        return sorted(
            result,
            key=lambda item: (-item["mean_risk_probability"], item["sector"] or ""),
        )

    def _hydrate(
        self, connection: sqlite3.Connection, rows: Sequence[sqlite3.Row]
    ) -> list[dict[str, Any]]:
        if not rows:
            return []
        ids = [int(row["id"]) for row in rows]
        placeholders = ",".join("?" for _ in ids)
        contributor_rows = connection.execute(
            "SELECT c.risk_record_id, f.feature, f.display_name, c.value, "
            "c.contribution, c.direction, c.rank FROM contributors c "
            "JOIN feature_catalog f ON f.id = c.feature_id "
            f"WHERE c.risk_record_id IN ({placeholders}) "
            "ORDER BY risk_record_id, direction DESC, rank, feature",
            ids,
        ).fetchall()
        by_record: dict[int, dict[str, list[dict[str, Any]]]] = {
            record_id: {"POSITIVE": [], "NEGATIVE": []} for record_id in ids
        }
        for contributor in contributor_rows:
            item = {
                "feature": contributor["feature"],
                "display_name": contributor["display_name"],
                "value": contributor["value"],
                "contribution": float(contributor["contribution"]),
                "direction": contributor["direction"],
                "rank": int(contributor["rank"]),
            }
            by_record[int(contributor["risk_record_id"])][contributor["direction"]].append(item)

        version = {
            "serving_contract_version": self.manifest["serving_contract_version"],
            "serving_artifact_version": self.manifest["serving_artifact_version"],
            "explanation_version": self.manifest["explanation_version"],
            "explanation_manifest_sha256": self.manifest["sources"][
                "explainability_manifest"
            ]["sha256"],
        }
        result = []
        for row in rows:
            contributor_group = by_record[int(row["id"])]
            all_contributors = (
                contributor_group["POSITIVE"] + contributor_group["NEGATIVE"]
            )
            result.append(
                {
                    "project_code": row["project_code"],
                    "report_month": row["report_month"],
                    "project_name": row["project_name"],
                    "agency": row["agency"],
                    "ministry": row["ministry"],
                    "sector": row["sector"],
                    "state": row["state"],
                    "regime": row["regime"],
                    "target": row["target"],
                    "model_id": row["model_id"],
                    "raw_probability": float(row["raw_probability"]),
                    "risk_probability": float(row["risk_probability"]),
                    "calibration_active": bool(row["calibration_active"]),
                    "risk_percentile": float(row["risk_percentile"]),
                    "risk_rank": int(row["risk_rank"]),
                    "population_size": int(row["population_size"]),
                    "top_positive_contributors": contributor_group["POSITIVE"],
                    "top_negative_contributors": contributor_group["NEGATIVE"],
                    "source_feature_values": {
                        item["feature"]: item["value"] for item in all_contributors
                    },
                    "version_metadata": {
                        **version,
                        "model_id": row["model_id"],
                        "explanation_method": row["explanation_method"],
                        "contribution_space": row["contribution_space"],
                        "ranking_score_type": "OPERATIONAL_PROBABILITY",
                    },
                }
            )
        return result


def score_distribution(values: Sequence[float]) -> dict[str, float]:
    if not values:
        raise ValueError("Cannot summarize an empty score population")
    ordered = sorted(float(value) for value in values)

    def quantile(probability: float) -> float:
        position = (len(ordered) - 1) * probability
        lower = math.floor(position)
        upper = math.ceil(position)
        if lower == upper:
            return ordered[lower]
        fraction = position - lower
        return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction

    return {
        "minimum": ordered[0],
        "p25": quantile(0.25),
        "median": quantile(0.50),
        "p75": quantile(0.75),
        "p90": quantile(0.90),
        "p95": quantile(0.95),
        "maximum": ordered[-1],
        "mean": math.fsum(ordered) / len(ordered),
    }
