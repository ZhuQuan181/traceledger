import type { ScorePayload, ScoreRow } from "../types";

const PROTOCOL: Record<string, string> = { "1": "ICMP", "6": "TCP", "17": "UDP" };

function value(value: unknown) {
  return value == null || value === "" ? "—" : String(value);
}

function csvCell(value: unknown) {
  const text = value == null ? "" : String(value);
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function downloadCsv(result: ScorePayload) {
  const columns = [
    "score", "src_ip", "dst_ip", "src_port", "dst_port", "protocol",
    "timestamp", "duration_ms", "fwd_packets", "bwd_packets",
    "fwd_bytes", "bwd_bytes", "bytes_per_s", "packets_per_s",
  ] as const;
  const lines = [
    columns.join(","),
    ...result.top.map((row) => columns.map((column) => csvCell(row[column])).join(",")),
  ];
  const blob = new Blob([`\ufeff${lines.join("\n")}`], { type: "text/csv;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `flowlab-score-${result.dataset.hash}-top${result.summary.returned}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(link.href), 0);
}

function endpoint(row: ScoreRow) {
  const source = value(row.src_ip);
  const destination = value(row.dst_ip);
  return `${source}${row.src_port != null ? `:${row.src_port}` : ""} → `
    + `${destination}${row.dst_port != null ? `:${row.dst_port}` : ""}`;
}

export function ScorePanel({ result }: { result: ScorePayload }) {
  return (
    <section className="score-result" aria-labelledby="score-result-title">
      <header className="score-head">
        <div>
          <span className="score-kicker">UNLABELED · {result.dataset.hash}</span>
          <h1 id="score-result-title">无标签可疑度排行</h1>
          <p>
            {result.dataset.source} · {result.dataset.rows.toLocaleString()} 条流 ·
            {" "}{result.model.name} · 前 {result.summary.returned} 条
          </p>
        </div>
        <button className="score-export" type="button" onClick={() => downloadCsv(result)}>
          导出 CSV
        </button>
      </header>

      <div className="score-summary">
        <div>
          <span>扫描流数</span>
          <strong>{result.summary.scored_rows.toLocaleString()}</strong>
        </div>
        <div>
          <span>最高分数</span>
          <strong>{result.summary.max_score?.toFixed(4) ?? "—"}</strong>
        </div>
        <div>
          <span>Top 中位数</span>
          <strong>{result.summary.median_top_score?.toFixed(4) ?? "—"}</strong>
        </div>
        <div>
          <span>Top P95</span>
          <strong>{result.summary.p95_top_score?.toFixed(4) ?? "—"}</strong>
        </div>
      </div>

      <div className="score-note" role="note">
        <strong>这不是评估结果。</strong> {result.note}
        分数只表示在当前批次内的相对可疑度，不能当作概率或跨数据集阈值。
        <span className="score-retention">
          排行只保留在当前服务进程；如需归档或交给他人复核，请先导出 CSV。
        </span>
      </div>

      {result.warnings?.map((warning) => (
        <p className="score-warning" role="alert" key={warning.rule}>{warning.message}</p>
      ))}

      {result.top.length === 0 ? (
        <p className="score-empty">没有可展示的流。</p>
      ) : (
        <>
          <div className="score-table-wrap">
            <table className="score-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>分数</th>
                  <th>源 → 目的</th>
                  <th>协议</th>
                  <th>时间</th>
                  <th>bytes/s</th>
                  <th>packets/s</th>
                </tr>
              </thead>
              <tbody>
                {result.top.map((row, index) => (
                  <tr key={`${row.timestamp ?? "flow"}-${row.src_ip ?? ""}-${index}`}>
                    <td className="score-rank">{String(index + 1).padStart(2, "0")}</td>
                    <td className="score-value">{row.score.toFixed(4)}</td>
                    <td className="score-endpoint" title={endpoint(row)}>{endpoint(row)}</td>
                    <td>{PROTOCOL[String(row.protocol)] ?? value(row.protocol)}</td>
                    <td className="score-time">{value(row.timestamp)}</td>
                    <td>{row.bytes_per_s?.toLocaleString() ?? "—"}</td>
                    <td>{row.packets_per_s?.toLocaleString() ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="score-cards">
            {result.top.map((row, index) => (
              <article className="score-card" key={`${row.timestamp ?? "flow"}-${index}`}>
                <span className="score-rank">{String(index + 1).padStart(2, "0")}</span>
                <strong>{row.score.toFixed(4)}</strong>
                <p>{endpoint(row)}</p>
                <span>
                  {PROTOCOL[String(row.protocol)] ?? value(row.protocol)}
                  {" · "}{value(row.timestamp)}
                </span>
              </article>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
