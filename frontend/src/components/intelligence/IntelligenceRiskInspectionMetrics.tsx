import React from "react";
import type { ProjectRiskHistoryPoint, ProjectIntelligenceRisk } from "@/types/project.ts";
import {
  evaluateObservationMovement,
  formatSignedDelta,
  areObservationsAdjacent,
  areObservationsSemanticallyComparable,
} from "@/utils/historicalComparability.ts";

interface IntelligenceRiskInspectionMetricsProps {
  record: ProjectRiskHistoryPoint;
  history?: ProjectRiskHistoryPoint[];
  currentRisk?: ProjectIntelligenceRisk | null;
}

export const IntelligenceRiskInspectionMetrics: React.FC<IntelligenceRiskInspectionMetricsProps> = ({
  record,
  history,
  currentRisk,
}) => {
  const hasCalibrated = record.calibration_active && typeof record.risk_probability === "number";
  const hasRaw = typeof record.raw_probability === "number";
  const hasRank = typeof record.risk_rank === "number" && record.risk_rank > 0;
  const hasPercentile = typeof record.risk_percentile === "number";
  const hasPopulation = typeof record.population_size === "number" && record.population_size > 0;

  // Adjacent historical movement evaluation
  const sortedHistory = [...(history || [])].sort((a, b) =>
    a.report_month.localeCompare(b.report_month)
  );
  const currentIndex = sortedHistory.findIndex(
    (h) => h.report_month === record.report_month
  );
  const prevRecord = currentIndex > 0 ? sortedHistory[currentIndex - 1] : null;
  const adjacentMovement = prevRecord
    ? evaluateObservationMovement(prevRecord, record, true)
    : null;

  // Current assessment comparison evaluation
  const isSameAsCurrent = currentRisk && currentRisk.report_month === record.report_month;
  const isAdjacentToCurrent =
    currentRisk && !isSameAsCurrent
      ? areObservationsAdjacent(history || [], record.report_month, currentRisk.report_month)
      : false;
  const isCurrentComparable =
    isAdjacentToCurrent &&
    currentRisk &&
    areObservationsSemanticallyComparable(record, currentRisk);

  const currentMovement =
    isAdjacentToCurrent && currentRisk
      ? evaluateObservationMovement(record, currentRisk, true)
      : null;

  return (
    <div className="terminal-card inspection-metrics-card">
      <div className="terminal-card-header">
        <div className="terminal-card-title-lockup">
          <span className="terminal-section-eyebrow">OBSERVED EVALUATION METRICS</span>
          <h4 className="terminal-card-title">HISTORICAL RISK & PORTFOLIO POSITION</h4>
        </div>
        <span className="terminal-badge-muted monospace">
          TARGET: target_effective_schedule_ext_3m
        </span>
      </div>

      <div className="terminal-inspection-metrics-grid">
        {/* Metric 1: Calibrated Risk Probability */}
        <div className="inspection-metric-box primary">
          <span className="inspection-metric-label">CALIBRATED OPERATIONAL RISK</span>
          <div className="inspection-metric-value monospace">
            {hasCalibrated ? (
              `${(record.risk_probability * 100).toFixed(1)}%`
            ) : record.calibration_active ? (
              <span className="muted">UNAVAILABLE</span>
            ) : (
              <span className="muted font-normal text-xs">RAW / UNCALIBRATED</span>
            )}
          </div>
          <span className="inspection-metric-subtext monospace">
            {record.calibration_active ? (
              hasCalibrated ? (
                "Operational probability (Platt-calibrated)"
              ) : (
                "Calibrated score unavailable"
              )
            ) : (
              "Evaluation origin was served uncalibrated"
            )}
          </span>
        </div>

        {/* Metric 2: Raw Model Probability */}
        <div className="inspection-metric-box">
          <span className="inspection-metric-label">RAW MODEL PROBABILITY</span>
          <div className="inspection-metric-value monospace muted">
            {hasRaw ? `${(record.raw_probability * 100).toFixed(1)}%` : "UNAVAILABLE"}
          </div>
          <span className="inspection-metric-subtext monospace">
            Pre-calibration unweighted model probability
          </span>
        </div>

        {/* Metric 3: Portfolio Rank */}
        <div className="inspection-metric-box">
          <span className="inspection-metric-label">PORTFOLIO RANK</span>
          <div className="inspection-metric-value monospace">
            {hasRank ? (
              <>
                #{record.risk_rank}
                {hasPopulation && (
                  <span className="inspection-metric-population">
                    {" "}/ {record.population_size.toLocaleString()}
                  </span>
                )}
              </>
            ) : (
              <span className="muted">UNAVAILABLE</span>
            )}
          </div>
          <span className="inspection-metric-subtext monospace">
            {hasRank && hasPopulation
              ? `Ranked within ${record.population_size.toLocaleString()} evaluated projects`
              : "Cross-sectional portfolio rank"}
          </span>
        </div>

        {/* Metric 4: Risk Percentile */}
        <div className="inspection-metric-box">
          <span className="inspection-metric-label">PERCENTILE</span>
          <div className="inspection-metric-value monospace">
            {hasPercentile ? `P${(record.risk_percentile * 100).toFixed(1)}` : "UNAVAILABLE"}
          </div>
          <span className="inspection-metric-subtext monospace">
            {hasPercentile
              ? `Exceeds ${(record.risk_percentile * 100).toFixed(1)}% of evaluated cohort`
              : "Normalized portfolio risk percentile"}
          </span>
        </div>
      </div>

      {/* Adjacent Historical Movement Section */}
      <div className="inspection-movement-section" role="region" aria-label="Adjacent Historical Movement">
        <div className="inspection-movement-header">
          <span className="inspection-movement-eyebrow monospace">
            {prevRecord ? `ADJACENT MOVEMENT (vs ${prevRecord.report_month})` : "HISTORICAL SEQUENCE POSITION"}
          </span>
        </div>

        {!prevRecord ? (
          <div className="inspection-movement-content baseline monospace">
            <span className="terminal-movement-badge baseline">BASELINE OBSERVATION</span>
            <span className="movement-note muted">
              Initial recorded evaluation for this project. No preceding observation exists for adjacent movement comparison.
            </span>
          </div>
        ) : adjacentMovement?.status === "COMPARABLE" ? (
          <div className="inspection-movement-content comparable monospace">
            <div className="movement-deltas-row">
              <div className="movement-delta-item">
                <span className="movement-delta-label">CALIBRATED RISK:</span>
                <span className="movement-delta-val font-bold">
                  {formatSignedDelta(adjacentMovement.probabilityDelta, "pp")}
                </span>
              </div>
              <div className="movement-delta-item">
                <span className="movement-delta-label">RAW PROBABILITY:</span>
                <span className="movement-delta-val">
                  {formatSignedDelta(adjacentMovement.rawProbabilityDelta, "pp")}
                </span>
              </div>
              <div className="movement-delta-item">
                <span className="movement-delta-label">RANK:</span>
                <span className="movement-delta-val">
                  {adjacentMovement.rankDelta !== undefined
                    ? adjacentMovement.rankDelta > 0
                      ? `+${adjacentMovement.rankDelta}`
                      : `${adjacentMovement.rankDelta}`
                    : "—"}
                </span>
              </div>
              <div className="movement-delta-item">
                <span className="movement-delta-label">PERCENTILE:</span>
                <span className="movement-delta-val">
                  {formatSignedDelta(adjacentMovement.percentileDelta, "pp")}
                </span>
              </div>
            </div>
            <span className="movement-subtext muted text-xs">
              Adjacent observation ({prevRecord.report_month} → {record.report_month}) is semantically comparable: identical model ({record.model_id}), regime ({record.regime}), and calibration state.
            </span>
          </div>
        ) : (
          <div className="inspection-movement-content limited monospace">
            <span className="terminal-movement-badge limited">COMPARABILITY LIMITED</span>
            <span className="movement-note muted">
              Evaluations span differing {adjacentMovement?.transitions.map((t) => t.type).join(" / ")} specifications ({prevRecord.regime} / {prevRecord.model_id} vs {record.regime} / {record.model_id}). Numerical movement delta is suppressed.
            </span>
          </div>
        )}
      </div>

      {/* Current Assessment Relationship (Only when comparing against current assessment) */}
      {currentRisk && !isSameAsCurrent && (
        <div className="inspection-current-comparison" role="region" aria-label="Current Assessment Relationship">
          <div className="inspection-movement-header">
            <span className="inspection-movement-eyebrow monospace">
              CURRENT ASSESSMENT RELATIONSHIP (vs {currentRisk.report_month})
            </span>
          </div>

          {!isAdjacentToCurrent ? (
            <div className="inspection-non-adjacent-box monospace">
              <div className="terminal-movement-badge not-established">
                COMPARISON NOT ESTABLISHED (NON-ADJACENT OBSERVATIONS)
              </div>
              <p className="movement-note text-xs muted">
                Current assessment ({currentRisk.report_month}) and selected historical observation ({record.report_month}) are non-adjacent evaluations. An automated movement delta is not calculated. Values are shown separately:
              </p>
              <div className="non-adjacent-values-grid">
                <div className="non-adjacent-col">
                  <span className="col-label">INSPECTED HISTORICAL ({record.report_month}):</span>
                  <span className="col-val font-bold">
                    {(record.risk_probability * 100).toFixed(1)}% (raw: {(record.raw_probability * 100).toFixed(1)}%, {record.regime}, {record.model_id})
                  </span>
                </div>
                <div className="non-adjacent-col">
                  <span className="col-label">CURRENT ASSESSMENT ({currentRisk.report_month}):</span>
                  <span className="col-val font-bold">
                    {(currentRisk.risk_probability * 100).toFixed(1)}% (raw: {(currentRisk.raw_probability * 100).toFixed(1)}%, {currentRisk.regime}, {currentRisk.model_id})
                  </span>
                </div>
              </div>
            </div>
          ) : isCurrentComparable && currentMovement ? (
            <div className="inspection-movement-content comparable monospace">
              <div className="movement-deltas-row">
                <div className="movement-delta-item">
                  <span className="movement-delta-label">CALIBRATED RISK:</span>
                  <span className="movement-delta-val font-bold">
                    {formatSignedDelta(currentMovement.probabilityDelta, "pp")}
                  </span>
                </div>
                <div className="movement-delta-item">
                  <span className="movement-delta-label">RAW PROBABILITY:</span>
                  <span className="movement-delta-val">
                    {formatSignedDelta(currentMovement.rawProbabilityDelta, "pp")}
                  </span>
                </div>
              </div>
            </div>
          ) : (
            <div className="inspection-movement-content limited monospace">
              <span className="terminal-movement-badge limited">COMPARABILITY LIMITED</span>
              <span className="movement-note muted">
                Current assessment and historical observation cross model/regime/calibration boundaries. Direct probability delta is suppressed.
              </span>
            </div>
          )}
        </div>
      )}

      <div className="inspection-metrics-notice monospace text-xs">
        <span>* Operational risk probability and raw decision score are distinct serving fields; raw probabilities are never presented as calibrated.</span>
      </div>
    </div>
  );
};
