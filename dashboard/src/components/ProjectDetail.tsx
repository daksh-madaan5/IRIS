import { CalendarRange, Info, Landmark, MapPin, Network, ShieldCheck } from "lucide-react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { modelLabel, monthLabel, percentile, probability, reported } from "../format";
import type { Contributor, HistoryResponse, RiskRecord } from "../types";

interface ProjectDetailProps {
  project: RiskRecord;
  history: HistoryResponse;
}

function ContributorList({ title, items, kind }: { title: string; items: Contributor[]; kind: "positive" | "negative" }) {
  const max = Math.max(...items.map((item) => Math.abs(item.contribution)), 0.001);
  return (
    <div className="contributor-side">
      <h4>{title}</h4>
      {items.length === 0 ? <p className="muted">No contributors in this direction.</p> : items.map((item) => (
        <div className="contributor" key={item.feature}>
          <div className="contributor-label"><span>{item.display_name}</span><strong>{item.contribution > 0 ? "+" : ""}{item.contribution.toFixed(3)}</strong></div>
          <div className="contributor-value">Feature value: {item.value ?? "Not reported"}</div>
          <div className="contributor-track"><span className={kind} style={{ width: `${Math.max(3, Math.abs(item.contribution) / max * 100)}%` }} /></div>
        </div>
      ))}
    </div>
  );
}

export function ProjectDetail({ project, history }: ProjectDetailProps) {
  const historyData = history.items.map((item) => ({
    month: item.report_month,
    label: monthLabel(item.report_month).replace(" ", " ’").slice(0, 9),
    probability: Number((item.risk_probability * 100).toFixed(2)),
    rank: item.risk_rank,
  }));
  return (
    <section className="detail-section" aria-labelledby="detail-heading">
      <div className="detail-identity">
        <div>
          <p className="eyebrow">Project intelligence · exact source ID</p>
          <h2 id="detail-heading">{reported(project.project_name)}</h2>
          <div className="identity-code"><code>{project.project_code}</code><span>{monthLabel(project.report_month)}</span></div>
        </div>
        <div className="detail-score">
          <span>Risk probability</span>
          <strong>{probability(project.risk_probability)}</strong>
          <small>{percentile(project.risk_percentile)} percentile · rank {project.risk_rank} of {project.population_size}</small>
        </div>
      </div>
      <div className="metadata-grid">
        <div><Landmark size={16} /><span>Ministry / agency</span><strong>{reported(project.ministry)}<br />{reported(project.agency)}</strong></div>
        <div><Network size={16} /><span>Sector</span><strong>{reported(project.sector)}</strong></div>
        <div><MapPin size={16} /><span>State</span><strong>{reported(project.state)}</strong></div>
        <div><ShieldCheck size={16} /><span>Model / regime</span><strong>{modelLabel(project.model_id)}<br />{project.regime}</strong></div>
        <div><CalendarRange size={16} /><span>Calibration</span><strong>{project.calibration_active ? "Active · temporal Platt" : "Inactive · raw model probability"}</strong></div>
      </div>
      <div className="detail-grid">
        <article className="panel contributor-panel">
          <div className="panel-heading"><div><p className="eyebrow">Prediction explanation</p><h3>Top contributors</h3></div><span>Raw margin / logit</span></div>
          <div className="disclaimer"><Info size={16} /><p>Contributors explain the model prediction and should not be interpreted as causal effects.</p></div>
          <div className="contributor-grid">
            <ContributorList title="Raised predicted risk" items={project.top_positive_contributors} kind="positive" />
            <ContributorList title="Reduced predicted risk" items={project.top_negative_contributors} kind="negative" />
          </div>
        </article>
        <article className="panel history-panel">
          <div className="panel-heading"><div><p className="eyebrow">Exact-ID history</p><h3>Risk over time</h3></div><span>{history.count} observed months</span></div>
          <div className="history-chart" aria-label={`Risk history for exact project code ${project.project_code}`}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={historyData} margin={{ top: 14, right: 16, bottom: 4, left: -16 }}>
                <CartesianGrid stroke="#e0e7e8" vertical={false} />
                <XAxis dataKey="month" tick={{ fontSize: 11, fill: "#60727c" }} tickLine={false} axisLine={false} />
                <YAxis domain={[0, 100]} tickFormatter={(value) => `${value}%`} tick={{ fontSize: 11, fill: "#60727c" }} tickLine={false} axisLine={false} />
                <Tooltip formatter={(value) => [`${value}%`, "Risk probability"]} labelFormatter={(value) => monthLabel(String(value))} />
                <Line type="monotone" dataKey="probability" stroke="#c86a3a" strokeWidth={2.5} dot={{ r: 3, fill: "#fff", strokeWidth: 2 }} activeDot={{ r: 5 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <ol className="history-list" aria-label="Chronological exact-ID risk history">
            {history.items.map((item) => <li key={item.report_month}><span>{monthLabel(item.report_month)}</span><strong>{probability(item.risk_probability)}</strong><small>Rank {item.risk_rank}/{item.population_size}</small></li>)}
          </ol>
          <p className="chart-footnote">History contains this literal project code only. Gaps or disappearance do not imply completion.</p>
        </article>
      </div>
    </section>
  );
}
