import type { TopFlow } from "../types";
import { num } from "../format";

const PROTO: Record<number, string> = { 1: "ICMP", 6: "TCP", 17: "UDP" };

export function TopFlows({ flows, leakPort, threshold }: {
  flows: TopFlow[];
  leakPort?: number | null;
  threshold: number;
}) {
  if (!flows.length) return null;
  const visible = flows.slice(0, 15);
  return (
    <>
      <div className="table-scroll flows-table-wrap" role="region" aria-label="最可疑的流" tabIndex={0}>
        <table className="table flows-table">
          <thead>
            <tr>
              <th scope="col">源</th>
              <th scope="col">目的</th>
              <th scope="col" className="num">端口</th>
              <th scope="col">协议</th>
              <th scope="col">时间</th>
              <th scope="col" className="score-cell">分数</th>
              <th scope="col">判断依据</th>
              <th scope="col">真实标签</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((f, i) => {
              const attack = f.label && String(f.label).toLowerCase() !== "benign";
              const portHit = leakPort != null && f.dst_port === leakPort;
              const passed = f.score >= threshold;
              return (
                <tr key={i}>
                  <td className="lead">{f.src_ip ?? "—"}</td>
                  <td className="lead">{f.dst_ip ?? "—"}</td>
                  <td className={`num ${portHit ? "port-hit" : ""}`}>
                    {f.dst_port ?? "—"}
                  </td>
                  <td className="muted">{f.protocol == null ? "—" : `${PROTO[f.protocol] ?? f.protocol}`}</td>
                  <td className="lead muted">{f.timestamp ?? "—"}</td>
                  <td className="score-cell">
                    <span className="score-wrap">
                      <span className="score-track"><i style={{ width: `${Math.round(f.score * 100)}%` }} /></span>
                      <span className="score-num">{num(f.score, 3)}</span>
                    </span>
                  </td>
                  <td className="reason">
                    {portHit ? "端口命中" : passed ? "分数超阈值" : "高分排序（未过阈值）"}
                  </td>
                  <td>{f.label ? <span className={attack ? "tag-bad" : "tag-ok"}>{f.label}</span> : "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <ul className="flow-cards" aria-label="最可疑的流（移动端）">
        {visible.map((f, i) => {
          const attack = f.label && String(f.label).toLowerCase() !== "benign";
          const portHit = leakPort != null && f.dst_port === leakPort;
          const passed = f.score >= threshold;
          return (
            <li className="flow-card" key={i}>
              <div className="flow-card-head">
                <div className="flow-pair">
                  <span>{f.src_ip ?? "—"}</span>
                  <i aria-hidden="true">→</i>
                  <span>{f.dst_ip ?? "—"}</span>
                </div>
                <strong className="mono">{num(f.score, 3)}</strong>
              </div>
              <span className="score-track" aria-hidden="true">
                <i style={{ width: `${Math.round(f.score * 100)}%` }} />
              </span>
              <div className="flow-card-meta">
                <span className={`mono ${portHit ? "port-hit" : ""}`}>
                  {f.dst_port ?? "—"} / {f.protocol == null ? "—" : PROTO[f.protocol] ?? f.protocol}
                </span>
                <span className="reason">
                  {portHit ? "端口命中" : passed ? "分数超阈值" : "高分排序（未过阈值）"}
                </span>
                {f.label ? <span className={attack ? "tag-bad" : "tag-ok"}>{f.label}</span> : null}
              </div>
              {f.timestamp && <time className="flow-time">{f.timestamp}</time>}
            </li>
          );
        })}
      </ul>
    </>
  );
}
