import type { Payload } from "../types";
import { LeakList } from "./LeakList";

export function ContextPanel({ payload, onCopy, onDownloadMd, onDownloadHtml, onDownloadJson,
                              onDownloadCsv, onRerunWithout,
                              copied, onCloseMobile, mobileOpen }: {
  payload: Payload | null;
  onCopy: () => void;
  onDownloadMd: () => void;
  onDownloadHtml: () => void;
  onDownloadJson: () => void;
  onDownloadCsv: () => void;
  onRerunWithout: (column: string) => void;
  copied: boolean;
  onCloseMobile: () => void;
  mobileOpen: boolean;
}) {
  const d = payload?.dataset;
  const usedFeatures = new Set(payload?.dataset.features?.used ?? []);
  const rerunLeak = payload?.warnings.find((w) =>
    (w.rule === "id_leak" || w.rule === "target_leak" || w.rule === "port_leak")
    && w.columns.some((c) => usedFeatures.has(String(c)))
  );

  return (
    <aside className="context" id="context-drawer" data-drawer="context"
           role={mobileOpen ? "dialog" : undefined}
           aria-modal={mobileOpen ? "true" : undefined}
           aria-label="报告与数据审计">
      <button className="drawer-close drawer-close-right" onClick={onCloseMobile}>
        关闭报告栏
      </button>
      <section>
        <h2>数据审计 {payload && <span className={`badge ${payload.warnings.length ? "warn" : "ok"}`}>{payload.warnings.length}</span>}</h2>
        {payload ? <LeakList warnings={payload.warnings} /> : <p className="hint">跑一次实验后显示。</p>}
        {rerunLeak && (
          <button className="wide-btn act"
                  onClick={() => onRerunWithout(
                    String(rerunLeak.columns.find((c) => usedFeatures.has(String(c))))
                  )}>
            → 去掉 {String(rerunLeak.columns.find((c) => usedFeatures.has(String(c))))} 重跑，对比 AUC 变化
          </button>
        )}
      </section>

      {!payload && (
        <section className="context-map">
          <h2>运行后生成</h2>
          <ol>
            <li><span>01</span><div><strong>泄漏与切分检查</strong><p>端口、ID、目标列和时间切分是否让指标虚高。</p></div></li>
            <li><span>02</span><div><strong>数据构成</strong><p>标签分布、参与训练的特征列，以及编码后的维度。</p></div></li>
            <li><span>03</span><div><strong>实验指纹</strong><p>数据哈希、随机种子、阈值和速率兜底参数。</p></div></li>
            <li><span>04</span><div><strong>可离线归档的报告</strong><p>HTML 自包含，Markdown 可直接贴进实验附录。</p></div></li>
          </ol>
          <p className="hint">所有计算和报告都留在这台机器上。</p>
        </section>
      )}

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
            {d.experiment_fingerprint && <><dt>实验指纹</dt><dd className="mono">{d.experiment_fingerprint}</dd></>}
            <dt>格式</dt><dd>{d.format?.format ?? "—"}</dd>
            <dt>标签</dt><dd>{d.labels?.mode ?? "—"}{d.labels?.total ? ` (${d.labels.labelled}/${d.labels.total})` : ""}</dd>
            <dt>切分</dt><dd>{d.split === "temporal" ? "时间切分"
              : d.split_requested === "temporal" ? "随机（已退化）" : "随机切分"}</dd>
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
            {(() => {
              // 只报结论卡里"没通过/需注意"的项，避免和结论卡打架
              const items = (payload.verdict?.checks ?? [])
                .filter((c) => c.status !== "pass")
                .map((c) => <li key={c.name}>{c.detail}</li>);
              if (items.length) return items;
              return <li>这份结果没有待办项，把命令和指纹贴进附录即可复现。</li>;
            })()}
            {(payload.dataset.test ?? 0) < 500 && (
              <li>测试集只有 {payload.dataset.test} 条，建议加大样本再下结论。</li>
            )}
          </ul>
        </section>
      )}

      {payload?.experiment?.command && (
        <section>
          <h2>复现命令</h2>
          <details className="command-details">
            <summary>查看本次实验命令</summary>
            <pre>{payload.experiment.command}</pre>
          </details>
        </section>
      )}

      {payload && (
        <section className="export-block">
          <h2>导出报告</h2>
          <button className="wide-btn primary" onClick={onDownloadHtml}>下载 HTML 报告</button>
          <button className="wide-btn" onClick={onDownloadMd}>下载 Markdown</button>
          <button className="wide-btn" onClick={onDownloadJson}>下载 JSON</button>
          <button className="wide-btn" onClick={onDownloadCsv}>下载模型指标 CSV</button>
          <button className="wide-btn" onClick={onCopy}>{copied ? "已复制 Markdown" : "复制 Markdown"}</button>
        </section>
      )}
    </aside>
  );
}
