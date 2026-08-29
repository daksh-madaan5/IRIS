import { afterEach, describe, expect, it, vi } from "vitest";
import { irisApi } from "./api";
import { riskRecord } from "./test/fixtures";
import type { DashboardFilters } from "./types";

const filters: DashboardFilters = {
  regime: "MODERN",
  sector: "Roads & Highways",
  agency: "",
  ministry: "",
  state: "Telangana",
  search: " 617936 ",
};

afterEach(() => vi.restoreAllMocks());

function respond(body: unknown) {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } }),
  );
}

describe("IRIS API integration contract", () => {
  it("keeps report-month and display filters in the FastAPI request", async () => {
    respond({ report_month: "2026-03", page: 2, page_size: 25, total: 1, items: [] });
    await irisApi.projects("2026-03", filters, 2);
    const url = String(vi.mocked(fetch).mock.calls[0][0]);
    expect(url).toContain("report_month=2026-03");
    expect(url).toContain("sector=Roads+%26+Highways");
    expect(url).toContain("state=Telangana");
    expect(url).toContain("search=617936");
    expect(url).toContain("page=2");
  });

  it("requests history for the literal source identifier only", async () => {
    respond({ project_code: "N06000087", regime_filter: null, count: 0, items: [] });
    await irisApi.history("N06000087");
    expect(fetch).toHaveBeenCalledWith("/api/risk/project/N06000087/history");
  });

  it("accepts project detail metadata without transforming source values", async () => {
    const record = riskRecord({ agency: "ministry of housing and urban affairs" });
    respond(record);
    const result = await irisApi.project("617936", "2026-04");
    expect(result.agency).toBe("ministry of housing and urban affairs");
    expect(result.risk_probability).toBe(0.94);
    expect(result.risk_rank).toBe(1);
  });
});
