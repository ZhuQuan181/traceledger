import type { ModelInfo } from "../types";

type Props = {
  models: ModelInfo[];
  selected: string[];
  onToggleModel: (name: string) => void;
  source: "demo" | "file";
  onSource: (s: "demo" | "file") => void;
  normal: number;
  attack: number;
  onNormal: (n: number) => void;
  onAttack: (n: number) => void;
  split: "temporal" | "random";
  onSplit: (s: "temporal" | "random") => void;
  threshold: number;
  onThreshold: (t: number) => void;
  file: File | null;
  onFile: (f: File | null) => void;
  busy: boolean;
  onRun: () => void;
  error: string | null;
};

const KIND_LABEL: Record<string, string> = {
  supervised: "监督",
  unsupervised: "无监督",
};

export function ControlPanel(p: Props) {
  return (
    <aside className="controls">
      <section className="block">
        <h2>数据</h2>
        <div className="seg" role="radiogroup" aria-label="数据来源">
          <button role="radio" aria-checked={p.source === "demo"} className={p.source === "demo" ? "on" : ""} onClick={() => p.onSource("demo")}>
            合成数据
          </button>
          <button role="radio" aria-checked={p.source === "file"} className={p.source === "file" ? "on" : ""} onClick={() => p.onSource("file")}>
            上传文件
          </button>
        </div>

        {p.source === "demo" ? (
          <div className="pair">
            <label>
              <span>正常流</span>
              <input type="number" name="normal-flows" autoComplete="off" min={100} max={200000} step={100}
                     value={p.normal} onChange={(e) => p.onNormal(Number(e.target.value))} />
            </label>
            <label>
              <span>攻击流</span>
              <input type="number" name="attack-flows" autoComplete="off" min={10} max={50000} step={10}
                     value={p.attack} onChange={(e) => p.onAttack(Number(e.target.value))} />
            </label>
          </div>
        ) : (
          <label className={`drop ${p.file ? "filled" : ""}`}>
            <input type="file" name="flow-file" accept=".csv,.pcap,.pcapng"
                   onChange={(e) => p.onFile(e.target.files?.[0] ?? null)} />
            <strong>{p.file ? p.file.name : "选择 CSV 或 pcap"}</strong>
            <span>{p.file ? `${(p.file.size / 1024).toFixed(0)} KB` : "pcap 需要本机安装 tshark；无标签时请用命令行 score"}</span>
          </label>
        )}
      </section>

      <section className="block">
        <h2>切分</h2>
        <div className="seg" role="radiogroup" aria-label="切分方式">
          <button role="radio" aria-checked={p.split === "temporal"} className={p.split === "temporal" ? "on" : ""} onClick={() => p.onSplit("temporal")}>
            时间切分
          </button>
          <button role="radio" aria-checked={p.split === "random"} className={p.split === "random" ? "on" : ""} onClick={() => p.onSplit("random")}>
            随机切分
          </button>
        </div>
        <p className="hint">
          {p.split === "temporal"
            ? "前 70% 训练、后 30% 测试。数据带时间戳时，这是唯一诚实的做法。"
            : "分层随机。若数据有时间戳，会触发泄漏警告。"}
        </p>
      </section>

      <section className="block">
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

      <section className="block">
        <h2>判定阈值</h2>
        <div className="slider-row">
          <input type="range" name="threshold" min={0.05} max={0.95} step={0.01} value={p.threshold}
                 aria-label="判定阈值" onChange={(e) => p.onThreshold(Number(e.target.value))} />
          <output className="mono">{p.threshold.toFixed(2)}</output>
        </div>
        <p className="hint">分数高于阈值即判为攻击。调低会抓更多，也会误报更多。</p>
      </section>

      <div className="run-wrap">
        <button className="run" onClick={p.onRun} disabled={p.busy || p.selected.length === 0 || (p.source === "file" && !p.file)}>
          {p.busy ? "实验进行中…" : "运行实验"}
        </button>
        {p.error && <p className="error" role="alert">{p.error}</p>}
      </div>
    </aside>
  );
}
