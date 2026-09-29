import React from "react";
import {
  ResponsiveContainer,
  ComposedChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceArea,
  ReferenceLine,
  Cell,
} from "recharts";
import type { ScoreDistribution } from "@/types/risk.ts";
import { IrisChartTooltip } from "./IrisChartTooltip.tsx";

interface IrisQuantileDistributionChartProps {
  distribution?: ScoreDistribution;
  height?: number | string;
  reportMonth?: string;
}

export const IrisQuantileDistributionChart: React.FC<IrisQuantileDistributionChartProps> = ({
  distribution,
  height = 180,
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

  const minVal = Number((min * 100).toFixed(2));
  const p25Val = Number((p25 * 100).toFixed(1));
  const medianVal = Number((median * 100).toFixed(1));
  const meanVal = Number((mean * 100).toFixed(1));
  const p75Val = Number((p75 * 100).toFixed(1));
  const p90Val = Number((p90 * 100).toFixed(1));
  const p95Val = Number((p95 * 100).toFixed(1));
  const maxVal = Number((max * 100).toFixed(1));

  // 8 Distinct Empirical Quantile Points strictly from API along the horizontal probability axis
  const empiricalMarkers = [
    { x: minVal, y: 1, stat: "MIN", label: "Minimum Observed", percentile: "0%", isTail: false, isMedian: false },
    { x: p25Val, y: 1, stat: "P25", label: "25th Percentile (Q1)", percentile: "25%", isTail: false, isMedian: false },
    { x: medianVal, y: 1, stat: "MEDIAN", label: "Median Risk (P50)", percentile: "50%", isTail: false, isMedian: true },
    { x: meanVal, y: 1, stat: "MEAN", label: "Portfolio Average Risk", percentile: "MEAN", isTail: false, isMedian: false },
    { x: p75Val, y: 1, stat: "P75", label: "75th Percentile (Q3)", percentile: "75%", isTail: false, isMedian: false },
    { x: p90Val, y: 1, stat: "P90", label: "90th Percentile", percentile: "90%", isTail: true, isMedian: false },
    { x: p95Val, y: 1, stat: "P95", label: "95th Percentile (Tail Risk)", percentile: "95%", isTail: true, isMedian: false },
    { x: maxVal, y: 1, stat: "MAX", label: "Maximum Observed", percentile: "100%", isTail: true, isMedian: false },
  ];

  return (
    <div
      style={{
        width: "100%",
        display: "flex",
        flexDirection: "column",
        gap: "10px",
        position: "relative",
      }}
      aria-label="Empirical Risk Quantile Distribution Chart"
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px", fontFamily: "var(--font-mono)", fontSize: "10px", color: "var(--color-text-muted)" }}>
        <span>EMPIRICAL QUANTILE SUMMARY (PROBABILITY SCALE 0% → 100%)</span>
        <span>IQR: [{p25Val}% — {p75Val}%] | MEDIAN: {medianVal}% | MEAN: {meanVal}% | P95 TAIL: {p95Val}%</span>
      </div>

      <div style={{ width: "100%", height: typeof height === "number" ? Math.max(height - 40, 140) : height, minHeight: "140px" }}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart
            margin={{ top: 22, right: 32, left: 32, bottom: 8 }}
          >
            <CartesianGrid stroke="#E2E3DF" strokeDasharray="3 3" vertical={true} horizontal={false} />

            <XAxis
              type="number"
              dataKey="x"
              domain={[0, 100]}
              stroke="#606460"
              tick={{ fill: "#606460", fontSize: 10, fontFamily: "var(--font-mono)", fontWeight: 600 }}
              tickLine={{ stroke: "#D1D4D1" }}
              axisLine={{ stroke: "#D1D4D1" }}
              tickFormatter={(val: number) => `${val}%`}
              ticks={[0, 20, 40, 60, 80, 100]}
            />
            <YAxis
              type="number"
              domain={[0, 2]}
              hide
            />

            {/* Interquartile Range (IQR = P25 to P75) Reference Area on horizontal probability scale */}
            <ReferenceArea
              x1={p25Val}
              x2={p75Val}
              fill="#C5ECD3"
              fillOpacity={0.5}
              stroke="#1A3C2B"
              strokeWidth={1}
              strokeDasharray="3 3"
            />

            {/* Median Vertical Reference Line */}
            {median > 0 && (
              <ReferenceLine
                x={medianVal}
                stroke="#1A3C2B"
                strokeWidth={2}
                label={{
                  value: `MEDIAN ${medianVal}%`,
                  position: "top",
                  fill: "#1A3C2B",
                  fontSize: 10,
                  fontFamily: "var(--font-mono)",
                  fontWeight: 700,
                }}
              />
            )}

            {/* Mean Vertical Reference Line (visual marker without clashing bottom label) */}
            {mean > 0 && (
              <ReferenceLine
                x={meanVal}
                stroke="#0D0E0D"
                strokeWidth={1.5}
                strokeDasharray="3 3"
              />
            )}

            {/* P95 Tail Position Vertical Reference Line */}
            {p95 > 0 && (
              <ReferenceLine
                x={p95Val}
                stroke="#BA1A1A"
                strokeWidth={2}
                strokeDasharray="3 3"
                label={{
                  value: `P95 ${p95Val}%`,
                  position: "top",
                  fill: "#BA1A1A",
                  fontSize: 10,
                  fontFamily: "var(--font-mono)",
                  fontWeight: 700,
                }}
              />
            )}

          {/* Base midline baseline track */}
          <ReferenceLine
            y={1}
            stroke="#C4C6C2"
            strokeWidth={2}
          />

          <Tooltip
            cursor={{ strokeDasharray: "3 3", stroke: "#A0A4A0" }}
            content={
              <IrisChartTooltip
                titlePrefix="QUANTILE STATISTIC"
                customFormatter={(payload) => {
                  const entry = Array.isArray(payload) ? payload[0]?.payload : undefined;
                  if (!entry) return [];
                  return [
                    {
                      label: "STATISTIC",
                      value: `${entry.stat} (${entry.percentile})`,
                      color: "#FFFFFF",
                      subtext: entry.label,
                    },
                    {
                      label: "CALIBRATED RISK",
                      value: `${entry.x}%`,
                      color: entry.isTail ? "#BA1A1A" : entry.isMedian ? "#1A3C2B" : "#D1D4D1",
                    },
                    ...(reportMonth ? [{ label: "EVAL CYCLE", value: reportMonth, color: "#808480" }] : []),
                  ];
                }}
              />
            }
          />

          {/* Discrete Empirical Quantile Scatter Points */}
          <Scatter
            data={empiricalMarkers}
            isAnimationActive={false}
          >
            {empiricalMarkers.map((entry) => (
              <Cell
                key={`marker-${entry.stat}`}
                fill={entry.isTail ? "#BA1A1A" : entry.isMedian ? "#1A3C2B" : "#0D0E0D"}
                stroke="#FFFFFF"
                strokeWidth={1.5}
                r={entry.isTail || entry.isMedian ? 6 : 4.5}
              />
            ))}
          </Scatter>
        </ComposedChart>
      </ResponsiveContainer>
    </div>

      {/* Axis Marker Labels Footer */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "8px",
          paddingTop: "6px",
          borderTop: "1px solid var(--color-border-hairline)",
          fontFamily: "var(--font-mono)",
          fontSize: "10px",
          color: "var(--color-text-muted)",
        }}
      >
        <span>MIN: <strong>{minVal}%</strong></span>
        <span>P25: <strong>{p25Val}%</strong></span>
        <span style={{ color: "#1A3C2B", fontWeight: 700 }}>MEDIAN: {medianVal}%</span>
        <span style={{ color: "var(--color-primary-950)", fontWeight: 600 }}>MEAN: {meanVal}%</span>
        <span>P75: <strong>{p75Val}%</strong></span>
        <span>P90: <strong>{p90Val}%</strong></span>
        <span style={{ color: "#BA1A1A", fontWeight: 700 }}>P95: {p95Val}%</span>
        <span>MAX: <strong>{maxVal}%</strong></span>
      </div>
    </div>
  );
};
