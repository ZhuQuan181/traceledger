import type { Warning } from "../types";

const LABEL: Record<Warning["severity"], string> = { high: "高", medium: "中", low: "低" };

export function LeakList({ warnings }: { warnings: Warning[] }) {
  if (!warnings.length) {
    return <p className="hint">没有发现特征或切分上的明显泄漏。</p>;
  }
  return (
    <div className="leaks">
      {warnings.map((w, i) => (
        <div className={`leak sev-${w.severity}`} key={i}>
          <div className="leak-rule">
            {w.rule}
            <span className={`sev sev-${w.severity}`}>{LABEL[w.severity]}风险 · {w.columns.slice(0, 2).join(", ")}</span>
          </div>
          <div>
            <p>{w.message}</p>
            <p className="fix">建议：{w.suggestion}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
