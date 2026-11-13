import type { TopFlow } from "../types";

const PROTO: Record<number, string> = { 1: "ICMP", 6: "TCP", 17: "UDP" };

export function TopFlows({ flows, model }: { flows: TopFlow[]; model: string | null }) {
  if (!flows.length) return null;
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>最可疑的流</h2>
        <span className="dim">{model} 打分 · 前 {flows.length} 条</span>
      </div>
      <table className="grid-table flows">
        <thead>
          <tr>
            <th scope="col">源</th>
            <th scope="col">目的</th>
            <th scope="col">端口</th>
            <th scope="col">协议</th>
            <th scope="col">时间</th>
            <th scope="col">分数</th>
            <th scope="col">真实标签</th>
          </tr>
        </thead>
        <tbody>
          {flows.map((f, i) => (
            <tr key={i}>
              <td className="mono tiny">{f.src_ip ?? "—"}</td>
              <td className="mono tiny">{f.dst_ip ?? "—"}</td>
              <td className="mono tiny">{f.dst_port ?? "—"}</td>
              <td className="mono tiny">{f.protocol == null ? "—" : `${f.protocol} ${PROTO[f.protocol] ?? ""}`.trim()}</td>
              <td className="mono tiny dim">{f.timestamp ?? "—"}</td>
              <td className="score-cell">
                <span className="mono tiny">{f.score.toFixed(3)}</span>
                <span className="score-bar" style={{ width: `calc((100% - 16px) * ${f.score.toFixed(3)})` }} aria-hidden="true" />
              </td>
              <td className="tiny">
                {f.label ? <span className={String(f.label).toLowerCase() === "benign" ? "tag-ok" : "tag-bad"}>{f.label}</span> : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
