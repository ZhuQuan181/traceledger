import { useEffect, useMemo, useRef, useState } from "react";
import { fetchHistory, fetchModels, loadRun, runDemo, runUpload } from "./api";
import { num, pct } from "./format";
import type { ModelInfo, Payload, RunRow } from "./types";
import { TopBar } from "./components/TopBar";
import { ConfigRail } from "./components/ConfigRail";
import { ContextPanel } from "./components/ContextPanel";
import { MetricMatrix } from "./components/MetricMatrix";
import { SignalStrip } from "./components/SignalStrip";
import { AblationTable } from "./components/AblationTable";
import { TopFlows } from "./components/TopFlows";
import { VerdictCard } from "./components/VerdictCard";
import { ChecklistCard } from "./components/ChecklistCard";
import { FlowPreview } from "./components/FlowPreview";
import { InvestigationPanel } from "./components/InvestigationPanel";
import { HistoryList } from "./components/HistoryList";
import { ThresholdScan } from "./components/ThresholdScan";

const ALL = ["mlp", "iforest", "autoencoder"];
type MobilePanel = "config" | "history" | "context" | null;

function configSignature(config: {
  models: string[];
  split: string;
  test_size: number;
  validation_size: number;
  seed: number;
  threshold: number;
  threshold_mode: "fixed" | "f1";
  ablate: string | null;
  source: string;
  normal: number;
  attack: number;
  leaky: boolean;
}) {
  return JSON.stringify({
    ...config,
    models: [...config.models].sort(),
    ablate: config.ablate || null,
  });
}

function csvCell(value: unknown) {
  const text = value == null ? "" : String(value);
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function metricsCsv(payload: Payload) {
  const header = [
    "model", "kind", "validation_auc", "test_auc", "test_pr_auc", "test_f1",
    "precision", "recall", "fpr", "threshold", "duration_s", "tn", "fp", "fn", "tp",
  ];
  const rows = payload.results.map((row) => [
    row.model,
    row.kind,
    row.validation_metrics?.auc,
    row.metrics.auc,
    row.metrics.pr_auc,
    row.metrics.f1,
    row.metrics.precision,
    row.metrics.recall,
    row.metrics.fpr,
    row.threshold,
    row.duration_s,
    row.confusion.tn,
    row.confusion.fp,
    row.confusion.fn,
    row.confusion.tp,
  ]);
  return [header, ...rows].map((row) => row.map(csvCell).join(",")).join("\n");
}

export default function App() {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [selected, setSelected] = useState<string[]>(ALL);
  const [source, setSource] = useState<"demo" | "file">("demo");
  const [normal, setNormal] = useState(5000);
  const [attack, setAttack] = useState(500);
  const [leaky, setLeaky] = useState(false);
  const [split, setSplit] = useState<"temporal" | "random" | "group">("temporal");
  const [testSize, setTestSize] = useState(0.3);
  const [validationSize, setValidationSize] = useState(0.2);
  const [seed, setSeed] = useState(42);
  const [threshold, setThreshold] = useState(0.5);
  const [thresholdMode, setThresholdMode] = useState<"fixed" | "f1">("fixed");
  const [ablate, setAblate] = useState("");
  const [ablationColumns, setAblationColumns] = useState<string[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [labelsFile, setLabelsFile] = useState<File | null>(null);
  const [allowPickle, setAllowPickle] = useState(false);
  const [payload, setPayload] = useState<Payload | null>(null);
  const [history, setHistory] = useState<RunRow[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [historyNotice, setHistoryNotice] = useState<string | null>(null);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [mobilePanel, setMobilePanel] = useState<MobilePanel>(null);
  const requestInFlight = useRef(false);

  useEffect(() => {
    fetchModels().then((items) => {
      setModels(items);
      setConnectionError(null);
    }).catch(() => {
      setModels(ALL.map((n) => ({ name: n, kind: n === "mlp" ? "supervised" : "unsupervised" })));
      setConnectionError("无法连接本地 FlowLab 后端；当前配置只是占位，运行实验仍会失败。");
    });
    refreshHistory();
  }, []);

  useEffect(() => {
    if (!mobilePanel) return;
    const previous = document.body.style.overflow;
    const previousFocus = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
    document.body.style.overflow = "hidden";
    const drawer = document.querySelector<HTMLElement>(`[data-drawer="${mobilePanel}"]`);
    const focusable = () => Array.from(
      drawer?.querySelectorAll<HTMLElement>(
        'button:not(:disabled), [href], input:not(:disabled), select:not(:disabled), ' +
        'textarea:not(:disabled), [tabindex]:not([tabindex="-1"])'
      ) ?? []
    ).filter((element) => element.offsetParent !== null);
    const frame = window.requestAnimationFrame(() => focusable()[0]?.focus());
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setMobilePanel(null);
        return;
      }
      if (event.key !== "Tab" || !drawer) return;
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
      document.body.style.overflow = previous;
      document.removeEventListener("keydown", onKey, true);
      if (previousFocus?.isConnected) previousFocus.focus();
    };
  }, [mobilePanel]);

  useEffect(() => {
    if (!busy) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [busy]);

  useEffect(() => {
    const media = window.matchMedia("(max-width: 900px)");
    const onChange = () => {
      if (!media.matches) setMobilePanel(null);
    };
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  function refreshHistory() {
    fetchHistory().then((items) => {
      setHistory(items);
    }).catch(() => setHistory([]));
  }

  const best = useMemo(() => {
    if (!payload?.results.length) return null;
    return payload.results.reduce((a, b) =>
      ((b.validation_metrics?.auc ?? b.metrics.auc ?? 0)
        > (a.validation_metrics?.auc ?? a.metrics.auc ?? 0) ? b : a));
  }, [payload]);

  const currentConfig = useMemo(() => configSignature({
    models: selected,
    split,
    test_size: testSize,
    validation_size: validationSize,
    seed,
    threshold,
    threshold_mode: thresholdMode,
    ablate: ablate || null,
    source: source === "demo"
      ? `demo:${normal}:${attack}:${leaky}`
      : `file:${file?.name ?? ""}`,
    normal,
    attack,
    leaky,
  }), [selected, split, testSize, validationSize, seed, threshold, thresholdMode, ablate, source, normal, attack, leaky, file]);

  const resultConfig = useMemo(() => {
    const exp = payload?.experiment;
    if (!exp) return null;
    return configSignature({
      models: exp.models,
      split: exp.split,
      test_size: exp.test_size ?? 0.3,
      validation_size: exp.validation_size ?? 0.2,
      seed: exp.seed ?? 42,
      threshold: exp.threshold ?? 0.5,
      threshold_mode: exp.threshold_mode ?? "fixed",
      ablate: exp.ablate ?? null,
      source: exp.source_kind === "demo"
        ? `demo:${exp.normal}:${exp.attack}:${Boolean(exp.leaky)}`
        : `file:${(exp.source_ref ?? "").split(/[\\/]/).pop() ?? ""}`,
      normal: exp.normal,
      attack: exp.attack,
      leaky: Boolean(exp.leaky),
    });
  }, [payload]);

  const stale = Boolean(payload && resultConfig && currentConfig !== resultConfig);

  function restoreConfig(data: Payload, restoreSource: boolean) {
    const exp = data.experiment;
    if (!exp) {
      if (restoreSource) {
        setHistoryNotice("这次历史记录生成于旧版本，未保存完整运行配置；必须手动核对数据与参数后再重跑。");
      }
      return;
    }
    setSelected(exp.models);
    setSplit(exp.split);
    setTestSize(exp.test_size ?? 0.3);
    setValidationSize(exp.validation_size ?? 0.2);
    setSeed(exp.seed ?? 42);
    setThreshold(exp.threshold ?? 0.5);
    setThresholdMode(exp.threshold_mode ?? "fixed");
    setAblate(exp.ablate ?? "");
    setNormal(exp.normal ?? 5000);
    setAttack(exp.attack ?? 500);
    setLeaky(Boolean(exp.leaky));
    if (exp.source_kind === "demo") {
      setSource("demo");
      if (restoreSource) {
        setFile(null);
        setLabelsFile(null);
      }
      setHistoryNotice(null);
    } else {
      setSource("file");
      if (restoreSource) {
        setFile(null);
        setLabelsFile(null);
        setHistoryNotice(
          `这次实验来自上传文件「${exp.source_ref || "未知文件"}」。浏览器不能恢复本地文件，`
          + "请重新选择同一数据与标签文件后再重跑。"
        );
      }
    }
  }

  function revealResults() {
    if (!window.matchMedia("(max-width: 900px)").matches) return;
    window.requestAnimationFrame(() => {
      document.getElementById("result-start")?.scrollIntoView({
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
        block: "start",
      });
    });
  }

  function applyPayload(data: Payload, preferredAblate?: string, restoreSource = false) {
    setPayload(data);
    const used = data.dataset.features?.used ?? [];
    setAblationColumns(used);
    setAblate((current) => {
      const target = preferredAblate ?? current;
      return target && used.includes(target) ? target : "";
    });
    restoreConfig(data, restoreSource);
  }

  async function run(override?: { ablate?: string }) {
    if (requestInFlight.current) return;
    if (selected.length === 0) {
      setError("至少选择一个模型。");
      return;
    }
    if (source === "file" && !file) {
      setError("请先选择数据文件。");
      return;
    }
    if (source === "demo" && (normal < 100 || normal > 200_000 || attack < 10 || attack > 50_000)) {
      setError("正常流需在 100–200,000 之间，攻击流需在 10–50,000 之间。");
      return;
    }
    if (testSize < 0.05 || testSize > 0.5) {
      setError("测试集比例需在 0.05–0.5 之间。");
      return;
    }
    if (validationSize < 0.05 || validationSize > 0.4 || testSize + validationSize > 0.8) {
      setError("验证集需在 0.05–0.4 之间，且验证集与测试集合计不超过 80%。");
      return;
    }
    requestInFlight.current = true;
    setBusy(true);
    setError(null);
    setMobilePanel(null);
    try {
      const ablateValue = override?.ablate ?? ablate;
      const params = {
        seed, split, test_size: testSize, validation_size: validationSize, models: selected,
        threshold, threshold_mode: thresholdMode,
        ablate: ablateValue || null,
      };
      const data = source === "demo"
        ? await runDemo({ ...params, normal, attack, leaky })
        : await runUpload(file!, params, labelsFile, allowPickle);
      applyPayload(data, ablateValue);
      setConnectionError(null);
      refreshHistory();
      revealResults();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      requestInFlight.current = false;
      setBusy(false);
    }
  }

  async function openRun(id: string) {
    if (requestInFlight.current) return;
    requestInFlight.current = true;
    setBusy(true);
    setError(null);
    setMobilePanel(null);
    try {
      applyPayload(await loadRun(id), undefined, true);
      revealResults();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      requestInFlight.current = false;
      setBusy(false);
    }
  }

  function toggleModel(name: string) {
    setSelected((s) => (s.includes(name) ? s.filter((x) => x !== name) : [...s, name]));
  }

  function selectFile(next: File | null) {
    setFile(next);
    setLabelsFile(null);
    setAblate("");
    setAblationColumns([]);
    setHistoryNotice(null);
    setError(null);
    if (!/\.(pkl|pickle|p)$/i.test(next?.name ?? "")) setAllowPickle(false);
  }

  function save(content: string, mime: string, ext: string) {
    if (!payload) return;
    const blob = new Blob([content], { type: `${mime};charset=utf-8` });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `flowlab-${payload.dataset.hash}.${ext}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.setTimeout(() => URL.revokeObjectURL(a.href), 0);
  }

  async function copy() {
    if (!payload) return;
    setError(null);
    try {
      await navigator.clipboard.writeText(payload.report_md);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      const area = document.createElement("textarea");
      area.value = payload.report_md;
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      const ok = document.execCommand("copy");
      area.remove();
      if (ok) {
        setCopied(true);
        window.setTimeout(() => setCopied(false), 1600);
      } else {
        setError("复制失败，请改用下载 Markdown。");
      }
    }
  }

  const canRun = selected.length > 0 && (source === "demo" || file !== null);

  const d = payload?.dataset;
  // "受泄漏影响" 一律以结论卡为准：消融已排除端口时 verdict != fail，就不该再标红
  const suspicious = payload?.verdict?.level === "fail"
    || (payload?.verdict?.level === "warn" && payload.verdict.checks.some(
         (c) => c.name === "指标可信度" && c.status === "warn" && c.detail.includes("满分")));
  const portLeakColumn = payload?.warnings.find((w) => w.rule === "port_leak")?.columns[0];
  // 徽标措辞跟着结论走：消融已证明端口无影响时，不能再写"受泄漏影响"
  const verdictLevel = payload?.verdict?.level;
  const bestBadge = verdictLevel === "fail" ? (portLeakColumn ? `受 ${portLeakColumn} 影响` : "指标待复核")
    : verdictLevel === "warn" && suspicious ? "最高分 · 需换数据确认"
    : "最佳";
  const flowNo = payload?.ablation ? 4 : 3;
  const sectionNo = {
    flow: String(flowNo).padStart(2, "0"),
    investigation: String(flowNo + 1).padStart(2, "0"),
  };

  return (
    <div className={`shell mobile-panel-${mobilePanel ?? "none"}`}>
      <a className="skip" href="#main">跳到主要内容</a>
      <TopBar payload={payload} busy={busy} runs={history} activeRun={payload?.run_id}
              onOpenRun={openRun} mobilePanel={mobilePanel}
              onOpenPanel={(panel) => setMobilePanel((current) => current === panel ? null : panel)} />

      {mobilePanel && (
        <button className="drawer-backdrop" aria-label="关闭侧栏"
                onClick={() => setMobilePanel(null)} />
      )}

      {mobilePanel === "history" && (
        <aside className="mobile-history-drawer" id="history-drawer" data-drawer="history"
               role="dialog" aria-modal="true" aria-label="最近实验">
          <header>
            <div>
              <span>LOCAL HISTORY</span>
              <h2>最近实验</h2>
            </div>
            <button className="drawer-close" onClick={() => setMobilePanel(null)}>关闭</button>
          </header>
          <HistoryList runs={history} active={payload?.run_id}
                       onOpen={(id) => { openRun(id); }} />
          <p className="hint">历史只保存在本机 SQLite 中；打开上传文件的记录后，需要重新选择原文件才能重跑。</p>
        </aside>
      )}

      <div className="workspace">
        <ConfigRail
          models={models} selected={selected} onToggleModel={toggleModel}
          source={source}
          onSource={(s) => {
            setSource(s);
            setError(null);
            setFile(null);
            setLabelsFile(null);
            setAllowPickle(false);
            setAblate("");
            setAblationColumns([]);
          }}
          normal={normal} attack={attack} onNormal={setNormal} onAttack={setAttack}
          leaky={leaky} onLeaky={setLeaky}
          split={split} onSplit={setSplit}
          testSize={testSize} onTestSize={setTestSize}
          validationSize={validationSize} onValidationSize={setValidationSize}
          seed={seed} onSeed={setSeed}
          threshold={threshold} onThreshold={setThreshold}
          thresholdMode={thresholdMode} onThresholdMode={setThresholdMode}
          ablate={ablate} onAblate={setAblate} ablationColumns={ablationColumns}
          file={file} onFile={selectFile}
          labelsFile={labelsFile} onLabelsFile={setLabelsFile}
          allowPickle={allowPickle} onAllowPickle={setAllowPickle}
          busy={busy} onRun={() => run()} error={error} notice={historyNotice} stale={stale}
          onCloseMobile={() => setMobilePanel(null)}
          mobileOpen={mobilePanel === "config"}
        />

        <main className="canvas" id="main">
          {connectionError && (
            <div className="connection-warning" role="status">
              {connectionError} 请在本机运行 <code>uv run flowlab serve</code>。
            </div>
          )}
          {error && (
            <div className="run-error" role="alert">
              <span>{error}</span>
              <button type="button" onClick={() => setError(null)} aria-label="关闭错误提示">
                关闭
              </button>
            </div>
          )}

          {!payload && !busy && (
            <section className="intro">
              <div className="intro-copy">
                <p className="intro-kicker"><span className="live" aria-hidden="true" />本地流量实验室</p>
                <h1>先跑一次，<br />再谈模型。</h1>
                <p>
                  把流量实验拆成四步：导入数据、审计泄漏、统一特征、对比模型。
                  每一步的输入输出都写进报告，换个人也能复现。
                </p>
                <div className="intro-actions">
                  <button className="primary-action intro-run" onClick={() => run()}
                          disabled={busy || !canRun}>
                    {source === "file" && !file ? "先选择数据文件" : "用当前配置跑一次"}
                  </button>
                  {history.length > 0 && <span className="hint">或从顶部打开一次历史实验</span>}
                </div>
                {!canRun && (
                  <p className="intro-warning" role="status">
                    {source === "file" ? "上传模式需要先选择一个数据文件。" : "至少选择一个模型。"}
                  </p>
                )}
              </div>

              <FlowPreview flows={normal + attack} threshold={threshold} />

              <ol className="intro-steps">
                <li><span>导入</span>默认合成数据；自己的数据切到「上传文件」。</li>
                <li><span>切分</span>优先时间切分，带时间戳却随机切分会报泄漏。</li>
                <li><span>审计</span>看消融结果，判断指标是否靠单一列撑着。</li>
                <li><span>对比</span>多个模型共用同一份特征矩阵，指标才可比。</li>
              </ol>
            </section>
          )}

          {payload && d && best && (
            <>
              {stale && (
                <div className="config-stale" role="status">
                  <span>当前配置已修改；下方仍是上一次运行的结果。</span>
                  <button type="button" onClick={() => run()} disabled={busy}>按当前配置运行</button>
                </div>
              )}
              <header className="head" id="result-start">
                <div className="head-kicker">
                  RUN {payload.run_id ?? "—"} <span className="dot-sep">·</span> {d.format?.format ?? "data"}
                </div>
                <h1>{d.source.replace(/（.*?）/g, "")}</h1>
                <p className="head-sub">
                  {d.rows.toLocaleString()} 条流 <span className="dot-sep">/</span> 训练 {d.train.toLocaleString()}{" "}
                  · 验证 {d.validation.toLocaleString()} <span className="dot-sep">/</span> 测试{" "}
                  {d.test.toLocaleString()} <span className="dot-sep">/</span>{" "}
                  {d.split === "temporal" ? "时间切分"
                    : d.split === "group" ? "实体分组切分"
                    : d.split_requested === "temporal" ? "随机切分（时间切分已退化）" : "随机切分"}
                  {d.generalization ? ` · ${d.generalization}` : ""}
                </p>
                <div className="split-meter" aria-hidden="true">
                  <span className="split-train" style={{ width: `${Math.round((d.train / d.rows) * 100)}%` }} />
                  <span className="split-validation" style={{ width: `${Math.round((d.validation / d.rows) * 100)}%` }} />
                  <span className="split-test" style={{ width: `${Math.round((d.test / d.rows) * 100)}%` }} />
                </div>

                <div className="verdict">
                  <div className="v-item">
                    <span className="v-k">验证集最佳</span>
                    <span className="v-v mono">{best.model}</span>
                  </div>
                  <div className="v-item">
                    <span className="v-k">AUC</span>
                    <span className={`v-v ${suspicious ? "caution" : ""}`}>
                      {num(best.metrics.auc)}
                      {suspicious && (
                        <span className="v-flag">
                          {verdictLevel === "fail"
                            ? `待复核${portLeakColumn ? ` · ${portLeakColumn}` : ""}`
                            : "需换数据确认"}
                        </span>
                      )}
                    </span>
                  </div>
                  <div className="v-item">
                    <span className="v-k">F1</span>
                    <span className="v-v">{num(best.metrics.f1)}</span>
                  </div>
                  <div className="v-item">
                    <span className="v-k">误报率</span>
                    <span className="v-v mono">
                      {pct(best.metrics.fpr)}
                    </span>
                  </div>
                  <div className="v-note">
                    {suspicious
                      ? `AUC 接近满分，${payload.warnings.length} 项泄漏待确认 — 先看下方结论。`
                      : best.kind === "supervised" ? "监督模型，使用训练集标签" : "无监督基线，不使用标签"}
                  </div>
                </div>
              </header>

              {payload.verdict && <VerdictCard verdict={payload.verdict} />}
              {payload.checklist && payload.checklist.length > 0 && (
                <ChecklistCard items={payload.checklist} />
              )}

              <section className="block">
                <header className="block-head">
                  <h2><span className="idx">01</span>模型对比</h2>
                  <span className="aside">验证集选模型 · 测试集报成绩</span>
                </header>
                <MetricMatrix results={payload.results} bestModel={payload.best_model}
                              suspicious={suspicious} badge={bestBadge} />
              </section>

              <section className="block">
                <header className="block-head">
                  <h2><span className="idx">02</span>
                    {payload.score_curve_basis === "time" ? "分数峰值随时间" : "分数峰值（按测试样本顺序）"}
                  </h2>
                  <span className="aside">
                    {payload.score_curve_basis === "time" ? "测试集已按时间排序" : "随机/分组切分不代表时间顺序"}
                    {" · "}柱高＝窗口最高分 · 红条＝窗口内含超阈值流
                  </span>
                </header>
                <SignalStrip curve={best.score_curve ?? payload.score_curve ?? []} threshold={d.threshold} />
                <ThresholdScan
                  rows={best.threshold_scan ?? payload.threshold_scan ?? []}
                  active={best.threshold ?? d.threshold}
                />
              </section>

              {payload.ablation && (
                <section className="block">
                  <header className="block-head">
                    <h2><span className="idx">03</span>消融：去掉 {payload.ablation.column}</h2>
                    <span className="aside">Δ 为正 = 指标靠这一列撑着</span>
                  </header>
                  <AblationTable ablation={payload.ablation} />
                </section>
              )}

              <section className="block">
                <header className="block-head">
                  <h2><span className="idx">{sectionNo.flow}</span>最可疑的流</h2>
                  <span className="aside">{best.model} 打分 · 前 15 条</span>
                </header>
                <TopFlows flows={payload.top_flows}
                          threshold={best.threshold ?? d.threshold}
                          leakPort={(payload.warnings.find((w) => w.rule === "port_leak")?.value) ?? null} />
              </section>

              <section className="block">
                <header className="block-head">
                  <h2><span className="idx">{sectionNo.investigation}</span>调查线索</h2>
                  <span className="aside">按类型、源 IP 与典型错误拆开看</span>
                </header>
                <InvestigationPanel result={best} />
              </section>

              <p className="footnote">
                标签对齐 {d.labels?.mode ?? "—"}（{d.labels?.labelled ?? 0}/{d.labels?.total ?? 0}） · 速率兜底{" "}
                {d.engineering?.min_duration_ms ?? 1} ms · 随机种子 {d.seed ?? 42} · 报告自包含，可离线归档
              </p>
            </>
          )}
        </main>

        <ContextPanel
          payload={payload}
          onCopy={copy}
          onDownloadMd={() => payload && save(payload.report_md, "text/markdown", "md")}
          onDownloadHtml={() => payload && save(payload.report_html, "text/html", "html")}
          onDownloadJson={() => payload && save(
            JSON.stringify(payload, null, 2), "application/json", "json"
          )}
          onDownloadCsv={() => payload && save(metricsCsv(payload), "text/csv", "csv")}
          onRerunWithout={(col) => { setAblate(col); run({ ablate: col }); }}
          copied={copied}
          onCloseMobile={() => setMobilePanel(null)}
          mobileOpen={mobilePanel === "context"}
        />
      </div>
    </div>
  );
}
