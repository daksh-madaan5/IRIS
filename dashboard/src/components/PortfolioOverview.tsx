import { BarChart3, Database, Gauge, SlidersHorizontal } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { probability } from "../format";
import type { SummaryResponse } from "../types";

interface PortfolioOverviewProps {
  summary: SummaryResponse;
}

const quantileLabels: Array<[keyof SummaryResponse["score_distribution"], string]> = [
  ["minimum", "Min"],
  ["p25", "25th"],
  ["median", "Median"],
  ["p75", "75th"],
  ["p90", "90th"],
  ["p95", "95th"],
  ["maximum", "Max"],
];

export function PortfolioOverview({ summary }: PortfolioOverviewProps) {
  const regime = summary.regimes.map((item) => item.regime).join(" + ");
  const calibration = summary.regimes.some((item) => item.calibration_active);
  const topSectors = summary.sector_summary.slice(0, 8).map((item) => ({
    name: item.sector ?? "Not reported",
    average: Number((item.mean_risk_probability * 100).toFixed(1)),
    projects: item.project_count,
  }));
  return (
    <section aria-labelledby="portfolio-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Portfolio overview</p>
          <h2 id="portfolio-heading">Monthly risk posture</h2>
        </div>
        <p className="scope-note">Probabilities are model estimates, not certainty.</p>
      </div>
      <div className="metric-strip">
        <article className="metric">
          <Database size={18} aria-hidden="true" />
          <div><span>Total projects</span><strong>{summary.project_count.toLocaleString("en-IN")}</strong></div>
        </article>
        <article className="metric">
          <Gauge size={18} aria-hidden="true" />
          <div><span>Mean probability</span><strong>{probability(summary.score_distribution.mean)}</strong></div>
        </article>
        <article className="metric">
          <BarChart3 size={18} aria-hidden="true" />
          <div><span>Median probability</span><strong>{probability(summary.score_distribution.median)}</strong></div>
        </article>
        <article className="metric">
          <SlidersHorizontal size={18} aria-hidden="true" />
          <div><span>Regime · calibration</span><strong>{regime} · {calibration ? "Active" : "Inactive"}</strong></div>
        </article>
      </div>
      <div className="overview-grid">
        <article className="panel distribution-panel">
          <div className="panel-heading">
            <div><p className="eyebrow">Risk score distribution</p><h3>Portfolio quantiles</h3></div>
            <span>Operational probability</span>
          </div>
          <div className="quantile-track" aria-label="Risk probability quantiles">
            <div className="track-line" />
            {quantileLabels.map(([key, label]) => {
              const value = summary.score_distribution[key];
              return (
                <div
                  className={`quantile-marker ${key === "median" ? "median" : ""}`}
                  key={key}
                  style={{ left: `${Math.max(1.5, Math.min(98.5, value * 100))}%` }}
                >
                  <span>{label}</span>
                  <strong>{probability(value)}</strong>
                </div>
              );
            })}
          </div>
          <p className="chart-footnote">Relative spread for the current filtered portfolio; no alert threshold is applied.</p>
        </article>
        <article className="panel sector-panel">
          <div className="panel-heading">
            <div><p className="eyebrow">Sector summary</p><h3>Average probability</h3></div>
            <span>Top 8 sectors</span>
          </div>
          <div className="sector-chart" aria-label="Sector average risk probability chart">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={topSectors} layout="vertical" margin={{ top: 4, right: 8, bottom: 0, left: 4 }}>
                <CartesianGrid stroke="#dfe6e8" horizontal={false} />
                <XAxis type="number" domain={[0, 100]} hide />
                <YAxis type="category" dataKey="name" width={116} tick={{ fontSize: 11, fill: "#52656f" }} tickLine={false} axisLine={false} />
                <Tooltip formatter={(value) => [`${value}%`, "Average probability"]} />
                <Bar dataKey="average" fill="#2b6d74" radius={[0, 3, 3, 0]} barSize={12} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </article>
      </div>
    </section>
  );
}
