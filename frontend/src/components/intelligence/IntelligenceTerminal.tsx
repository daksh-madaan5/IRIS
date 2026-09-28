import React from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, RefreshCw, Layers } from "lucide-react";
import { fetchProjectRiskIntelligence } from "@/api/projects.ts";
import { IntelligenceProjectSelector } from "./IntelligenceProjectSelector.tsx";
import { IntelligenceTerminalHeader } from "./IntelligenceTerminalHeader.tsx";
import { IntelligenceRiskAssessment } from "./IntelligenceRiskAssessment.tsx";
import { IntelligenceExplainability } from "./IntelligenceExplainability.tsx";
import { IntelligenceSignals } from "./IntelligenceSignals.tsx";
import { IntelligenceRiskHistory } from "./IntelligenceRiskHistory.tsx";
import { IntelligenceGovernance } from "./IntelligenceGovernance.tsx";
import { IntelligenceDataAvailability } from "./IntelligenceDataAvailability.tsx";
import { IntelligenceRiskInspectionDrawer } from "./IntelligenceRiskInspectionDrawer.tsx";
import { IntelligenceNavigation } from "./IntelligenceNavigation.tsx";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner.tsx";

interface IntelligenceTerminalProps {
  selectedProjectCode: string | null;
  onSelectProject: (projectCode: string) => void;
  onClearProject: () => void;
}

export const IntelligenceTerminal: React.FC<IntelligenceTerminalProps> = ({
  selectedProjectCode,
  onSelectProject,
  onClearProject,
}) => {
  // PR-08: Selected historical evaluation month for deep inspection
  const [selectedEvaluationMonth, setSelectedEvaluationMonth] = React.useState<string | null>(null);

  // Clear historical inspection when project changes or is cleared
  React.useEffect(() => {
    setSelectedEvaluationMonth(null);
  }, [selectedProjectCode]);

  const {
    data: intelligence,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["projects", selectedProjectCode, "risk-intelligence"],
    queryFn: () => fetchProjectRiskIntelligence(selectedProjectCode!),
    enabled: Boolean(selectedProjectCode),
  });

  const handleClearProject = React.useCallback(() => {
    setSelectedEvaluationMonth(null);
    onClearProject();
  }, [onClearProject]);

  // Resolve exact historical record from actual history collection
  const selectedHistoricalRecord = React.useMemo(() => {
    if (!selectedEvaluationMonth || !intelligence?.history) return null;
    return intelligence.history.find((h) => h.report_month === selectedEvaluationMonth) || null;
  }, [selectedEvaluationMonth, intelligence?.history]);

  return (
    <section className="terminal-workspace" aria-labelledby="terminal-heading">
      {/* Terminal Workspace Top Header */}
      <div className="terminal-workspace-header">
        <div className="terminal-workspace-title-lockup">
          <div className="terminal-badge-eyebrow">
            <Layers size={13} />
            <span>IRIS INTELLIGENCE WORKSTATION</span>
          </div>
          <h2 id="terminal-heading" className="terminal-workspace-title">
            PROJECT RISK INTELLIGENCE TERMINAL
          </h2>
          <p className="terminal-workspace-desc">
            Decision-support console for single-project schedule extension risk evaluation, signed model drivers, and longitudinal history inspection.
          </p>
        </div>

        {/* Project Lookup / Selector Bar */}
        <IntelligenceProjectSelector
          selectedProjectCode={selectedProjectCode}
          onSelectProject={onSelectProject}
          onClear={handleClearProject}
        />
      </div>

      {/* State 1: EMPTY / NO PROJECT SELECTED */}
      {!selectedProjectCode && (
        <div className="terminal-empty-state-card" role="region" aria-label="Terminal Empty State">
          <div className="terminal-empty-icon-lockup">
            <span className="terminal-empty-symbol">◈</span>
          </div>
          <h3 className="terminal-empty-title">INTELLIGENCE TERMINAL</h3>
          <p className="terminal-empty-prompt">Select a project to begin analysis.</p>
          <p className="terminal-empty-sub">
            Enter a canonical project code or search by project name above to inspect schedule risk
            assessments, model governance, signed drivers, and chronological evaluation history.
          </p>
        </div>
      )}

      {/* State 2: LOADING */}
      {selectedProjectCode && isLoading && (
        <div className="terminal-loading-state-card" aria-busy="true" role="status">
          <LoadingSpinner size="lg" />
          <div className="terminal-loading-text-lockup">
            <span className="terminal-loading-title">FETCHING PROJECT INTELLIGENCE...</span>
            <span className="terminal-loading-sub monospace">
              RETRIEVING SCHEDULE RISK INTELLIGENCE RECORD: {selectedProjectCode}
            </span>
          </div>
        </div>
      )}

      {/* State 3: ERROR */}
      {selectedProjectCode && !isLoading && error && (
        <div className="terminal-error-state-card" role="alert">
          <div className="terminal-error-header">
            <AlertTriangle size={20} className="terminal-error-icon" />
            <div className="terminal-error-title-wrap">
              <span className="terminal-error-eyebrow">TRANSMISSION OR RECORD FAILURE</span>
              <h3 className="terminal-error-title">PROJECT INTELLIGENCE UNAVAILABLE</h3>
            </div>
          </div>

          <p className="terminal-error-desc">
            An error occurred while retrieving schedule-risk intelligence for project code{" "}
            <strong className="monospace">{selectedProjectCode}</strong>. Verify the project code
            exists in the monitored portfolio or retry the request.
          </p>

          <div className="terminal-error-details monospace">
            {error instanceof Error ? error.message : "Unknown error encountered"}
          </div>

          <div className="terminal-error-actions">
            <button
              type="button"
              className="terminal-error-btn retry"
              onClick={() => refetch()}
              aria-label="Retry loading project intelligence"
            >
              <RefreshCw size={13} />
              <span>RETRY TRANSMISSION</span>
            </button>
            <button
              type="button"
              className="terminal-error-btn clear"
              onClick={handleClearProject}
              aria-label="Clear project selection"
            >
              <span>SELECT ANOTHER PROJECT</span>
            </button>
          </div>
        </div>
      )}

      {/* State 4: SUCCESS / LOADED (Assessed or Unassessed) */}
      {selectedProjectCode && !isLoading && !error && intelligence && (
        <div className="terminal-content-layout">
          {/* Identity & Provenance Header */}
          <IntelligenceTerminalHeader
            project={intelligence.project}
            snapshotReportMonth={intelligence.snapshot?.report_month}
            riskReportMonth={
              intelligence.risk?.report_month ||
              intelligence.data_availability?.risk_report_month
            }
          />

          {/* Primary Assessment & Governance Row */}
          <div className="terminal-grid-2col">
            <IntelligenceRiskAssessment risk={intelligence.risk} />
            <IntelligenceGovernance model={intelligence.model} />
          </div>

          {/* PR-07: Dedicated Explainability & Driver Analysis Layer */}
          <IntelligenceExplainability
            risk={intelligence.risk}
            model={intelligence.model}
            drivers={intelligence.drivers}
            dataAvailability={intelligence.data_availability}
          />

          {/* Observational Signals & Recent Changes */}
          <IntelligenceSignals
            signals={intelligence.signals}
            recentChanges={intelligence.recent_changes}
          />

          {/* PR-08 Upgraded Longitudinal History with Selection Controls */}
          <IntelligenceRiskHistory
            history={intelligence.history}
            selectedMonth={selectedEvaluationMonth}
            onSelectMonth={setSelectedEvaluationMonth}
          />

          {/* Unserved ML Domains / Data Availability */}
          <IntelligenceDataAvailability availability={intelligence.data_availability} />

          {/* PR-16: Canonical Workspace Navigation Footer */}
          <IntelligenceNavigation
            projectCode={intelligence.project.project_code}
            variant="footer"
          />

          {/* PR-08: Historical Risk Evaluation Inspection Drawer */}
          <IntelligenceRiskInspectionDrawer
            isOpen={Boolean(selectedHistoricalRecord)}
            record={selectedHistoricalRecord}
            history={intelligence.history}
            project={intelligence.project}
            snapshot={intelligence.snapshot}
            currentRisk={intelligence.risk}
            onClose={() => setSelectedEvaluationMonth(null)}
            onSelectMonth={setSelectedEvaluationMonth}
          />
        </div>
      )}
    </section>
  );
};
