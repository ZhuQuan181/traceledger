import type { ErrorExample, Result } from "../types";
import { int, num, pct } from "../format";

function ErrorTable({ rows, title, tone }: {
  rows: ErrorExample[];
  title: string;
  tone: "miss" | "false";
}) {
  if (!rows.length) return null;
  return (
    <details className={`investigation-details ${tone}`}>
      <summary>{title} <span>{rows.length}</span></summary>
      <div className="table-scroll" tabIndex={0} role="region" aria-label={title}>
        <table className="table error-table">
          <thead>
            <tr>
              <th scope="col">源</th>
              <th scope="col">目的</th>
              <th scope="col" className="num">端口</th>
              <th scope="col" className="num">分数</th>
              <th scope="col">真实标签</th>
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, 8).map((row, index) => (
              <tr key={`${row.src_ip}-${row.dst_ip}-${index}`}>
                <td className="lead">{row.src_ip ?? "—"}</td>
                <td className="lead">{row.dst_ip ?? "—"}</td>
                <td className="num">{row.dst_port ?? "—"}</td>
                <td className="num">{num(row.score, 3)}</td>
                <td className="muted">{row.label ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

export function InvestigationPanel({ result }: { result: Result }) {
  const labels = result.by_label ?? [];
  const sources = result.source_ranking ?? [];
  const misses = result.false_negatives ?? [];
  const falseAlarms = result.false_positives ?? [];
  if (!labels.length && !sources.length && !misses.length && !falseAlarms.length) {
    return <p className="hint">这次实验没有生成分类与错误样本明细。</p>;
  }

  return (
    <div className="investigation">
      <div className="investigation-grid">
        {labels.length > 0 && (
          <section className="subpanel">
            <h3>按真实类型拆分</h3>
            <p className="subpanel-note">攻击看召回率，BENIGN 看误报率。</p>
            <div className="table-scroll" tabIndex={0} role="region" aria-label="按真实类型拆分">
              <table className="table compact-table">
                <thead>
                  <tr>
                    <th scope="col">类型</th>
                    <th scope="col">性质</th>
                    <th scope="col" className="num">样本</th>
                    <th scope="col" className="num">判为攻击</th>
                    <th scope="col" className="num">比例</th>
                  </tr>
                </thead>
                <tbody>
                  {labels.map((row) => (
                    <tr key={`${row.kind}-${row.label}`}>
                      <th scope="row">{row.label}</th>
                      <td className="muted">{row.kind === "benign" ? "误报率" : "召回率"}</td>
                      <td className="num">{int(row.total)}</td>
                      <td className="num">{int(row.flagged)}</td>
                      <td className="num">{pct(row.rate)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {sources.length > 0 && (
          <section className="subpanel">
            <h3>先排查的源 IP</h3>
            <p className="subpanel-note">按命中攻击数排序，同时显示其中的误报量。</p>
            <div className="table-scroll" tabIndex={0} role="region" aria-label="源 IP 告警排序">
              <table className="table compact-table">
                <thead>
                  <tr>
                    <th scope="col">源 IP</th>
                    <th scope="col" className="num">告警</th>
                    <th scope="col" className="num">真攻击</th>
                    <th scope="col" className="num">误报</th>
                  </tr>
                </thead>
                <tbody>
                  {sources.map((row) => (
                    <tr key={row.src_ip}>
                      <th scope="row" className="lead">{row.src_ip}</th>
                      <td className="num">{int(row.alerts)}</td>
                      <td className="num">{int(row.true_attacks)}</td>
                      <td className="num bad">{int(row.false_alarms)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </div>

      <ErrorTable rows={misses} title="典型漏报（攻击但未过阈值）" tone="miss" />
      <ErrorTable rows={falseAlarms} title="典型误报（正常但被判为攻击）" tone="false" />
    </div>
  );
}
