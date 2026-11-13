import { useMemo, useState } from "react";
import type { Result } from "../types";

type Key = "auc" | "f1" | "fpr" | "duration_s";

function val(r: Result, k: Key): number {
  if (k === "duration_s") return r.duration_s;
  const v = r.metrics[k];
  return v == null ? -1 : (v as number);
}

export function MetricMatrix({ results, bestModel }: { results: Result[]; bestModel: string | null }) {
  const [sortKey, setSortKey] = useState<Key>("auc");
  const rows = useMemo(() => [...results].sort((a, b) => val(b, sortKey) - val(a, sortKey)), [results, sortKey]);
  const th = (k: Key, label: string) => (
    <th scope="col" className="num" aria-sort={sortKey === k ? "descending" : "none"}>
      <button className={`sort ${sortKey === k ? "active" : ""}`} onClick={() => setSortKey(k)}>{label}</button>
    </th>
  );

  return (
    <table className="table matrix">
      <thead>
        <tr className="group-row">
          <th scope="col" rowSpan={2} className="corner">模型</th>
          <th scope="colgroup" colSpan={4} className="group">性能指标</th>
          <th scope="colgroup" colSpan={4} className="group">混淆矩阵</th>
        </tr>
        <tr>
          {th("auc", "AUC")}
          {th("f1", "F1")}
          {th("fpr", "误报率")}
          {th("duration_s", "耗时")}
          <th scope="col" className="num">TP</th>
          <th scope="col" className="num">FP</th>
          <th scope="col" className="num">FN</th>
          <th scope="col" className="num">TN</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.model} className={r.model === bestModel ? "best" : ""}>
            <th scope="row">
              <span className="lead">{r.model}</span>
              <span className="row-sub">{r.kind === "supervised" ? "监督" : "无监督"}</span>
              {r.model === bestModel && <span className="best-tag">最佳</span>}
            </th>
            <td className="num strong">
              {r.metrics.auc == null ? "—" : r.metrics.auc.toFixed(4)}
              <span className="cell-bar" aria-hidden="true">
                <i style={{ width: `${Math.round((r.metrics.auc ?? 0) * 100)}%` }} />
              </span>
            </td>
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
