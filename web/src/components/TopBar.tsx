import type { Payload } from "../types";

export function TopBar({ payload, busy, onDownloadMd, onDownloadHtml }: {
  payload: Payload | null;
  busy: boolean;
  onDownloadMd: () => void;
  onDownloadHtml: () => void;
}) {
  return (
    <header className="topbar">
      <div className="wordmark">
        <strong>FlowLab</strong>
        <span>流量异常检测工作台</span>
      </div>
      <div className="top-actions">
        <span className="run-chip">
          <span className={`dot ${busy ? "busy" : ""}`} aria-hidden="true" />
          {busy ? "运行中" : payload ? `run ${payload.run_id ?? payload.dataset.hash}` : "空闲"}
        </span>
        {payload && (
          <>
            <button className="ghost-btn" onClick={onDownloadMd}>Markdown</button>
            <button className="ghost-btn solid" onClick={onDownloadHtml}>HTML 报告</button>
          </>
        )}
      </div>
    </header>
  );
}
