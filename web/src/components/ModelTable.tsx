import { useMemo, useState } from "react";
import type { Result } from "../types";

type Key = "auc" | "f1" | "fpr" | "duration_s";

const COLS: { key: Key; label: string; hint: string }[] = [
  { key: "auc", label: "AUC", hint: "排序能力，1 最好" },
  { key: "f1", label: "F1", hint: "精确率与召回率的调和平均" },
  { key: "fpr", label: "误报率", hint: "正常流被误判的比例，越低越好" },
  { key: "duration_s", label: "耗时", hint: "训练加推理的墙钟时间" },
];

function value(r: Result, k: Key): number {
  if (k === "duration_s") return r.duration_s;
  const v = r.metrics[k];
  return v == null ? -1 : (v as number);
}

export function ModelTable({ results, bestModel }: { results: Result[]; bestModel: string | null }) {
  const [sortKey, setSortKey] = useState<Key>("auc");
  const rows = useMemo(
    () => [...results].sort((a, b) => value(b, sortKey) - value(a, sortKey)),
    [results, sortKey]
  );

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>模型对比</h2>
        <span className="dim">按 {COLS.find((c) => c.key === sortKey)?.label} 排序</span>
      </div>
      <table className="grid-table">
        <thead>
          <tr>
            <th scope="col">模型</th>
            <th scope="col">类型</th>
            {COLS.map((c) => (
              <th key={c.key} scope="col" aria-sort={sortKey === c.key ? "descending" : "none"}>
                <button className={`sort ${sortKey === c.key ? "active" : ""}`} onClick={() => setSortKey(c.key)} title={c.hint}>
                  {c.label}
                </button>
              </th>
            ))}
            <th scope="col" className="cm-h">TP</th>
            <th scope="col" className="cm-h">FP</th>
            <th scope="col" className="cm-h">FN</th>
            <th scope="col" className="cm-h">TN</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.model} className={r.model === bestModel ? "best" : ""}>
              <th scope="row">
                <span className="mono">{r.model}</span>
                {r.model === bestModel && <span className="best-tag">最佳</span>}
              </th>
              <td className="dim">{r.kind === "supervised" ? "监督" : "无监督"}</td>
              <td className="num strong">{r.metrics.auc == null ? "—" : r.metrics.auc.toFixed(4)}</td>
              <td className="num">{r.metrics.f1.toFixed(4)}</td>
              <td className="num">{r.metrics.fpr == null ? "—" : `${(r.metrics.fpr * 100).toFixed(2)}%`}</td>
              <td className="num">{r.duration_s.toFixed(2)}s</td>
              <td className="num tiny">{r.confusion.tp}</td>
              <td className="num tiny bad">{r.confusion.fp}</td>
              <td className="num tiny bad">{r.confusion.fn}</td>
              <td className="num tiny">{r.confusion.tn}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
