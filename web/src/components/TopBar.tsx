import type { Payload, RunRow } from "../types";
import { RunTimeline } from "./RunTimeline";

export function TopBar({ payload, busy, runs, activeRun, onOpenRun, onDownloadHtml }: {
  payload: Payload | null;
  busy: boolean;
  runs: RunRow[];
  activeRun?: string;
  onOpenRun: (id: string) => void;
  onDownloadHtml: () => void;
}) {
  return (
    <header className="topbar">
      <div className="wordmark">
        <strong>FlowLab</strong>
        <span>流量异常检测</span>
      </div>

      <div className="timeline-wrap">
        <span className={`live ${busy ? "busy" : ""}`} aria-hidden="true" />
        <span className="timeline-label">最近</span>
        <RunTimeline runs={runs} active={activeRun} onOpen={onOpenRun} />
      </div>

      <div className="top-actions">
        {payload ? (
          <button className="ghost-btn solid" onClick={onDownloadHtml}>下载 HTML 报告</button>
        ) : (
          <span className="idle">{busy ? "运行中…" : "未运行"}</span>
        )}
      </div>
    </header>
  );
}
