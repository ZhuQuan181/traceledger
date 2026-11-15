import { useEffect, useState } from "react";
import type { Job } from "../types";

const STEPS = [
  { key: "data", label: "数据" },
  { key: "validate", label: "校验" },
  { key: "features", label: "特征" },
  { key: "model", label: "模型" },
  { key: "ablation", label: "消融" },
  { key: "report", label: "报告" },
] as const;

const PHASE_STEP: Record<Job["phase"], number> = {
  queued: 0,
  loading: 0,
  validating: 1,
  features: 2,
  model: 3,
  ablation: 4,
  report: 5,
  done: 6,
};

const STATUS_LABEL: Record<Job["status"], string> = {
  queued: "排队中",
  running: "运行中",
  cancelling: "正在取消",
  succeeded: "已完成",
  failed: "运行失败",
  cancelled: "已取消",
  interrupted: "服务重启中断",
};

function elapsed(seconds: number) {
  if (seconds < 60) return `${Math.max(0, Math.round(seconds))} 秒`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes} 分 ${Math.round(seconds % 60)} 秒`;
}

export function RunProgress({
  job,
  cancelBusy,
  compact = false,
  onCancel,
  onDismiss,
}: {
  job: Job;
  cancelBusy?: boolean;
  compact?: boolean;
  onCancel: () => void | Promise<void>;
  onDismiss?: () => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const active = job.status === "queued" || job.status === "running"
    || job.status === "cancelling";
  const step = PHASE_STEP[job.phase] ?? 0;
  const visibleSteps = STEPS.filter((item) => item.key !== "ablation" || job.has_ablation);
  const currentKey = STEPS[step]?.key;
  const currentVisibleIndex = visibleSteps.findIndex((item) => item.key === currentKey);

  useEffect(() => setConfirming(false), [job.job_id, job.status]);

  async function cancel() {
    if (!confirming) {
      setConfirming(true);
      return;
    }
    setConfirming(false);
    await onCancel();
  }

  return (
    <section
      className={`run-progress ${compact ? "compact" : ""} status-${job.status}`}
      aria-label="后台实验进度"
    >
      <header className="run-progress-head">
        <div>
          <span className="run-progress-kicker">LOCAL JOB · {job.job_id.slice(0, 8)}</span>
          <strong>{statusHeading(job)}</strong>
        </div>
        <span className={`job-state job-state-${job.status}`}>{STATUS_LABEL[job.status]}</span>
      </header>

      {!compact && active && (
        <ol className="run-phases" aria-label="实验阶段">
          {visibleSteps.map((item, index) => {
            const state = job.phase === "done" || index < currentVisibleIndex
              ? "done"
              : index === currentVisibleIndex ? "current" : "pending";
            return (
              <li key={item.key} className={state} aria-current={state === "current" ? "step" : undefined}>
                <i aria-hidden="true" />
                <span>{item.label}</span>
              </li>
            );
          })}
        </ol>
      )}

      <div
        className="job-bar"
        role="progressbar"
        aria-label="实验完成度"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={job.percent}
        aria-valuetext={`${job.percent}%，${job.message}`}
      >
        <span style={{ width: `${job.percent}%` }} />
      </div>

      <div className="job-meta" role="status" aria-live="polite">
        <span>{job.message}</span>
        <span className="job-numbers">
          {job.phase === "model" || job.phase === "ablation"
            ? `${job.completed_models}/${job.total_models} · `
            : ""}
          {job.percent}% · {elapsed(job.elapsed_s)}
        </span>
      </div>

      {active && (
        <p className="job-continuity">
          关闭页面不会中断本机任务；刷新后可恢复进度，服务重启会把未完成任务标为中断。
        </p>
      )}
      {(job.status === "failed" || job.status === "interrupted") && job.error && (
        <p className="job-error" role="alert">{job.error}</p>
      )}

      <div className="job-actions">
        {active && (
          confirming ? (
            <>
              <span className="job-confirm-copy">确认取消？已完成模型的中间结果不会写入历史。</span>
              <button className="job-cancel danger" type="button" disabled={cancelBusy}
                      onClick={cancel}>
                {cancelBusy ? "取消中…" : "确认取消"}
              </button>
              <button className="job-cancel" type="button" onClick={() => setConfirming(false)}>
                继续运行
              </button>
            </>
          ) : (
            <button className="job-cancel" type="button" disabled={job.status === "cancelling"}
                    onClick={cancel}>
              {job.status === "cancelling" ? "正在取消…" : "取消实验"}
            </button>
          )
        )}
        {!active && onDismiss && (
          <button className="job-cancel" type="button" onClick={onDismiss}>
            收起
          </button>
        )}
      </div>
    </section>
  );
}

function statusHeading(job: Job) {
  if (job.status === "queued") return "本机执行位忙碌";
  if (job.status === "succeeded") return "结果已写入本地历史";
  if (job.status === "failed") return "这次实验没有完成";
  if (job.status === "cancelled") return "任务已停止";
  if (job.status === "interrupted") return "服务重启，任务已中断";
  if (job.phase === "model" || job.phase === "ablation") {
    return job.message;
  }
  return job.message;
}
