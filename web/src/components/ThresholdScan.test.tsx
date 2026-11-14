import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ThresholdScan } from "./ThresholdScan";

describe("ThresholdScan", () => {
  it("shows deployment tradeoffs and highlights the nearest threshold", () => {
    const { container } = render(
      <ThresholdScan
        active={0.52}
        rows={[
          { threshold: 0.3, precision: 0.8, recall: 0.95, f1: 0.87, fpr: 0.08 },
          { threshold: 0.5, precision: 0.9, recall: 0.8, f1: 0.85, fpr: 0.03 },
          { threshold: 0.7, precision: 0.95, recall: 0.5, f1: 0.65, fpr: 0.01 },
        ]}
      />,
    );
    expect(screen.getByText("阈值权衡")).toBeInTheDocument();
    expect(container.querySelector("tr.on")?.textContent).toContain("0.50");
    expect(screen.getByText(/测试集只用于报告/)).toBeInTheDocument();
  });
});
