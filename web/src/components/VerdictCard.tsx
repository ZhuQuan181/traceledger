import type { Verdict } from "../types";

const ICON: Record<Verdict["level"], string> = { ok: "✓", warn: "!", fail: "×" };
const LABEL: Record<Verdict["level"], string> = { ok: "可用", warn: "需说明", fail: "不可用" };
const MARK: Record<string, string> = { pass: "通过", warn: "注意", fail: "不通过" };

export function VerdictCard({ verdict }: { verdict: Verdict }) {
  return (
    <section className={`verdict-card ${verdict.level}`} aria-live="polite">
      <div className="vc-head">
        <span className="vc-icon" aria-hidden="true">{ICON[verdict.level]}</span>
        <div>
          <span className="vc-label">{LABEL[verdict.level]}</span>
          <p className="vc-headline">{verdict.headline}</p>
        </div>
      </div>

      <ul className="vc-checks">
        {verdict.checks.map((c) => (
          <li key={c.name} className={`chk ${c.status}`}>
            <span className="chk-dot" aria-hidden="true" />
            <span className="chk-name">{c.name}</span>
            <span className="chk-mark">{MARK[c.status] ?? c.status}</span>
            <span className="chk-detail">{c.detail}</span>
          </li>
        ))}
      </ul>

      <p className="vc-note">
        判断依据：CICIDS 类数据集的常见区间（AUC 0.93–0.99、误报率 0.5%–8%）。只用于发现异常，不是评分标准。
      </p>
    </section>
  );
}
