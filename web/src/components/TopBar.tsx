import type { Job, Payload, RunRow } from "../types";
import { RunTimeline } from "./RunTimeline";

export function TopBar({
  payload,
  busy,
  job,
  runs,
  activeRun,
  onOpenRun,
  mobilePanel,
  onOpenPanel,
  onCompare,
  onHistory,
}: {
  payload: Payload | null;
  busy: boolean;
  job: Job | null;
  runs: RunRow[];
  activeRun?: string;
  onOpenRun: (id: string) => void;
  mobilePanel: "config" | "context" | null;
  onOpenPanel: (panel: "config" | "context") => void;
  onCompare: () => void;
  onHistory: () => void;
}) {
  return (
    <header className="topbar">
      <div className="wordmark">
        <span className="brand-sign" aria-hidden="true"><i /><i /><i /></span>
        <strong>FlowLab</strong>
        <span>流量异常检测</span>
      </div>

      <div className="timeline-wrap">
        <span className={`live ${busy ? "busy" : ""}`} aria-hidden="true" />
        <span className="timeline-label">最近</span>
        <RunTimeline runs={runs} active={activeRun} onOpen={onOpenRun} />
      </div>

      <div className="top-actions">
        <button className="compare-trigger history-trigger" type="button" onClick={onHistory}
                aria-haspopup="dialog">
          历史
        </button>
        <button className="compare-trigger" type="button" onClick={onCompare}
                aria-haspopup="dialog">
          对比
        </button>
        <nav className="mobile-nav" aria-label="移动端视图">
          <button className={mobilePanel === "config" ? "on" : ""}
                  aria-expanded={mobilePanel === "config"} aria-controls="config-drawer"
                  onClick={() => onOpenPanel("config")}>
            配置
          </button>
          <button className={mobilePanel === "context" ? "on" : ""}
                  aria-expanded={mobilePanel === "context"} aria-controls="context-drawer"
                  onClick={() => onOpenPanel("context")}>
            报告
          </button>
        </nav>
        <span className="idle" role="status" aria-live="polite">
          {job?.status === "queued"
            ? "排队中"
            : job && ["running", "cancelling"].includes(job.status)
              ? `${job.message} · ${job.percent}%`
              : busy ? "准备中…" : payload ? (payload.run_id ?? "已就绪") : "未运行"}
        </span>
      </div>
    </header>
  );
}
