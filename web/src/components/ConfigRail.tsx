import type { Job, ModelInfo } from "../types";
import { RunProgress } from "./RunProgress";

type Props = {
  models: ModelInfo[];
  selected: string[];
  onToggleModel: (name: string) => void;
  source: "demo" | "file";
  onSource: (s: "demo" | "file") => void;
  normal: number; attack: number;
  onNormal: (n: number) => void; onAttack: (n: number) => void;
  leaky: boolean; onLeaky: (v: boolean) => void;
  split: "temporal" | "random" | "group";
  onSplit: (s: "temporal" | "random" | "group") => void;
  testSize: number; onTestSize: (v: number) => void;
  validationSize: number; onValidationSize: (v: number) => void;
  seed: number; onSeed: (v: number) => void;
  threshold: number; onThreshold: (t: number) => void;
  thresholdMode: "fixed" | "f1" | "fpr";
  onThresholdMode: (mode: "fixed" | "f1" | "fpr") => void;
  targetFpr: number; onTargetFpr: (value: number) => void;
  ablate: string; onAblate: (col: string) => void;
  ablationColumns: string[];
  file: File | null; onFile: (f: File | null) => void;
  labelsFile: File | null; onLabelsFile: (f: File | null) => void;
  allowPickle: boolean; onAllowPickle: (v: boolean) => void;
  scoreModels: ModelInfo[];
  scoreModel: string; onScoreModel: (name: string) => void;
  scoreTop: number; onScoreTop: (value: number) => void;
  onScore: () => void;
  preflightBusy: boolean;
  onPreflight: () => void;
  busy: boolean; onRun: () => void; error: string | null; notice: string | null;
  job: Job | null;
  cancelBusy: boolean;
  onCancelJob: () => void | Promise<void>;
  onDismissJob: () => void;
  stale?: boolean;
  onCloseMobile: () => void;
  mobileOpen: boolean;
};

const KIND_LABEL: Record<string, string> = { supervised: "监督", unsupervised: "无监督" };

export function ConfigRail(p: Props) {
  const needsPickle = p.source === "file" && /\.(pkl|pickle|p)$/i.test(p.file?.name ?? "");

  return (
    <aside className="rail" id="config-drawer" data-drawer="config"
           role={p.mobileOpen ? "dialog" : undefined}
           aria-modal={p.mobileOpen ? "true" : undefined}
           aria-label="实验配置">
      <button className="drawer-close drawer-close-left" onClick={p.onCloseMobile}>
        关闭配置
      </button>
      <section>
        <h2>数据</h2>
        <fieldset className="seg">
          <legend className="sr-only">数据来源</legend>
          <label>
            <input type="radio" name="data-source" checked={p.source === "demo"}
                   onChange={() => p.onSource("demo")} />
            <span>合成数据</span>
          </label>
          <label>
            <input type="radio" name="data-source" checked={p.source === "file"}
                   onChange={() => p.onSource("file")} />
            <span>上传文件</span>
          </label>
        </fieldset>

        {p.source === "demo" ? (
          <>
            <div className="pair">
              <label><span>正常流</span>
                <input type="number" name="normal-flows" autoComplete="off" min={100} max={200000} step={100}
                       value={p.normal} onChange={(e) => p.onNormal(Number(e.target.value))} /></label>
              <label><span>攻击流</span>
                <input type="number" name="attack-flows" autoComplete="off" min={10} max={50000} step={10}
                       value={p.attack} onChange={(e) => p.onAttack(Number(e.target.value))} /></label>
            </div>
            <label className="switch">
              <span>极端模式：攻击只在端口上不同</span>
              <input type="checkbox" checked={p.leaky} onChange={(e) => p.onLeaky(e.target.checked)} />
            </label>
          </>
        ) : (
          <>
            <label className={`drop ${p.file ? "filled" : ""}`}>
              <input type="file" name="flow-file"
                     accept=".csv,.tsv,.json,.jsonl,.parquet,.npy,.npz,.pkl,.pickle,.xlsx,.xls,.pcap,.pcapng,.log,.log.gz,.gz"
                     onChange={(e) => p.onFile(e.target.files?.[0] ?? null)} />
              <strong>{p.file ? p.file.name : "选择数据文件"}</strong>
              <span>{p.file ? `${(p.file.size / 1024).toFixed(0)} KB` : "csv / json / parquet / npy / npz / pkl / pcap / Zeek log"}</span>
            </label>
            <label className={`drop compact ${p.labelsFile ? "filled" : ""}`}>
              <input type="file" name="labels-file" accept=".csv,.tsv,.json,.jsonl,.parquet,.xlsx,.xls"
                     onChange={(e) => p.onLabelsFile(e.target.files?.[0] ?? null)} />
              <strong>{p.labelsFile ? p.labelsFile.name : "标签文件（可选）"}</strong>
              <span>五元组 / flow_id / 行序</span>
            </label>
            {needsPickle && (
              <label className="switch">
                <span>允许 pickle（会执行代码）</span>
                <input type="checkbox" checked={p.allowPickle} onChange={(e) => p.onAllowPickle(e.target.checked)} />
              </label>
            )}
            <button
              className="preflight-action"
              type="button"
              onClick={p.onPreflight}
              disabled={!p.file || p.busy || p.preflightBusy}
            >
              {p.preflightBusy ? "正在读取并预检…" : "预检数据与切分"}
            </button>
            <p className="hint">
              先检查列映射、标签、时间戳和切分后类别；只读取，不训练。
            </p>
          </>
        )}
      </section>

      <section>
        <h2>切分</h2>
        <fieldset className="seg">
          <legend className="sr-only">切分方式</legend>
          <label>
            <input type="radio" name="split-mode" checked={p.split === "temporal"}
                   onChange={() => p.onSplit("temporal")} />
            <span>时间切分</span>
          </label>
          <label>
            <input type="radio" name="split-mode" checked={p.split === "random"}
                   onChange={() => p.onSplit("random")} />
            <span>随机切分</span>
          </label>
          <label>
            <input type="radio" name="split-mode" checked={p.split === "group"}
                   onChange={() => p.onSplit("group")} />
            <span>实体分组</span>
          </label>
        </fieldset>
        <div className="pair">
          <label><span>测试集比例</span>
            <input type="number" name="test-size" min={0.05} max={0.5} step={0.05}
                   value={p.testSize} onChange={(e) => p.onTestSize(Number(e.target.value))} /></label>
          <label><span>验证集比例</span>
            <input type="number" name="validation-size" min={0.05} max={0.4} step={0.05}
                   value={p.validationSize} onChange={(e) => p.onValidationSize(Number(e.target.value))} /></label>
        </div>
        <div className="pair single">
          <label><span>随机种子</span>
            <input type="number" name="seed" min={0} step={1}
                   value={p.seed} onChange={(e) => p.onSeed(Number(e.target.value))} /></label>
        </div>
        <p className="hint">{p.split === "temporal"
          ? `按时间依次划出 ${Math.round((1 - p.testSize - p.validationSize) * 100)}% 训练、${Math.round(p.validationSize * 100)}% 验证、${Math.round(p.testSize * 100)}% 测试。`
          : p.split === "group"
            ? "按 flow_id / 五元组 / src_ip 分组，同一实体只落在一个子集；用于新实体泛化。"
            : "分层随机。若数据带时间戳，会触发时间泄漏警告。"}</p>
        <p className="hint">验证集只用于选模型；测试集不参与选择，只报最终成绩。</p>
      </section>

      <section>
        <h2>模型</h2>
        <ul className="checklist">
          {p.models.map((m) => (
            <li key={m.name}>
              <label>
                <input type="checkbox" checked={p.selected.includes(m.name)} onChange={() => p.onToggleModel(m.name)} />
                <span className="model-name">{m.name}</span>
                <span className="model-kind">{KIND_LABEL[m.kind] ?? m.kind}</span>
              </label>
            </li>
          ))}
        </ul>
      </section>

      {p.source === "file" && (
        <section className="score-config">
          <h2>无标签打分</h2>
          <p className="hint">不要求 label；只按无监督分数排序，不计算 AUC/F1。</p>
          <label className="inline-field">
            <span>打分模型</span>
            <select name="score-model" value={p.scoreModel}
                    onChange={(e) => p.onScoreModel(e.target.value)}>
              {p.scoreModels.map((model) => (
                <option key={model.name} value={model.name}>{model.name}</option>
              ))}
            </select>
          </label>
          <label className="inline-field">
            <span>返回条数</span>
            <input className="score-top" type="number" name="score-top"
                   min={1} max={500} step={10} value={p.scoreTop}
                   onChange={(e) => p.onScoreTop(Number(e.target.value))} />
          </label>
          <button className="score-run" type="button" onClick={p.onScore}
                  disabled={p.busy || !p.file || !p.scoreModel}>
            {p.file ? `用 ${p.scoreModel} 打分` : "先选择数据文件"}
          </button>
        </section>
      )}

      <section>
        <h2>阈值与消融</h2>
        <label className="inline-field">
          <span>阈值策略</span>
          <select name="threshold-mode" value={p.thresholdMode}
                  onChange={(e) => p.onThresholdMode(e.target.value as "fixed" | "f1" | "fpr")}>
            <option value="fixed">手动阈值</option>
            <option value="f1">验证集 F1 自动</option>
            <option value="fpr">验证集目标误报率</option>
          </select>
        </label>
        <div className="slider-row">
          <output>{p.thresholdMode === "fixed" ? "阈值" : "回退阈值"} {p.threshold.toFixed(2)}</output>
          <input type="range" name="threshold" min={0.05} max={0.95} step={0.01} value={p.threshold}
                 aria-label="判定阈值" disabled={p.thresholdMode !== "fixed"}
                 onChange={(e) => p.onThreshold(Number(e.target.value))} />
          <span className="range-ends" aria-hidden="true">0.05</span>
          <span className="range-ends" aria-hidden="true">0.95</span>
        </div>
        {p.thresholdMode === "fpr" && (
          <div className="slider-row">
            <output>目标误报率 {(p.targetFpr * 100).toFixed(1)}%</output>
            <input type="range" name="target-fpr" min={0.001} max={0.2} step={0.001}
                   value={p.targetFpr} aria-label="目标误报率"
                   onChange={(e) => p.onTargetFpr(Number(e.target.value))} />
            <span className="range-ends" aria-hidden="true">0.1%</span>
            <span className="range-ends" aria-hidden="true">20%</span>
          </div>
        )}
        <label className="inline-field">
          <span>消融列</span>
          <select name="ablate" value={p.ablate} disabled={p.ablationColumns.length === 0}
                  onChange={(e) => p.onAblate(e.target.value)}>
            <option value="">{p.ablationColumns.length ? "不消融" : "先运行一次"}</option>
            {p.ablationColumns.map((col) => (
              <option key={col} value={col}>{col}</option>
            ))}
          </select>
        </label>
        <p className="hint">{p.ablationColumns.length === 0
          ? "先运行一次，系统会列出这次实际参与训练的特征列。"
          : p.ablate
            ? `会多跑一遍：去掉 ${p.ablate} 后对比 AUC。`
            : "选一列后系统会去掉它重跑，量化这一列的贡献。"}</p>
        <p className="hint">
          {p.thresholdMode === "f1"
            ? "每个模型只用验证集最大化 F1 来选择阈值；测试集不参与阈值选择。"
            : p.thresholdMode === "fpr"
              ? "每个模型在验证集上选择满足目标误报率、召回率最高的阈值；测试集不参与选择。"
            : "阈值改动需重新运行才会更新混淆矩阵、F1 与误报率。"}
        </p>
      </section>

      <section className="rail-run">
        {p.job && (
          <RunProgress
            job={p.job}
            compact
            cancelBusy={p.cancelBusy}
            onCancel={p.onCancelJob}
            onDismiss={p.onDismissJob}
          />
        )}
        <button className="run" onClick={p.onRun}
                disabled={p.busy || p.selected.length === 0 || (p.source === "file" && !p.file)}>
          {p.job?.status === "running" || p.job?.status === "cancelling"
            ? "实验进行中…"
            : p.job?.status === "queued" ? "已排队…"
            : p.stale ? "按新配置运行" : "运行实验"}
        </button>
        {p.notice && <p className="notice" role="status">{p.notice}</p>}
        {p.error && <p className="error" role="alert">{p.error}</p>}
        <p className="rail-note">本地运行 · 数据与报告都不出这台机器</p>
      </section>
    </aside>
  );
}
