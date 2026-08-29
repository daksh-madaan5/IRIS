import { ChevronLeft, ChevronRight, ExternalLink } from "lucide-react";
import { percentile, probability, reported } from "../format";
import type { ProjectListResponse } from "../types";

interface RiskTableProps {
  projects: ProjectListResponse;
  selectedCode: string | null;
  onSelect: (projectCode: string) => void;
  onPage: (page: number) => void;
}

export function RiskTable({ projects, selectedCode, onSelect, onPage }: RiskTableProps) {
  const pages = Math.ceil(projects.total / projects.page_size);
  return (
    <section className="panel ranked-panel" aria-labelledby="ranked-heading">
      <div className="panel-heading table-heading">
        <div><p className="eyebrow">Ranked risks</p><h2 id="ranked-heading">Project watchlist</h2></div>
        <span>{projects.total.toLocaleString("en-IN")} matching projects · rank 1 is highest</span>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Rank</th><th>Project</th><th>Code</th><th>Agency</th><th>Sector</th><th>State</th>
              <th className="numeric">Probability</th><th className="numeric">Percentile</th><th>Calibration</th><th><span className="sr-only">Open</span></th>
            </tr>
          </thead>
          <tbody>
            {projects.items.map((item) => (
              <tr
                key={`${item.project_code}-${item.report_month}`}
                className={selectedCode === item.project_code ? "selected-row" : ""}
                onClick={() => onSelect(item.project_code)}
              >
                <td><span className="rank-number">{item.risk_rank}</span></td>
                <td className="project-cell"><strong>{reported(item.project_name)}</strong></td>
                <td><code>{item.project_code}</code></td>
                <td>{reported(item.agency)}</td>
                <td>{reported(item.sector)}</td>
                <td>{reported(item.state)}</td>
                <td className="numeric probability-cell">{probability(item.risk_probability)}</td>
                <td className="numeric">{percentile(item.risk_percentile)}</td>
                <td><span className="status-text">{item.calibration_active ? "Active" : "Inactive"}</span></td>
                <td><button aria-label={`Open project ${item.project_code}`} onClick={(event) => { event.stopPropagation(); onSelect(item.project_code); }}><ExternalLink size={15} /></button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="pagination">
        <span>Page {projects.page} of {pages}</span>
        <div>
          <button aria-label="Previous page" disabled={projects.page === 1} onClick={() => onPage(projects.page - 1)}><ChevronLeft size={17} /></button>
          <button aria-label="Next page" disabled={projects.page >= pages} onClick={() => onPage(projects.page + 1)}><ChevronRight size={17} /></button>
        </div>
      </div>
    </section>
  );
}
