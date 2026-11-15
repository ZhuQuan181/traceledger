import type { PreflightCheck, PreflightResult, SplitCoverage } from "../types";

const STATUS_TEXT: Record<PreflightCheck["status"], string> = {
  pass: "通过",
  warn: "注意",
  fail: "阻断",
};

const SCOPE_TEXT: Record<PreflightCheck["scope"], string> = {
  evaluation: "评估",
  scoring: "评分",
  both: "两者",
};

const SPLIT_TEXT: Record<SplitCoverage["split"], string> = {
  train: "训练",
  validation: "验证",
  test: "测试",
};

function percent(value: number | null) {
  return value == null ? "—" : `${(value * 100).toFixed(1)}%`;
}

function coverageBar(row: SplitCoverage) {
  const total = Math.max(1, row.rows);
  return (
    <div className="pf-bar" aria-hidden="true">
      <span className="pf-bar-benign" style={{ width: `${(row.benign / total) * 100}%` }} />
      <span className="pf-bar-attack" style={{ width: `${(row.attack / total) * 100}%` }} />
    </div>
  );
}

export function PreflightPanel({
  result,
  onRun,
  onScore,
  onDismiss,
}: {
  result: PreflightResult;
  onRun: () => void;
  onScore: () => void;
  onDismiss: () => void;
}) {
  const failures = result.checks.filter((check) => check.status === "fail");
  const warnings = result.checks.filter((check) => check.status === "warn");
  const verdict = result.ready_for_evaluation
    ? warnings.length
      ? "可以评估，但有需要确认的前提"
      : "数据与切分通过预检"
    : result.ready_for_scoring
      ? "完整评估被阻断，仍可进行无标签评分"
      : "当前文件还不能进入分析";
  const relevantMappings = result.column_mapping.filter(
    (row) => row.mapped || row.role,
  );

  return (
    <section className="preflight" id="preflight-panel" aria-labelledby="preflight-title">
      <header className="pf-head">
        <div>
          <span className="pf-kicker">DATA PREFLIGHT · {result.dataset.hash}</span>
          <h1 id="preflight-title">先核对，再训练。</h1>
          <p>
            {result.source} · {result.dataset.rows.toLocaleString()} 行 ·
            {" "}{result.dataset.columns} 列 · {result.dataset.features} 个可用特征
          </p>
        </div>
        <button className="pf-close" type="button" onClick={onDismiss}>关闭预检</button>
      </header>

      <div
        className={`pf-verdict ${result.ready_for_evaluation ? warnings.length ? "warn" : "ok" : "fail"}`}
        role="status"
      >
        <span className="pf-verdict-mark" aria-hidden="true">
          {result.ready_for_evaluation ? (warnings.length ? "!" : "✓") : "×"}
        </span>
        <div>
          <strong>{verdict}</strong>
          <p>
            {result.blockers.evaluation.length
              ? `${result.blockers.evaluation.length} 项会阻断完整评估。`
              : warnings.length
                ? `${warnings.length} 项不会阻断，但会改变结论适用范围。`
                : "没有发现阻断项，可以按当前配置启动实验。"}
          </p>
        </div>
      </div>

      <div className="pf-stats">
        <div>
          <span>可用特征</span>
          <strong>{result.dataset.features}</strong>
        </div>
        <div>
          <span>标签覆盖</span>
          <strong>
            {result.labels.present
              ? `${((result.labels.benign ?? 0) + (result.labels.attack ?? 0)).toLocaleString()}`
              : "无"}
          </strong>
        </div>
        <div>
          <span>时间戳可解析</span>
          <strong>{percent(result.timestamp.parse_rate)}</strong>
        </div>
        <div>
          <span>空值 / inf</span>
          <strong>{result.missing.cells.toLocaleString()} / {result.non_finite.cells.toLocaleString()}</strong>
        </div>
      </div>

      {failures.length > 0 && (
        <section className="pf-blockers" aria-label="阻断项">
          <h2>现在需要处理</h2>
          <ol>
            {failures.map((check) => (
              <li key={check.key}>
                <strong>{check.label}</strong>
                <span>{check.detail}</span>
                {check.hint && <em>{check.hint}</em>}
              </li>
            ))}
          </ol>
        </section>
      )}

      <div className="pf-grid">
        <section className="pf-checks" aria-label="预检项目">
          <header>
            <h2>检查清单</h2>
            <span>{result.checks.length} 项 · 状态含文字标签</span>
          </header>
          <ul>
            {result.checks.map((check) => (
              <li className={`pf-check ${check.status}`} key={check.key}>
                <span className="pf-check-mark" aria-hidden="true">
                  {check.status === "pass" ? "✓" : check.status === "warn" ? "!" : "×"}
                </span>
                <div>
                  <div className="pf-check-title">
                    <strong>{check.label}</strong>
                    <span>{STATUS_TEXT[check.status]}</span>
                    <small>{SCOPE_TEXT[check.scope]}</small>
                  </div>
                  <p>{check.detail}</p>
                  {check.hint && <p className="pf-check-hint">{check.hint}</p>}
                </div>
              </li>
            ))}
          </ul>
        </section>

        <section className="pf-split" aria-label="切分后类别覆盖">
          <header>
            <h2>切分后覆盖</h2>
            <span>
              {result.split
                ? `${result.split.requested} → ${result.split.effective}`
                : "还没有可用切分"}
            </span>
          </header>
          {result.split?.coverage.length ? (
            <>
              <div className="pf-coverage">
                {result.split.coverage.map((row) => (
                  <div className="pf-coverage-row" key={row.split}>
                    <div>
                      <strong>{SPLIT_TEXT[row.split]}</strong>
                      <span>{row.rows.toLocaleString()} 行</span>
                    </div>
                    {coverageBar(row)}
                    <p>
                      <span>BENIGN {row.benign.toLocaleString()}</span>
                      <span>攻击 {row.attack.toLocaleString()}</span>
                    </p>
                  </div>
                ))}
              </div>
              <p className="pf-legend">
                <span className="pf-legend-benign">BENIGN</span>
                <span className="pf-legend-attack">攻击</span>
                {result.split.entity_key && `实体键：${result.split.entity_key}`}
              </p>
              {result.split.fell_back && (
                <p className="pf-callout">
                  时间戳不足，时间切分已退化为随机切分；报告不能声称时间外推。
                </p>
              )}
            </>
          ) : (
            <p className="pf-empty">
              当前数据或参数不足以规划三段切分；仍可尝试无标签评分。
            </p>
          )}
        </section>
      </div>

      <details className="pf-mapping">
        <summary>
          列映射：{result.column_mapping.length} 个原始列，
          {" "}{relevantMappings.filter((row) => row.mapped).length} 个经过别名映射
        </summary>
        {relevantMappings.length ? (
          <div className="pf-map-wrap">
            <table>
              <thead>
                <tr><th>原始列</th><th>内部字段</th><th>角色</th></tr>
              </thead>
              <tbody>
                {relevantMappings.map((row) => (
                  <tr key={row.original}>
                    <td>{row.original}</td>
                    <td><code>{row.canonical}</code></td>
                    <td>{row.role ?? (row.mapped ? "映射字段" : "特征")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p>没有需要特别说明的列映射。</p>
        )}
      </details>

      <footer className="pf-actions">
        <button
          className="primary-action"
          type="button"
          onClick={onRun}
          disabled={!result.ready_for_evaluation}
          title={result.ready_for_evaluation ? undefined : "先处理上方阻断项"}
        >
          {result.ready_for_evaluation ? "开始完整评估" : "完整评估暂不可用"}
        </button>
        <button
          className="secondary-action"
          type="button"
          onClick={onScore}
          disabled={!result.ready_for_scoring}
        >
          只打分（无需标签）
        </button>
        <p>
          预检只读取数据并规划切分，不训练模型；点击评估后才会占用后台执行位。
        </p>
      </footer>
    </section>
  );
}
