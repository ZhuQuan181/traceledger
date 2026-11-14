type Props = {
  flows: number;
  threshold: number;
};

const TRACE = Array.from({ length: 56 }, (_, i) => {
  const wave = (Math.sin(i * 0.61) + 1) * 0.075;
  const grain = (Math.sin(i * 2.13) + 1) * 0.045;
  const burst = (i >= 14 && i <= 18) || (i >= 36 && i <= 42);
  const anomaly = burst ? 0.42 + (Math.sin(i * 1.7) + 1) * 0.09 : 0;
  return Math.min(0.99, 0.15 + wave + grain + anomaly);
});

export function FlowPreview({ flows, threshold }: Props) {
  const hits = TRACE.filter((height) => height >= threshold).length;

  return (
    <section
      className="flow-preview"
      aria-label={`合成流量轨迹预览：${TRACE.length} 个时间窗中 ${hits} 个越过 ${threshold.toFixed(2)} 阈值`}
    >
      <header className="trace-head">
        <div>
          <span className="trace-kicker">流量轨迹预览</span>
          <strong>{flows.toLocaleString("en-US")} 条合成流</strong>
        </div>
        <span className="trace-local"><i aria-hidden="true" />本地</span>
      </header>

      <div className="trace-chart" aria-hidden="true">
        <div className="trace-axis">
          <span>1.0</span>
          <span>0.5</span>
          <span>0.0</span>
        </div>
        <div className="trace-plot">
          <div className="trace-bars">
            {TRACE.map((height, i) => (
              <span
                key={i}
                className={`trace-bar ${height >= threshold ? "is-hit" : ""}`}
                style={{ height: `${Math.round(height * 100)}%` }}
              />
            ))}
          </div>
          <div className="trace-threshold" style={{ bottom: `${threshold * 100}%` }}>
            <span>{threshold.toFixed(2)}</span>
          </div>
        </div>
      </div>

      <footer className="trace-legend">
        <span><i className="legend-normal" />正常窗</span>
        <span><i className="legend-alert" />越阈值</span>
        <span className="trace-count">{hits} / {TRACE.length} 窗</span>
      </footer>
    </section>
  );
}
