import { useEffect, useRef, useState } from "react";
import { deleteRun, fetchHistoryPage, pruneHistory, updateRunMeta } from "../api";
import type { HistoryPage, RunRow, RunStatus } from "../types";

const PAGE_SIZE = 30;

const STATUS_LABEL: Record<RunStatus, string> = {
  unreviewed: "未标记",
  baseline: "基准",
  failed: "失败",
  archived: "已归档",
};

const EMPTY_PAGE: HistoryPage = {
  runs: [],
  total: 0,
  available: 0,
  db_bytes: 0,
  models: [],
};

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function timeLabel(value: string) {
  return (value || "").slice(0, 16).replace("T", " ");
}

export function HistoryPanel({
  active,
  onOpen,
  onClose,
  onChanged,
}: {
  active?: string;
  onOpen: (id: string) => void;
  onClose: () => void;
  onChanged: () => void;
}) {
  const dialogRef = useRef<HTMLElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  const [query, setQuery] = useState("");
  const [model, setModel] = useState("");
  const [status, setStatus] = useState<RunStatus | "">("");
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<HistoryPage>(EMPTY_PAGE);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [keep, setKeep] = useState("50");
  const [pruneArmed, setPruneArmed] = useState(false);
  const [pruning, setPruning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const dialog = dialogRef.current;
    const focusable = () => Array.from(
      dialog?.querySelectorAll<HTMLElement>(
        'button:not(:disabled), [href], input:not(:disabled), select:not(:disabled), ' +
        'textarea:not(:disabled), summary, [tabindex]:not([tabindex="-1"])',
      ) ?? [],
    ).filter((element) => element.offsetParent !== null);
    const frame = window.requestAnimationFrame(() => {
      (dialog?.querySelector<HTMLElement>(".history-close") ?? focusable()[0])?.focus();
    });
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab" || !dialog) return;
      const items = focusable();
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey, true);
    return () => {
      window.cancelAnimationFrame(frame);
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", onKey, true);
      if (previous?.isConnected) previous.focus();
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const timer = window.setTimeout(() => {
      setLoading(true);
      fetchHistoryPage({ limit: PAGE_SIZE, offset, q: query, model, status })
        .then((data) => {
          if (cancelled) return;
          if (data.total > 0 && offset >= data.total) {
            setOffset(Math.max(0, Math.floor((data.total - 1) / PAGE_SIZE) * PAGE_SIZE));
            return;
          }
          if (!data.total && offset !== 0) {
            setOffset(0);
            return;
          }
          setPage(data);
          setDrafts(Object.fromEntries(data.runs.map((run) => [run.id, run.note ?? ""])));
          setError(null);
        })
        .catch((reason) => {
          if (!cancelled) {
            setError(reason instanceof Error ? reason.message : String(reason));
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
  }, [query, model, status, offset, reloadKey]);

  function applyUpdate(updated: { id: string; note: string; status: RunStatus }) {
    setPage((current) => ({
      ...current,
      runs: current.runs.map((run) => run.id === updated.id ? { ...run, ...updated } : run),
    }));
    setDrafts((current) => ({ ...current, [updated.id]: updated.note }));
    setNotice(`已更新 ${updated.id}`);
    onChanged();
  }

  async function saveMeta(
    run: RunRow,
    patch: { note?: string; status?: RunStatus },
  ) {
    setSavingId(run.id);
    setError(null);
    try {
      applyUpdate(await updateRunMeta(run.id, patch));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setSavingId(null);
    }
  }

  async function removeRun(run: RunRow) {
    setDeletingId(run.id);
    setError(null);
    setNotice(null);
    try {
      await deleteRun(run.id);
      setConfirmDeleteId(null);
      setNotice(`已删除 ${run.id}`);
      onChanged();
      if (page.runs.length === 1 && offset >= PAGE_SIZE) {
        setOffset((current) => Math.max(0, current - PAGE_SIZE));
      } else {
        setReloadKey((key) => key + 1);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setDeletingId(null);
    }
  }

  async function applyPrune() {
    const parsed = Number(keep);
    if (!Number.isInteger(parsed) || parsed < 1 || parsed > 5000) {
      setError("保留数量需为 1–5000 的整数。");
      return;
    }
    setPruning(true);
    setError(null);
    setNotice(null);
    try {
      const result = await pruneHistory(parsed);
      setPruneArmed(false);
      setOffset(0);
      setReloadKey((key) => key + 1);
      setNotice(
        result.deleted
          ? `已清理 ${result.deleted} 次旧实验，保留最近 ${result.remaining} 次。`
          : "没有需要清理的实验。",
      );
      onChanged();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setPruning(false);
    }
  }

  function openRun(id: string) {
    onOpen(id);
    onClose();
  }

  const rangeStart = page.total ? offset + 1 : 0;
  const rangeEnd = offset + page.runs.length;
  const hasPrevious = offset > 0;
  const hasNext = offset + page.runs.length < page.total;

  return (
    <div className="compare-layer history-layer">
      <button className="compare-backdrop" type="button" aria-label="关闭实验历史"
              onClick={onClose} />
      <section className="compare-dialog history-dialog" ref={dialogRef}
               data-history-dialog role="dialog" aria-modal="true"
               aria-labelledby="history-title" aria-busy={loading}>
        <header className="compare-head">
          <div>
            <span>LOCAL HISTORY</span>
            <h2 id="history-title">实验历史</h2>
            <p>搜索、标记并回到任意一次实验；数据只保存在本机 SQLite。</p>
          </div>
          <button className="compare-close history-close" type="button" onClick={onClose}>
            关闭
          </button>
        </header>

        <div className="history-capacity">
          <span>本机共 <strong>{page.available.toLocaleString()}</strong> 次实验</span>
          <span>当前筛选 <strong>{page.total.toLocaleString()}</strong> 次</span>
          <span>数据库 <strong>{formatBytes(page.db_bytes)}</strong></span>
        </div>

        <div className="history-filters">
          <label>
            <span>搜索</span>
            <input type="search" value={query} placeholder="来源、指纹、模型或备注"
                   aria-label="搜索历史" onChange={(event) => {
                     setQuery(event.target.value);
                     setOffset(0);
                   }} />
          </label>
          <label>
            <span>模型</span>
            <select value={model} aria-label="按模型筛选"
                    onChange={(event) => {
                      setModel(event.target.value);
                      setOffset(0);
                    }}>
              <option value="">全部模型</option>
              {page.models.map((name) => <option key={name} value={name}>{name}</option>)}
            </select>
          </label>
          <label>
            <span>状态</span>
            <select value={status} aria-label="按状态筛选"
                    onChange={(event) => {
                      setStatus(event.target.value as RunStatus | "");
                      setOffset(0);
                    }}>
              <option value="">全部状态</option>
              {(Object.entries(STATUS_LABEL) as [RunStatus, string][]).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>
          <button className="history-refresh" type="button"
                  onClick={() => setReloadKey((key) => key + 1)}>
            刷新
          </button>
        </div>

        <details className="history-maintenance">
          <summary>清理旧记录</summary>
          <div className="history-maintenance-body">
            <p>按创建时间保留最近的实验，更旧的记录会永久删除。至少保留 1 条。</p>
            <label>
              <span>保留最近</span>
              <input type="number" min="1" max="5000" step="1" value={keep}
                     aria-label="保留最近多少次实验"
                     onChange={(event) => {
                       setKeep(event.target.value);
                       setPruneArmed(false);
                     }} />
              <span>次</span>
            </label>
            {pruneArmed ? (
              <div className="history-confirm" role="alert">
                <span>将永久删除超出保留数量的历史，确认继续？</span>
                <button type="button" className="danger" disabled={pruning}
                        onClick={applyPrune}>
                  {pruning ? "清理中…" : "确认清理"}
                </button>
                <button type="button" disabled={pruning}
                        onClick={() => setPruneArmed(false)}>
                  取消
                </button>
              </div>
            ) : (
              <button className="history-prune" type="button"
                      disabled={loading || !Number.isInteger(Number(keep))}
                      onClick={() => setPruneArmed(true)}>
                清理更旧记录
              </button>
            )}
          </div>
        </details>

        {error && <p className="history-message error" role="alert">{error}</p>}
        {notice && <p className="history-message" role="status">{notice}</p>}

        {loading && !page.runs.length ? (
          <p className="history-empty">正在读取本地历史…</p>
        ) : !page.runs.length ? (
          <p className="history-empty">没有符合条件的实验。清空筛选或先跑一次实验。</p>
        ) : (
          <ul className="history-panel-list">
            {page.runs.map((run) => {
              const statusValue = run.status ?? "unreviewed";
              return (
                <li key={run.id} className={`hp-item ${run.id === active ? "on" : ""}`}>
                  <button className="hp-open" type="button" onClick={() => openRun(run.id)}>
                    <span className="hp-id">{run.id}</span>
                    <span className={`hp-status status-${statusValue}`}>
                      {STATUS_LABEL[statusValue]}
                    </span>
                    <span className="hp-source">{run.source || "未知来源"}</span>
                    <span className="hp-model">{run.best_model ?? "—"}</span>
                    <span className="hp-auc">{run.best_auc == null ? "—" : run.best_auc.toFixed(4)}</span>
                    <span className="hp-time">{timeLabel(run.created_at)}</span>
                  </button>
                  <div className="hp-note">{run.note || "未添加备注"} · {run.rows.toLocaleString()} 条流</div>
                  <details className="hp-manage">
                    <summary>备注 / 状态</summary>
                    <div className="hp-edit">
                      <label>
                        <span>状态</span>
                        <select value={statusValue} disabled={savingId === run.id}
                                aria-label={`状态 ${run.id}`}
                                onChange={(event) => saveMeta(run, {
                                  status: event.target.value as RunStatus,
                                })}>
                          {(Object.entries(STATUS_LABEL) as [RunStatus, string][]).map(
                            ([value, label]) => <option key={value} value={value}>{label}</option>,
                          )}
                        </select>
                      </label>
                      <label className="hp-note-field">
                        <span>备注</span>
                        <input value={drafts[run.id] ?? ""} maxLength={500}
                               aria-label={`备注 ${run.id}`}
                               placeholder="例如：去掉端口后重跑"
                               onChange={(event) => setDrafts((current) => ({
                                 ...current,
                                 [run.id]: event.target.value,
                               }))} />
                      </label>
                      <button type="button" disabled={savingId === run.id}
                              onClick={() => saveMeta(run, { note: drafts[run.id] ?? "" })}>
                        {savingId === run.id ? "保存中…" : "保存备注"}
                      </button>
                    </div>
                    <div className="hp-danger-zone">
                      {confirmDeleteId === run.id ? (
                        <div className="history-confirm" role="alert">
                          <span>删除后不可恢复，确认删除 {run.id}？</span>
                          <button type="button" className="danger"
                                  disabled={deletingId === run.id}
                                  onClick={() => removeRun(run)}>
                            {deletingId === run.id ? "删除中…" : "确认删除"}
                          </button>
                          <button type="button" disabled={deletingId === run.id}
                                  onClick={() => setConfirmDeleteId(null)}>
                            取消
                          </button>
                        </div>
                      ) : (
                        <button className="history-delete" type="button"
                                onClick={() => setConfirmDeleteId(run.id)}>
                          删除这次实验
                        </button>
                      )}
                    </div>
                  </details>
                </li>
              );
            })}
          </ul>
        )}
        {(page.total > PAGE_SIZE || offset > 0) && (
          <nav className="history-pagination" aria-label="历史分页">
            <button type="button" disabled={!hasPrevious || loading}
                    onClick={() => setOffset((current) => Math.max(0, current - PAGE_SIZE))}>
              上一页
            </button>
            <span aria-live="polite">
              第 {rangeStart.toLocaleString()}–{rangeEnd.toLocaleString()} 条，
              共 {page.total.toLocaleString()} 条
            </span>
            <button type="button" disabled={!hasNext || loading}
                    onClick={() => setOffset((current) => current + PAGE_SIZE)}>
              下一页
            </button>
          </nav>
        )}
      </section>
    </div>
  );
}
