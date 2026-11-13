import type { RunRow } from "../types";

export function HistoryList({ runs, active, onOpen }: {
  runs: RunRow[];
  active?: string;
  onOpen: (id: string) => void;
}) {
  if (!runs.length) {
    return <p className="hint">还没有实验记录。跑一次就会出现在这里。</p>;
  }
  return (
    <ul className="history">
      {runs.slice(0, 6).map((r) => (
        <li key={r.id}>
          <button
            className={`history-row ${r.id === active ? "on" : ""}`}
            onClick={() => onOpen(r.id)}
            title={`${r.source} · ${r.created_at}`}
          >
            <span className="mono hash">
              {r.dataset_hash}{" "}
              <span className="hist-time">{(r.created_at || "").slice(11, 16)} · {r.id.slice(0, 4)}</span>
            </span>
            <span className="hist-meta">
              <span className="hist-src">{r.source}</span>
              <span className="mono hist-auc">
                {r.best_model ?? "—"} {r.best_auc == null ? "" : r.best_auc.toFixed(3)}
              </span>
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
