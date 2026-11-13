import type { Ablation } from "../types";

export function AblationTable({ ablation }: { ablation: Ablation }) {
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>消融：去掉 {ablation.column}</h2>
        <span className="dim">Δ 为正 = 原来的指标靠这一列撑着</span>
      </div>
      <table className="grid-table">
        <thead>
          <tr>
            <th scope="col">模型</th>
            <th scope="col" className="num">含该列 AUC</th>
            <th scope="col" className="num">去掉后 AUC</th>
            <th scope="col" className="num">Δ</th>
          </tr>
        </thead>
        <tbody>
          {ablation.rows.map((r) => (
            <tr key={r.model}>
              <th scope="row" className="mono">{r.model}</th>
              <td className="num">{r.auc_with == null ? "—" : r.auc_with.toFixed(4)}</td>
              <td className="num">{r.auc_without == null ? "—" : r.auc_without.toFixed(4)}</td>
              <td className={`num ${(r.delta ?? 0) > 0.02 ? "bad" : ""}`}>
                {r.delta == null ? "—" : (r.delta > 0 ? "+" : "") + r.delta.toFixed(4)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
