type Bucket = { p: number; h: number };

export function SignalStrip({ curve, threshold }: { curve: Bucket[]; threshold: number }) {
  if (!curve.length) return null;
  const hits = curve.filter((b) => b.h > 0).length;
  return (
    <>
      <div className="signal" role="img"
           aria-label={`按时间顺序的分数分布，共 ${curve.length} 个时间窗，${hits} 个含超阈值流`}>
        <div className="signal-y" aria-hidden="true"><span>1.0</span><span>0.5</span><span>0.0</span></div>
        <div className="signal-plot">
          <div className="signal-bars">
            {curve.map((b, i) => (
              <span
                key={i}
                className="tick"
                style={{ height: `${Math.max(2, Math.min(100, b.p * 100))}%` }}
                title={`第 ${i + 1} 窗 · 最高分 ${b.p.toFixed(3)} · 超阈值比例 ${(b.h * 100).toFixed(0)}%`}
              />
            ))}
          </div>
          <div className="hit-strip" aria-hidden="true">
            {curve.map((b, i) => (
              <span key={i} className={b.h > 0 ? "hit" : ""} style={{ opacity: b.h > 0 ? 0.35 + 0.65 * Math.min(1, b.h * 3) : 0 }} />
            ))}
          </div>
          <div className="signal-base" aria-hidden="true" />
          <div className="thr" style={{ bottom: `${Math.round(threshold * 100)}%` }}>
            <span>阈值 {threshold.toFixed(2)}</span>
          </div>
        </div>
      </div>
      <div className="signal-cap">
        <span>窗口 1</span>
        <span>
          <i className="legend-bar" aria-hidden="true" /> 柱高＝该窗最高分
          <i className="legend-hit" aria-hidden="true" /> 红色＝窗内含超阈值流（{hits}/{curve.length}）
        </span>
        <span>窗口 {curve.length}</span>
      </div>
    </>
  );
}
