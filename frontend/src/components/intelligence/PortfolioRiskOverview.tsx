import React from "react";
import type { SummaryResponse } from "@/types/risk.ts";
import { IrisQuantileDistributionChart } from "@/components/common/charts/IrisQuantileDistributionChart.tsx";

interface PortfolioRiskOverviewProps {
  summary?: SummaryResponse;
}

export const PortfolioRiskOverview: React.FC<PortfolioRiskOverviewProps> = ({ summary }) => {
  const dist = summary?.score_distribution;
  const min = dist?.minimum ?? 0;
  const p25 = dist?.p25 ?? 0;
  const median = dist?.median ?? 0;
  const mean = dist?.mean ?? 0;
  const p75 = dist?.p75 ?? 0;
  const p95 = dist?.p95 ?? 0;
  const max = dist?.maximum ?? 1;

  const evaluatedCount = summary?.project_count != null
    ? summary.project_count.toLocaleString()
    : "—";

  const meanFormatted = dist?.mean != null
    ? `${(dist.mean * 100).toFixed(1)}%`
    : "—";

  const medianFormatted = dist?.median != null
    ? `${(dist.median * 100).toFixed(1)}%`
    : "—";

  const p95Formatted = dist?.p95 != null
    ? `${(dist.p95 * 100).toFixed(1)}%`
    : "—";

  const maxFormatted = dist?.maximum != null
    ? `${(dist.maximum * 100).toFixed(1)}%`
    : "—";

  return (
    <section className="intelligence-section">
      <div className="intelligence-section-header">
        <div className="intelligence-section-title-lockup">
          <h2 className="intelligence-section-title">01. Portfolio Risk Overview</h2>
          <span className="intelligence-section-subtitle">
            EARLY WARNING RISK PROFILE & EVALUATED POPULATION
          </span>
        </div>
        <span className="intelligence-section-subtitle">
          TARGET: target_effective_schedule_ext_3m
        </span>
      </div>

      <div className="intelligence-risk-overview-container">
        {/* Main Recharts Empirical Quantile Distribution Chart Card */}
        <div className="intelligence-risk-band-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span className="intelligence-section-subtitle" style={{ color: "var(--color-primary-950)", fontWeight: 700 }}>
              HORIZONTAL PROBABILITY DISTRIBUTION & QUANTILE BAND
            </span>
            <span className="intelligence-section-subtitle">
              SCALE: 0.0 (0%) TO 1.0 (100%)
            </span>
          </div>

          <div style={{ width: "100%", marginTop: "8px" }}>
            <IrisQuantileDistributionChart
              distribution={dist}
              height={180}
              reportMonth={summary?.report_month}
            />
          </div>
        </div>

        {/* Risk KPI Metric Cells Strip */}
        <div className="intelligence-risk-kpi-grid">
          <div className="intelligence-risk-kpi-cell">
            <span className="intelligence-risk-kpi-label">EVALUATED</span>
            <span className="intelligence-risk-kpi-val">{evaluatedCount}</span>
            <span className="intelligence-risk-kpi-sub">MONITORED PROJECTS</span>
          </div>

          <div className="intelligence-risk-kpi-cell">
            <span className="intelligence-risk-kpi-label">MEAN RISK</span>
            <span className="intelligence-risk-kpi-val">{meanFormatted}</span>
            <span className="intelligence-risk-kpi-sub">PORTFOLIO AVERAGE</span>
          </div>

          <div className="intelligence-risk-kpi-cell">
            <span className="intelligence-risk-kpi-label">MEDIAN RISK</span>
            <span className="intelligence-risk-kpi-val" style={{ color: "#1A3C2B" }}>
              {medianFormatted}
            </span>
            <span className="intelligence-risk-kpi-sub">50TH PERCENTILE</span>
          </div>

          <div className="intelligence-risk-kpi-cell">
            <span className="intelligence-risk-kpi-label">95TH PERCENTILE</span>
            <span className="intelligence-risk-kpi-val" style={{ color: "#BA1A1A" }}>
              {p95Formatted}
            </span>
            <span className="intelligence-risk-kpi-sub">TAIL RISK THRESHOLD</span>
          </div>

          <div className="intelligence-risk-kpi-cell">
            <span className="intelligence-risk-kpi-label">MAXIMUM RISK</span>
            <span className="intelligence-risk-kpi-val" style={{ color: "#BA1A1A" }}>
              {maxFormatted}
            </span>
            <span className="intelligence-risk-kpi-sub">HIGHEST EVALUATED</span>
          </div>
        </div>
      </div>
    </section>
  );
};
