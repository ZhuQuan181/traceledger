import type { ModelInfo } from "../types";

type Props = {
  models: ModelInfo[];
  selected: string[];
  onToggleModel: (name: string) => void;
  source: "demo" | "file";
  onSource: (s: "demo" | "file") => void;
  normal: number; attack: number;
  onNormal: (n: number) => void; onAttack: (n: number) => void;
  leaky: boolean; onLeaky: (v: boolean) => void;
  split: "temporal" | "random";
  onSplit: (s: "temporal" | "random") => void;
  threshold: number; onThreshold: (t: number) => void;
  ablate: string; onAblate: (col: string) => void;
  ablationColumns: string[];
  file: File | null; onFile: (f: File | null) => void;
  labelsFile: File | null; onLabelsFile: (f: File | null) => void;
  allowPickle: boolean; onAllowPickle: (v: boolean) => void;
  busy: boolean; onRun: () => void; error: string | null;
};

const KIND_LABEL: Record<string, string> = { supervised: "监督", unsupervised: "无监督" };

export function ConfigRail(p: Props) {
  const needsPickle = p.source === "file" && /\.(pkl|pickle|p)$/i.test(p.file?.name ?? "");

  return (
    <aside className="rail">
      <section>
        <h2>数据</h2>
        <div className="seg" role="radiogroup" aria-label="数据来源">
          <button role="radio" aria-checked={p.source === "demo"} className={p.source === "demo" ? "on" : ""}
                  onClick={() => p.onSource("demo")}>合成数据</button>
          <button role="radio" aria-checked={p.source === "file"} className={p.source === "file" ? "on" : ""}
                  onClick={() => p.onSource("file")}>上传文件</button>
        </div>

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
                     accept=".csv,.tsv,.json,.jsonl,.parquet,.npy,.npz,.pkl,.pickle,.xlsx,.xls,.pcap,.pcapng"
                     onChange={(e) => p.onFile(e.target.files?.[0] ?? null)} />
              <strong>{p.file ? p.file.name : "选择数据文件"}</strong>
              <span>{p.file ? `${(p.file.size / 1024).toFixed(0)} KB` : "csv / json / parquet / npy / npz / pkl / pcap"}</span>
            </label>
            <label className={`drop compact ${p.labelsFile ? "filled" : ""}`}>
              <input type="file" name="labels-file" accept=".csv,.json,.jsonl,.parquet,.npy,.npz,.pkl,.xlsx"
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
          </>
        )}
      </section>

      <section>
        <h2>切分</h2>
        <div className="seg" role="radiogroup" aria-label="切分方式">
          <button role="radio" aria-checked={p.split === "temporal"} className={p.split === "temporal" ? "on" : ""}
                  onClick={() => p.onSplit("temporal")}>时间切分</button>
          <button role="radio" aria-checked={p.split === "random"} className={p.split === "random" ? "on" : ""}
                  onClick={() => p.onSplit("random")}>随机切分</button>
        </div>
        <p className="hint">{p.split === "temporal"
          ? "前 70% 训练、后 30% 测试。带时间戳时这是唯一诚实的做法。"
          : "分层随机。若数据带时间戳，会触发时间泄漏警告。"}</p>
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

      <section>
        <h2>阈值与消融</h2>
        <div className="slider-row">
          <output>阈值 {p.threshold.toFixed(2)}</output>
          <input type="range" name="threshold" min={0.05} max={0.95} step={0.01} value={p.threshold}
                 aria-label="判定阈值" onChange={(e) => p.onThreshold(Number(e.target.value))} />
          <span className="range-ends" aria-hidden="true">0.05</span>
          <span className="range-ends" aria-hidden="true">0.95</span>
        </div>
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
      </section>

      <section className="rail-run">
        <button className="run" onClick={p.onRun}
                disabled={p.busy || p.selected.length === 0 || (p.source === "file" && !p.file)}>
          {p.busy ? "实验进行中…" : "运行实验"}
        </button>
        {p.error && <p className="error" role="alert">{p.error}</p>}
        <p className="rail-note">本地运行 · 数据与报告都不出这台机器</p>
      </section>
    </aside>
  );
}
