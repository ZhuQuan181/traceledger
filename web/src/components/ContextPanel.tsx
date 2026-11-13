import type { Payload } from "../types";
import { LeakList } from "./LeakList";

export function ContextPanel({ payload, onCopy, onDownloadMd, onDownloadHtml, onRerunWithout, copied }: {
  payload: Payload | null;
  onCopy: () => void;
  onDownloadMd: () => void;
  onDownloadHtml: () => void;
  onRerunWithout: (column: string) => void;
  copied: boolean;
}) {
  const d = payload?.dataset;
  const portLeak = payload?.warnings.find((w) => w.rule === "port_leak");
  const anyLeak = payload?.warnings.find((w) => w.rule === "id_leak" || w.rule === "target_leak") ?? portLeak;

  return (
    <aside className="context">
      <section>
        <h2>泄漏检查 {payload && <span className={`badge ${payload.warnings.length ? "warn" : "ok"}`}>{payload.warnings.length}</span>}</h2>
        {payload ? <LeakList warnings={payload.warnings} /> : <p className="hint">跑一次实验后显示。</p>}
        {anyLeak && (
          <button className="wide-btn act" onClick={() => onRerunWithout(anyLeak.columns[0] as string)}>
            → 去掉 {String(anyLeak.columns[0])} 重跑，对比 AUC 变化
          </button>
        )}
      </section>

      {d?.classes?.length ? (
        <section>
          <h2>数据构成</h2>
          <div className="dist">
            {d.classes.map((c) => {
              const total = d.classes!.reduce((s, x) => s + x.count, 0) || 1;
              return (
                <div className="dist-row" key={c.label}>
                  <span className="dist-label" title={c.label}>{c.label}</span>
                  <span className="dist-bar"><i style={{ width: `${Math.max(2, (c.count / total) * 100)}%` }} /></span>
                  <span className="dist-count mono">{c.count.toLocaleString()}</span>
                </div>
              );
            })}
          </div>
          {d.features?.used?.length ? (
            <details className="feat-details">
              <summary>{d.features.used.length} 列参与训练 · 编码后 {d.features.encoded} 维</summary>
              <p className="feat-chips">
                {d.features.used.map((f) => <code key={f}>{f}</code>)}
              </p>
            </details>
          ) : null}
        </section>
      ) : null}

      {d && (
        <section>
          <h2>实验信息</h2>
          <dl className="facts">
            <dt>指纹</dt><dd className="mono">{d.hash}</dd>
            <dt>格式</dt><dd>{d.format?.format ?? "—"}</dd>
            <dt>标签</dt><dd>{d.labels?.mode ?? "—"}{d.labels?.total ? ` (${d.labels.labelled}/${d.labels.total})` : ""}</dd>
            <dt>切分</dt><dd>{d.split === "temporal" ? "时间切分" : "随机切分"}</dd>
            <dt>种子</dt><dd className="mono">{d.seed ?? 42}</dd>
            <dt>速率兜底</dt><dd className="mono">{d.engineering?.min_duration_ms ?? 1} ms</dd>
          </dl>
        </section>
      )}

      {payload && (
        <section>
          <h2>下一步</h2>
          <ul className="steps">
            {payload.warnings.some((w) => w.rule === "time_leak") && (
              <li>改用时间切分：随机切分会让"未来"进训练集。</li>
            )}
            {(payload.results.find((r) => r.model === payload.best_model)?.metrics.auc ?? 0) >= 0.995
              && payload.warnings.length > 0 && (
              <li>AUC 已接近 1，先修泄漏再比较模型——现在的高低不说明泛化能力。</li>
            )}
            {(payload.dataset.test ?? 0) < 50 && <li>测试集不足 50 条，建议加大样本再下结论。</li>}
            {payload.warnings.length === 0 && (
              <li>没有明显泄漏，可以把这批参数记进实验历史，换数据集复现一次。</li>
            )}
          </ul>
        </section>
      )}

      {payload && (
        <section className="export-block">
          <h2>导出</h2>
          <button className="wide-btn" onClick={onCopy}>{copied ? "已复制 Markdown" : "复制 Markdown"}</button>
          <button className="wide-btn" onClick={onDownloadMd}>下载 Markdown</button>
        </section>
      )}
    </aside>
  );
}
