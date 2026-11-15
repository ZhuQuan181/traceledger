import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "./api";
import App from "./App";
import type { Job, Payload, PreflightResult, RunRow, ScorePayload } from "./types";

vi.mock("./api", () => ({
  cancelJob: vi.fn(),
  createDemoJob: vi.fn(),
  createScoreJob: vi.fn(),
  createUploadJob: vi.fn(),
  fetchActiveJobs: vi.fn(),
  fetchComparison: vi.fn(),
  fetchJob: vi.fn(),
  fetchJobResult: vi.fn(),
  fetchModels: vi.fn(),
  fetchHistory: vi.fn(),
  fetchHistoryPage: vi.fn(),
  deleteRun: vi.fn(),
  pruneHistory: vi.fn(),
  loadRun: vi.fn(),
  preflightUpload: vi.fn(),
  updateRunMeta: vi.fn(),
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
    train: 60,
    validation: 24,
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
    validation_size: 0.2,
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
    validation_metrics: {
      auc: 0.92, pr_auc: 0.9, accuracy: 0.9, precision: 0.9,
      recall: 0.8, f1: 0.85, fpr: 0.02, support: 24, attack_support: 5,
    },
    confusion: { tn: 28, fp: 0, fn: 2, tp: 6 },
    validation_confusion: { tn: 18, fp: 1, fn: 1, tp: 4 },
    duration_s: 0.1,
    params: {},
    split: "random",
    split_requested: "temporal",
    dataset_hash: "deadbeef",
    n_train: 60,
    n_validation: 24,
    n_test: 36,
    threshold: 0.4,
    top_flows: [],
    score_curve: [],
    score_curve_basis: "order",
    by_label: [],
    false_positives: [],
    false_negatives: [],
    source_ranking: [],
  }],
  best_model: "mlp",
  top_flows: [],
  score_curve: [],
  score_curve_basis: "order",
  investigation: { by_label: [], false_positives: [], false_negatives: [], source_ranking: [] },
  report_md: "# report",
  report_html: "<html></html>",
} as Payload;

const runningJob: Job = {
  job_id: "job123456789",
  kind: "demo",
  status: "running",
  phase: "model",
  completed_models: 1,
  total_models: 3,
  percent: 42,
  message: "训练与评分",
  elapsed_s: 3.2,
  run_id: null,
  error: null,
  has_ablation: false,
  result_available: false,
  created_at: "2026-11-15T09:00:00+08:00",
  started_at: "2026-11-15T09:00:01+08:00",
  finished_at: null,
};

const succeededJob: Job = {
  ...runningJob,
  status: "succeeded",
  phase: "done",
  completed_models: 3,
  percent: 100,
  message: "实验完成，结果已保存",
  run_id: "abc123",
  finished_at: "2026-11-15T09:00:08+08:00",
};

const scorePayload: ScorePayload = {
  mode: "score",
  generated_at: "2026-11-15T09:00:08+08:00",
  source: "flows.csv",
  dataset: {
    source: "flows.csv",
    rows: 120,
    columns: 8,
    hash: "deadbeef",
    format: { format: "csv" },
  },
  model: { name: "iforest", kind: "unsupervised" },
  top: [
    {
      score: 0.97,
      src_ip: "10.0.0.1",
      dst_ip: "10.0.0.2",
      src_port: 54321,
      dst_port: 443,
      protocol: 6,
      timestamp: "2026-11-15 09:00:00",
      bytes_per_s: 1200,
      packets_per_s: 12,
    },
  ],
  summary: {
    returned: 1,
    scored_rows: 120,
    max_score: 0.97,
    median_top_score: 0.97,
    p95_top_score: 0.97,
  },
  warnings: [],
  note: "无标签模式只做可疑度排序，不计算 AUC、F1 或误报率。",
};

const preflightResult: PreflightResult = {
  source: "flows.csv",
  dataset: { rows: 120, columns: 10, features: 8, hash: "deadbeef" },
  column_mapping: [
    {
      original: "Source IP",
      normalized: "source_ip",
      canonical: "src_ip",
      mapped: true,
      role: "源 IP",
    },
  ],
  checks: [
    {
      key: "labels",
      label: "标签",
      status: "pass",
      scope: "evaluation",
      detail: "BENIGN 90 行，攻击 30 行。",
      hint: null,
    },
  ],
  missing: { cells: 0, columns: [] },
  non_finite: { cells: 0, columns: {} },
  timestamp: { column: "timestamp", parse_rate: 1, invalid: 0 },
  labels: {
    present: true,
    missing: 0,
    benign: 90,
    attack: 30,
    classes: [
      { label: "BENIGN", count: 90, kind: "benign" },
      { label: "DDoS", count: 30, kind: "attack" },
    ],
  },
  split: {
    requested: "temporal",
    effective: "temporal",
    fell_back: false,
    coverage: [
      { split: "train", rows: 60, benign: 45, attack: 15 },
      { split: "validation", rows: 24, benign: 18, attack: 6 },
      { split: "test", rows: 36, benign: 27, attack: 9 },
    ],
    entity_key: "5-tuple",
    warnings: [],
  },
  ready_for_evaluation: true,
  ready_for_scoring: true,
  blockers: { evaluation: [], scoring: [] },
};

describe("App history restore", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    vi.mocked(api.fetchModels).mockResolvedValue([
      { name: "iforest", kind: "unsupervised" },
      { name: "mlp", kind: "supervised" },
    ]);
    vi.mocked(api.fetchHistory).mockResolvedValue([run]);
    vi.mocked(api.fetchActiveJobs).mockResolvedValue([]);
    vi.mocked(api.fetchHistoryPage).mockResolvedValue({
      runs: [{ ...run, note: "removed dst_port", status: "unreviewed" }],
      total: 1,
      available: 1,
      db_bytes: 4096,
      models: ["mlp"],
    });
    vi.mocked(api.loadRun).mockResolvedValue(payload);
    vi.mocked(api.createDemoJob).mockResolvedValue(runningJob);
    vi.mocked(api.createScoreJob).mockResolvedValue({ ...runningJob, kind: "score" });
    vi.mocked(api.createUploadJob).mockResolvedValue({ ...runningJob, kind: "upload" });
    vi.mocked(api.preflightUpload).mockResolvedValue(preflightResult);
    vi.mocked(api.fetchJob).mockResolvedValue(succeededJob);
    vi.mocked(api.fetchJobResult).mockResolvedValue(scorePayload);
    vi.mocked(api.cancelJob).mockResolvedValue({ ...runningJob, status: "cancelling" });
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
    expect(screen.getByRole("button", { name: "按新配置运行" })).toBeDisabled();
  });

  it("shows a failed run outside the mobile configuration drawer", async () => {
    vi.mocked(api.createDemoJob).mockRejectedValue(new Error("数据校验失败"));
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "用当前配置跑一次" }));

    const alerts = await screen.findAllByRole("alert");
    expect(alerts.some((alert) => alert.textContent?.includes("数据校验失败"))).toBe(true);
    expect(screen.getByRole("button", { name: "关闭错误提示" })).toBeInTheDocument();
  });

  it("does not start a second experiment while one is in flight", async () => {
    render(<App />);
    const run = await screen.findByRole("button", { name: "用当前配置跑一次" });

    fireEvent.click(run);
    fireEvent.click(run);

    await waitFor(() => expect(api.createDemoJob).toHaveBeenCalledTimes(1));
    expect(api.createUploadJob).not.toHaveBeenCalled();
  });

  it("marks results stale after the configuration changes", async () => {
    const demoPayload = {
      ...payload,
      experiment: {
        ...payload.experiment,
        source_kind: "demo",
        source_ref: null,
        normal: 5000,
        attack: 500,
        leaky: false,
      },
    } as Payload;
    vi.mocked(api.loadRun).mockResolvedValue(demoPayload);
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "用当前配置跑一次" }));
    expect(await screen.findByRole("heading", { name: "01 模型对比" })).toBeInTheDocument();

    fireEvent.change(screen.getByRole("slider", { name: "判定阈值" }), {
      target: { value: "0.6" },
    });
    expect(screen.getByText(/当前配置已修改/)).toBeInTheDocument();
  });

  it("shows live job progress and requires confirmation before cancelling", async () => {
    vi.mocked(api.fetchJob).mockResolvedValue(runningJob);
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "用当前配置跑一次" }));

    const progressbars = await screen.findAllByRole("progressbar", { name: "实验完成度" });
    expect(progressbars[0]).toHaveAttribute("aria-valuenow", "42");
    await user.click(screen.getAllByRole("button", { name: "取消实验" })[0]);
    expect(screen.getByRole("button", { name: "确认取消" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "确认取消" }));
    await waitFor(() => expect(api.cancelJob).toHaveBeenCalledWith("job123456789"));
  });

  it("restores an active job after a page refresh", async () => {
    window.localStorage.setItem("flowlab.active-job", "job123456789");
    render(<App />);

    expect(await screen.findByRole("heading", { name: "01 模型对比" })).toBeInTheDocument();
    expect(api.fetchJob).toHaveBeenCalledWith("job123456789");
    expect(window.localStorage.getItem("flowlab.active-job")).toBeNull();
  });

  it("recovers a queued job from the API when local storage is unavailable", async () => {
    vi.mocked(api.fetchActiveJobs).mockResolvedValue([{ ...runningJob, status: "queued" }]);
    render(<App />);

    expect(await screen.findByRole("heading", { name: "01 模型对比" })).toBeInTheDocument();
    expect(api.fetchJob).toHaveBeenCalledWith("job123456789");
  });

  it("scores an unlabeled upload without requiring evaluation labels", async () => {
    vi.mocked(api.fetchJob).mockResolvedValue({
      ...succeededJob,
      kind: "score",
      result_available: true,
      run_id: null,
    });
    const user = userEvent.setup();
    const { container } = render(<App />);

    await user.click(screen.getByRole("radio", { name: "上传文件" }));
    const file = new File(["src_ip,dst_ip\n10.0.0.1,10.0.0.2\n"], "flows.csv", {
      type: "text/csv",
    });
    fireEvent.change(container.querySelector('input[name="flow-file"]')!, {
      target: { files: [file] },
    });
    await user.click(screen.getByRole("button", { name: "用 iforest 打分" }));

    expect(await screen.findByRole("heading", { name: "无标签可疑度排行" })).toBeInTheDocument();
    expect(screen.getByText(/不计算 AUC、F1 或误报率/)).toBeInTheDocument();
    expect(screen.getByText(/排行只保留在当前服务进程/)).toBeInTheDocument();
    expect(api.createScoreJob).toHaveBeenCalledWith(file, "iforest", 20, false);
    expect(api.fetchJobResult).toHaveBeenCalledWith("job123456789");

    const replacement = new File(["src_ip,dst_ip\n10.0.0.3,10.0.0.4\n"], "new-flows.csv", {
      type: "text/csv",
    });
    fireEvent.change(container.querySelector('input[name="flow-file"]')!, {
      target: { files: [replacement] },
    });
    expect(screen.queryByRole("heading", { name: "无标签可疑度排行" })).not.toBeInTheDocument();
  });

  it("preflights an upload before starting the long-running evaluation", async () => {
    const user = userEvent.setup();
    const { container } = render(<App />);
    await user.click(screen.getByRole("radio", { name: "上传文件" }));
    const file = new File(["src_ip,dst_ip\n10.0.0.1,10.0.0.2\n"], "flows.csv", {
      type: "text/csv",
    });
    fireEvent.change(container.querySelector('input[name="flow-file"]')!, {
      target: { files: [file] },
    });
    await user.click(screen.getByRole("button", { name: "预检数据与切分" }));

    expect(await screen.findByRole("heading", { name: "先核对，再训练。" }))
      .toBeInTheDocument();
    expect(screen.getByText(/数据与切分通过预检/)).toBeInTheDocument();
    expect(screen.getByText(/Source IP/)).toBeInTheDocument();
    expect(api.preflightUpload).toHaveBeenCalledWith(
      file,
      { split: "temporal", test_size: 0.3, validation_size: 0.2, seed: 42 },
      null,
      false,
    );

    await user.click(screen.getByRole("button", { name: "开始完整评估" }));
    expect(api.createUploadJob).toHaveBeenCalledWith(
      file,
      expect.objectContaining({ split: "temporal", seed: 42 }),
      null,
      false,
    );
  });

  it("exposes the mobile configuration panel as a modal dialog", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: "配置" }));
    expect(screen.getByRole("dialog", { name: "实验配置" })).toHaveAttribute("aria-modal", "true");
  });

  it("opens the cross-experiment comparison from the top bar", async () => {
    const comparisonRuns = [
      run,
      {
        ...run,
        id: "def456",
        created_at: "2026-11-15T10:00:00+08:00",
        best_model: "iforest",
        best_auc: 0.95,
      },
    ];
    vi.mocked(api.fetchHistory).mockResolvedValue(comparisonRuns);
    vi.mocked(api.fetchHistoryPage).mockResolvedValue({
      runs: comparisonRuns,
      total: comparisonRuns.length,
      available: comparisonRuns.length,
      db_bytes: 4096,
      models: ["mlp", "iforest"],
    });
    vi.mocked(api.fetchComparison).mockResolvedValue({
      status: "comparable",
      comparable: true,
      headline: "可直接比较：同数据、同特征、同切分",
      warnings: [],
      checks: [
        { key: "dataset", label: "数据指纹", ok: true, detail: "全部使用 deadbeef" },
        { key: "features", label: "特征矩阵", ok: true, detail: "特征列一致" },
        { key: "split", label: "切分与测试集", ok: true, detail: "切分一致" },
      ],
      baseline_run_id: "abc123",
      command: "uv run flowlab compare abc123 def456",
      runs: [],
      markdown: "# 对比",
    });
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: "对比" }));
    expect(screen.getByRole("dialog", { name: "跨实验对比" })).toBeInTheDocument();
    await user.click(await screen.findByRole("checkbox", { name: "选择 abc123" }));
    await user.click(await screen.findByRole("checkbox", { name: "选择 def456" }));
    await user.click(screen.getByRole("button", { name: "生成对比" }));
    expect(await screen.findByText("可直接比较")).toBeInTheDocument();
    expect(api.fetchComparison).toHaveBeenCalledWith(["abc123", "def456"]);
  });

  it("opens searchable history and saves annotations", async () => {
    vi.mocked(api.updateRunMeta).mockResolvedValue({
      id: "abc123",
      note: "keep this baseline",
      status: "baseline",
      updated_at: "2026-11-15T10:00:00+08:00",
    });
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: "历史" }));
    expect(screen.getByRole("dialog", { name: "实验历史" })).toBeInTheDocument();
    expect(await screen.findByText(/removed dst_port/)).toBeInTheDocument();
    expect(screen.getByText("4.0 KB")).toBeInTheDocument();

    await user.type(screen.getByRole("searchbox", { name: "搜索历史" }), "port");
    await waitFor(() => {
      expect(api.fetchHistoryPage).toHaveBeenLastCalledWith(
        expect.objectContaining({ q: "port" }),
      );
    });

    await user.click(screen.getByText("备注 / 状态"));
    await user.selectOptions(screen.getByRole("combobox", { name: "状态 abc123" }), "baseline");
    await waitFor(() => {
      expect(api.updateRunMeta).toHaveBeenCalledWith("abc123", { status: "baseline" });
    });
  });
});
