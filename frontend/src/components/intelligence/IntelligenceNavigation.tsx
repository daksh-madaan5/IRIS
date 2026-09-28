/**
 * Intelligence Terminal Navigation Component (PR-16)
 * 
 * Strict Routing Governance:
 * - Canonical routes ONLY:
 *   - /projects/{projectCode}
 *   - /projects
 *   - /analytics (only when Analytics context actually exists)
 * - FORBIDDEN: /intelligence/projects
 * - Preserves return context to Analytics when entered from an Analytics investigation action.
 * - Supports keyboard navigation and accessible link labels.
 */

import React from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import { ArrowLeft, ExternalLink, Grid, Compass } from "lucide-react";
import type { AnalyticsInvestigationContext } from "@/utils/analyticsProjectNavigation.ts";

export interface IntelligenceNavigationProps {
  projectCode?: string | null;
  variant?: "header" | "footer" | "banner";
  className?: string;
}

export const IntelligenceNavigation: React.FC<IntelligenceNavigationProps> = ({
  projectCode,
  variant = "footer",
  className = "",
}) => {
  const location = useLocation();
  const [searchParams] = useSearchParams();

  // Check for Analytics context from PR-15 navigation state or query parameters
  const navState = location.state as AnalyticsInvestigationContext | undefined;
  const isFromAnalyticsState =
    navState?.source === "analytics" || Boolean((navState as any)?.analyticsUrl);
  const isFromAnalyticsQuery =
    searchParams.get("source") === "analytics" || searchParams.get("from") === "analytics";
  const hasAnalyticsContext = isFromAnalyticsState || isFromAnalyticsQuery;

  // Preserve the exact originating Analytics URL (with filters) if available
  const analyticsReturnUrl = navState?.analyticsUrl || "/analytics";

  // Check for Projects context from location state if investigator came from /projects
  const projectsReturnUrl =
    (location.state as { projectsUrl?: string } | undefined)?.projectsUrl || "/projects";

  return (
    <nav
      className={`terminal-navigation-bar ${variant} ${className}`.trim()}
      aria-label="Intelligence terminal workspace navigation"
    >
      <div className="terminal-navigation-inner">
        {/* Return to Analytics */}
        <Link
          to={analyticsReturnUrl}
          className="terminal-nav-action secondary analytics-return"
          aria-label={
            hasAnalyticsContext
              ? "Return to originating Analytics investigation workspace"
              : "Navigate to Risk Analytics"
          }
          data-testid="link-back-to-analytics"
        >
          <ArrowLeft size={14} aria-hidden="true" />
          <span>BACK TO ANALYTICS</span>
        </Link>

        {/* Project Portfolio Navigation */}
        <Link
          to={projectsReturnUrl}
          className="terminal-nav-action secondary"
          aria-label="View canonical project portfolio"
          data-testid="link-project-portfolio"
        >
          <Grid size={14} aria-hidden="true" />
          <span>PROJECT PORTFOLIO</span>
        </Link>

        {/* Canonical Project Detail Navigation */}
        {projectCode && (
          <Link
            to={`/projects/${encodeURIComponent(projectCode.trim())}`}
            className="terminal-nav-action primary"
            aria-label={`Open project detail for ${projectCode}`}
            data-testid="link-project-detail"
          >
            <Compass size={14} aria-hidden="true" />
            <span>PROJECT DETAIL</span>
            <ExternalLink size={13} aria-hidden="true" />
          </Link>
        )}
      </div>
    </nav>
  );
};
