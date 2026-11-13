import { useEffect, useMemo, useState } from "react";
import { fetchHistory, fetchModels, loadRun, runDemo, runUpload } from "./api";
import { num, pct, secs } from "./format";
import type { ModelInfo, Payload, RunRow } from "./types";
import { TopBar } from "./components/TopBar";
import { ConfigRail } from "./components/ConfigRail";
import { ContextPanel } from "./components/ContextPanel";
import { MetricMatrix } from "./components/MetricMatrix";
import { SignalStrip } from "./components/SignalStrip";
import { AblationTable } from "./components/AblationTable";
import { TopFlows } from "./components/TopFlows";
import { VerdictCard } from "./components/VerdictCard";

const ALL = ["mlp", "iforest", "autoencoder"];

export default function App() {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [selected, setSelected] = useState<string[]>(ALL);
  const [source, setSource] = useState<"demo" | "file">("demo");
  const [normal, setNormal] = useState(5000);
  const [attack, setAttack] = useState(500);
  const [leaky, setLeaky] = useState(false);
  const [split, setSplit] = useState<"temporal" | "random">("temporal");
  const [threshold, setThreshold] = useState(0.5);
  const [ablate, setAblate] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [labelsFile, setLabelsFile] = useState<File | null>(null);
  const [allowPickle, setAllowPickle] = useState(false);
  const [payload, setPayload] = useState<Payload | null>(null);
  const [history, setHistory] = useState<RunRow[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetchModels().then(setModels).catch(() =>
      setModels(ALL.map((n) => ({ name: n, kind: n === "mlp" ? "supervised" : "unsupervised" }))));
    refreshHistory();
  }, []);

  function refreshHistory() {
    fetchHistory().then(setHistory).catch(() => setHistory([]));
  }

  const best = useMemo(() => {
    if (!payload?.results.length) return null;
    return payload.results.reduce((a, b) => ((b.metrics.auc ?? 0) > (a.metrics.auc ?? 0) ? b : a));
  }, [payload]);

  async function run(override?: { ablate?: string }) {
    setBusy(true);
    setError(null);
    try {
      const ablateValue = override?.ablate ?? ablate;
      const params = { seed: 42, split, models: selected, threshold, ablate: ablateValue || null };
      const data = source === "demo"
        ? await runDemo({ ...params, normal, attack, leaky })
        : await runUpload(file!, params, labelsFile, allowPickle);
      setPayload(data);
      refreshHistory();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setPayload(null);
    } finally {
      setBusy(false);
    }
  }

  async function openRun(id: string) {
    setBusy(true);
    setError(null);
    try {
      setPayload(await loadRun(id));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  function toggleModel(name: string) {
    setSelected((s) => (s.includes(name) ? s.filter((x) => x !== name) : [...s, name]));
  }

  function save(content: string, mime: string, ext: string) {
    if (!payload) return;
    const blob = new Blob([content], { type: `${mime};charset=utf-8` });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `flowlab-${payload.dataset.hash}.${ext}`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  async function copy() {
    if (!payload) return;
    await navigator.clipboard.writeText(payload.report_md);
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  }

  const d = payload?.dataset;
  const suspicious = Boolean(payload?.warnings.length) && (best?.metrics.auc ?? 0) >= 0.995;
  const portLeakColumn = payload?.warnings.find((w) => w.rule === "port_leak")?.columns[0];
  const sectionNo = payload?.ablation ? { flow: "04" } : { flow: "03" };

  return (
    <div className="shell">
      <a className="skip" href="#main">跳到主要内容</a>
      <TopBar payload={payload} busy={busy} runs={history} activeRun={payload?.run_id} onOpenRun={openRun} />

      <div className="workspace">
        <ConfigRail
          models={models} selected={selected} onToggleModel={toggleModel}
          source={source} onSource={(s) => { setSource(s); setError(null); setFile(null); setLabelsFile(null); }}
          normal={normal} attack={attack} onNormal={setNormal} onAttack={setAttack}
          leaky={leaky} onLeaky={setLeaky}
          split={split} onSplit={setSplit}
          threshold={threshold} onThreshold={setThreshold}
          ablate={ablate} onAblate={setAblate}
          file={file} onFile={setFile}
          labelsFile={labelsFile} onLabelsFile={setLabelsFile}
          allowPickle={allowPickle} onAllowPickle={setAllowPickle}
          busy={busy} onRun={() => run()} error={error}
        />

        <main className="canvas" id="main">
          {!payload && !busy && (
            <section className="intro">
              <h1>先跑一次，<br />再谈模型。</h1>
              <p>
                FlowLab 把流量实验拆成四步：导入数据、审计泄漏、统一特征、对比模型。
                每一步的输入输出都写进报告，换个人也能复现。
              </p>
              <ol>
                <li>左侧已默认选好合成数据；要跑自己的数据，切到「上传文件」。</li>
                <li>时间切分优先；带时间戳却用随机切分，会直接报时间泄漏。</li>
                <li>选一个消融列，看指标是不是靠它撑着。</li>
                <li>多个模型共用同一份特征矩阵，指标才真的可比。</li>
              </ol>
              <div className="intro-actions">
                <button className="ghost-btn outline intro-run" onClick={() => run()}
                        disabled={busy || selected.length === 0}>用当前配置跑一次</button>
                {history.length > 0 && <span className="hint">或点顶部的历史实验</span>}
              </div>
            </section>
          )}

          {payload && d && best && (
            <>
              <header className="head">
                <div className="head-kicker">
                  RUN {payload.run_id ?? "—"} <span className="dot-sep">·</span> {d.format?.format ?? "data"}
                </div>
                <h1>{d.source.replace(/（.*?）/g, "")}</h1>
                <p className="head-sub">
                  {d.rows.toLocaleString()} 条流 <span className="dot-sep">/</span> 训练 {d.train.toLocaleString()}{" "}
                  · 测试 {d.test.toLocaleString()} <span className="dot-sep">/</span>{" "}
                  {d.split === "temporal" ? "时间切分" : "随机切分"}
                </p>

                <div className="verdict">
                  <div className="v-item">
                    <span className="v-k">最佳模型</span>
                    <span className="v-v mono">{best.model}</span>
                  </div>
                  <div className="v-item">
                    <span className="v-k">AUC</span>
                    <span className={`v-v ${suspicious ? "caution" : ""}`}>
                      {num(best.metrics.auc)}
                      {suspicious && (
                        <span className="v-flag">
                          待复核{portLeakColumn ? ` · ${portLeakColumn}` : ""}
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
                      ? `AUC 接近满分且存在 ${payload.warnings.length} 条泄漏 — 先看下方结论。`
                      : best.kind === "supervised" ? "监督模型，使用训练集标签" : "无监督基线，不使用标签"}
                  </div>
                </div>
              </header>

              {payload.verdict && <VerdictCard verdict={payload.verdict} />}

              <section className="block">
                <header className="block-head">
                  <h2><span className="idx">01</span>模型对比</h2>
                  <span className="aside">按 AUC 排序 · 同一份特征矩阵</span>
                </header>
                <MetricMatrix results={payload.results} bestModel={payload.best_model} suspicious={suspicious} />
              </section>

              <section className="block">
                <header className="block-head">
                  <h2><span className="idx">02</span>分数峰值随时间</h2>
                  <span className="aside">柱高＝窗口最高分 · 红条＝窗口内含超阈值流</span>
                </header>
                <SignalStrip curve={best.score_curve ?? payload.score_curve ?? []} threshold={d.threshold} />
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
                          leakPort={(payload.warnings.find((w) => w.rule === "port_leak")?.value) ?? null} />
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
          onRerunWithout={(col) => { setAblate(col); run({ ablate: col }); }}
          copied={copied}
        />
      </div>
    </div>
  );
}
