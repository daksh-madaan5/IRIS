import React from "react";
import type { ProjectIntelligenceRisk } from "@/types/project.ts";
import { IntelligenceRiskProbabilityScale } from "./IntelligenceRiskProbabilityScale.tsx";
import { IntelligencePortfolioPosition } from "./IntelligencePortfolioPosition.tsx";

interface IntelligenceRiskAssessmentProps {
  risk: ProjectIntelligenceRisk | null;
}

export const IntelligenceRiskAssessment: React.FC<IntelligenceRiskAssessmentProps> = ({ risk }) => {
  if (!risk) {
    return (
      <div className="terminal-card">
        <div className="terminal-card-header">
          <div className="terminal-card-title-lockup">
            <span className="terminal-section-eyebrow">PRODUCTION ASSESSMENT</span>
            <h3 className="terminal-card-title">CURRENT RISK ASSESSMENT</h3>
          </div>
          <span className="terminal-badge unassessed">NOT ASSESSED</span>
        </div>

        <p className="terminal-unassessed-desc">
          This project is recorded in canonical PAIMANA infrastructure monitoring records, but no
          operational risk assessment is currently served in the production model serving layer.
        </p>

        <div className="terminal-unserved-domains-strip">
          <div className="terminal-unserved-pill">
            <span className="unserved-name">Cost Overrun Risk</span>
            <span className="unserved-status">DATA PENDING</span>
          </div>
          <div className="terminal-unserved-pill">
            <span className="unserved-name">Progress Stagnation Risk</span>
            <span className="unserved-status">DATA PENDING</span>
          </div>
        </div>
      </div>
    );
  }

  const probabilityPercent = (risk.risk_probability * 100).toFixed(1);
  const rawProbabilityPercent = (risk.raw_probability * 100).toFixed(1);
  const percentilePercent = (risk.risk_percentile * 100).toFixed(1);

  return (
    <div className="terminal-card">
      <div className="terminal-card-header">
        <div className="terminal-card-title-lockup">
          <span className="terminal-section-eyebrow">PRODUCTION RISK ASSESSMENT</span>
          <h3 className="terminal-card-title">CURRENT RISK ASSESSMENT</h3>
        </div>
        <div className="terminal-badge-group">
          <span className="terminal-badge regime">{risk.regime} REGIME</span>
          <span className={`terminal-badge ${risk.calibration_active ? "calibrated" : "raw"}`}>
            {risk.calibration_active ? "CALIBRATION ACTIVE" : "RAW PROBABILITY"}
          </span>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="terminal-metrics-grid">
        {/* Risk Probability */}
        <div className="terminal-metric-cell primary-stat">
          <span className="metric-cell-label">
            {risk.calibration_active ? "CALIBRATED PROBABILITY" : "RAW MODEL PROBABILITY"}
          </span>
          <div className="metric-cell-val probability monospace">{probabilityPercent}%</div>
          {risk.calibration_active && (
            <span className="metric-cell-sub monospace">RAW: {rawProbabilityPercent}%</span>
          )}
        </div>

        {/* Portfolio Rank */}
        <div className="terminal-metric-cell">
          <span className="metric-cell-label">PORTFOLIO RISK RANK</span>
          <div className="metric-cell-val monospace">#{risk.risk_rank}</div>
          <span className="metric-cell-sub">OF {risk.population_size.toLocaleString()} MONITORED</span>
        </div>

        {/* Percentile (Displayed strictly as reported without derived TOP X%) */}
        <div className="terminal-metric-cell">
          <span className="metric-cell-label">RISK PERCENTILE</span>
          <div className="metric-cell-val monospace">{percentilePercent}%</div>
          <span className="metric-cell-sub monospace">P{percentilePercent}</span>
        </div>

        {/* Assessment Month */}
        <div className="terminal-metric-cell">
          <span className="metric-cell-label">ASSESSMENT MONTH</span>
          <div className="metric-cell-val monospace date">{risk.report_month}</div>
          <span className="metric-cell-sub monospace">TARGET: {risk.target}</span>
        </div>
      </div>

      {/* Visual Analytical Scales: Probability Scale & Portfolio Position */}
      <div className="terminal-assessment-visual-block">
        <IntelligenceRiskProbabilityScale
          probability={risk.risk_probability}
          rawProbability={risk.calibration_active ? risk.raw_probability : null}
          calibrationActive={risk.calibration_active}
          ariaLabel="Current schedule extension risk"
        />

        <IntelligencePortfolioPosition
          rank={risk.risk_rank}
          populationSize={risk.population_size}
          percentile={risk.risk_percentile}
        />
      </div>

      <div className="terminal-card-footer-meta">
        <span className="footer-meta-item monospace">MODEL ID: {risk.model_id}</span>
        <span className="footer-meta-item monospace">TARGET: {risk.target}</span>
      </div>
    </div>
  );
};
