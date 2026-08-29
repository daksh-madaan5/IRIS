import { useEffect, useMemo, useState } from "react";
import { AlertCircle, Building2, RefreshCw, Shield } from "lucide-react";
import { irisApi } from "./api";
import { FilterBar } from "./components/FilterBar";
import { PortfolioOverview } from "./components/PortfolioOverview";
import { ProjectDetail } from "./components/ProjectDetail";
import { RiskTable } from "./components/RiskTable";
import { monthLabel } from "./format";
import type {
  DashboardFilters,
  DashboardOptions,
  HistoryResponse,
  ProjectListResponse,
  RiskRecord,
  SummaryResponse,
} from "./types";

const emptyFilters: DashboardFilters = {
  regime: "",
  sector: "",
  agency: "",
  ministry: "",
  state: "",
  search: "",
};

function App() {
  const [options, setOptions] = useState<DashboardOptions | null>(null);
  const [month, setMonth] = useState("");
  const [filters, setFilters] = useState<DashboardFilters>(emptyFilters);
  const [page, setPage] = useState(1);
  const [summary, setSummary] = useState<SummaryResponse | null>(null);
  const [projects, setProjects] = useState<ProjectListResponse | null>(null);
  const [selectedCode, setSelectedCode] = useState<string | null>(null);
  const [detail, setDetail] = useState<RiskRecord | null>(null);
  const [history, setHistory] = useState<HistoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    irisApi.options()
      .then((response) => {
        if (!active) return;
        setOptions(response);
        setMonth(response.default_report_month);
      })
      .catch((reason: Error) => active && setError(reason.message))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!month) return;
    let active = true;
    irisApi.options(month).then((response) => active && setOptions(response)).catch(() => undefined);
    return () => { active = false; };
  }, [month]);

  useEffect(() => {
    if (!month) return;
    let active = true;
    setLoading(true);
    setError(null);
    Promise.all([
      irisApi.summary(month, filters),
      irisApi.projects(month, filters, page),
    ])
      .then(([summaryResponse, projectResponse]) => {
        if (!active) return;
        setSummary(summaryResponse);
        setProjects(projectResponse);
        if (!selectedCode && projectResponse.items.length) {
          setSelectedCode(projectResponse.items[0].project_code);
        }
      })
      .catch((reason: Error) => {
        if (!active) return;
        setSummary(null);
        setProjects(null);
        setError(reason.message);
      })
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [month, filters, page]); // selectedCode intentionally does not refetch the portfolio.

  useEffect(() => {
    if (!selectedCode || !month) return;
    let active = true;
    setDetailLoading(true);
    setDetailError(null);
    Promise.all([irisApi.project(selectedCode, month), irisApi.history(selectedCode)])
      .then(([record, historyResponse]) => {
        if (!active) return;
        setDetail(record);
        setHistory(historyResponse);
      })
      .catch((reason: Error) => {
        if (!active) return;
        setDetail(null);
        setHistory(null);
        setDetailError(reason.message);
      })
      .finally(() => active && setDetailLoading(false));
    return () => { active = false; };
  }, [selectedCode, month]);

  const regimeLabel = useMemo(() => {
    if (!summary) return "—";
    return summary.regimes.map((item) => item.regime === "LEGACY" ? "Legacy" : "Modern").join(" + ");
  }, [summary]);

  const updateFilters = (next: DashboardFilters) => {
    setPage(1);
    setFilters(next);
  };

  const changeMonth = (nextMonth: string) => {
    setMonth(nextMonth);
    setPage(1);
    setFilters(emptyFilters);
    setSelectedCode(null);
    setDetail(null);
    setHistory(null);
  };

  const retry = () => {
    if (month) {
      setFilters({ ...filters });
    } else {
      window.location.reload();
    }
  };

  if (!options && error && !month) {
    return (
      <main className="fatal-state">
        <div className="brand-mark"><Building2 size={28} /></div>
        <p className="eyebrow">IRIS service connection</p>
        <h1>Risk intelligence is temporarily unavailable</h1>
        <p>{error}</p>
        <button type="button" onClick={retry}><RefreshCw size={16} /> Try again</button>
      </main>
    );
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand">
          <div className="brand-mark"><Building2 size={24} aria-hidden="true" /></div>
          <div><strong>IRIS</strong><span>Infrastructure Risk Intelligence System</span></div>
        </div>
        <div className="header-context">
          <span><Shield size={14} /> Decision support</span>
          <small>Schedule extension risk · 3-month horizon</small>
        </div>
      </header>

      <main>
        <section className="command-bar" aria-label="Report context">
          <div>
            <p className="eyebrow">Monthly infrastructure monitor</p>
            <h1>Project risk overview</h1>
          </div>
          <div className="context-controls">
            <label>
              <span>Report month</span>
              <select aria-label="Report month" value={month} onChange={(event) => changeMonth(event.target.value)}>
                {(options?.report_months ?? []).slice().reverse().map((value) => <option key={value} value={value}>{monthLabel(value)}</option>)}
              </select>
            </label>
            <div className="regime-indicator"><span>Source regime</span><strong>{regimeLabel}</strong></div>
          </div>
        </section>

        {options && <FilterBar filters={filters} options={options} onChange={updateFilters} onReset={() => updateFilters(emptyFilters)} />}

        {loading && !summary && <section className="loading-state" aria-live="polite"><span /><div><strong>Loading locked risk records</strong><p>Retrieving portfolio ranks and explanations from IRIS.</p></div></section>}

        {error && !loading && (
          <section className="inline-state" role="alert"><AlertCircle size={20} /><div><strong>No portfolio results to show</strong><p>{error}</p></div><button onClick={retry}>Retry</button></section>
        )}

        {summary && <PortfolioOverview summary={summary} />}

        {projects && (
          <RiskTable projects={projects} selectedCode={selectedCode} onSelect={setSelectedCode} onPage={setPage} />
        )}

        {detailLoading && selectedCode && <section className="detail-loading" aria-live="polite">Loading project {selectedCode}…</section>}
        {detailError && !detailLoading && <section className="inline-state" role="alert"><AlertCircle size={20} /><div><strong>Project record unavailable</strong><p>{detailError}</p></div></section>}
        {detail && history && !detailLoading && <ProjectDetail project={detail} history={history} />}

        <aside className="method-note">
          <strong>Interpretation boundary</strong>
          <p>IRIS displays locked model estimates and within-month ranks. It does not apply an operational threshold, infer completion from disappearance, or link Legacy and Modern project identifiers.</p>
        </aside>
      </main>
      <footer><span>IRIS · Infrastructure monitoring decision support</span><span>Exact source identifiers · Missing values remain missing</span></footer>
    </div>
  );
}

export default App;
