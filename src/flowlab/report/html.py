"""单文件 HTML 报告：无外部依赖，可直接发邮件、贴内网、打印成 PDF。"""
from __future__ import annotations

import html
from datetime import datetime

from flowlab.eval.runner import EvalResult

CSS = """
:root{--ink:#131a1f;--muted:#5a6a72;--line:#d3dce0;--teal:#0b6b64;--alert:#b3121f;--amber:#96610a}
*{box-sizing:border-box}
body{margin:0;padding:40px 32px 64px;background:#f2f4f5;color:var(--ink);
  font:14px/1.65 "Inter","PingFang SC","Microsoft YaHei",system-ui,sans-serif}
.wrap{max-width:1040px;margin:0 auto}
h1{font-size:26px;margin:0 0 4px;letter-spacing:-.01em}
h2{font-size:14px;margin:34px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--line)}
.sub{color:var(--muted);font-size:13px;margin:0 0 22px}
.meta{width:100%;border-collapse:collapse;font-size:13px;background:#fbfcfc;border:1px solid var(--line)}
.meta th,.meta td{text-align:left;padding:7px 10px;border-bottom:1px solid #e6ecee}
.meta th{width:180px;color:var(--muted);font-weight:600}
.mono{font-family:"JetBrains Mono",ui-monospace,Consolas,monospace;font-size:12px}
table.data{width:100%;border-collapse:collapse;font-size:13px;background:#fbfcfc;border:1px solid var(--line)}
table.data th,table.data td{padding:7px 9px;border-bottom:1px solid #e6ecee;text-align:left}
table.data thead th{font-size:11.5px;color:var(--muted);border-bottom:1px solid #a9b8c0}
table.data tr:last-child td,table.data tr:last-child th{border-bottom:0}
.num{text-align:right;font-variant-numeric:tabular-nums;font-family:"JetBrains Mono",ui-monospace,monospace}
.best{box-shadow:inset 3px 0 0 var(--teal)}
.best-tag{font-size:10px;color:var(--teal);border:1px solid var(--teal);padding:0 4px;margin-left:6px}
.sigwrap{display:grid;grid-template-columns:26px 1fr;gap:8px;margin:8px 0 6px}
.sigy{display:flex;flex-direction:column;justify-content:space-between;align-items:flex-end;
  font:10px/1 "JetBrains Mono",monospace;color:var(--muted);padding-bottom:2px}
.signal{display:flex;align-items:flex-end;gap:1px;height:96px;
  border-bottom:1px solid #a9b8c0;position:relative}
.thr{position:absolute;left:0;right:0;border-top:1px dashed var(--alert);opacity:.7}
.thr span{position:absolute;right:0;top:-13px;font:10px/1 "JetBrains Mono",monospace;
  color:var(--alert);background:#f2f4f5;padding:0 3px}
.tick{flex:1;background:#8fb8b3;opacity:.55}
.tick.hit{background:var(--alert);opacity:.85}
.cap{color:var(--muted);font-size:11.5px;display:flex;justify-content:space-between}
.warn{border-left:3px solid var(--line);padding:8px 0 8px 10px;margin:8px 0;background:#fbfcfc}
.warn.high{border-color:var(--alert)}
.warn.medium{border-color:var(--amber)}
.warn p{margin:3px 0;font-size:13px}
.warn .fix{color:var(--muted);font-size:12px}
.tag{font-size:11px;padding:0 5px;border-radius:2px;background:#eef2f3}
.bad{color:var(--alert);font-weight:600}
.ok{color:#0b6b4f}
.foot{margin-top:38px;color:var(--muted);font-size:11.5px;border-top:1px solid var(--line);padding-top:12px}
@media print{body{background:#fff;padding:0}.wrap{max-width:none}h2{page-break-after:avoid}}
"""


def _e(v) -> str:
    return html.escape("" if v is None else str(v))


def _num(v, digits: int = 4) -> str:
    return "—" if v is None else f"{v:.{digits}f}"


def _signal(curve: list[dict], threshold: float) -> str:
    if not curve:
        return ""
    bars = "".join(
        f'<span class="tick{" hit" if b.get("h", 0) > 0 else ""}" '
        f'style="height:{max(3, min(100, b.get("p", 0) * 100)):.1f}%"></span>'
        for b in curve
    )
    return (
        f'<div class="sigwrap"><div class="sigy"><span>1.0</span><span>0.5</span><span>0.0</span></div>'
        f'<div class="signal">{bars}'
        f'<div class="thr" style="bottom:{threshold * 100:.0f}%"><span>阈值 {threshold:.2f}</span></div>'
        f'</div></div>'
        f'<div class="cap"><span>测试集开头</span>'
        f'<span>柱高=窗口最高分，红色=含超阈值流</span>'
        f'<span>测试集结尾</span></div>'
    )


def render_html(results: list[EvalResult], warns: list[dict], meta: dict,
                ablation: dict | None = None) -> str:
    r0 = results[0] if results else None
    best = max(results, key=lambda r: (r.metrics.get("auc") or 0)) if results else None
    lab = meta.get("labels") or {}
    eng = meta.get("engineering") or {}

    rows_meta = [
        ("数据来源", _e(meta.get("source", "合成数据"))),
        ("样本量", f"{meta.get('rows', 0)}（训练 {r0.n_train if r0 else 0} / 测试 {r0.n_test if r0 else 0}）"),
        ("攻击样本", f"训练 {r0.attack_train if r0 else 0} / 测试 {r0.metrics.get('attack_support', 0) if r0 else 0}"),
        ("数据指纹", f'<span class="mono">{_e(r0.dataset_hash if r0 else "")}</span>'),
        ("切分方式", _e(r0.split if r0 else "")),
        ("随机种子", str(r0.seed if r0 else 42)),
        ("判定阈值", f"{r0.threshold if r0 else 0.5}"),
        ("标签对齐", _e(lab.get("mode", "embedded")) + (f"（{lab.get('labelled', 0)}/{lab.get('total', 0)}）" if lab else "")),
        ("速率兜底", f"{eng.get('min_duration_ms', '—')} ms"),
        ("生成时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    ]
    meta_html = "".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in rows_meta)

    warn_html = "".join(
        f'<div class="warn {_e(w["severity"])}">'
        f'<p><span class="tag mono">{_e(w["rule"])}</span> {_e(w["message"])}</p>'
        f'<p class="fix">建议：{_e(w["suggestion"])}</p></div>'
        for w in warns
    ) or '<p class="cap">未检测到明显的数据泄漏。</p>'

    model_rows = ""
    for r in results:
        m = r.metrics
        model_rows += (
            f'<tr class="{"best" if best and r.model == best.model else ""}">'
            f'<th scope="row" class="mono">{_e(r.model)}'
            f'{"<span class=best-tag>最佳</span>" if best and r.model == best.model else ""}</th>'
            f'<td>{_e(r.kind)}</td><td class="num">{_num(m.get("auc"))}</td>'
            f'<td class="num">{_num(m.get("f1"))}</td><td class="num">{_num(m.get("precision"))}</td>'
            f'<td class="num">{_num(m.get("recall"))}</td>'
            f'<td class="num">{"—" if m.get("fpr") is None else f"{m['fpr'] * 100:.2f}%"}</td>'
            f'<td class="num">{r.duration_s:.2f}s</td>'
            f'<td class="num">{r.confusion["tp"]}/{r.confusion["fp"]}/{r.confusion["fn"]}/{r.confusion["tn"]}</td>'
            f"</tr>"
        )

    flow_rows = ""
    for f in (best.top_flows if best else [])[:15]:
        is_attack = str(f.get("label", "")).strip().lower() not in {"", "benign", "none"}
        flow_rows += (
            f'<tr><td class="mono">{_e(f.get("src_ip"))}</td><td class="mono">{_e(f.get("dst_ip"))}</td>'
            f'<td class="mono">{_e(f.get("dst_port"))}</td><td class="mono">{_e(f.get("protocol"))}</td>'
            f'<td class="mono">{_e(f.get("timestamp"))}</td>'
            f'<td class="num">{_num(f.get("score"), 3)}</td>'
            f'<td class="{"bad" if is_attack else "ok"}">{_e(f.get("label"))}</td></tr>'
        )

    ab_html = ""
    if ablation:
        rows = "".join(
            f'<tr><td class="mono">{_e(x["model"])}</td><td class="num">{_num(x["auc_with"])}</td>'
            f'<td class="num">{_num(x["auc_without"])}</td>'
            f'<td class="num {"bad" if (x["delta"] or 0) > 0.02 else ""}">'
            f'{"—" if x["delta"] is None else f"{x['delta']:+.4f}"}</td></tr>'
            for x in ablation.get("rows", [])
        )
        ab_html = (
            f"<h2>消融：去掉 {_e(ablation.get('column'))}</h2>"
            f'<table class="data"><thead><tr><th>模型</th><th>AUC（含该列）</th>'
            f"<th>AUC（去掉后）</th><th>Δ</th></tr></thead><tbody>{rows}</tbody></table>"
            f'<p class="cap">{_e(ablation.get("note", ""))}</p>'
        )

    small = "" if (r0 and r0.n_test >= 50) else (
        '<p class="cap">⚠ 测试集不足 50 条，指标波动很大，不能当作结论。</p>'
    )

    curve = best.score_curve if best else []
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>FlowLab 实验报告 {_e(r0.dataset_hash if r0 else "")}</title>
<style>{CSS}</style></head>
<body><div class="wrap">
<h1>流量异常检测实验报告</h1>
<p class="sub">{_e(meta.get('source', ''))} · 指纹 <span class="mono">{_e(r0.dataset_hash if r0 else '')}</span></p>
<table class="meta">{meta_html}</table>
<h2>测试集分数分布</h2>
{_signal(curve, r0.threshold if r0 else 0.5)}
{small}
<h2>数据泄漏检查</h2>
{warn_html}
<h2>模型对比</h2>
<table class="data"><thead><tr><th>模型</th><th>类型</th><th>AUC</th><th>F1</th>
<th>精确率</th><th>召回率</th><th>误报率</th><th>耗时</th><th>TP/FP/FN/TN</th></tr></thead>
<tbody>{model_rows}</tbody></table>
{ab_html}
<h2>最可疑的流（{_e(best.model if best else '')}，前 15 条）</h2>
<table class="data"><thead><tr><th>源</th><th>目的</th><th>端口</th><th>协议</th>
<th>时间</th><th>分数</th><th>真实标签</th></tr></thead><tbody>{flow_rows}</tbody></table>
<h2>复现</h2>
<p class="mono">uv run flowlab demo --split {_e(r0.split if r0 else 'temporal')} --seed {r0.seed if r0 else 42} --models {_e(','.join(r.model for r in results))}</p>
<p class="cap">同样的数据指纹 + 同样的切分与随机种子，结果应逐位一致（浮点误差除外）。</p>
<div class="foot">FlowLab · 本文件自包含，可直接归档或打印为 PDF。</div>
</div></body></html>"""
