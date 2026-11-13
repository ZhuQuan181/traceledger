import type { Ablation } from "../types";

export function AblationTable({ ablation }: { ablation: Ablation }) {
  return (
    <table className="table">
      <thead>
        <tr>
          <th scope="col">模型</th>
          <th scope="col" className="num">AUC（含该列）</th>
          <th scope="col" className="num">AUC（去掉后）</th>
          <th scope="col" className="num">Δ</th>
        </tr>
      </thead>
      <tbody>
        {ablation.rows.map((r) => (
          <tr key={r.model}>
            <th scope="row"><span className="lead">{r.model}</span></th>
            <td className="num">{r.auc_with == null ? "—" : r.auc_with.toFixed(4)}</td>
            <td className="num">{r.auc_without == null ? "—" : r.auc_without.toFixed(4)}</td>
            <td className={`num ${(r.delta ?? 0) > 0.02 ? "bad" : ""}`}>
              {r.delta == null ? "—" : (r.delta > 0 ? "+" : "") + r.delta.toFixed(4)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
