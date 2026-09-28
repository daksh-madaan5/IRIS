import React from "react";
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
  ReferenceLine,
} from "recharts";
import type { ProjectRiskHistoryPoint } from "@/types/project.ts";
import { IrisChartTooltip } from "@/components/common/charts/IrisChartTooltip.tsx";
import { Eye } from "lucide-react";
import {
  detectObservationTransitions,
  evaluateObservationMovement,
  formatSignedDelta,
} from "@/utils/historicalComparability.ts";

interface IntelligenceRiskHistoryProps {
  history: ProjectRiskHistoryPoint[];
  selectedMonth?: string | null;
  onSelectMonth?: (month: string) => void;
}

export const IntelligenceRiskHistory: React.FC<IntelligenceRiskHistoryProps> = ({
  history,
  selectedMonth,
  onSelectMonth,
}) => {
  if (!history || history.length === 0) {
    return (
      <div className="terminal-card">
        <div className="terminal-card-header">
          <div className="terminal-card-title-lockup">
            <span className="terminal-section-eyebrow">LONGITUDINAL EVALUATION HISTORY</span>
            <h3 className="terminal-card-title">HISTORICAL RISK TRAJECTORY</h3>
          </div>
        </div>
        <div className="terminal-empty-text monospace">
          NO HISTORICAL EVALUATIONS RECORDED FOR THIS PROJECT
        </div>
      </div>
    );
  }

  // Sort chronologically ascending
  const sortedHistory = [...history].sort((a, b) =>
    a.report_month.localeCompare(b.report_month)
  );

  // Check for model / regime / calibration transition dynamically across history
  const regimesPresent = Array.from(new Set(sortedHistory.map((h) => h.regime)));
  const modelsPresent = Array.from(new Set(sortedHistory.map((h) => h.model_id)));
  const calibrationsPresent = Array.from(
    new Set(sortedHistory.map((h) => (h.calibration_active ? "CALIBRATED" : "RAW")))
  );
  const hasRegimeTransition = regimesPresent.length > 1;
  const hasModelTransition = modelsPresent.length > 1;
  const hasCalibrationTransition = calibrationsPresent.length > 1;

  // Find exact boundary months where regime, model, or calibration changed
  const transitions: Array<{
    month: string;
    fromRegime: string;
    toRegime: string;
    fromModel: string;
    toModel: string;
    fromCalib: string;
    toCalib: string;
    isModelOrRegime: boolean;
    isCalibration: boolean;
    typeLabel: string;
    referenceLineLabel: string;
  }> = [];

  for (let i = 1; i < sortedHistory.length; i++) {
    const prev = sortedHistory[i - 1];
    const curr = sortedHistory[i];
    const detected = detectObservationTransitions(prev, curr);
    if (detected.length > 0) {
      const isRegime = prev.regime !== curr.regime;
      const isModel = prev.model_id !== curr.model_id;
      const isCalib = prev.calibration_active !== curr.calibration_active;
      const types: string[] = [];
      if (isRegime) types.push("REGIME");
      if (isModel) types.push("MODEL");
      if (isCalib) types.push("CALIBRATION");

      let labelText = `TRANSITION: ${prev.regime} → ${curr.regime}`;
      if (!isRegime && isModel) {
        labelText = `MODEL TRANSITION: ${prev.model_id} → ${curr.model_id}`;
      } else if (!isRegime && !isModel && isCalib) {
        labelText = `CALIBRATION TRANSITION: ${prev.calibration_active ? "CALIBRATED" : "RAW"} → ${curr.calibration_active ? "CALIBRATED" : "RAW"}`;
      }

      transitions.push({
        month: curr.report_month,
        fromRegime: prev.regime,
        toRegime: curr.regime,
        fromModel: prev.model_id,
        toModel: curr.model_id,
        fromCalib: prev.calibration_active ? "CALIBRATED" : "RAW",
        toCalib: curr.calibration_active ? "CALIBRATED" : "RAW",
        isModelOrRegime: isRegime || isModel,
        isCalibration: isCalib,
        typeLabel: types.join(" / "),
        referenceLineLabel: labelText,
      });
    }
  }

  const isSingleObservation = sortedHistory.length === 1;

  const chartData = sortedHistory.map((h) => ({
    month: h.report_month,
    calibratedRisk: Number((h.risk_probability * 100).toFixed(1)),
    rawProbability: Number((h.raw_probability * 100).toFixed(1)),
    rank: h.risk_rank,
    percentile: Number((h.risk_percentile * 100).toFixed(1)),
    regime: h.regime,
    modelId: h.model_id,
    calibrationActive: h.calibration_active,
    isSelected: h.report_month === selectedMonth,
  }));

  /**
   * Strictly resolves actual evaluation month from an underlying historical record.
   * Never derives, interpolates, or approximates a month from raw coordinates.
   */
  const handleChartClick = (e: unknown) => {
    if (!onSelectMonth) return;
    const eventAny = e as {
      activePayload?: Array<{ payload?: { month?: string } }>;
      month?: string;
    };
    const candidateMonth =
      eventAny?.activePayload?.[0]?.payload?.month || eventAny?.month;
    if (!candidateMonth) return;

    // Strict validation: must match an actual historical record
    const matchingRecord = sortedHistory.find(
      (h) => h.report_month === candidateMonth
    );
    if (matchingRecord) {
      onSelectMonth(matchingRecord.report_month);
    }
  };

  return (
    <div className="terminal-card">
      <div className="terminal-card-header">
        <div className="terminal-card-title-lockup">
          <span className="terminal-section-eyebrow">LONGITUDINAL EVALUATION HISTORY</span>
          <h3 className="terminal-card-title">HISTORICAL RISK TRAJECTORY</h3>
        </div>
        <div className="terminal-history-stats">
          <span className="terminal-history-count monospace">
            {sortedHistory.length} EVALUATED {sortedHistory.length === 1 ? "MONTH" : "MONTHS"}
          </span>
        </div>
      </div>

      {/* Model / Regime / Calibration Transition Notice (Rendered dynamically only when transition exists) */}
      {(hasRegimeTransition || hasModelTransition || hasCalibrationTransition) && (
        <div className="terminal-transition-banner" role="note">
          <span className="transition-tag">
            {hasRegimeTransition
              ? "REGIME TRANSITION DETECTED"
              : hasModelTransition
              ? "MODEL TRANSITION DETECTED"
              : "CALIBRATION TRANSITION DETECTED"}
          </span>
          <span className="transition-desc">
            Historical evaluations span multiple regimes ({regimesPresent.join(" → ")}), model
            architectures ({modelsPresent.join(" → ")}), or calibration states (
            {calibrationsPresent.join(" → ")}). Historical points reflect their original
            serving models and are not recomputed with subsequent model weights.
          </span>
        </div>
      )}

      {/* State A: Single Observation (Do not render a misleading trend line) */}
      {isSingleObservation ? (
        <div className="terminal-single-history-card">
          <div className="terminal-single-history-header">
            <span className="single-history-badge monospace">DISCRETE SINGLE EVALUATION</span>
            <span className="single-history-month monospace">{sortedHistory[0].report_month}</span>
          </div>

          <div className="terminal-single-history-grid">
            <div className="single-history-metric">
              <span className="single-metric-label">OPERATIONAL RISK</span>
              <span className="single-metric-val monospace font-bold">
                {(sortedHistory[0].risk_probability * 100).toFixed(1)}%
              </span>
            </div>

            <div className="single-history-metric">
              <span className="single-metric-label">RAW PROBABILITY</span>
              <span className="single-metric-val monospace muted">
                {(sortedHistory[0].raw_probability * 100).toFixed(1)}%
              </span>
            </div>

            <div className="single-history-metric">
              <span className="single-metric-label">PORTFOLIO RANK</span>
              <span className="single-metric-val monospace">#{sortedHistory[0].risk_rank}</span>
            </div>

            <div className="single-history-metric">
              <span className="single-metric-label">PERCENTILE</span>
              <span className="single-metric-val monospace">
                P{(sortedHistory[0].risk_percentile * 100).toFixed(1)}
              </span>
            </div>

            <div className="single-history-metric">
              <span className="single-metric-label">MODEL & REGIME</span>
              <span className="single-metric-val monospace">
                {sortedHistory[0].regime} ({sortedHistory[0].model_id})
              </span>
            </div>

            <div className="single-history-metric">
              <span className="single-metric-label">CALIBRATION</span>
              <span className="single-metric-val monospace">
                {sortedHistory[0].calibration_active ? "ACTIVE" : "RAW / UNCALIBRATED"}
              </span>
            </div>
          </div>

          <div className="single-history-actions">
            <button
              type="button"
              className={`terminal-inspect-btn single-inspect ${
                sortedHistory[0].report_month === selectedMonth ? "active" : ""
              }`}
              onClick={() => onSelectMonth?.(sortedHistory[0].report_month)}
              aria-label={`Inspect historical evaluation for ${sortedHistory[0].report_month}`}
            >
              <Eye size={13} aria-hidden="true" />
              <span>
                {sortedHistory[0].report_month === selectedMonth
                  ? "INSPECTING EVALUATION"
                  : "INSPECT EVALUATION RECORD"}
              </span>
            </button>
          </div>

          <p className="terminal-single-history-note monospace">
            Only a single historical evaluation is recorded for this project. Longitudinal trajectory charts require multiple observation periods to establish a trend without manufacturing synthetic points.
          </p>
        </div>
      ) : (
        /* State B: Multi-Observation Longitudinal Line Chart */
        <div className="terminal-history-chart-wrapper">
          <div className="terminal-chart-guidance monospace">
            <span>TIP: Click any evaluation point or table row to inspect that month in detail.</span>
          </div>

          <div style={{ width: "100%", height: 230 }}>
            <ResponsiveContainer width="100%" height="100%" minWidth={0}>
              <ComposedChart
                data={chartData}
                margin={{ top: 16, right: 16, left: -20, bottom: 4 }}
                syncId="iris-terminal-history"
                onClick={handleChartClick}
              >
                <CartesianGrid stroke="#E2E3DF" strokeDasharray="3 3" vertical={false} />
                <XAxis
                  dataKey="month"
                  tick={{ fill: "#606460", fontSize: 10, fontFamily: "var(--font-mono)" }}
                  stroke="#E2E3DF"
                />
                <YAxis
                  domain={[0, 100]}
                  tick={{ fill: "#606460", fontSize: 10, fontFamily: "var(--font-mono)" }}
                  stroke="#E2E3DF"
                  tickFormatter={(v) => `${v}%`}
                />
                <Tooltip
                  content={
                    <IrisChartTooltip
                      titlePrefix="ASSESSMENT MONTH"
                      customFormatter={(payload) => {
                        const entry = Array.isArray(payload) ? payload[0]?.payload : undefined;
                        if (!entry) return [];
                        return [
                          {
                            label: "CALIBRATED RISK",
                            value: `${entry.calibratedRisk}%`,
                            color: "#1A3C2B",
                            subtext: entry.calibrationActive
                              ? "Operational calibrated risk"
                              : "Uncalibrated raw probability",
                          },
                          {
                            label: "RAW PROBABILITY",
                            value: `${entry.rawProbability}%`,
                            color: "#8A8E8A",
                          },
                          {
                            label: "PORTFOLIO RANK",
                            value: `#${entry.rank}`,
                            color: "#FFFFFF",
                          },
                          {
                            label: "PERCENTILE",
                            value: `P${entry.percentile}`,
                            color: "#FFFFFF",
                          },
                          {
                            label: "REGIME",
                            value: entry.regime,
                            color: "#E2E3DF",
                          },
                          {
                            label: "MODEL ID",
                            value: entry.modelId,
                            color: "#E2E3DF",
                          },
                          {
                            label: "CALIBRATION",
                            value: entry.calibrationActive ? "ACTIVE" : "RAW (INACTIVE)",
                            color: entry.calibrationActive ? "#92C2B0" : "#E2E3DF",
                          },
                        ];
                      }}
                    />
                  }
                />
                <Legend
                  verticalAlign="top"
                  align="right"
                  wrapperStyle={{
                    fontFamily: "var(--font-mono)",
                    fontSize: "9px",
                    letterSpacing: "0.06em",
                    textTransform: "uppercase",
                    paddingBottom: "8px",
                  }}
                />

                {/* Dynamic Transition Reference Lines */}
                {transitions.map((t) => (
                  <ReferenceLine
                    key={`trans-${t.month}`}
                    x={t.month}
                    stroke="#B45309"
                    strokeWidth={1.5}
                    strokeDasharray="4 4"
                    label={{
                      value: t.referenceLineLabel,
                      position: "insideTopRight",
                      fill: "#78350F",
                      fontSize: 9,
                      fontFamily: "var(--font-mono)",
                      fontWeight: 700,
                    }}
                  />
                ))}

                {/* Calibrated Risk Line with Click Support */}
                <Line
                  type="linear"
                  dataKey="calibratedRisk"
                  name="Calibrated Risk"
                  stroke="#1A3C2B"
                  strokeWidth={2}
                  dot={(props: { cx?: number; cy?: number; payload?: { month?: string } }) => {
                    const isSelected = props.payload?.month === selectedMonth;
                    return (
                      <circle
                        key={`dot-calib-${props.payload?.month}`}
                        cx={props.cx}
                        cy={props.cy}
                        r={isSelected ? 6 : 4}
                        fill={isSelected ? "#15803D" : "#1A3C2B"}
                        stroke="#FFFFFF"
                        strokeWidth={isSelected ? 2.5 : 1.5}
                        style={{ cursor: "pointer" }}
                        onClick={(e) => {
                          e.stopPropagation();
                          if (props.payload?.month) {
                            const exact = sortedHistory.find(
                              (h) => h.report_month === props.payload?.month
                            );
                            if (exact) onSelectMonth?.(exact.report_month);
                          }
                        }}
                      />
                    );
                  }}
                  activeDot={{ r: 6, fill: "#1A3C2B", stroke: "#FFFFFF", strokeWidth: 2 }}
                  isAnimationActive={false}
                />

                {/* Raw Probability Line with Click Support */}
                <Line
                  type="linear"
                  dataKey="rawProbability"
                  name="Raw Probability"
                  stroke="#8A8E8A"
                  strokeWidth={1.5}
                  strokeDasharray="4 2"
                  dot={(props: { cx?: number; cy?: number; payload?: { month?: string } }) => {
                    const isSelected = props.payload?.month === selectedMonth;
                    return (
                      <circle
                        key={`dot-raw-${props.payload?.month}`}
                        cx={props.cx}
                        cy={props.cy}
                        r={isSelected ? 5 : 3}
                        fill={isSelected ? "#15803D" : "#8A8E8A"}
                        stroke="#FFFFFF"
                        strokeWidth={isSelected ? 2 : 1}
                        style={{ cursor: "pointer" }}
                        onClick={(e) => {
                          e.stopPropagation();
                          if (props.payload?.month) {
                            const exact = sortedHistory.find(
                              (h) => h.report_month === props.payload?.month
                            );
                            if (exact) onSelectMonth?.(exact.report_month);
                          }
                        }}
                      />
                    );
                  }}
                  activeDot={{ r: 5, fill: "#1A3C2B", stroke: "#FFFFFF", strokeWidth: 1.5 }}
                  isAnimationActive={false}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Chronological Table as Accessible Alternative with Valid Table Structure */}
      <div className="terminal-history-table-wrap">
        <table className="terminal-history-table" aria-label="Chronological risk history">
          <thead>
            <tr>
              <th scope="col">MONTH</th>
              <th scope="col">CALIBRATED RISK</th>
              <th scope="col">RAW PROB</th>
              <th scope="col">MOVEMENT / COMPARABILITY</th>
              <th scope="col">RANK</th>
              <th scope="col">PERCENTILE</th>
              <th scope="col">REGIME</th>
              <th scope="col">MODEL ID</th>
              <th scope="col">CALIBRATION</th>
              <th scope="col">INSPECTION</th>
            </tr>
          </thead>
          <tbody>
            {sortedHistory.map((item, idx) => {
              const isSelected = item.report_month === selectedMonth;
              const prevItem = idx > 0 ? sortedHistory[idx - 1] : null;
              const mov = prevItem ? evaluateObservationMovement(prevItem, item, true) : null;
              return (
                <tr
                  key={item.report_month}
                  className={`terminal-history-row ${isSelected ? "selected" : ""}`}
                  aria-selected={isSelected}
                  onClick={() => onSelectMonth?.(item.report_month)}
                >
                  <td className="monospace font-bold">{item.report_month}</td>
                  <td className="monospace font-bold">
                    {(item.risk_probability * 100).toFixed(1)}%
                  </td>
                  <td className="monospace muted">
                    {(item.raw_probability * 100).toFixed(1)}%
                  </td>
                  <td className="monospace text-xs">
                    {!prevItem ? (
                      <span className="terminal-movement-badge baseline">BASELINE</span>
                    ) : mov?.status === "COMPARABLE" ? (
                      <span
                        className="terminal-movement-badge comparable"
                        title={`Comparable movement vs ${prevItem.report_month}`}
                      >
                        {formatSignedDelta(mov.probabilityDelta, "pp")}
                      </span>
                    ) : (
                      <span
                        className="terminal-movement-badge limited"
                        title={`Comparability limited across ${mov?.transitions.map((t) => t.type).join("/")} boundary`}
                      >
                        LIMITED ({mov?.transitions.map((t) => t.type).join("/")})
                      </span>
                    )}
                  </td>
                  <td className="monospace">#{item.risk_rank}</td>
                  <td className="monospace">P{(item.risk_percentile * 100).toFixed(1)}</td>
                  <td>
                    <span className={`terminal-mini-badge ${item.regime.toLowerCase()}`}>
                      {item.regime}
                    </span>
                  </td>
                  <td className="monospace muted" title={item.model_id}>
                    {item.model_id}
                  </td>
                  <td>
                    <span
                      className={`terminal-mini-status ${
                        item.calibration_active ? "active" : "inactive"
                      }`}
                    >
                      {item.calibration_active ? "ACTIVE" : "RAW"}
                    </span>
                  </td>
                  <td className="terminal-table-action-cell">
                    <button
                      type="button"
                      className={`terminal-inspect-btn ${isSelected ? "active" : ""}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectMonth?.(item.report_month);
                      }}
                      aria-label={`Inspect historical risk evaluation for ${item.report_month}`}
                    >
                      <Eye size={11} aria-hidden="true" />
                      <span>{isSelected ? "INSPECTED" : "INSPECT"}</span>
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
