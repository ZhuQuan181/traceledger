import { num, pct } from "../format";
import type { Result } from "../types";

export function ThresholdScan({ rows, active }: {
  rows: Result["threshold_scan"];
  active: number;
}) {
  if (!rows?.length) return null;
  const nearest = rows.reduce((best, row) =>
    Math.abs(row.threshold - active) < Math.abs(best.threshold - active) ? row : best
  );
  return (
    <div className="threshold-scan">
      <div className="threshold-head">
        <strong>阈值权衡</strong>
        <span>测试集诊断 · 自动阈值只用验证集</span>
      </div>
      <div className="table-scroll" role="region" aria-label="测试集阈值扫描" tabIndex={0}>
        <table className="table threshold-table">
          <thead>
            <tr>
              <th scope="col" className="num">阈值</th>
              <th scope="col" className="num">精确率</th>
              <th scope="col" className="num">召回率</th>
              <th scope="col" className="num">F1</th>
              <th scope="col" className="num">误报率</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.threshold} className={row === nearest ? "on" : ""}>
                <th scope="row" className="num mono">{row.threshold.toFixed(2)}</th>
                <td className="num">{num(row.precision, 3)}</td>
                <td className="num">{num(row.recall, 3)}</td>
                <td className="num">{num(row.f1, 3)}</td>
                <td className="num">{pct(row.fpr)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="hint">
        当前运行阈值 {active.toFixed(2)}，表中高亮最接近的一档。测试集只用于报告，
        不应根据这张表回头挑阈值。
      </p>
    </div>
  );
}
