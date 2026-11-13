import { useMemo, useState } from "react";
import type { Result } from "../types";

type Key = "auc" | "f1" | "fpr" | "duration_s";
const COLS: { key: Key; label: string }[] = [
  { key: "auc", label: "AUC" },
  { key: "f1", label: "F1" },
  { key: "fpr", label: "误报率" },
  { key: "duration_s", label: "耗时" },
];

function val(r: Result, k: Key): number {
  if (k === "duration_s") return r.duration_s;
  const v = r.metrics[k];
  return v == null ? -1 : (v as number);
}

export function ModelTable({ results, bestModel }: { results: Result[]; bestModel: string | null }) {
  const [sortKey, setSortKey] = useState<Key>("auc");
  const rows = useMemo(() => [...results].sort((a, b) => val(b, sortKey) - val(a, sortKey)), [results, sortKey]);

  return (
    <table className="table">
      <thead>
        <tr>
          <th scope="col">模型</th>
          <th scope="col">类型</th>
          {COLS.map((c) => (
            <th key={c.key} scope="col" className="num" aria-sort={sortKey === c.key ? "descending" : "none"}>
              <button className={`sort ${sortKey === c.key ? "active" : ""}`} onClick={() => setSortKey(c.key)}>
                {c.label}
              </button>
            </th>
          ))}
          <th scope="col" className="num">TP</th>
          <th scope="col" className="num">FP</th>
          <th scope="col" className="num">FN</th>
          <th scope="col" className="num">TN</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.model} className={r.model === bestModel ? "best" : ""}>
            <th scope="row"><span className="lead">{r.model}</span>
              {r.model === bestModel && <span className="best-tag">最佳</span>}
            </th>
            <td className="muted">{r.kind === "supervised" ? "监督" : "无监督"}</td>
            <td className="num">{r.metrics.auc == null ? "—" : r.metrics.auc.toFixed(4)}</td>
            <td className="num">{r.metrics.f1.toFixed(4)}</td>
            <td className="num">{r.metrics.fpr == null ? "—" : `${(r.metrics.fpr * 100).toFixed(2)}%`}</td>
            <td className="num muted">{r.duration_s.toFixed(2)}s</td>
            <td className="num">{r.confusion.tp.toLocaleString()}</td>
            <td className="num bad">{r.confusion.fp.toLocaleString()}</td>
            <td className="num bad">{r.confusion.fn.toLocaleString()}</td>
            <td className="num">{r.confusion.tn.toLocaleString()}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
