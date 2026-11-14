import { useEffect, useState } from "react";
import { fetchHistoryPage } from "../api";
import { num, pct } from "../format";
import type { Comparison, HistoryPage, RunRow } from "../types";

const PICKER_PAGE_SIZE = 12;

function delta(value: number | null | undefined, percent = false) {
  if (value == null) return "—";
  return percent ? `${value >= 0 ? "+" : ""}${(value * 100).toFixed(2)}%`
    : `${value >= 0 ? "+" : ""}${value.toFixed(4)}`;
}

const STATUS_LABEL = {
  comparable: "可直接比较",
  limited: "有限对照",
  incompatible: "不可直接比较",
};

export function ComparePanel({
  selected,
  onToggle,
  onCompare,
  onClose,
  comparison,
  busy,
  error,
  onDownload,
}: {
  selected: string[];
  onToggle: (id: string) => void;
  onCompare: () => void;
  onClose: () => void;
  comparison: Comparison | null;
  busy: boolean;
  error: string | null;
  onDownload: () => void;
}) {
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<HistoryPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const timer = window.setTimeout(() => {
      setLoading(true);
      fetchHistoryPage({ limit: PICKER_PAGE_SIZE, offset, q: query })
        .then((data) => {
          if (cancelled) return;
          setPage(data);
          setLoadError(null);
        })
        .catch((reason) => {
          if (!cancelled) {
            setLoadError(reason instanceof Error ? reason.message : String(reason));
          }
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, query ? 250 : 0);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [query, offset]);

  const runs: RunRow[] = page?.runs ?? [];
  const hasPrevious = offset > 0;
  const hasNext = Boolean(page && offset + runs.length < page.total);

  return (
    <div className="compare-layer">
      <button className="compare-backdrop" type="button" aria-label="关闭跨实验对比" onClick={onClose} />
      <section className="compare-dialog" data-compare-dialog role="dialog" aria-modal="true"
               aria-labelledby="compare-title">
        <header className="compare-head">
          <div>
            <span>EXPERIMENT COMPARISON</span>
            <h2 id="compare-title">跨实验对比</h2>
            <p>选择 2–4 次实验。先验证数据、特征和切分，再比较指标和差值。</p>
          </div>
          <button className="compare-close" type="button" onClick={onClose}>关闭</button>
        </header>

        <div className="compare-picker">
          <div className="compare-picker-head">
            <div>
              <strong>选择实验</strong>
              {page && (
                <span>
                  {page.total.toLocaleString()} 次匹配 · 本机共 {page.available.toLocaleString()} 次
                </span>
              )}
            </div>
            <span>已选 {selected.length}/4</span>
          </div>
          <label className="compare-search">
            <span>搜索</span>
            <input type="search" value={query} aria-label="搜索可对比实验"
                   placeholder="来源、指纹、模型或备注"
                   onChange={(event) => {
                     setQuery(event.target.value);
                     setOffset(0);
                   }} />
          </label>
          {loadError && <p className="error" role="alert">{loadError}</p>}
          {loading && !page ? (
            <p className="hint">正在读取实验历史…</p>
          ) : runs.length ? (
            <div className={`compare-options ${loading ? "is-loading" : ""}`}
                 aria-busy={loading}>
              {runs.map((run) => {
                const checked = selected.includes(run.id);
                const disabled = !checked && selected.length >= 4;
                return (
                  <label className={`compare-option ${checked ? "on" : ""}`} key={run.id}>
                    <input type="checkbox" checked={checked} disabled={disabled}
                           aria-label={`选择 ${run.id}`} onChange={() => onToggle(run.id)} />
                    <span className="co-id mono">{run.id}</span>
                    <span className="co-src">{run.source}</span>
                    <span className="co-time mono">{(run.created_at || "").slice(5, 16)}</span>
                    <span className="co-auc mono">{num(run.best_validation_auc ?? run.best_auc, 3)}</span>
                  </label>
                );
              })}
          </div>
          ) : (
            <p className="hint">
              {query ? "没有匹配的历史实验，试试其他关键词。" : "还没有可对比的历史实验。"}
            </p>
          )}
          {page && page.total > PICKER_PAGE_SIZE && (
            <nav className="compare-pagination" aria-label="可对比实验分页">
              <button type="button" disabled={!hasPrevious || loading}
                      onClick={() => setOffset((current) => Math.max(0, current - PICKER_PAGE_SIZE))}>
                上一页
              </button>
              <span>
                {offset + 1}–{offset + runs.length} / {page.total}
              </span>
              <button type="button" disabled={!hasNext || loading}
                      onClick={() => setOffset((current) => current + PICKER_PAGE_SIZE)}>
                下一页
              </button>
            </nav>
          )}
          <div className="compare-actions">
            <button className="wide-btn primary" type="button" onClick={onCompare}
                    disabled={selected.length < 2 || selected.length > 4 || busy}>
              {busy ? "正在对比…" : "生成对比"}
            </button>
            {error && <p className="error" role="alert">{error}</p>}
          </div>
        </div>

        {comparison && (
          <div className="compare-results">
            <div className={`compare-status ${comparison.status}`} role="status">
              <strong>{STATUS_LABEL[comparison.status]}</strong>
              <span>{comparison.headline}</span>
            </div>

            <dl className="compare-checks">
              {comparison.checks.map((check) => (
                <div className={check.ok ? "ok" : "bad"} key={check.key}>
                  <dt>{check.label}</dt>
                  <dd><span aria-hidden="true">{check.ok ? "✓" : "!"}</span> {check.detail}</dd>
                </div>
              ))}
            </dl>

            <div className="table-scroll" role="region" aria-label="跨实验指标对比" tabIndex={0}>
              <table className="table compare-table">
                <thead>
                  <tr>
                    <th scope="col">实验</th>
                    <th scope="col">模型</th>
                    <th scope="col" className="num">验证 AUC</th>
                    <th scope="col" className="num">测试 AUC</th>
                    <th scope="col" className="num">PR-AUC</th>
                    <th scope="col" className="num">F1</th>
                    <th scope="col" className="num">召回率</th>
                    <th scope="col" className="num">误报率</th>
                    <th scope="col" className="num">阈值</th>
                    <th scope="col">切分</th>
                  </tr>
                </thead>
                <tbody>
                  {comparison.runs.map((run) => (
                    <tr key={run.id} className={run.id === comparison.baseline_run_id ? "baseline" : ""}>
                      <th scope="row">
                        <span className="mono">{run.id}</span>
                        <small>{run.source}</small>
                      </th>
                      <td className="mono">{run.model ?? "—"}</td>
                      <td className="num">{num(run.validation_auc)}</td>
                      <td className="num">
                        {num(run.test_auc)}
                        <small className="delta">{delta(run.delta.test_auc)}</small>
                      </td>
                      <td className="num">{num(run.pr_auc)}</td>
                      <td className="num">
                        {num(run.f1)}
                        <small className="delta">{delta(run.delta.f1)}</small>
                      </td>
                      <td className="num">{num(run.recall)}</td>
                      <td className="num">
                        {pct(run.fpr)}
                        <small className="delta">{delta(run.delta.fpr, true)}</small>
                      </td>
                      <td className="num mono">{num(run.threshold, 2)}</td>
                      <td>{run.split}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="compare-foot">
              <div>
                <strong>复现对比</strong>
                <code>{comparison.command}</code>
              </div>
              <button className="wide-btn" type="button" onClick={onDownload}>
                下载 Markdown 对比表
              </button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
