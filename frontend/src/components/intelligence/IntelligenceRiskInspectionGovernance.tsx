import { AlertTriangle } from "lucide-react";
import type { ProjectRiskHistoryPoint } from "@/types/project.ts";

interface IntelligenceRiskInspectionGovernanceProps {
  record: ProjectRiskHistoryPoint;
  history: ProjectRiskHistoryPoint[];
}

/**
 * Maps authoritative model_id to human-readable family title.
 */
function getModelFamily(modelId?: string | null): string {
  if (!modelId) return "MODEL ARCHITECTURE UNSPECIFIED";
  if (modelId === "logistic_static_only__unweighted") {
    return "L2-Regularized Logistic Regression";
  }
  if (modelId === "catboost_full_v1__unweighted") {
    return "Gradient Boosted Decision Trees (CatBoost)";
  }
  return "Production Model";
}

/**
 * Maps authoritative model_id to exact explanation method.
 * Never displays a generic 'TreeSHAP / Logistic' combined label.
 */
export function getHistoricalExplanationMethod(modelId?: string | null): string {
  if (!modelId) {
    return "EXPLANATION METHOD NOT AVAILABLE";
  }
  if (modelId === "logistic_static_only__unweighted") {
    return "Logistic coefficient times transformed value";
  }
  if (modelId === "catboost_full_v1__unweighted") {
    return "CatBoost-native TreeSHAP";
  }
  return "EXPLANATION METHOD NOT AVAILABLE";
}

export const IntelligenceRiskInspectionGovernance: React.FC<
  IntelligenceRiskInspectionGovernanceProps
> = ({ record, history }) => {
  // Chronologically sort history to identify dynamic transition at this observation
  const sortedHistory = [...history].sort((a, b) =>
    a.report_month.localeCompare(b.report_month)
  );

  const currentIndex = sortedHistory.findIndex(
    (h) => h.report_month === record.report_month
  );

  const prevRecord = currentIndex > 0 ? sortedHistory[currentIndex - 1] : null;

  const isTransitionPoint =
    Boolean(prevRecord) &&
    (prevRecord!.regime !== record.regime || prevRecord!.model_id !== record.model_id);

  const isCalibrationTransition =
    Boolean(prevRecord) &&
    !isTransitionPoint &&
    prevRecord!.calibration_active !== record.calibration_active;

  const modelFamily = getModelFamily(record.model_id);
  const explanationMethod = getHistoricalExplanationMethod(record.model_id);

  return (
    <div className="terminal-card inspection-governance-card">
      <div className="terminal-card-header">
        <div className="terminal-card-title-lockup">
          <span className="terminal-section-eyebrow">MODEL & CALIBRATION PROVENANCE</span>
          <h4 className="terminal-card-title">GOVERNANCE METADATA</h4>
        </div>
        <span className="terminal-badge regime">{record.regime} REGIME</span>
      </div>

      {/* Dynamic Model/Regime Transition Notice */}
      {isTransitionPoint && prevRecord && (
        <div className="inspection-transition-alert" role="note">
          <div className="inspection-transition-header">
            <AlertTriangle size={14} className="text-amber-600" aria-hidden="true" />
            <span className="font-bold">MODEL/REGIME TRANSITION AT THIS OBSERVATION</span>
          </div>
          <p className="inspection-transition-desc monospace">
            This evaluation marks a transition from {prevRecord.regime} ({prevRecord.model_id}) to{" "}
            {record.regime} ({record.model_id}). Predictions reflect their respective model
            architectures without retrospective score backfilling.
          </p>
        </div>
      )}

      {/* Dynamic Calibration Transition Notice */}
      {isCalibrationTransition && prevRecord && (
        <div className="inspection-transition-alert calibration" role="note">
          <div className="inspection-transition-header">
            <AlertTriangle size={14} className="text-amber-600" aria-hidden="true" />
            <span className="font-bold">CALIBRATION TRANSITION AT THIS OBSERVATION</span>
          </div>
          <p className="inspection-transition-desc monospace">
            Calibration state transitioned from {prevRecord.calibration_active ? "ACTIVE (PLATT)" : "RAW / UNCALIBRATED"} to{" "}
            {record.calibration_active ? "ACTIVE (PLATT)" : "RAW / UNCALIBRATED"}. Calibrated probabilities across this boundary are not directly comparable.
          </p>
        </div>
      )}

      <div className="inspection-governance-grid">
        <div className="inspection-gov-item">
          <span className="inspection-gov-label">MODEL IDENTIFIER</span>
          <div className="inspection-gov-val monospace font-bold">{record.model_id}</div>
          <span className="inspection-gov-sub monospace">Production artifact model ID</span>
        </div>

        <div className="inspection-gov-item">
          <span className="inspection-gov-label">MODEL FAMILY</span>
          <div className="inspection-gov-val">{modelFamily}</div>
          <span className="inspection-gov-sub monospace">Supervised algorithm family</span>
        </div>

        <div className="inspection-gov-item">
          <span className="inspection-gov-label">EXPLANATION METHOD</span>
          <div className="inspection-gov-val monospace font-bold text-xs">
            {explanationMethod}
          </div>
          <span className="inspection-gov-sub monospace">
            Contribution framework strictly mapped to model ID
          </span>
        </div>

        <div className="inspection-gov-item">
          <span className="inspection-gov-label">CALIBRATION POLICY</span>
          <div className="inspection-gov-val monospace">
            {record.calibration_active
              ? "Temporal Platt Scaling (active on 2026-04)"
              : "Uncalibrated raw probability"}
          </div>
          <span className="inspection-gov-sub monospace">
            {record.calibration_active
              ? "Probability calibrated on out-of-fold validation"
              : "Pre-calibration model decision space"}
          </span>
        </div>
      </div>
    </div>
  );
};
