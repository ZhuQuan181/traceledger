type Bucket = { p: number; h: number };

export function SignalStrip({ curve, threshold }: { curve: Bucket[]; threshold: number }) {
  if (!curve.length) return null;
  const hits = curve.filter((b) => b.h > 0).length;
  return (
    <section className="panel signal-panel">
      <div className="panel-head">
        <h2>测试集分数分布</h2>
        <span className="mono dim">{hits} / {curve.length} 段超过阈值</span>
      </div>
      <div className="signal" role="img" aria-label={`按时间顺序的异常分数分布，共 ${curve.length} 段，${hits} 段超过阈值`}>
        <div className="signal-y" aria-hidden="true">
          <span>1.0</span>
          <span>0.5</span>
          <span>0.0</span>
        </div>
        <div className="signal-plot">
        <div className="signal-bars">
          {curve.map((b, i) => (
            <span
              key={i}
              className={`tick ${b.h > 0 ? "hit" : ""}`}
              style={{
                height: `${Math.max(3, Math.min(100, b.p * 100))}%`,
                opacity: b.h > 0 ? 0.35 + 0.65 * Math.min(1, b.h * 3) : 0.45,
              }}
              title={`第 ${i + 1} 段 · 最高分 ${b.p.toFixed(3)} · 超阈值 ${(b.h * 100).toFixed(0)}%`}
            />
          ))}
        </div>
        <div className="signal-base" aria-hidden="true" />
        <div className="threshold-line" style={{ bottom: `${Math.round(threshold * 100)}%` }} aria-hidden="true">
          <span>阈值 {threshold.toFixed(2)}</span>
        </div>
        </div>
      </div>
      <div className="signal-axis">
        <span>测试集开头</span>
        <span>时间顺序 · 柱高为窗口最高分，红色深度为超阈值比例</span>
        <span>测试集结尾</span>
      </div>
    </section>
  );
}
