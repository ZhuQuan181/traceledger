import { useEffect, useMemo, useState } from "react";
import { fetchModels, runDemo, runUpload } from "./api";
import type { ModelInfo, Payload } from "./types";
import { StatusRail } from "./components/StatusRail";
import { ControlPanel } from "./components/ControlPanel";
import { SignalStrip } from "./components/SignalStrip";
import { LeakList } from "./components/LeakList";
import { ModelTable } from "./components/ModelTable";
import { TopFlows } from "./components/TopFlows";

const ALL = ["mlp", "iforest", "autoencoder"];

export default function App() {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [selected, setSelected] = useState<string[]>(ALL);
  const [source, setSource] = useState<"demo" | "file">("demo");
  const [normal, setNormal] = useState(5000);
  const [attack, setAttack] = useState(500);
  const [split, setSplit] = useState<"temporal" | "random">("temporal");
  const [threshold, setThreshold] = useState(0.5);
  const [file, setFile] = useState<File | null>(null);
  const [labelsFile, setLabelsFile] = useState<File | null>(null);
  const [payload, setPayload] = useState<Payload | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetchModels().then(setModels).catch(() => setModels(ALL.map((n) => ({ name: n, kind: n === "mlp" ? "supervised" : "unsupervised" }))));
  }, []);

  const best = useMemo(() => {
    if (!payload?.results.length) return null;
    return payload.results.reduce((a, b) => ((b.metrics.auc ?? 0) > (a.metrics.auc ?? 0) ? b : a));
  }, [payload]);

  async function run() {
    setBusy(true);
    setError(null);
    try {
      const params = { seed: 42, split, models: selected, threshold };
      const data = source === "demo"
        ? await runDemo({ ...params, normal, attack })
        : await runUpload(file!, params, labelsFile);
      setPayload(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setPayload(null);
    } finally {
      setBusy(false);
    }
  }

  function toggleModel(name: string) {
    setSelected((s) => (s.includes(name) ? s.filter((x) => x !== name) : [...s, name]));
  }

  function download() {
    if (!payload) return;
    const blob = new Blob([payload.report_md], { type: "text/markdown;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `flowlab-report-${payload.dataset.hash}.md`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  async function copy() {
    if (!payload) return;
    await navigator.clipboard.writeText(payload.report_md);
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  }

  return (
    <div className="shell">
      <a className="skip" href="#main">跳到主要内容</a>
      <StatusRail payload={payload} busy={busy} />
      <div className="body">
        <ControlPanel
          models={models}
          selected={selected}
          onToggleModel={toggleModel}
          source={source}
          onSource={(s) => { setSource(s); setError(null); setFile(null); setLabelsFile(null); }}
          normal={normal}
          attack={attack}
          onNormal={setNormal}
          onAttack={setAttack}
          split={split}
          onSplit={setSplit}
          threshold={threshold}
          onThreshold={setThreshold}
          file={file}
          onFile={setFile}
          labelsFile={labelsFile}
          onLabelsFile={setLabelsFile}
          busy={busy}
          onRun={run}
          error={error}
        />

        <main className="stage" id="main">
          {busy && <div className="progress" aria-hidden="true" />}

          {!payload && !busy && (
            <section className="intro">
              <h1>先跑一次，再谈模型。</h1>
              <p>
                左边选数据集，点运行。系统会先检查数据泄漏，再用同一套特征把
                MLP 和两个无监督基线放在一起比较，最后给出可复现的报告。
              </p>
              <ul>
                <li>数据默认用合成流量，不碰你的真实数据。</li>
                <li>时间切分优先，随机切分会触发时间泄漏警告。</li>
                <li>每个模型都在同一份预处理上训练，指标可直接对比。</li>
              </ul>
            </section>
          )}

          {payload && (
            <div className="report">
              <section className="summary" aria-live="polite">
                <h1 className="sr-only">实验报告</h1>
                <p>
                  {payload.dataset.source} · {payload.dataset.rows.toLocaleString()} 条流 · 训练{" "}
                  {payload.dataset.train.toLocaleString()} / 测试 {payload.dataset.test.toLocaleString()} ·{" "}
                  {payload.dataset.split === "temporal" ? "时间切分" : "随机切分"} · 阈值{" "}
                  {payload.dataset.threshold.toFixed(2)}
                  {payload.dataset.labels?.mode && (
                    <span className="dim"> · 标签对齐 {payload.dataset.labels.mode}
                      （{payload.dataset.labels.labelled}/{payload.dataset.labels.total}）</span>
                  )}
                  {payload.dataset.engineering?.min_duration_ms && (
                    <span className="dim"> · 速率兜底 {payload.dataset.engineering.min_duration_ms} ms</span>
                  )}
                </p>
                <div className="actions">
                  <button onClick={copy}>{copied ? "已复制" : "复制 Markdown"}</button>
                  <button className="primary" onClick={download}>下载报告</button>
                </div>
              </section>

              <SignalStrip curve={best?.score_curve ?? []} threshold={payload.dataset.threshold} />
              <LeakList warnings={payload.warnings} />
              <ModelTable results={payload.results} bestModel={payload.best_model} />
              <TopFlows flows={payload.top_flows} model={payload.best_model} />
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
