import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ComparePanel } from "./ComparePanel";
import { fetchHistoryPage } from "../api";
import type { Comparison, RunRow } from "../types";

vi.mock("../api", () => ({
  fetchHistoryPage: vi.fn(),
}));

const runs: RunRow[] = [
  {
    id: "abc123",
    created_at: "2026-11-15T09:00:00+08:00",
    source: "flows.csv",
    dataset_hash: "deadbeef",
    split: "temporal",
    rows: 120,
    best_model: "mlp",
    best_auc: 0.91,
    best_validation_auc: 0.9,
  },
  {
    id: "def456",
    created_at: "2026-11-15T10:00:00+08:00",
    source: "flows.csv",
    dataset_hash: "deadbeef",
    split: "temporal",
    rows: 120,
    best_model: "iforest",
    best_auc: 0.94,
    best_validation_auc: 0.93,
  },
];

const comparison: Comparison = {
  status: "limited",
  comparable: false,
  headline: "只能作为对照：数据相同，但特征矩阵或切分不同",
  warnings: ["特征列或编码维度不一致"],
  checks: [
    { key: "dataset", label: "数据指纹", ok: true, detail: "全部使用 deadbeef" },
    { key: "features", label: "特征矩阵", ok: false, detail: "特征列或编码维度不一致" },
    { key: "split", label: "切分与测试集", ok: true, detail: "切分一致" },
  ],
  baseline_run_id: "abc123",
  command: "uv run flowlab compare abc123 def456",
  markdown: "# 对比",
  runs: [
    {
      id: "abc123",
      created_at: "2026-11-15T09:00:00+08:00",
      source: "flows.csv",
      dataset_hash: "deadbeef",
      split: "temporal",
      model: "mlp",
      validation_auc: 0.9,
      test_auc: 0.91,
      pr_auc: 0.89,
      f1: 0.86,
      precision: 0.88,
      recall: 0.84,
      fpr: 0.04,
      threshold: 0.5,
      duration_s: 0.1,
      features: ["a"],
      delta: {
        validation_auc: 0,
        test_auc: 0,
        pr_auc: 0,
        f1: 0,
        recall: 0,
        fpr: 0,
      },
    },
    {
      id: "def456",
      created_at: "2026-11-15T10:00:00+08:00",
      source: "flows.csv",
      dataset_hash: "deadbeef",
      split: "temporal",
      model: "iforest",
      validation_auc: 0.93,
      test_auc: 0.94,
      pr_auc: 0.92,
      f1: 0.9,
      precision: 0.91,
      recall: 0.89,
      fpr: 0.02,
      threshold: 0.5,
      duration_s: 0.2,
      features: ["a", "b"],
      delta: {
        validation_auc: 0.03,
        test_auc: 0.03,
        pr_auc: 0.03,
        f1: 0.04,
        recall: 0.05,
        fpr: -0.02,
      },
    },
  ],
};

describe("ComparePanel", () => {
  beforeEach(() => {
    vi.mocked(fetchHistoryPage).mockResolvedValue({
      runs,
      total: runs.length,
      available: runs.length,
      db_bytes: 4096,
      models: ["mlp", "iforest"],
    });
  });

  it("requires two runs before enabling comparison", async () => {
    const user = userEvent.setup();
    const onToggle = vi.fn();
    render(
      <ComparePanel
        selected={["abc123"]}
        onToggle={onToggle}
        onCompare={vi.fn()}
        onClose={vi.fn()}
        comparison={null}
        busy={false}
        error={null}
        onDownload={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: "生成对比" })).toBeDisabled();
    await user.click(await screen.findByRole("checkbox", { name: "选择 def456" }));
    expect(onToggle).toHaveBeenCalledWith("def456");
  });

  it("shows comparability checks, deltas and markdown export", async () => {
    const user = userEvent.setup();
    const onDownload = vi.fn();
    render(
      <ComparePanel
        selected={["abc123", "def456"]}
        onToggle={vi.fn()}
        onCompare={vi.fn()}
        onClose={vi.fn()}
        comparison={comparison}
        busy={false}
        error={null}
        onDownload={onDownload}
      />,
    );
    expect(screen.getByText("有限对照")).toBeInTheDocument();
    expect(screen.getByText(/特征列或编码维度不一致/)).toBeInTheDocument();
    expect(screen.getAllByText("+0.0300").length).toBeGreaterThan(0);
    expect(screen.getByText("uv run flowlab compare abc123 def456")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "下载 Markdown 对比表" }));
    expect(onDownload).toHaveBeenCalledTimes(1);
  });

  it("searches and pages through the complete local history", async () => {
    const user = userEvent.setup();
    vi.mocked(fetchHistoryPage).mockImplementation(async (query = {}) => ({
      runs: query.q ? [] : runs,
      total: query.q ? 0 : 14,
      available: 14,
      db_bytes: 4096,
      models: ["mlp", "iforest"],
    }));
    render(
      <ComparePanel
        selected={[]}
        onToggle={vi.fn()}
        onCompare={vi.fn()}
        onClose={vi.fn()}
        comparison={null}
        busy={false}
        error={null}
        onDownload={vi.fn()}
      />,
    );

    await screen.findByRole("checkbox", { name: "选择 abc123" });
    expect(screen.getByText(/14 次匹配/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "下一页" }));
    expect(fetchHistoryPage).toHaveBeenLastCalledWith(
      expect.objectContaining({ offset: 12 }),
    );
    await user.type(screen.getByRole("searchbox", { name: "搜索可对比实验" }), "port");
    expect(await screen.findByText(/没有匹配的历史实验/)).toBeInTheDocument();
    expect(fetchHistoryPage).toHaveBeenLastCalledWith(
      expect.objectContaining({ q: "port", offset: 0 }),
    );
  });
});
