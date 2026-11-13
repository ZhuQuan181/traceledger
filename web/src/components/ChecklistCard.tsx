import type { ChecklistItem } from "../types";

export function ChecklistCard({ items }: { items: ChecklistItem[] }) {
  if (!items.length) return null;
  const passed = items.filter((i) => i.ok).length;
  const allOk = passed === items.length;

  return (
    <section className={`checklist-card ${allOk ? "done" : ""}`}>
      <div className="cc-head">
        <h2>自查清单</h2>
        <span className="cc-count">{passed}/{items.length}</span>
      </div>
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
    </section>
  );
}
