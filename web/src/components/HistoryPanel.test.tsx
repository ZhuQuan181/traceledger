import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { deleteRun, fetchHistoryPage, pruneHistory } from "../api";
import type { RunRow } from "../types";
import { HistoryPanel } from "./HistoryPanel";

vi.mock("../api", () => ({
  deleteRun: vi.fn(),
  fetchHistoryPage: vi.fn(),
  pruneHistory: vi.fn(),
  updateRunMeta: vi.fn(),
}));

function row(index: number): RunRow {
  return {
    id: `run-${index.toString().padStart(2, "0")}`,
    created_at: `2026-11-15T${String(index % 24).padStart(2, "0")}:00:00+08:00`,
    source: "flows.csv",
    dataset_hash: "deadbeef",
    split: "temporal",
    rows: 120,
    best_model: "mlp",
    best_auc: 0.9,
    note: index === 0 ? "baseline" : "",
    status: "unreviewed",
  };
}

describe("HistoryPanel", () => {
  beforeEach(() => {
    vi.mocked(fetchHistoryPage).mockResolvedValue({
      runs: Array.from({ length: 30 }, (_, index) => row(index)),
      total: 45,
      available: 45,
      db_bytes: 4096,
      models: ["mlp"],
    });
    vi.mocked(deleteRun).mockResolvedValue({ deleted: "run-00" });
    vi.mocked(pruneHistory).mockResolvedValue({ deleted: 10, remaining: 35 });
  });

  it("pages through history and resets to page one when the search changes", async () => {
    const user = userEvent.setup();
    render(
      <HistoryPanel
        onOpen={vi.fn()}
        onClose={vi.fn()}
        onChanged={vi.fn()}
      />,
    );

    await screen.findByText("run-00");
    expect(fetchHistoryPage).toHaveBeenLastCalledWith(
      expect.objectContaining({ limit: 30, offset: 0 }),
    );
    await user.click(screen.getByRole("button", { name: "下一页" }));
    await waitFor(() => {
      expect(fetchHistoryPage).toHaveBeenLastCalledWith(
        expect.objectContaining({ offset: 30 }),
      );
    });

    await user.type(screen.getByRole("searchbox", { name: "搜索历史" }), "port");
    await waitFor(() => {
      expect(fetchHistoryPage).toHaveBeenLastCalledWith(
        expect.objectContaining({ q: "port", offset: 0 }),
      );
    });
  });

  it("requires confirmation before deleting an experiment", async () => {
    const onChanged = vi.fn();
    const user = userEvent.setup();
    render(
      <HistoryPanel
        onOpen={vi.fn()}
        onClose={vi.fn()}
        onChanged={onChanged}
      />,
    );

    await screen.findByText("run-00");
    await user.click(screen.getAllByText("备注 / 状态")[0]);
    await user.click(screen.getAllByRole("button", { name: "删除这次实验" })[0]);
    expect(deleteRun).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "确认删除" }));
    await waitFor(() => expect(deleteRun).toHaveBeenCalledWith("run-00"));
    expect(onChanged).toHaveBeenCalled();
  });

  it("prunes old history only after a second confirmation", async () => {
    const onChanged = vi.fn();
    const user = userEvent.setup();
    render(
      <HistoryPanel
        onOpen={vi.fn()}
        onClose={vi.fn()}
        onChanged={onChanged}
      />,
    );

    await screen.findByText("run-00");
    await user.click(screen.getByText("清理旧记录"));
    await user.click(screen.getByRole("button", { name: "清理更旧记录" }));
    expect(pruneHistory).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "确认清理" }));
    await waitFor(() => expect(pruneHistory).toHaveBeenCalledWith(50));
    expect(onChanged).toHaveBeenCalled();
  });
});
