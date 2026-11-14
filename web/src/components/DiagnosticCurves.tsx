import type { Result } from "../types";

type Point = {
  threshold?: number | null;
  [key: string]: number | null | undefined;
};

function CurvePlot({
  title,
  caption,
  points,
  xKey,
  yKey,
  diagonal = false,
}: {
  title: string;
  caption: string;
  points: Point[];
  xKey: string;
  yKey: string;
  diagonal?: boolean;
}) {
  if (!points.length) return null;
  const width = 360;
  const height = 220;
  const pad = 30;
  const px = (value: number) => pad + value * (width - pad * 2);
  const py = (value: number) => height - pad - value * (height - pad * 2);
  const valueAt = (point: Point, key: string) => Number(point[key] ?? 0);
  const path = points
    .map((point, index) => `${index ? "L" : "M"} ${px(valueAt(point, xKey)).toFixed(2)} ${py(valueAt(point, yKey)).toFixed(2)}`)
    .join(" ");
  return (
    <figure className="curve-plot">
      <figcaption>
        <strong>{title}</strong>
        <span>{caption}</span>
      </figcaption>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${title}曲线`}>
        {[0, 0.25, 0.5, 0.75, 1].map((tick) => (
          <g key={tick} className="curve-grid">
            <line x1={px(tick)} x2={px(tick)} y1={py(0)} y2={py(1)} />
            <line x1={px(0)} x2={px(1)} y1={py(tick)} y2={py(tick)} />
          </g>
        ))}
        {diagonal && (
          <line className="curve-diagonal" x1={px(0)} y1={py(0)} x2={px(1)} y2={py(1)} />
        )}
        <path className="curve-line" d={path} />
        <line className="curve-axis" x1={px(0)} x2={px(1)} y1={py(0)} y2={py(0)} />
        <line className="curve-axis" x1={px(0)} x2={px(0)} y1={py(0)} y2={py(1)} />
        <text className="curve-tick" x={px(0)} y={height - 9}>0</text>
        <text className="curve-tick" x={px(1)} y={height - 9} textAnchor="end">1</text>
        <text className="curve-tick" x={5} y={py(1) + 3}>1</text>
        <text className="curve-tick" x={5} y={py(0) + 3}>0</text>
      </svg>
    </figure>
  );
}

export function DiagnosticCurves({ result }: { result: Result }) {
  const hasCurves = result.roc_curve?.length || result.pr_curve?.length;
  if (!hasCurves) return null;
  return (
    <div className="diagnostic-curves">
      <div className="curve-head">
        <div>
          <strong>排序与校准</strong>
          <span>曲线来自测试集；校准只对监督模型的概率输出有意义。</span>
        </div>
        {result.brier_score != null && (
          <span className="brier">Brier {result.brier_score.toFixed(4)}</span>
        )}
      </div>
      <div className="curve-grid-layout">
        <CurvePlot
          title="ROC"
          caption="FPR → TPR"
          points={result.roc_curve}
          xKey="fpr"
          yKey="tpr"
          diagonal
        />
        <CurvePlot
          title="PR"
          caption="召回率 → 精确率"
          points={result.pr_curve}
          xKey="recall"
          yKey="precision"
        />
        {result.calibration?.length > 0 && (
          <CurvePlot
            title="校准"
            caption="预测概率 → 实际攻击比例"
            points={result.calibration}
            xKey="mean_predicted"
            yKey="fraction_positive"
            diagonal
          />
        )}
      </div>
      <p className="hint">{result.calibration_note}</p>
    </div>
  );
}
