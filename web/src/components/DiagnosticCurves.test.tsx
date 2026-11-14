import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DiagnosticCurves } from "./DiagnosticCurves";
import type { Result } from "../types";

function result(overrides: Partial<Result>): Result {
  return {
    model: "mlp",
    kind: "supervised",
    roc_curve: [
      { fpr: 0, tpr: 0, threshold: null },
      { fpr: 0.1, tpr: 0.8, threshold: 0.7 },
      { fpr: 1, tpr: 1, threshold: 0 },
    ],
    pr_curve: [
      { recall: 0, precision: 1, threshold: 1 },
      { recall: 0.8, precision: 0.9, threshold: 0.7 },
      { recall: 1, precision: 0.4, threshold: 0 },
    ],
    calibration: [
      { mean_predicted: 0.1, fraction_positive: 0.08 },
      { mean_predicted: 0.8, fraction_positive: 0.76 },
    ],
    brier_score: 0.1234,
    calibration_note: "监督模型输出概率，可参考校准曲线与 Brier score。",
    ...overrides,
  } as Result;
}

describe("DiagnosticCurves", () => {
  it("renders ROC, PR and calibration with Brier for a supervised model", () => {
    render(<DiagnosticCurves result={result({})} />);
    expect(screen.getByText("排序与校准")).toBeInTheDocument();
    expect(screen.getByText("Brier 0.1234")).toBeInTheDocument();
    expect(screen.getAllByRole("img")).toHaveLength(3);
    expect(screen.getByRole("img", { name: "ROC曲线" })).toBeInTheDocument();
    expect(screen.getByText(/监督模型输出概率/)).toBeInTheDocument();
  });

  it("keeps the probability caveat and hides Brier for anomaly scores", () => {
    render(
      <DiagnosticCurves
        result={result({
          kind: "unsupervised",
          calibration: [],
          brier_score: null,
          calibration_note: "无监督模型输出异常分数，不是概率；不计算 Brier 与校准曲线。",
        })}
      />,
    );
    expect(screen.queryByText(/^Brier /)).not.toBeInTheDocument();
    expect(screen.getAllByRole("img")).toHaveLength(2);
    expect(screen.getByText(/不是概率/)).toBeInTheDocument();
  });

  it("renders nothing when curve data is unavailable", () => {
    const { container } = render(
      <DiagnosticCurves
        result={result({ roc_curve: [], pr_curve: [], calibration: [], brier_score: null })}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});
