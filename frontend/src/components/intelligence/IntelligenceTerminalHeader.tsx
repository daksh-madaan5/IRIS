import React from "react";
import { Link } from "react-router-dom";
import { ExternalLink } from "lucide-react";
import type { ProjectIntelligenceIdentity } from "@/types/project.ts";

interface IntelligenceTerminalHeaderProps {
  project: ProjectIntelligenceIdentity;
  snapshotReportMonth?: string | null;
  riskReportMonth?: string | null;
}

export const IntelligenceTerminalHeader: React.FC<IntelligenceTerminalHeaderProps> = ({
  project,
  snapshotReportMonth,
  riskReportMonth,
}) => {
  const isCoincident =
    Boolean(snapshotReportMonth && riskReportMonth && snapshotReportMonth === riskReportMonth);
  const isDivergent =
    Boolean(snapshotReportMonth && riskReportMonth && snapshotReportMonth !== riskReportMonth);

  return (
    <div className="terminal-header-card">
      <div className="terminal-header-top">
        <div className="terminal-identity-lockup">
          <div className="terminal-eyebrow-strip">
            <span className="terminal-eyebrow">CANONICAL PROJECT RECORD</span>
            <span className="terminal-code-badge monospace">{project.project_code}</span>
            {project.legacy_ocms_code && (
              <span className="terminal-legacy-badge monospace">
                LEGACY OCMS: {project.legacy_ocms_code}
              </span>
            )}
            {project.pmgid && (
              <span className="terminal-legacy-badge monospace">PMGID: {project.pmgid}</span>
            )}
          </div>

          <h2 className="terminal-project-name">{project.project_name}</h2>

          <div className="terminal-meta-pills" aria-label="Project taxonomy metadata">
            {project.agency && (
              <span className="terminal-meta-pill agency">
                <span className="pill-key">AGENCY:</span> {project.agency}
              </span>
            )}
            {project.sector && (
              <span className="terminal-meta-pill sector">
                <span className="pill-key">SECTOR:</span> {project.sector}
              </span>
            )}
            {project.state && (
              <span className="terminal-meta-pill state">
                <span className="pill-key">STATE:</span> {project.state}
              </span>
            )}
            {project.ministry && (
              <span className="terminal-meta-pill ministry">
                <span className="pill-key">MINISTRY:</span> {project.ministry}
              </span>
            )}
          </div>
        </div>

        <div className="terminal-header-actions">
          <Link
            to="/projects"
            className="terminal-portfolio-nav-link"
            aria-label="View project portfolio"
            data-testid="header-link-portfolio"
          >
            <span>PROJECT PORTFOLIO</span>
          </Link>
          <Link
            to={`/projects/${encodeURIComponent(project.project_code)}`}
            className="terminal-nav-link"
            aria-label={`View full project detail for ${project.project_code}`}
          >
            <span>VIEW FULL PROJECT DETAIL</span>
            <ExternalLink size={14} />
          </Link>
        </div>
      </div>

      {/* Temporal Boundary Strip: Snapshot Month vs Risk Assessment Month */}
      <div className="terminal-temporal-strip" aria-label="Evaluation cycle provenance">
        <div className="terminal-temporal-content">
          <div className="terminal-temporal-item">
            <span className="temporal-key">PROJECT SNAPSHOT MONTH:</span>
            <span className="temporal-val monospace">{snapshotReportMonth || "—"}</span>
          </div>
          <span className="terminal-temporal-separator" aria-hidden="true">
            /
          </span>
          <div className="terminal-temporal-item">
            <span className="temporal-key">RISK ASSESSMENT MONTH:</span>
            <span className="temporal-val monospace">{riskReportMonth || "NOT ASSESSED"}</span>
          </div>
        </div>

        {/* Visual Temporal Markers */}
        <div className="terminal-temporal-markers" aria-hidden="true">
          <div className="temporal-marker-row">
            <span className="marker-row-label monospace">SNAPSHOT</span>
            <div className="marker-track">
              <div className="marker-point active">
                <span className="marker-dot" />
                <span className="marker-text monospace">{snapshotReportMonth || "—"}</span>
              </div>
            </div>
          </div>

          <div className="temporal-marker-row">
            <span className="marker-row-label monospace">ASSESSMENT</span>
            <div className="marker-track">
              {riskReportMonth ? (
                <div className={`marker-point ${isCoincident ? "coincident" : "divergent"}`}>
                  <span className="marker-dot" />
                  <span className="marker-text monospace">{riskReportMonth}</span>
                </div>
              ) : (
                <div className="marker-point unassessed">
                  <span className="marker-text monospace">NOT ASSESSED</span>
                </div>
              )}
            </div>
          </div>

          {isDivergent && (
            <span className="temporal-alignment-tag divergent monospace">
              TEMPORAL ALIGNMENT: Distinct evaluation cycles ({riskReportMonth} model assessment vs {snapshotReportMonth} physical snapshot)
            </span>
          )}
          {isCoincident && (
            <span className="temporal-alignment-tag coincident monospace">
              TEMPORAL ALIGNMENT: Synchronized evaluation cycle ({snapshotReportMonth})
            </span>
          )}
        </div>
      </div>
    </div>
  );
};
