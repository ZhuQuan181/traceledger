import type { ChecklistItem } from "../types";

export function ChecklistCard({ items }: { items: ChecklistItem[] }) {
  if (!items.length) return null;
  const passed = items.filter((i) => i.ok).length;
  const allOk = passed === items.length;

  return (
    <details className={`checklist-card ${allOk ? "done" : ""}`}>
      <summary className="cc-head">
        <span className="cc-title">自查清单</span>
        <span className="cc-count">{passed}/{items.length}</span>
      </summary>
      <ul className="cc-list">
        {items.map((i) => (
          <li key={i.item} className={i.ok ? "ok" : "todo"}>
            <span className="cc-box" aria-hidden="true">{i.ok ? "✓" : ""}</span>
            <span className="cc-item">{i.item}</span>
            <span className="cc-note">{i.detail}</span>
          </li>
        ))}
      </ul>
      <p className="cc-foot">
        {allOk ? "全部通过，可以直接进附录。" : "未勾选的项补完再投稿——这些是审稿人最容易问到的。"}
      </p>
    </details>
  );
}
