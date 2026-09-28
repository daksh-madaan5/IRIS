/**
 * Historical Risk Evaluation Comparability & Movement Utilities (PR-16)
 * 
 * Strict Governance & Comparison Discipline:
 * 1. Do NOT use calibration_active alone as proof that two calibrated probabilities are semantically comparable.
 * 2. At minimum: same model_id, same regime, and compatible calibration state must be established.
 * 3. Only calculate/display probability/rank/percentile movement when two observations are strictly adjacent
 *    in the chronological evaluation sequence and semantically comparable.
 * 4. Non-adjacent observations (such as a historical point vs current assessment separated by other months)
 *    must NOT automatically receive a calculated movement delta.
 * 5. If comparison cannot be established, truthfully display "COMPARABILITY LIMITED" or "COMPARISON NOT ESTABLISHED".
 * 6. Never create synthetic trend scores, momentum scores, or early warning scores.
 */

import type { ProjectRiskHistoryPoint, ProjectIntelligenceRisk } from "@/types/project.ts";

export type RiskObservationLike = ProjectRiskHistoryPoint | ProjectIntelligenceRisk;

export interface TransitionDescriptor {
  type: "MODEL" | "REGIME" | "CALIBRATION";
  from: string;
  to: string;
  description: string;
}

export interface MovementResult {
  isComparable: boolean;
  status: "COMPARABLE" | "COMPARABILITY_LIMITED" | "COMPARISON_NOT_ESTABLISHED";
  label: string;
  transitions: TransitionDescriptor[];
  probabilityDelta?: number;
  rawProbabilityDelta?: number;
  rankDelta?: number;
  percentileDelta?: number;
}

/**
 * Checks if two observations are immediately adjacent in the chronological evaluation sequence.
 */
export function areObservationsAdjacent(
  history: RiskObservationLike[],
  aMonth: string,
  bMonth: string
): boolean {
  if (!aMonth || !bMonth || aMonth === bMonth) return false;
  const uniqueMonths = Array.from(
    new Set([...history.map((h) => h.report_month), aMonth, bMonth])
  ).sort();
  const idxA = uniqueMonths.indexOf(aMonth);
  const idxB = uniqueMonths.indexOf(bMonth);
  if (idxA === -1 || idxB === -1) return false;
  return Math.abs(idxA - idxB) === 1;
}

/**
 * Validates semantic comparability between two risk evaluations.
 * 
 * CRITICAL RULE:
 * Calibration_active === true alone does NOT prove comparability.
 * Two observations are comparable ONLY IF:
 * 1. Identical model_id
 * 2. Identical regime
 * 3. Compatible calibration active state
 */
export function areObservationsSemanticallyComparable(
  a: RiskObservationLike | null | undefined,
  b: RiskObservationLike | null | undefined
): boolean {
  if (!a || !b) return false;

  // 1. Model architecture must match exactly
  if (a.model_id !== b.model_id) return false;

  // 2. Regime must match exactly
  if (a.regime !== b.regime) return false;

  // 3. Calibration status must match (both calibrated or both uncalibrated raw)
  if (a.calibration_active !== b.calibration_active) return false;

  return true;
}

/**
 * Detects specific transition boundaries between two consecutive evaluations.
 */
export function detectObservationTransitions(
  prev: RiskObservationLike,
  curr: RiskObservationLike
): TransitionDescriptor[] {
  const transitions: TransitionDescriptor[] = [];

  if (prev.regime !== curr.regime) {
    transitions.push({
      type: "REGIME",
      from: prev.regime,
      to: curr.regime,
      description: `Regime changed from ${prev.regime} to ${curr.regime}`,
    });
  }

  if (prev.model_id !== curr.model_id) {
    transitions.push({
      type: "MODEL",
      from: prev.model_id,
      to: curr.model_id,
      description: `Model architecture changed from ${prev.model_id} to ${curr.model_id}`,
    });
  }

  if (prev.calibration_active !== curr.calibration_active) {
    transitions.push({
      type: "CALIBRATION",
      from: prev.calibration_active ? "CALIBRATED" : "RAW",
      to: curr.calibration_active ? "CALIBRATED" : "RAW",
      description: `Calibration state transitioned from ${prev.calibration_active ? "Calibrated (Platt)" : "Raw / Uncalibrated"} to ${curr.calibration_active ? "Calibrated (Platt)" : "Raw / Uncalibrated"}`,
    });
  }

  return transitions;
}

/**
 * Evaluates movement between two observations.
 * 
 * Enforces:
 * - Adjacency requirement: non-adjacent observations do NOT receive calculated movement deltas.
 * - Semantic comparability requirement: differing model/regime/calibration returns COMPARABILITY_LIMITED.
 */
export function evaluateObservationMovement(
  prior: RiskObservationLike | null | undefined,
  current: RiskObservationLike | null | undefined,
  isAdjacent: boolean = true
): MovementResult {
  if (!prior || !current) {
    return {
      isComparable: false,
      status: "COMPARISON_NOT_ESTABLISHED",
      label: "COMPARISON NOT ESTABLISHED",
      transitions: [],
    };
  }

  // If observations are not consecutive / adjacent in observation history
  if (!isAdjacent) {
    return {
      isComparable: false,
      status: "COMPARISON_NOT_ESTABLISHED",
      label: "COMPARISON NOT ESTABLISHED (NON-ADJACENT EVALUATIONS)",
      transitions: detectObservationTransitions(prior, current),
    };
  }

  const transitions = detectObservationTransitions(prior, current);

  // If any transition exists, comparability is limited
  if (transitions.length > 0) {
    return {
      isComparable: false,
      status: "COMPARABILITY_LIMITED",
      label: "COMPARABILITY LIMITED",
      transitions,
    };
  }

  // If semantic comparability fails for any other reason
  if (!areObservationsSemanticallyComparable(prior, current)) {
    return {
      isComparable: false,
      status: "COMPARABILITY_LIMITED",
      label: "COMPARABILITY LIMITED",
      transitions,
    };
  }

  // Observations are adjacent and semantically comparable
  const probDelta = Number(((current.risk_probability - prior.risk_probability) * 100).toFixed(1));
  const rawDelta = Number(((current.raw_probability - prior.raw_probability) * 100).toFixed(1));
  const rankDelta = current.risk_rank - prior.risk_rank;
  const percentileDelta = Number(((current.risk_percentile - prior.risk_percentile) * 100).toFixed(1));

  return {
    isComparable: true,
    status: "COMPARABLE",
    label: "COMPARABLE MOVEMENT",
    transitions: [],
    probabilityDelta: probDelta,
    rawProbabilityDelta: rawDelta,
    rankDelta,
    percentileDelta,
  };
}

/**
 * Format signed delta string (e.g. +2.5 pp, -1.0 pp, 0.0 pp).
 */
export function formatSignedDelta(value: number | undefined, unit: string = "pp"): string {
  if (value === undefined || Number.isNaN(value)) return "—";
  if (value > 0) return `+${value} ${unit}`.trim();
  if (value < 0) return `${value} ${unit}`.trim();
  return `0.0 ${unit}`.trim();
}
