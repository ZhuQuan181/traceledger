import type { Warning } from "../types";

const LABEL: Record<Warning["severity"], string> = { high: "高", medium: "中", low: "低" };

export function LeakList({ warnings }: { warnings: Warning[] }) {
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>数据泄漏检查</h2>
        <span className="mono dim">{warnings.length} 条</span>
      </div>
      {warnings.length === 0 ? (
        <p className="empty-note">没有发现特征或切分上的明显泄漏。</p>
      ) : (
        <ul className="leaks">
          {warnings.map((w, i) => (
            <li key={i} className={`leak sev-${w.severity}`}>
              <div className="leak-rail" aria-hidden="true" />
              <div className="leak-body">
                <div className="leak-top">
                  <span className="mono rule">{w.rule}</span>
                  <span className="sev">{LABEL[w.severity]}</span>
                  <span className="cols mono">{w.columns.join(", ")}</span>
                </div>
                <p className="leak-msg">{w.message}</p>
                <p className="leak-fix">{w.suggestion}</p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
