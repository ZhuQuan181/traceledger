import type { TopFlow } from "../types";

const PROTO: Record<number, string> = { 1: "ICMP", 6: "TCP", 17: "UDP" };

export function TopFlows({ flows, model }: { flows: TopFlow[]; model: string | null }) {
  if (!flows.length) return null;
  return (
    <table className="table flows-table">
      <thead>
        <tr>
          <th scope="col">源</th>
          <th scope="col">目的</th>
          <th scope="col" className="num">端口</th>
          <th scope="col">协议</th>
          <th scope="col">时间</th>
          <th scope="col" className="score-cell">分数</th>
          <th scope="col">真实标签</th>
        </tr>
      </thead>
      <tbody>
        {flows.slice(0, 15).map((f, i) => {
          const attack = f.label && String(f.label).toLowerCase() !== "benign";
          return (
            <tr key={i}>
              <td className="lead">{f.src_ip ?? "—"}</td>
              <td className="lead">{f.dst_ip ?? "—"}</td>
              <td className="num">{f.dst_port ?? "—"}</td>
              <td className="muted">{f.protocol == null ? "—" : `${PROTO[f.protocol] ?? f.protocol}`}</td>
              <td className="lead muted">{f.timestamp ?? "—"}</td>
              <td className="score-cell">
                <span className="score-wrap">
                  <span className="score-track"><i style={{ width: `${Math.round(f.score * 100)}%` }} /></span>
                  <span className="score-num">{f.score.toFixed(3)}</span>
                </span>
              </td>
              <td>{f.label ? <span className={attack ? "tag-bad" : "tag-ok"}>{f.label}</span> : "—"}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
