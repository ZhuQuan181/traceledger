import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "./api";
import App from "./App";
import type { Payload, RunRow } from "./types";

vi.mock("./api", () => ({
  fetchModels: vi.fn(),
  fetchHistory: vi.fn(),
  loadRun: vi.fn(),
  runDemo: vi.fn(),
  runUpload: vi.fn(),
}));

const run: RunRow = {
  id: "abc123",
  created_at: "2026-11-15T09:00:00+08:00",
  source: "flows.csv",
  dataset_hash: "deadbeef",
  split: "random",
  rows: 120,
  best_model: "mlp",
  best_auc: 0.93,
};

const payload = {
  run_id: "abc123",
  dataset: {
    source: "flows.csv",
    rows: 120,
    train: 84,
    test: 36,
    hash: "deadbeef",
    split: "random",
    split_requested: "temporal",
    split_fallback: true,
    threshold: 0.4,
    seed: 7,
    labels: { mode: "embedded", labelled: 120, total: 120 },
    features: { used: ["bytes_per_s"], encoded: 1 },
    classes: [],
    engineering: { min_duration_ms: 1 },
    format: { format: "csv" },
  },
  experiment: {
    models: ["mlp"],
    split: "temporal",
    split_effective: "random",
    test_size: 0.25,
    seed: 7,
    threshold: 0.4,
    explain: true,
    ablate: null,
    source_kind: "upload",
    source_ref: "flows.csv",
    normal: 1000,
    attack: 100,
    leaky: false,
    source: "flows.csv",
    command: "uv run flowlab run flows.csv --seed 7",
  },
  generated_at: "2026-11-15T09:00:00+08:00",
  experiment_fingerprint: "fingerprint",
  verdict: { level: "warn", headline: "需说明", reasons: [], checks: [] },
  checklist: [],
  warnings: [],
  results: [{
    model: "mlp",
    kind: "supervised",
    metrics: {
      auc: 0.93, pr_auc: 0.91, accuracy: 0.9, precision: 0.9,
      recall: 0.8, f1: 0.85, fpr: 0.01, support: 36, attack_support: 8,
    },
    confusion: { tn: 28, fp: 0, fn: 2, tp: 6 },
    duration_s: 0.1,
    params: {},
    split: "random",
    split_requested: "temporal",
    dataset_hash: "deadbeef",
    n_train: 84,
    n_test: 36,
    threshold: 0.4,
    top_flows: [],
    score_curve: [],
    by_label: [],
    false_positives: [],
    false_negatives: [],
    source_ranking: [],
  }],
  best_model: "mlp",
  top_flows: [],
  score_curve: [],
  investigation: { by_label: [], false_positives: [], false_negatives: [], source_ranking: [] },
  report_md: "# report",
  report_html: "<html></html>",
} as Payload;

describe("App history restore", () => {
  beforeEach(() => {
    vi.mocked(api.fetchModels).mockResolvedValue([{ name: "mlp", kind: "supervised" }]);
    vi.mocked(api.fetchHistory).mockResolvedValue([run]);
    vi.mocked(api.loadRun).mockResolvedValue(payload);
  });

  it("restores parameters and refuses to silently rerun an unavailable uploaded file", async () => {
    const user = userEvent.setup();
    render(<App />);
    const chip = await screen.findByTitle(/flows\.csv/);
    await user.click(chip);

    await waitFor(() => {
      expect(screen.getByText(/这次实验来自上传文件「flows\.csv」/)).toBeInTheDocument();
    });
    expect(screen.getByRole("spinbutton", { name: "随机种子" })).toHaveValue(7);
    expect(screen.getByRole("spinbutton", { name: "测试集比例" })).toHaveValue(0.25);
    expect(screen.getByRole("button", { name: "运行实验" })).toBeDisabled();
  });

  it("shows a failed run outside the mobile configuration drawer", async () => {
    vi.mocked(api.runDemo).mockRejectedValue(new Error("数据校验失败"));
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "用当前配置跑一次" }));

    const alerts = await screen.findAllByRole("alert");
    expect(alerts.some((alert) => alert.textContent?.includes("数据校验失败"))).toBe(true);
    expect(screen.getByRole("button", { name: "关闭错误提示" })).toBeInTheDocument();
  });

  it("does not start a second experiment while one is in flight", async () => {
    vi.mocked(api.runDemo).mockResolvedValue(payload);
    render(<App />);
    const run = await screen.findByRole("button", { name: "用当前配置跑一次" });

    fireEvent.click(run);
    fireEvent.click(run);

    await waitFor(() => expect(api.runDemo).toHaveBeenCalledTimes(1));
  });
});
