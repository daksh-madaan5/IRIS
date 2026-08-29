import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { history, riskRecord } from "../test/fixtures";
import { ProjectDetail } from "./ProjectDetail";

describe("ProjectDetail", () => {
  it("renders exact project identity, score, explanation, and chronological history", () => {
    render(<ProjectDetail project={riskRecord()} history={history} />);
    expect(screen.getByRole("heading", { name: "National Highway Capacity Expansion" })).toBeInTheDocument();
    expect(screen.getAllByText("94.0%").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("Months to effective schedule")).toBeInTheDocument();
    const historyItems = screen.getByRole("list", { name: "Chronological exact-ID risk history" }).children;
    expect(historyItems[0]).toHaveTextContent("March 2026");
    expect(historyItems[1]).toHaveTextContent("April 2026");
  });

  it("preserves missing metadata and includes the non-causal disclaimer", () => {
    const { container } = render(<ProjectDetail project={riskRecord({ ministry: null, state: null })} history={history} />);
    expect((container.textContent?.match(/Not reported/g) ?? []).length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("Contributors explain the model prediction and should not be interpreted as causal effects.")).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/red\/amber\/green|risk band|authoritative threshold/i);
  });
});
