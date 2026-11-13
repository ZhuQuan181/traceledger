import type { RunRow } from "../types";

export function RunTimeline({ runs, active, onOpen }: {
  runs: RunRow[]; active?: string; onOpen: (id: string) => void;
}) {
  if (!runs.length) return <span className="timeline-empty">还没有历史实验</span>;
  return (
    <div className="timeline" role="list" aria-label="最近的实验">
      {runs.slice(0, 6).map((r) => (
        <button
          key={r.id}
          role="listitem"
          className={`run-chip ${r.id === active ? "on" : ""}`}
          onClick={() => onOpen(r.id)}
          title={`${r.source} · ${r.created_at} · 最佳 ${r.best_model ?? "—"} ${r.best_auc?.toFixed(4) ?? ""}`}
        >
          <span className="chip-hash">{r.id.slice(0, 4)}</span>
          <span className="chip-auc">{r.best_auc == null ? "—" : r.best_auc.toFixed(3)}</span>
          <span className="chip-time">{(r.created_at || "").slice(11, 16)}</span>
        </button>
      ))}
    </div>
  );
}
