import React from "react";
import type {
  ProjectRiskHistoryPoint,
  ProjectIntelligenceIdentity,
  ProjectIntelligenceSnapshot,
  ProjectIntelligenceRisk,
} from "@/types/project.ts";
import { IntelligenceRiskInspectionHeader } from "./IntelligenceRiskInspectionHeader.tsx";
import { IntelligenceRiskInspectionMetrics } from "./IntelligenceRiskInspectionMetrics.tsx";
import { IntelligenceRiskInspectionGovernance } from "./IntelligenceRiskInspectionGovernance.tsx";
import { IntelligenceRiskInspectionDrivers } from "./IntelligenceRiskInspectionDrivers.tsx";
import { IntelligenceRiskInspectionTimeline } from "./IntelligenceRiskInspectionTimeline.tsx";
import { animateDrawerEnter, animateDrawerExit } from "@/lib/motion/presets.ts";
import { Database, ShieldAlert, Check } from "lucide-react";

interface IntelligenceRiskInspectionDrawerProps {
  isOpen: boolean;
  record: ProjectRiskHistoryPoint | null;
  history: ProjectRiskHistoryPoint[];
  project: ProjectIntelligenceIdentity;
  snapshot?: ProjectIntelligenceSnapshot | null;
  currentRisk?: ProjectIntelligenceRisk | null;
  onClose: () => void;
  onSelectMonth?: (month: string) => void;
}

export const IntelligenceRiskInspectionDrawer: React.FC<
  IntelligenceRiskInspectionDrawerProps
> = ({
  isOpen,
  record,
  history,
  project,
  snapshot,
  currentRisk,
  onClose,
  onSelectMonth,
}) => {
  const backdropRef = React.useRef<HTMLDivElement>(null);
  const drawerRef = React.useRef<HTMLDivElement>(null);
  const closeButtonRef = React.useRef<HTMLButtonElement>(null);
  const previouslyFocusedElement = React.useRef<HTMLElement | null>(null);
  const isClosing = React.useRef(false);

  // Focus restoration & Escape handling
  const handleClose = React.useCallback(() => {
    if (isClosing.current) return;
    isClosing.current = true;
    animateDrawerExit(backdropRef.current, drawerRef.current, () => {
      onClose();
      isClosing.current = false;
      if (previouslyFocusedElement.current) {
        previouslyFocusedElement.current.focus();
      }
    });
  }, [onClose]);

  React.useEffect(() => {
    if (isOpen && record) {
      // Store current focus
      previouslyFocusedElement.current = document.activeElement as HTMLElement | null;

      // Lock body scroll
      const prevOverflow = document.body.style.overflow;
      document.body.style.overflow = "hidden";

      // Animate entry
      animateDrawerEnter(backdropRef.current, drawerRef.current, () => {
        // Shift focus to close button
        closeButtonRef.current?.focus();
      });

      // Escape key listener
      const onKeyDown = (e: KeyboardEvent) => {
        if (e.key === "Escape") {
          e.preventDefault();
          handleClose();
        } else if (e.key === "Tab") {
          // Focus trap inside drawer
          if (!drawerRef.current) return;
          const focusableElements = drawerRef.current.querySelectorAll<HTMLElement>(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
          );
          if (focusableElements.length === 0) return;
          const firstElem = focusableElements[0];
          const lastElem = focusableElements[focusableElements.length - 1];

          if (e.shiftKey && document.activeElement === firstElem) {
            e.preventDefault();
            lastElem.focus();
          } else if (!e.shiftKey && document.activeElement === lastElem) {
            e.preventDefault();
            firstElem.focus();
          }
        }
      };

      window.addEventListener("keydown", onKeyDown);

      return () => {
        window.removeEventListener("keydown", onKeyDown);
        document.body.style.overflow = prevOverflow;
      };
    }
  }, [isOpen, record, handleClose]);

  if (!isOpen || !record) return null;

  // Audit of availability on this exact record
  const hasDrivers = Boolean(
    (record as unknown as { top_positive_contributors?: unknown[] })
      ?.top_positive_contributors?.length
  );
  const hasRank = typeof record.risk_rank === "number" && record.risk_rank > 0;

  return (
    <div
      ref={backdropRef}
      className="intelligence-modal-backdrop terminal-inspection-backdrop"
      onClick={handleClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="historical-drawer-title"
      aria-describedby="historical-drawer-desc"
    >
      <div
        ref={drawerRef}
        className="intelligence-drawer terminal-inspection-drawer"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Drawer Header */}
        <IntelligenceRiskInspectionHeader
          record={record}
          project={project}
          currentRisk={currentRisk}
          onClose={handleClose}
          closeButtonRef={closeButtonRef}
        />

        {/* Observed Risk Metrics & Portfolio Rank */}
        <IntelligenceRiskInspectionMetrics
          record={record}
          history={history}
          currentRisk={currentRisk}
        />

        {/* Model Governance & Regime Provenance */}
        <IntelligenceRiskInspectionGovernance record={record} history={history} />

        {/* Historical Driver Evidence */}
        <IntelligenceRiskInspectionDrivers record={record} />

        {/* Observation Sequence & Snapshot Timeline */}
        <IntelligenceRiskInspectionTimeline
          record={record}
          history={history}
          snapshot={snapshot}
          onSelectMonth={onSelectMonth}
        />

        {/* Data Availability & Integrity Disclosure */}
        <div className="terminal-card inspection-availability-card" role="region" aria-label="Inspection Data Availability">
          <div className="terminal-card-header">
            <div className="terminal-card-title-lockup">
              <span className="terminal-section-eyebrow">INTEGRITY AUDIT</span>
              <h4 className="terminal-card-title">DATA AVAILABILITY DISCLOSURE</h4>
            </div>
            <div className="terminal-badge-muted monospace">
              <Database size={11} aria-hidden="true" />
              <span>RECORD PROVENANCE</span>
            </div>
          </div>

          <div className="inspection-availability-list monospace text-xs">
            <div className="inspection-availability-item">
              <Check size={12} className="text-emerald-600" aria-hidden="true" />
              <span className="availability-key">Historical evaluation record:</span>
              <span className="availability-val font-bold">AVAILABLE ({record.report_month})</span>
            </div>

            <div className="inspection-availability-item">
              <Check size={12} className="text-emerald-600" aria-hidden="true" />
              <span className="availability-key">Model & regime metadata:</span>
              <span className="availability-val font-bold">{record.regime} ({record.model_id})</span>
            </div>

            <div className="inspection-availability-item">
              <Check size={12} className="text-emerald-600" aria-hidden="true" />
              <span className="availability-key">Calibration status:</span>
              <span className="availability-val font-bold">
                {record.calibration_active ? "ACTIVE (PLATT)" : "RAW / UNCALIBRATED"}
              </span>
            </div>

            <div className="inspection-availability-item">
              <Check size={12} className="text-emerald-600" aria-hidden="true" />
              <span className="availability-key">Cross-sectional portfolio rank:</span>
              <span className="availability-val font-bold">
                {hasRank ? `#${record.risk_rank} of ${record.population_size}` : "UNAVAILABLE"}
              </span>
            </div>

            <div className="inspection-availability-item">
              <ShieldAlert size={12} className="text-amber-600" aria-hidden="true" />
              <span className="availability-key">Historical driver evidence:</span>
              <span className="availability-val font-bold">
                {hasDrivers ? "AVAILABLE" : "UNAVAILABLE IN CURRENT SERVING CONTRACT"}
              </span>
            </div>
          </div>

          <div className="terminal-card-footnote">
            Historical inspection displays verified records from the production schedule-risk serving database. No synthetic points, interpolated values, or unserved scores are manufactured.
          </div>
        </div>
      </div>
    </div>
  );
};
