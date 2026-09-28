import React from "react";
import { X, Calendar, Shield, Clock } from "lucide-react";
import type {
  ProjectRiskHistoryPoint,
  ProjectIntelligenceIdentity,
  ProjectIntelligenceRisk,
} from "@/types/project.ts";

interface IntelligenceRiskInspectionHeaderProps {
  record: ProjectRiskHistoryPoint;
  project: ProjectIntelligenceIdentity;
  currentRisk?: ProjectIntelligenceRisk | null;
  onClose: () => void;
  closeButtonRef?: React.RefObject<HTMLButtonElement | null>;
}

export const IntelligenceRiskInspectionHeader: React.FC<IntelligenceRiskInspectionHeaderProps> = ({
  record,
  project,
  currentRisk,
  onClose,
  closeButtonRef,
}) => {
  return (
    <div className="terminal-inspection-header">
      <div className="inspection-header-top">
        <div className="inspection-eyebrow-group">
          <span className="terminal-section-eyebrow">HISTORICAL RISK EVALUATION</span>
          <span className="inspection-historical-tag monospace">HISTORICAL OBSERVATION</span>
          <div className="inspection-context-badge monospace">
            <Calendar size={12} aria-hidden="true" />
            <span>OBSERVED {record.report_month}</span>
          </div>
        </div>

        <button
          ref={closeButtonRef}
          type="button"
          className="terminal-drawer-close-btn"
          onClick={onClose}
          aria-label={`Close historical inspection for ${record.report_month}`}
        >
          <X size={15} aria-hidden="true" />
          <span>CLOSE</span>
        </button>
      </div>

      <div className="inspection-title-lockup">
        <h3 id="historical-drawer-title" className="terminal-drawer-title monospace">
          {record.report_month} RISK RECORD
        </h3>
        <div className="inspection-project-identity">
          <span className="inspection-project-code monospace font-bold">
            {project.project_code}
          </span>
          <span className="inspection-project-divider">/</span>
          <span className="inspection-project-name">{project.project_name}</span>
        </div>
        {(project.agency || project.sector || project.state) && (
          <div className="inspection-project-meta monospace">
            {project.agency && <span>AGENCY: {project.agency}</span>}
            {project.sector && <span>SECTOR: {project.sector}</span>}
            {project.state && <span>STATE: {project.state}</span>}
          </div>
        )}
      </div>

      <div className="inspection-header-badges">
        <div className="inspection-pill regime">
          <Shield size={12} aria-hidden="true" />
          <span>REGIME: {record.regime}</span>
        </div>
        <div className="inspection-pill model monospace" title={record.model_id}>
          <span>MODEL: {record.model_id}</span>
        </div>
        <div className={`inspection-pill ${record.calibration_active ? "calibrated" : "raw"}`}>
          <span>
            CALIBRATION: {record.calibration_active ? "ACTIVE (PLATT)" : "RAW / UNCALIBRATED"}
          </span>
        </div>
        {currentRisk && (
          <div className="inspection-pill comparison monospace">
            <Clock size={12} aria-hidden="true" />
            <span>
              CURRENT: {currentRisk.report_month} | INSPECTED: {record.report_month}
            </span>
          </div>
        )}
      </div>

      <p id="historical-drawer-desc" className="sr-only">
        Historical schedule-risk evaluation record for project {project.project_code} as observed in {record.report_month}.
      </p>
    </div>
  );
};
