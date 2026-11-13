import type { Payload, Result } from "../types";

export function MetricsBand({ payload, best }: { payload: Payload; best: Result | null }) {
  const m = best?.metrics;
  const leaky = payload.warnings.some((w) => w.rule === "id_leak" || w.rule === "target_leak" || w.rule === "port_leak");
  const suspicious = leaky && (m?.auc ?? 0) >= 0.995;
  return (
    <div className="band">
      <div className="cell">
        <div className="k">最佳模型</div>
        <div className="v model-name-v">{best?.model ?? "—"}</div>
        <div className="n">{best ? (best.kind === "supervised" ? "监督学习" : "无监督基线") : ""}</div>
      </div>
      <div className="cell">
        <div className="k">AUC</div>
        <div className={`v ${suspicious ? "warn-v" : ""}`}>{m?.auc == null ? "—" : m.auc.toFixed(4)}</div>
        <div className={`n ${suspicious ? "warn-n" : ""}`}>
          {suspicious ? "接近满分，且存在泄漏 — 先看右侧提示" : "排序能力，1 表示完美"}
        </div>
      </div>
      <div className="cell">
        <div className="k">F1</div>
        <div className="v">{m ? m.f1.toFixed(4) : "—"}</div>
        <div className="n">
          {m ? `精确率 ${m.precision.toFixed(3)} · 召回率 ${m.recall.toFixed(3)}` : ""}
        </div>
      </div>
      <div className="cell">
        <div className="k">误报率</div>
        <div className="v mono-num">
          {m?.fpr == null ? "—" : `${(m.fpr * 100).toFixed(2)}%`}
        </div>
        <div className="n">
          正常流被误判 · 测试集 {m ? m.attack_support : 0} 条攻击
        </div>
      </div>
    </div>
  );
}
