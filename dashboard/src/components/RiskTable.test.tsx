import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { riskRecord } from "../test/fixtures";
import { RiskTable } from "./RiskTable";

describe("RiskTable", () => {
  it("preserves API ranking order and opens the selected project", async () => {
    const onSelect = vi.fn();
    render(<RiskTable projects={{
      report_month: "2026-04", page: 1, page_size: 25, total: 2,
      items: [
        riskRecord({ project_code: "TOP001", project_name: "First ranked project", risk_rank: 1 }),
        riskRecord({ project_code: "NEXT02", project_name: "Second ranked project", risk_rank: 2 }),
      ],
    }} selectedCode={null} onSelect={onSelect} onPage={vi.fn()} />);
    const rows = screen.getAllByRole("row").slice(1);
    expect(within(rows[0]).getByText("First ranked project")).toBeInTheDocument();
    expect(within(rows[1]).getByText("Second ranked project")).toBeInTheDocument();
    await userEvent.click(within(rows[0]).getByRole("button", { name: "Open project TOP001" }));
    expect(onSelect).toHaveBeenCalledWith("TOP001");
  });
});
