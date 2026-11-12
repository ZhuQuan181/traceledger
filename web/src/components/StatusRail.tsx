import type { Payload } from "../types";

export function StatusRail({ payload, busy }: { payload: Payload | null; busy: boolean }) {
  return (
    <header className="rail">
      <div className="brand">
        <span className="brand-mark" aria-hidden="true" />
        <span className="brand-name">FlowLab</span>
        <span className="brand-sub">流量异常检测工作台</span>
      </div>
      <div className="rail-meta" aria-live="polite">
        {busy && <span className="pulse">实验中</span>}
        {payload && !busy && (
          <>
            <span className="chip mono">hash {payload.dataset.hash}</span>
            <span className="chip mono">{payload.dataset.rows.toLocaleString()} 条流</span>
            <span className="chip mono">{payload.dataset.split === "temporal" ? "时间切分" : "随机切分"}</span>
          </>
        )}
      </div>
    </header>
  );
}
