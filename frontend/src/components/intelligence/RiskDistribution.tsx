import React from "react";
import type { ScoreDistribution } from "@/types/risk.ts";
import { IrisQuantileDistributionChart } from "@/components/common/charts/IrisQuantileDistributionChart.tsx";

interface RiskDistributionProps {
  distribution?: ScoreDistribution;
  reportMonth: string;
}

export const RiskDistribution: React.FC<RiskDistributionProps> = ({
  distribution,
  reportMonth,
}) => {
  const min = distribution?.minimum ?? 0;
  const p25 = distribution?.p25 ?? 0;
  const median = distribution?.median ?? 0;
  const mean = distribution?.mean ?? 0;
  const p75 = distribution?.p75 ?? 0;
  const p90 = distribution?.p90 ?? 0;
  const p95 = distribution?.p95 ?? 0;
  const max = distribution?.maximum ?? 1;

  return (
    <section className="intelligence-section">
      <div className="intelligence-section-header">
        <div className="intelligence-section-title-lockup">
          <h2 className="intelligence-section-title">03. Model Output Distribution</h2>
          <span className="intelligence-section-subtitle">
            EMPIRICAL QUANTILE SUMMARY ({reportMonth})
          </span>
        </div>
        <span className="intelligence-section-subtitle">
          CALIBRATED PROBABILITY QUANTILE BREAKDOWN
        </span>
      </div>

      <div className="intelligence-dist-card">
        {/* 8 Quantile Metric Stat Cells */}
        <div className="intelligence-dist-stats-grid">
          <div className="intelligence-dist-stat-cell">
            <span className="intelligence-dist-stat-label">MINIMUM</span>
            <span className="intelligence-dist-stat-val">{(min * 100).toFixed(2)}%</span>
          </div>

          <div className="intelligence-dist-stat-cell">
            <span className="intelligence-dist-stat-label">P25 (25TH)</span>
            <span className="intelligence-dist-stat-val">{(p25 * 100).toFixed(1)}%</span>
          </div>

          <div className="intelligence-dist-stat-cell">
            <span className="intelligence-dist-stat-label">MEDIAN (P50)</span>
            <span className="intelligence-dist-stat-val" style={{ color: "#1A3C2B" }}>
              {(median * 100).toFixed(1)}%
            </span>
          </div>

          <div className="intelligence-dist-stat-cell">
            <span className="intelligence-dist-stat-label">MEAN</span>
            <span className="intelligence-dist-stat-val">{(mean * 100).toFixed(1)}%</span>
          </div>

          <div className="intelligence-dist-stat-cell">
            <span className="intelligence-dist-stat-label">P75 (75TH)</span>
            <span className="intelligence-dist-stat-val">{(p75 * 100).toFixed(1)}%</span>
          </div>

          <div className="intelligence-dist-stat-cell">
            <span className="intelligence-dist-stat-label">P90 (90TH)</span>
            <span className="intelligence-dist-stat-val" style={{ color: "#BA1A1A" }}>
              {(p90 * 100).toFixed(1)}%
            </span>
          </div>

          <div className="intelligence-dist-stat-cell">
            <span className="intelligence-dist-stat-label">P95 (95TH)</span>
            <span className="intelligence-dist-stat-val" style={{ color: "#BA1A1A" }}>
              {(p95 * 100).toFixed(1)}%
            </span>
          </div>

          <div className="intelligence-dist-stat-cell">
            <span className="intelligence-dist-stat-label">MAXIMUM</span>
            <span className="intelligence-dist-stat-val" style={{ color: "#BA1A1A" }}>
              {(max * 100).toFixed(1)}%
            </span>
          </div>
        </div>

        {/* Advanced Recharts Quantile Distribution Chart */}
        <div style={{ padding: "16px 20px", background: "#FFFFFF", borderTop: "1px solid var(--color-border-hairline)" }}>
          <IrisQuantileDistributionChart
            distribution={distribution}
            height={200}
            reportMonth={reportMonth}
          />
        </div>
      </div>
    </section>
  );
};
