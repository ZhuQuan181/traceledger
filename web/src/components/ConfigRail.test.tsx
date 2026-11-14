import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ConfigRail } from "./ConfigRail";

function props() {
  return {
    models: [
      { name: "mlp", kind: "supervised" },
      { name: "iforest", kind: "unsupervised" },
    ],
    selected: ["mlp"],
    onToggleModel: vi.fn(),
    source: "demo" as const,
    onSource: vi.fn(),
    normal: 5000,
    attack: 500,
    onNormal: vi.fn(),
    onAttack: vi.fn(),
    leaky: false,
    onLeaky: vi.fn(),
    split: "temporal" as const,
    onSplit: vi.fn(),
    testSize: 0.3,
    onTestSize: vi.fn(),
    validationSize: 0.2,
    onValidationSize: vi.fn(),
    seed: 42,
    onSeed: vi.fn(),
    threshold: 0.5,
    onThreshold: vi.fn(),
    thresholdMode: "fixed" as const,
    onThresholdMode: vi.fn(),
    targetFpr: 0.01,
    onTargetFpr: vi.fn(),
    ablate: "",
    onAblate: vi.fn(),
    ablationColumns: [],
    file: null,
    onFile: vi.fn(),
    labelsFile: null,
    onLabelsFile: vi.fn(),
    allowPickle: false,
    onAllowPickle: vi.fn(),
    busy: false,
    onRun: vi.fn(),
    error: null,
    notice: null,
    onCloseMobile: vi.fn(),
    mobileOpen: false,
  };
}

describe("ConfigRail", () => {
  it("uses native radio groups and updates the split mode", async () => {
    const user = userEvent.setup();
    const p = props();
    render(<ConfigRail {...p} />);
    expect(screen.getByRole("radio", { name: "时间切分" })).toBeChecked();

    await user.click(screen.getByRole("radio", { name: "随机切分" }));
    expect(p.onSplit).toHaveBeenCalledWith("random");
  });

  it("accepts Zeek logs for data but not pickle label sidecars", () => {
    const p = { ...props(), source: "file" as const };
    const { container } = render(<ConfigRail {...p} />);
    const dataInput = container.querySelector<HTMLInputElement>('input[name="flow-file"]');
    const labelInput = container.querySelector<HTMLInputElement>('input[name="labels-file"]');
    expect(dataInput?.accept).toContain(".log");
    expect(dataInput?.accept).toContain(".pcap");
    expect(labelInput?.accept).not.toContain(".pkl");
  });

  it("shows the historical-upload notice next to the run action", () => {
    render(<ConfigRail {...props()} notice="请重新选择原文件" />);
    expect(screen.getByText("请重新选择原文件")).toBeInTheDocument();
  });

  it("exposes the validation-only target false-positive threshold", () => {
    const p = { ...props(), thresholdMode: "fpr" as const };
    render(<ConfigRail {...p} />);
    expect(screen.getByRole("slider", { name: "目标误报率" })).toHaveValue("0.01");
    expect(screen.getByText(/验证集上选择满足目标误报率/)).toBeInTheDocument();
  });
});
