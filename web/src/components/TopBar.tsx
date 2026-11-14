import type { Payload, RunRow } from "../types";
import { RunTimeline } from "./RunTimeline";

export function TopBar({ payload, busy, runs, activeRun, onOpenRun }: {
  payload: Payload | null;
  busy: boolean;
  runs: RunRow[];
  activeRun?: string;
  onOpenRun: (id: string) => void;
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
        <span className="idle" role="status" aria-live="polite">
          {busy ? "运行中…" : payload ? (payload.run_id ?? "已就绪") : "未运行"}
        </span>
      </div>
    </header>
  );
}
