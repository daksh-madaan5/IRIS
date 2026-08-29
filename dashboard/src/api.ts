import type {
  ApiErrorShape,
  DashboardFilters,
  DashboardOptions,
  HistoryResponse,
  ProjectListResponse,
  RiskRecord,
  SummaryResponse,
} from "./types";

const API_BASE = import.meta.env.VITE_IRIS_API_BASE ?? "/api";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`);
  } catch {
    throw new ApiError(
      "IRIS risk service is unavailable. Start the FastAPI service and try again.",
      0,
    );
  }
  if (!response.ok) {
    let body: ApiErrorShape = {};
    try {
      body = (await response.json()) as ApiErrorShape;
    } catch {
      // Preserve the stable fallback below for non-JSON upstream failures.
    }
    throw new ApiError(body.detail ?? "The risk service could not complete the request.", response.status);
  }
  return (await response.json()) as T;
}

function query(params: Record<string, string | number | undefined>): string {
  const values = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") values.set(key, String(value));
  });
  return values.toString();
}

function filterParams(filters: DashboardFilters): Record<string, string | undefined> {
  return {
    regime: filters.regime || undefined,
    sector: filters.sector || undefined,
    agency: filters.agency || undefined,
    ministry: filters.ministry || undefined,
    state: filters.state || undefined,
    search: filters.search.trim() || undefined,
  };
}

export const irisApi = {
  options(reportMonth?: string) {
    const suffix = reportMonth ? `?${query({ report_month: reportMonth })}` : "";
    return request<DashboardOptions>(`/risk/options${suffix}`);
  },
  projects(reportMonth: string, filters: DashboardFilters, page: number, pageSize = 25) {
    return request<ProjectListResponse>(
      `/risk/projects?${query({
        report_month: reportMonth,
        page,
        page_size: pageSize,
        ...filterParams(filters),
      })}`,
    );
  },
  summary(reportMonth: string, filters: DashboardFilters) {
    return request<SummaryResponse>(
      `/risk/summary?${query({
        report_month: reportMonth,
        top_n: 10,
        ...filterParams(filters),
      })}`,
    );
  },
  project(projectCode: string, reportMonth: string) {
    return request<RiskRecord>(
      `/risk/project/${encodeURIComponent(projectCode)}?${query({ report_month: reportMonth })}`,
    );
  },
  history(projectCode: string) {
    return request<HistoryResponse>(
      `/risk/project/${encodeURIComponent(projectCode)}/history`,
    );
  },
};
