import type { Payload, RunRow } from "../types";
import { RunTimeline } from "./RunTimeline";

export function TopBar({ payload, busy, runs, activeRun, onOpenRun, mobilePanel, onOpenPanel }: {
  payload: Payload | null;
  busy: boolean;
  runs: RunRow[];
  activeRun?: string;
  onOpenRun: (id: string) => void;
  mobilePanel: "config" | "history" | "context" | null;
  onOpenPanel: (panel: "config" | "history" | "context") => void;
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
        <nav className="mobile-nav" aria-label="移动端视图">
          <button className={mobilePanel === "config" ? "on" : ""}
                  aria-expanded={mobilePanel === "config"} aria-controls="config-drawer"
                  onClick={() => onOpenPanel("config")}>
            配置
          </button>
          <button className={mobilePanel === "history" ? "on" : ""}
                  aria-expanded={mobilePanel === "history"} aria-controls="history-drawer"
                  onClick={() => onOpenPanel("history")}>
            历史
          </button>
          <button className={mobilePanel === "context" ? "on" : ""}
                  aria-expanded={mobilePanel === "context"} aria-controls="context-drawer"
                  onClick={() => onOpenPanel("context")}>
            报告
          </button>
        </nav>
        <span className="idle" role="status" aria-live="polite">
          {busy ? "运行中…" : payload ? (payload.run_id ?? "已就绪") : "未运行"}
        </span>
      </div>
    </header>
  );
}
