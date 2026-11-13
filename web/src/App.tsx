import { useEffect, useMemo, useState } from "react";
import { fetchHistory, fetchModels, loadRun, runDemo, runUpload } from "./api";
import type { ModelInfo, Payload, RunRow } from "./types";
import { TopBar } from "./components/TopBar";
import { Rail } from "./components/Rail";
import { MetricsBand } from "./components/MetricsBand";
import { SignalStrip } from "./components/SignalStrip";
import { LeakList } from "./components/LeakList";
import { ModelTable } from "./components/ModelTable";
import { AblationTable } from "./components/AblationTable";
import { TopFlows } from "./components/TopFlows";

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

  async function run() {
    setBusy(true);
    setError(null);
    try {
      const params = { seed: 42, split, models: selected, threshold, ablate: ablate || null };
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

  const fmt = payload?.dataset.format;
  const d = payload?.dataset;

  return (
    <div className="shell">
      <a className="skip" href="#main">跳到主要内容</a>
      <TopBar payload={payload} busy={busy}
              onDownloadMd={() => payload && save(payload.report_md, "text/markdown", "md")}
              onDownloadHtml={() => payload && save(payload.report_html, "text/html", "html")} />

      <div className="body">
        <Rail
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
          history={history} activeRun={payload?.run_id} onOpenRun={openRun}
          busy={busy} onRun={run} error={error}
        />

        <main className="doc" id="main">
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
                <button className="ghost-btn solid intro-run" onClick={run}
                        disabled={busy || selected.length === 0}>用当前配置跑一次</button>
                {history.length > 0 && (
                  <span className="hint">或从左侧「历史」打开上一次实验</span>
                )}
              </div>
            </section>
          )}

          {payload && d && (
            <>
              <header className="doc-head">
                <span className="kicker">
                  RUN {payload.run_id ?? "—"} · {fmt?.format ?? "data"} · 指纹 {d.hash}
                </span>
                <h1>{d.source.replace(/（.*?）/g, "")}</h1>
                <p className="sub">
                  {d.rows.toLocaleString()} 条流<span className="sep">/</span>
                  训练 {d.train.toLocaleString()} · 测试 {d.test.toLocaleString()}<span className="sep">/</span>
                  {d.split === "temporal" ? "时间切分" : "随机切分"}<span className="sep">/</span>
                  阈值 {d.threshold.toFixed(2)}
                  {d.attack_test != null && <><span className="sep">/</span>测试集攻击 {d.attack_test} 条</>}
                </p>
              </header>

              <MetricsBand payload={payload} best={best} />

              {payload.warnings.length > 0 && (
                <p className="riskline">
                  <span className="risk-tag">{payload.warnings.length} 条泄漏</span>
                  <span><b>{payload.warnings[0].rule}</b>：{payload.warnings[0].message}</span>
                  <a href="#leaks">看明细</a>
                </p>
              )}

              <section className="section">
                <header>
                  <h2><span className="idx">01</span>测试集分数分布</h2>
                  <span className="aside">按时间顺序 · 每窗最高分</span>
                </header>
                <SignalStrip curve={best?.score_curve ?? payload.score_curve ?? []} threshold={d.threshold} />
              </section>

              <section className="section" id="leaks">
                <header>
                  <h2><span className="idx">02</span>数据泄漏检查</h2>
                  <span className="aside">{payload.warnings.length} 条</span>
                </header>
                <LeakList warnings={payload.warnings} />
              </section>

              <section className="section">
                <header>
                  <h2><span className="idx">03</span>模型对比</h2>
                  <span className="aside">{payload.results.length} 个模型 · 同一份特征矩阵 · 右侧为混淆矩阵 TP/FP/FN/TN</span>
                </header>
                <ModelTable results={payload.results} bestModel={payload.best_model} />
              </section>

              {payload.ablation && (
                <section className="section">
                  <header>
                    <h2><span className="idx">04</span>消融：去掉 {payload.ablation.column}</h2>
                    <span className="aside">Δ 为正 = 指标靠这一列撑着</span>
                  </header>
                  <AblationTable ablation={payload.ablation} />
                </section>
              )}

              <section className="section">
                <header>
                  <h2><span className="idx">{payload.ablation ? "05" : "04"}</span>最可疑的流</h2>
                  <span className="aside">{payload.best_model} 打分 · 前 15 条</span>
                </header>
                <TopFlows flows={payload.top_flows} model={payload.best_model} />
              </section>

              <div className="footnote">
                {d.labels?.mode && `标签对齐 ${d.labels.mode}（${d.labels.labelled ?? 0}/${d.labels.total ?? 0}） · `}
                速率兜底 {d.engineering?.min_duration_ms ?? 1} ms · 随机种子 {d.seed ?? 42} ·
                报告自包含，可离线归档
              </div>
            </>
          )}
        </main>
      </div>
    </div>
  );
}
