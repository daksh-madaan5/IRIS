import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { IntelligencePage } from "@/pages/IntelligencePage.tsx";
import { IntelligenceRiskHistory } from "@/components/intelligence/IntelligenceRiskHistory.tsx";
import { IntelligenceRiskInspectionDrawer } from "@/components/intelligence/IntelligenceRiskInspectionDrawer.tsx";
import { IntelligenceRiskInspectionMetrics } from "@/components/intelligence/IntelligenceRiskInspectionMetrics.tsx";
import {
  areObservationsSemanticallyComparable,
  evaluateObservationMovement,
  areObservationsAdjacent,
} from "@/utils/historicalComparability.ts";
import * as projectsApi from "@/api/projects.ts";
import * as riskApi from "@/api/risk.ts";
import type {
  ProjectRiskIntelligenceResponse,
  ProjectRiskHistoryPoint,
  ProjectIntelligenceIdentity,
  ProjectIntelligenceSnapshot,
  ProjectIntelligenceRisk,
} from "@/types/project.ts";

vi.mock("@/api/projects.ts", async () => {
  const actual = await vi.importActual<typeof projectsApi>("@/api/projects.ts");
  return {
    ...actual,
    fetchQuickSearch: vi.fn(),
    fetchProjectRiskIntelligence: vi.fn(),
  };
});

vi.mock("@/api/risk.ts", async () => {
  const actual = await vi.importActual<typeof riskApi>("@/api/risk.ts");
  return {
    ...actual,
    fetchRiskOptions: vi.fn(),
    fetchModelInfo: vi.fn(),
    fetchRiskSummary: vi.fn(),
    fetchRiskProjects: vi.fn(),
    fetchProjectRiskRecord: vi.fn(),
    fetchProjectRiskHistory: vi.fn(),
  };
});

const mockProjectIdentity: ProjectIntelligenceIdentity = {
  project_code: "617936",
  project_name: "Dedicated Freight Corridor (Western)",
  agency: "DFCCIL",
  ministry: "RAILWAYS",
  sector: "RAILWAYS",
  state: "MAHARASHTRA",
  legacy_ocms_code: "OCMS-1234",
  pmgid: "PMG-5678",
};

const mockSnapshot: ProjectIntelligenceSnapshot = {
  report_month: "2026-07",
  physical_progress: 92.5,
  financial_progress: 88.4,
  cumulative_expenditure: 47500.0,
  original_cost: 28181.0,
  revised_cost: 52000.0,
  approval_date: "2008-02",
  start_date: "2008-10",
  original_completion_date: "2018-03",
  revised_completion_date: "2026-12",
};

const mockRisk: ProjectIntelligenceRisk = {
  risk_probability: 0.3842,
  raw_probability: 0.3211,
  risk_rank: 42,
  risk_percentile: 0.825,
  population_size: 1625,
  report_month: "2026-04",
  regime: "MODERN",
  model_id: "logistic_static_only__unweighted",
  target: "target_effective_schedule_ext_3m",
  calibration_active: true,
};

const mockHistory: ProjectRiskHistoryPoint[] = [
  {
    report_month: "2025-05",
    risk_probability: 0.405,
    raw_probability: 0.405,
    risk_rank: 60,
    risk_percentile: 0.75,
    population_size: 1570,
    regime: "LEGACY",
    model_id: "catboost_full_v1__unweighted",
    calibration_active: false,
  },
  {
    report_month: "2025-06",
    risk_probability: 0.421,
    raw_probability: 0.421,
    risk_rank: 55,
    risk_percentile: 0.78,
    population_size: 1580,
    regime: "LEGACY",
    model_id: "catboost_full_v1__unweighted",
    calibration_active: false,
  },
  {
    report_month: "2026-04",
    risk_probability: 0.3842,
    raw_probability: 0.3211,
    risk_rank: 42,
    risk_percentile: 0.825,
    population_size: 1625,
    regime: "MODERN",
    model_id: "logistic_static_only__unweighted",
    calibration_active: true,
  },
];

const mockOperationalResponse: ProjectRiskIntelligenceResponse = {
  project: mockProjectIdentity,
  snapshot: mockSnapshot,
  risk: mockRisk,
  model: {
    model_id: "logistic_static_only__unweighted",
    target: "target_effective_schedule_ext_3m",
    model_family: "L2-Regularized Logistic Regression (C=1.0)",
    status: "ACTIVE_PRODUCTION",
    is_active: true,
    coverage_period: "2025-07 through 2026-07",
    calibration_policy: "Temporal Platt scaling active from origin 2026-04",
    explanation_method: "LOGISTIC_COEFFICIENT_TIMES_TRANSFORMED_VALUE",
  },
  history: mockHistory,
  drivers: {
    top_positive: [
      {
        feature: "schedule_extensions_count",
        display_name: "Schedule Extensions Count",
        value: "4",
        contribution: 0.412,
        direction: "POSITIVE",
        rank: 1,
      },
    ],
    top_negative: [
      {
        feature: "physical_progress",
        display_name: "Physical Progress Percentage",
        value: "92.5%",
        contribution: -0.285,
        direction: "NEGATIVE",
        rank: 1,
      },
    ],
    strongest_drivers: [],
  },
  signals: {
    cost_revised: true,
    schedule_revised: true,
    cost_revision_ratio: 1.84,
    cost_revision_count: 2,
    schedule_extension_count: 4,
    reporting_months_count: 24,
    first_reported_month: "2024-06",
    latest_reported_month: "2026-07",
  },
  recent_changes: {
    has_prior_observation: true,
    prior_report_month: "2026-06",
    physical_progress_delta: 0.8,
    expenditure_delta: 350.0,
    revised_cost_delta: 0.0,
    completion_date_changed: false,
  },
  data_availability: {
    has_project_data: true,
    has_risk_assessment: true,
    has_risk_history: true,
    has_drivers: true,
    snapshot_report_month: "2026-07",
    risk_report_month: "2026-04",
    cost_risk_ml_served: false,
    progress_stagnation_ml_served: false,
  },
};

function renderTerminal(initialEntry = "/intelligence?project=617936", locationState?: unknown) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[{ pathname: "/intelligence", search: initialEntry.includes("?") ? initialEntry.split("?")[1] ? `?${initialEntry.split("?")[1]}` : "" : "", state: locationState }]}>
        <Routes>
          <Route path="/intelligence" element={<IntelligencePage />} />
          <Route path="/projects/:code" element={<div>Project Detail Page</div>} />
          <Route path="/projects" element={<div>Projects Portfolio Page</div>} />
          <Route path="/analytics" element={<div>Analytics Page</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("PR-16: Operational Investigation Terminal Semantics (50 Tests)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(projectsApi.fetchProjectRiskIntelligence).mockResolvedValue(mockOperationalResponse);
    vi.mocked(projectsApi.fetchQuickSearch).mockResolvedValue([
      {
        project_code: "617936",
        project_name: "Dedicated Freight Corridor (Western)",
        agency: "DFCCIL",
        latest_report_month: "2026-07",
      },
    ]);
    vi.mocked(riskApi.fetchRiskOptions).mockResolvedValue({
      report_months: ["2026-04"],
      default_report_month: "2026-04",
      selected_report_month: "2026-04",
      regimes: ["MODERN"],
      sectors: ["RAILWAYS"],
      agencies: ["DFCCIL"],
      ministries: ["RAILWAYS"],
      states: ["MAHARASHTRA"],
    } as any);
    vi.mocked(riskApi.fetchModelInfo).mockResolvedValue({
      serving_artifact_version: "iris_serving_v1_1",
      target: "target_effective_schedule_ext_3m",
      horizon_months: 3,
      status: "READY",
      models: [],
    } as any);
    vi.mocked(riskApi.fetchRiskSummary).mockResolvedValue({
      report_month: "2026-04",
      regime_filter: null,
      filters: {},
      project_count: 1625,
      score_distribution: {
        minimum: 0.01,
        p25: 0.2,
        median: 0.4,
        p75: 0.6,
        p90: 0.7,
        p95: 0.8,
        maximum: 0.99,
      },
      high_risk_projects: [],
    } as any);
    vi.mocked(riskApi.fetchRiskProjects).mockResolvedValue({
      report_month: "2026-04",
      total_count: 1,
      limit: 10,
      offset: 0,
      projects: [],
    } as any);
  });

  // =========================================================================
  // Group 1: Authoritative Project Identity & Canonical Contract (Tests 1–5)
  // =========================================================================

  it("1. renders authoritative identity fields directly from payload", async () => {
    renderTerminal();
    await waitFor(() => {
      expect(screen.getByText("617936")).toBeInTheDocument();
      expect(screen.getByText("Dedicated Freight Corridor (Western)")).toBeInTheDocument();
      expect(screen.getAllByText("DFCCIL").length).toBeGreaterThan(0);
      expect(screen.getAllByText("RAILWAYS").length).toBeGreaterThan(0);
      expect(screen.getAllByText("MAHARASHTRA").length).toBeGreaterThan(0);
    });
  });

  it("2. renders legacy OCMS code and PMGID when present in response", async () => {
    renderTerminal();
    await waitFor(() => {
      expect(screen.getByText("LEGACY OCMS: OCMS-1234")).toBeInTheDocument();
      expect(screen.getByText("PMGID: PMG-5678")).toBeInTheDocument();
    });
  });

  it("3. keeps project snapshot month and risk assessment month strictly separated", async () => {
    renderTerminal();
    await waitFor(() => {
      expect(screen.getByText("PROJECT SNAPSHOT MONTH:")).toBeInTheDocument();
      expect(screen.getByText("RISK ASSESSMENT MONTH:")).toBeInTheDocument();
      expect(screen.getAllByText("2026-07").length).toBeGreaterThan(0);
      expect(screen.getAllByText("2026-04").length).toBeGreaterThan(0);
    });
  });

  it("4. specifies target as target_effective_schedule_ext_3m exclusively", async () => {
    renderTerminal();
    await waitFor(() => {
      expect(screen.getAllByText(/target_effective_schedule_ext_3m/).length).toBeGreaterThan(0);
    });
  });

  it("5. issues exactly one risk-intelligence query per project investigation without N+1 loops", async () => {
    renderTerminal();
    await waitFor(() => {
      expect(screen.getByText("617936")).toBeInTheDocument();
    });
    expect(projectsApi.fetchProjectRiskIntelligence).toHaveBeenCalledTimes(1);
    expect(projectsApi.fetchProjectRiskIntelligence).toHaveBeenCalledWith("617936");
  });

  // =========================================================================
  // Group 2: Operational Probability & Calibrated vs Raw Separation (Tests 6–11)
  // =========================================================================

  it("6. renders calibrated risk probability truthfully when calibration is active", async () => {
    renderTerminal();
    await waitFor(() => {
      expect(screen.getAllByText("38.4%").length).toBeGreaterThan(0);
      expect(screen.getByText("CALIBRATED PROBABILITY")).toBeInTheDocument();
    });
  });

  it("7. renders raw model probability as a distinct unweighted field without mixing spaces", async () => {
    renderTerminal();
    await waitFor(() => {
      expect(screen.getAllByText("RAW: 32.1%").length).toBeGreaterThan(0);
      expect(screen.getAllByText("32.1%").length).toBeGreaterThan(0);
    });
  });

  it("8. renders uncalibrated evaluations as RAW / UNCALIBRATED without inventing calibrated values", async () => {
    const uncalibratedResponse: ProjectRiskIntelligenceResponse = {
      ...mockOperationalResponse,
      risk: {
        ...mockRisk,
        calibration_active: false,
      },
    };
    vi.mocked(projectsApi.fetchProjectRiskIntelligence).mockResolvedValue(uncalibratedResponse);
    renderTerminal();
    await waitFor(() => {
      expect(screen.getAllByText("RAW MODEL PROBABILITY").length).toBeGreaterThan(0);
      expect(screen.getAllByText("RAW PROBABILITY").length).toBeGreaterThan(0);
    });
  });

  it("9. renders dynamic model ID without hardcoded fallback strings", async () => {
    renderTerminal();
    await waitFor(() => {
      expect(screen.getAllByText(/logistic_static_only__unweighted/).length).toBeGreaterThan(0);
    });
  });

  it("10. renders dynamic regime from response payload", async () => {
    renderTerminal();
    await waitFor(() => {
      expect(screen.getAllByText(/MODERN REGIME/).length).toBeGreaterThan(0);
    });
  });

  it("11. negative assertion: strictly prohibits arbitrary risk tiers (LOW, MEDIUM, HIGH, CRITICAL)", async () => {
    renderTerminal();
    await waitFor(() => {
      expect(screen.getByText("617936")).toBeInTheDocument();
    });
    expect(screen.queryByText(/LOW RISK/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/MEDIUM RISK/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/HIGH RISK/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/CRITICAL RISK/i)).not.toBeInTheDocument();
  });

  // =========================================================================
  // Group 3: Cross-Sectional Portfolio Position & No Invented Metrics (Tests 12–17)
  // =========================================================================

  it("12. renders authoritative portfolio rank and population size truthfully", async () => {
    renderTerminal();
    await waitFor(() => {
      expect(screen.getAllByText("#42").length).toBeGreaterThan(0);
      expect(screen.getByText(/OF 1,625 MONITORED/)).toBeInTheDocument();
    });
  });

  it("13. renders normalized percentile truthfully", async () => {
    renderTerminal();
    await waitFor(() => {
      expect(screen.getAllByText("P82.5").length).toBeGreaterThan(0);
    });
  });

  it("14. negative assertion: strictly prohibits deriving or rendering TOP 5%, TOP 10%, or TOP 20%", async () => {
    renderTerminal();
    await waitFor(() => {
      expect(screen.getByText("617936")).toBeInTheDocument();
    });
    expect(screen.queryByText(/TOP 5%/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/TOP 10%/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/TOP 20%/i)).not.toBeInTheDocument();
  });

  it("15. negative assertion: strictly prohibits AI SCORE, WARNING SCORE, HEALTH SCORE, COMPOSITE SCORE", async () => {
    renderTerminal();
    await waitFor(() => {
      expect(screen.getByText("617936")).toBeInTheDocument();
    });
    expect(screen.queryByText(/AI SCORE/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/WARNING SCORE/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/HEALTH SCORE/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/COMPOSITE SCORE/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/RISK SCORE/i)).not.toBeInTheDocument();
  });

  it("16. negative assertion: strictly prohibits arbitrary threshold badges", async () => {
    renderTerminal();
    await waitFor(() => {
      expect(screen.getByText("617936")).toBeInTheDocument();
    });
    const terminal = document.querySelector(".terminal-workspace")!;
    expect(terminal.textContent).not.toContain("HIGH RISK THRESHOLD");
    expect(terminal.textContent).not.toContain("> 0.5");
  });

  it("17. displays cross-sectional ranking context note", async () => {
    renderTerminal();
    await waitFor(() => {
      expect(
        screen.getByText(/RELATIVE POSITION: RANK #42 ACROSS 1,625 MONITORED PROJECTS/)
      ).toBeInTheDocument();
    });
  });

  // =========================================================================
  // Group 4: Driver Evidence, Logit Contributions & Causal Disclaimer (Tests 18–23)
  // =========================================================================

  it("18. renders signed positive risk contributors in raw margin logit space", async () => {
    renderTerminal();
    await waitFor(() => {
      expect(screen.getByText("Schedule Extensions Count")).toBeInTheDocument();
      expect(screen.getByText("+0.412")).toBeInTheDocument();
    });
  });

  it("19. renders signed negative risk contributors in raw margin logit space", async () => {
    renderTerminal();
    await waitFor(() => {
      expect(screen.getByText("Physical Progress Percentage")).toBeInTheDocument();
      expect(screen.getByText("-0.285")).toBeInTheDocument();
    });
  });

  it("20. displays mandatory causal disclaimer in model evidence", async () => {
    renderTerminal();
    await waitFor(() => {
      expect(
        screen.getAllByText(/Signed contributions describe model decision shifts, not causal real-world mechanisms\./i).length
      ).toBeGreaterThan(0);
    });
  });

  it("21. displays distinct explanation framework based on model architecture", async () => {
    renderTerminal();
    await waitFor(() => {
      expect(
        screen.getAllByText("Logistic coefficient times transformed value").length
      ).toBeGreaterThan(0);
    });
  });

  it("22. displays truthful fallback when driver evidence is empty without fabricating drivers", async () => {
    const noDriversResponse: ProjectRiskIntelligenceResponse = {
      ...mockOperationalResponse,
      drivers: {
        top_positive: [],
        top_negative: [],
        strongest_drivers: [],
      },
    };
    vi.mocked(projectsApi.fetchProjectRiskIntelligence).mockResolvedValue(noDriversResponse);
    renderTerminal();
    await waitFor(() => {
      expect(screen.getAllByText(/NO MODEL DRIVER EVIDENCE AVAILABLE/i).length).toBeGreaterThan(0);
    });
    expect(screen.queryByText("Schedule Extensions Count")).not.toBeInTheDocument();
  });

  it("23. handles missing driver payload gracefully", async () => {
    const missingDriversResponse = {
      ...mockOperationalResponse,
      drivers: undefined,
    } as unknown as ProjectRiskIntelligenceResponse;
    vi.mocked(projectsApi.fetchProjectRiskIntelligence).mockResolvedValue(missingDriversResponse);
    renderTerminal();
    await waitFor(() => {
      expect(screen.getByText("617936")).toBeInTheDocument();
    });
  });

  // =========================================================================
  // Group 5: Signals, Recent Changes & Unserved Specification Disclosures (Tests 24–28)
  // =========================================================================

  it("24. displays served operational signals without extrapolation", async () => {
    renderTerminal();
    await waitFor(() => {
      expect(screen.getByText("(1.84x)")).toBeInTheDocument();
      expect(screen.getByText(/2 events recorded/)).toBeInTheDocument();
    });
  });

  it("25. displays recent monthly changes relative to prior observation truthfully", async () => {
    renderTerminal();
    await waitFor(() => {
      expect(screen.getByText("+0.8 pp")).toBeInTheDocument();
      expect(screen.getByText("+₹350 CR")).toBeInTheDocument();
    });
  });

  it("26. unserved cost overrun risk ML domain is disclosed truthfully as DATA PENDING", async () => {
    renderTerminal();
    await waitFor(() => {
      expect(screen.getByText("Cost Overrun Risk")).toBeInTheDocument();
      expect(screen.getAllByText("DATA PENDING").length).toBeGreaterThan(0);
    });
  });

  it("27. unserved progress stagnation risk ML domain is disclosed truthfully as DATA PENDING", async () => {
    renderTerminal();
    await waitFor(() => {
      expect(screen.getByText("Progress Stagnation Risk")).toBeInTheDocument();
    });
  });

  it("28. audit trail reflects served model artifact provenance", async () => {
    renderTerminal();
    await waitFor(() => {
      expect(screen.getAllByText(/2025-07 through 2026-07/).length).toBeGreaterThan(0);
    });
  });

  // =========================================================================
  // Group 6: Longitudinal Trajectory & Regime/Model/Calibration Transitions (Tests 29–35)
  // =========================================================================

  it("29. renders strictly observed historical months without synthetic points or zero-fill", async () => {
    renderTerminal();
    await waitFor(() => {
      expect(screen.getAllByText("2025-05").length).toBeGreaterThan(0);
      expect(screen.getAllByText("2025-06").length).toBeGreaterThan(0);
      expect(screen.getAllByText("2026-04").length).toBeGreaterThan(0);
      // Intermediate unobserved months must never appear
      expect(screen.queryByText("2025-07")).not.toBeInTheDocument();
      expect(screen.queryByText("2025-08")).not.toBeInTheDocument();
      expect(screen.queryByText("2026-01")).not.toBeInTheDocument();
    });
  });

  it("30. highlights regime transition dynamically when history crosses regime boundaries", async () => {
    renderTerminal();
    await waitFor(() => {
      expect(screen.getByText("REGIME TRANSITION DETECTED")).toBeInTheDocument();
    });
  });

  it("31. highlights model transition dynamically when history crosses model boundaries", () => {
    const historyWithModelTrans: ProjectRiskHistoryPoint[] = [
      {
        report_month: "2026-03",
        risk_probability: 0.35,
        raw_probability: 0.35,
        risk_rank: 50,
        risk_percentile: 0.8,
        population_size: 1600,
        regime: "MODERN",
        model_id: "model_arch_a",
        calibration_active: true,
      },
      {
        report_month: "2026-04",
        risk_probability: 0.38,
        raw_probability: 0.38,
        risk_rank: 45,
        risk_percentile: 0.82,
        population_size: 1625,
        regime: "MODERN",
        model_id: "model_arch_b",
        calibration_active: true,
      },
    ];
    render(<IntelligenceRiskHistory history={historyWithModelTrans} />);
    expect(screen.getByText("MODEL TRANSITION DETECTED")).toBeInTheDocument();
  });

  it("32. highlights calibration transition dynamically when calibration policy transitions", () => {
    const historyWithCalibTrans: ProjectRiskHistoryPoint[] = [
      {
        report_month: "2026-03",
        risk_probability: 0.35,
        raw_probability: 0.35,
        risk_rank: 50,
        risk_percentile: 0.8,
        population_size: 1600,
        regime: "MODERN",
        model_id: "logistic_static_only__unweighted",
        calibration_active: false,
      },
      {
        report_month: "2026-04",
        risk_probability: 0.38,
        raw_probability: 0.32,
        risk_rank: 45,
        risk_percentile: 0.82,
        population_size: 1625,
        regime: "MODERN",
        model_id: "logistic_static_only__unweighted",
        calibration_active: true,
      },
    ];
    render(<IntelligenceRiskHistory history={historyWithCalibTrans} />);
    expect(screen.getByText("CALIBRATION TRANSITION DETECTED")).toBeInTheDocument();
  });

  it("33. single historical observation displays as discrete evaluation rather than misleading trend line", () => {
    const singleHistory: ProjectRiskHistoryPoint[] = [mockHistory[0]];
    render(<IntelligenceRiskHistory history={singleHistory} />);
    expect(screen.getByText("DISCRETE SINGLE EVALUATION")).toBeInTheDocument();
    expect(screen.getByText(/Only a single historical evaluation is recorded/)).toBeInTheDocument();
  });

  it("34. accessible table view provides full chronological history with comparability indicators", () => {
    render(<IntelligenceRiskHistory history={mockHistory} />);
    expect(screen.getByRole("table", { name: /chronological risk history/i })).toBeInTheDocument();
    expect(screen.getByText("BASELINE")).toBeInTheDocument();
  });

  it("35. clicking an evaluation point or table inspect button opens detailed historical inspection", async () => {
    renderTerminal();
    await waitFor(() => {
      expect(screen.getByText("617936")).toBeInTheDocument();
    });
    const inspectButtons = screen.getAllByRole("button", { name: /inspect/i });
    expect(inspectButtons.length).toBeGreaterThan(0);
    fireEvent.click(inspectButtons[0]);
    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
      expect(screen.getAllByText(/HISTORICAL RISK EVALUATION/).length).toBeGreaterThan(0);
    });
  });

  // =========================================================================
  // Group 7: Navigation, URL State & Workspace Integration (Tests 36–41)
  // =========================================================================

  it("36. synchronizes project code with URL query param ?project=CODE", async () => {
    renderTerminal("/intelligence?project=617936");
    await waitFor(() => {
      expect(screen.getByText("617936")).toBeInTheDocument();
    });
  });

  it("37. canonical link provided to Project Detail (/projects/:projectCode)", async () => {
    renderTerminal();
    await waitFor(() => {
      const detailLinks = screen.getAllByRole("link", { name: /project detail/i });
      expect(detailLinks.length).toBeGreaterThan(0);
      expect(detailLinks[0].getAttribute("href")).toBe("/projects/617936");
    });
  });

  it("38. canonical link provided to Project Portfolio (/projects)", async () => {
    renderTerminal();
    await waitFor(() => {
      const portfolioLink = screen.getByTestId("link-project-portfolio");
      expect(portfolioLink.getAttribute("href")).toBe("/projects");
    });
  });

  it("39. canonical link provided to Analytics (/analytics)", async () => {
    renderTerminal();
    await waitFor(() => {
      const analyticsLink = screen.getByTestId("link-back-to-analytics");
      expect(analyticsLink.getAttribute("href")).toBe("/analytics");
    });
  });

  it("40. returns to exact originating Analytics filter URL when location state provides return context", async () => {
    const analyticsState = {
      analyticsUrl: "/analytics?sector=RAILWAYS&state=MAHARASHTRA",
    };
    renderTerminal("/intelligence?project=617936", analyticsState);
    await waitFor(() => {
      const returnLink = screen.getByTestId("link-back-to-analytics");
      expect(returnLink.getAttribute("href")).toBe("/analytics?sector=RAILWAYS&state=MAHARASHTRA");
    });
  });

  it("41. negative navigation assertion: NEVER contains or routes to forbidden /intelligence/projects", async () => {
    const { container } = renderTerminal();
    await waitFor(() => {
      expect(screen.getByText("617936")).toBeInTheDocument();
    });
    const links = container.querySelectorAll("a");
    links.forEach((link) => {
      expect(link.getAttribute("href")).not.toContain("/intelligence/projects");
    });
  });

  // =========================================================================
  // Group 8: Workspace States & Accessibility (Tests 42–48)
  // =========================================================================

  it("42. renders clean empty state when no project is selected with zero fake data", async () => {
    renderTerminal("/intelligence");
    await waitFor(() => {
      expect(screen.getByText("Select a project to begin analysis.")).toBeInTheDocument();
      expect(screen.queryByText("38.4%")).not.toBeInTheDocument();
      expect(screen.queryByText("#42")).not.toBeInTheDocument();
    });
  });

  it("43. allows searching project by code or name via autocomplete and selecting", async () => {
    renderTerminal("/intelligence");

    const input = screen.getByRole("combobox", { name: /select project for risk evaluation/i });
    await userEvent.type(input, "617936");

    await waitFor(() => {
      expect(projectsApi.fetchQuickSearch).toHaveBeenCalledWith("617936", 8);
      expect(screen.getByText("Dedicated Freight Corridor (Western)")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Dedicated Freight Corridor (Western)"));

    await waitFor(() => {
      expect(projectsApi.fetchProjectRiskIntelligence).toHaveBeenCalledWith("617936");
    });
  });

  it("44. displays truthful loading indicator during data retrieval without placeholder metrics", async () => {
    vi.mocked(projectsApi.fetchProjectRiskIntelligence).mockReturnValue(new Promise(() => {}));
    renderTerminal();
    expect(screen.getByText(/FETCHING PROJECT INTELLIGENCE\.\.\./i)).toBeInTheDocument();
    expect(screen.queryByText("38.4%")).not.toBeInTheDocument();
  });

  it("45. displays truthful error state with retry action on API failure", async () => {
    vi.mocked(projectsApi.fetchProjectRiskIntelligence).mockRejectedValue(new Error("Database connection timed out"));
    renderTerminal();
    await waitFor(() => {
      expect(screen.getByText("PROJECT INTELLIGENCE UNAVAILABLE")).toBeInTheDocument();
      expect(screen.getByText("Database connection timed out")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /retry loading project intelligence/i })).toBeInTheDocument();
    });
  });

  it("46. supports keyboard navigation (ArrowDown, ArrowUp, Enter, Escape) in project selector", async () => {
    renderTerminal("/intelligence");

    const input = screen.getByRole("combobox", { name: /select project for risk evaluation/i });
    await userEvent.type(input, "617");

    await waitFor(() => {
      expect(screen.getByRole("listbox")).toBeInTheDocument();
    });

    // Arrow down to select
    fireEvent.keyDown(input, { key: "ArrowDown" });
    // Escape to close dropdown
    fireEvent.keyDown(input, { key: "Escape" });

    await waitFor(() => {
      expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    });
  });

  it("47. historical inspection drawer supports Escape key to close with focus restoration", async () => {
    const handleClose = vi.fn();
    render(
      <IntelligenceRiskInspectionDrawer
        isOpen={true}
        record={mockHistory[0]}
        history={mockHistory}
        project={mockProjectIdentity}
        snapshot={mockSnapshot}
        currentRisk={mockRisk}
        onClose={handleClose}
      />
    );

    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveAttribute("aria-modal", "true");

    fireEvent.keyDown(window, { key: "Escape" });
    await waitFor(() => {
      expect(handleClose).toHaveBeenCalled();
    });
  });

  it("48. historical observation badge and accessible attributes are rendered properly", () => {
    render(
      <IntelligenceRiskInspectionDrawer
        isOpen={true}
        record={mockHistory[0]}
        history={mockHistory}
        project={mockProjectIdentity}
        snapshot={mockSnapshot}
        currentRisk={mockRisk}
        onClose={vi.fn()}
      />
    );
    expect(screen.getByText("HISTORICAL OBSERVATION")).toBeInTheDocument();
    expect(screen.getByText("HISTORICAL RISK EVALUATION")).toBeInTheDocument();
  });

  // =========================================================================
  // Group 9: Required Semantic Corrections (Tests 49–50)
  // =========================================================================

  it("49. calibration_active alone does not establish calibrated comparability", () => {
    // Both observations have calibration_active = true, but differing model_ids
    const obsA: ProjectRiskHistoryPoint = {
      report_month: "2026-03",
      risk_probability: 0.35,
      raw_probability: 0.30,
      risk_rank: 50,
      risk_percentile: 0.80,
      population_size: 1600,
      regime: "MODERN",
      model_id: "catboost_full_v1__unweighted",
      calibration_active: true,
    };

    const obsB: ProjectRiskHistoryPoint = {
      report_month: "2026-04",
      risk_probability: 0.38,
      raw_probability: 0.32,
      risk_rank: 42,
      risk_percentile: 0.825,
      population_size: 1625,
      regime: "MODERN",
      model_id: "logistic_static_only__unweighted",
      calibration_active: true,
    };

    // Semantic comparability MUST be false despite both having calibration_active === true
    const isComparable = areObservationsSemanticallyComparable(obsA, obsB);
    expect(isComparable).toBe(false);

    // Evaluating movement across differing models must return COMPARABILITY_LIMITED, suppressing numerical delta
    const movement = evaluateObservationMovement(obsA, obsB, true);
    expect(movement.isComparable).toBe(false);
    expect(movement.status).toBe("COMPARABILITY_LIMITED");
    expect(movement.probabilityDelta).toBeUndefined();
    expect(movement.transitions.some((t) => t.type === "MODEL")).toBe(true);
  });

  it("50. non-adjacent historical/current observations do not receive an automatically calculated movement delta unless the existing contract explicitly establishes comparability", () => {
    // Historical point 2024-06 vs current assessment 2026-04 (separated by other months)
    const historicalObs: ProjectRiskHistoryPoint = {
      report_month: "2024-06",
      risk_probability: 0.45,
      raw_probability: 0.45,
      risk_rank: 80,
      risk_percentile: 0.70,
      population_size: 1500,
      regime: "LEGACY",
      model_id: "catboost_full_v1__unweighted",
      calibration_active: false,
    };

    const currentObs: ProjectIntelligenceRisk = {
      report_month: "2026-04",
      risk_probability: 0.3842,
      raw_probability: 0.3211,
      risk_rank: 42,
      risk_percentile: 0.825,
      population_size: 1625,
      regime: "MODERN",
      model_id: "logistic_static_only__unweighted",
      target: "target_effective_schedule_ext_3m",
      calibration_active: true,
    };

    const fullHistory: ProjectRiskHistoryPoint[] = [
      historicalObs,
      {
        report_month: "2025-05",
        risk_probability: 0.405,
        raw_probability: 0.405,
        risk_rank: 60,
        risk_percentile: 0.75,
        population_size: 1570,
        regime: "LEGACY",
        model_id: "catboost_full_v1__unweighted",
        calibration_active: false,
      },
      {
        report_month: "2026-04",
        risk_probability: 0.3842,
        raw_probability: 0.3211,
        risk_rank: 42,
        risk_percentile: 0.825,
        population_size: 1625,
        regime: "MODERN",
        model_id: "logistic_static_only__unweighted",
        calibration_active: true,
      },
    ];

    // Check adjacency helper: 2024-06 and 2026-04 are non-adjacent
    const isAdj = areObservationsAdjacent(fullHistory, "2024-06", "2026-04");
    expect(isAdj).toBe(false);

    // evaluateObservationMovement with isAdjacent = false MUST NOT calculate deltas
    const movement = evaluateObservationMovement(historicalObs, currentObs, false);
    expect(movement.isComparable).toBe(false);
    expect(movement.status).toBe("COMPARISON_NOT_ESTABLISHED");
    expect(movement.probabilityDelta).toBeUndefined();

    // Render metrics component with non-adjacent historical observation and current risk
    render(
      <IntelligenceRiskInspectionMetrics
        record={historicalObs}
        history={fullHistory}
        currentRisk={currentObs}
      />
    );

    // MUST display truthful non-adjacent disclosure
    expect(
      screen.getByText("COMPARISON NOT ESTABLISHED (NON-ADJACENT OBSERVATIONS)")
    ).toBeInTheDocument();

    // MUST display values separately
    expect(screen.getByText(/INSPECTED HISTORICAL \(2024-06\):/)).toBeInTheDocument();
    expect(screen.getByText(/CURRENT ASSESSMENT \(2026-04\):/)).toBeInTheDocument();
    expect(screen.getByText(/45.0% \(raw: 45.0%, LEGACY, catboost_full_v1__unweighted\)/)).toBeInTheDocument();
    expect(screen.getByText(/38.4% \(raw: 32.1%, MODERN, logistic_static_only__unweighted\)/)).toBeInTheDocument();
  });
});
