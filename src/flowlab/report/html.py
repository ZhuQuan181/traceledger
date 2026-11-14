"""单文件 HTML 报告：只做排版，所有数值来自 ReportView。"""

from __future__ import annotations

import html
import json

from flowlab.eval.runner import EvalResult
from flowlab.report.view import ReportView, build_view

CSS = """
:root{--paper:#fbfaf7;--ink:#14161a;--ink2:#3d444b;--muted:#616870;--rule:#e7e3da;
--rule2:#cdc7ba;--navy:#1b3b5f;--alert:#a4262c;--amber:#8a5a00;--ok:#1d6a4a}
*{box-sizing:border-box}
body{margin:0;padding:56px 40px 72px;background:var(--paper);color:var(--ink);
font:14px/1.65 "Inter","PingFang SC","Microsoft YaHei",system-ui,sans-serif;-webkit-font-smoothing:antialiased}
.wrap{max-width:1000px;margin:0 auto}
.mono{font-family:"IBM Plex Mono",ui-monospace,Consolas,monospace;font-variant-numeric:tabular-nums}
.table-scroll{width:100%;overflow-x:auto;-webkit-overflow-scrolling:touch}
h1{font-family:"Newsreader",Georgia,serif;font-weight:400;font-size:36px;line-height:1.15;
letter-spacing:-.015em;margin:0 0 4px}
h2{font-family:"Newsreader",Georgia,serif;font-weight:400;font-size:23px;margin:44px 0 14px}
h2 .idx{font-family:"IBM Plex Mono",monospace;font-size:11px;color:var(--muted);margin-right:10px;vertical-align:2px}
h3{font-size:14px;font-weight:600;margin:22px 0 8px;color:var(--ink2)}
.sub{color:var(--ink2);font-size:13px;margin:0}
.kicker{font-family:"IBM Plex Mono",monospace;font-size:11.5px;color:var(--ink2);margin:0 0 4px}
.band{display:grid;grid-template-columns:repeat(4,1fr);border-top:1px solid var(--ink);
border-bottom:1px solid var(--rule);margin:22px 0 0}
.band .cell{padding:18px 18px 20px 0}
.band .cell+.cell{border-left:1px solid var(--rule);padding-left:18px}
.band .k{font-size:11px;color:var(--muted);margin-bottom:6px}
.band .v{font-family:"Newsreader",Georgia,serif;font-size:34px;line-height:1;letter-spacing:-.02em}
.band .v.mono{font-family:"IBM Plex Mono",monospace;font-size:30px;letter-spacing:-.04em}
.band .v.warn{color:var(--alert)}
.band .n{font-size:11.5px;color:var(--muted);margin-top:8px}
.band .n.warn{color:var(--alert)}
.risk{margin:16px 0 0;padding:10px 14px;border-left:2px solid var(--alert);
background:rgba(164,38,44,.045);font-size:13px;display:flex;gap:10px;align-items:baseline}
.risk .tag{font-family:"IBM Plex Mono",monospace;font-size:11px;color:var(--alert)}
.risk .more{margin-left:auto;font-size:11.5px;color:var(--muted)}
.verdict{margin:18px 0 4px;padding:16px 18px;border:1px solid var(--rule);
border-left:3px solid var(--ok);background:#f7faf8}
.verdict.warn{border-left-color:var(--amber);background:#fdfaf3}
.verdict.fail{border-left-color:var(--alert);background:#fdf6f6}
.verdict .vh{margin:0 0 10px;font-size:15px;font-weight:500;line-height:1.45}
.verdict .vl{margin:0 0 4px;font-family:"IBM Plex Mono",monospace;font-size:11px;
letter-spacing:.06em;color:var(--muted)}
.verdict .vi{margin-right:8px}
.verdict table.check{width:100%;border-collapse:collapse;font-size:12.5px}
.verdict table.check th,.verdict table.check td{
text-align:left;padding:6px 8px;border-bottom:1px solid rgba(0,0,0,.06)}
.verdict table.check thead th{font-size:11px;color:var(--muted);font-weight:600}
.verdict table.check tr:last-child th,.verdict table.check tr:last-child td{border-bottom:0}
.verdict table.check th[scope=row]{width:88px;font-weight:500}
.verdict table.check td.st{width:64px;font-size:11.5px}
.verdict table.check tr.fail td.st{color:var(--alert);font-weight:600}
.verdict table.check tr.warn td.st{color:var(--amber);font-weight:600}
.verdict table.check tr.pass td.st{color:var(--ok)}
.verdict .cap{margin-top:8px}
.selfcheck{margin:14px 0 4px;padding:14px 18px;border:1px solid var(--rule);background:#fcfbf8}
.sc-head{margin:0 0 10px;font-size:12px;color:var(--muted);letter-spacing:.02em}
.sc-count{font-family:"IBM Plex Mono",monospace;color:var(--ink2);margin-left:6px}
.sc-list{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:1px}
.sc-list li{display:grid;grid-template-columns:16px 150px 1fr;gap:10px;align-items:baseline;
padding:5px 0;font-size:12.5px;border-top:1px solid rgba(0,0,0,.05)}
.sc-list li:first-child{border-top:0}
.sc-list .box{width:13px;height:13px;border:1px solid var(--rule2);border-radius:2px;
display:grid;place-items:center;font-size:9px;line-height:1;color:#fff}
.sc-list li.ok .box{background:var(--ok);border-color:var(--ok)}
.sc-list .ck-item{color:var(--ink2)}
.sc-list li.todo .ck-item{color:var(--alert)}
.sc-list .ck-note{color:var(--muted);font-size:12px}
table.data{width:100%;border-collapse:collapse;font-size:13px}
table.data.wide{min-width:900px}
table.data.flows{min-width:760px}
table.data thead th{text-align:left;font-size:11.5px;font-weight:600;color:var(--ink2);
padding:0 12px 9px;border-bottom:1px solid var(--rule2);white-space:nowrap}
table.data td,table.data tbody th{padding:12px;border-bottom:1px solid var(--rule);text-align:left}
table.data tbody th{font-weight:500}
table.data tbody tr:last-child td,table.data tbody tr:last-child th{border-bottom:0}
table.data .num{text-align:right;font-family:"IBM Plex Mono",monospace;font-variant-numeric:tabular-nums}
table.data thead th.num{text-align:right}
table.data tr.best{background:#f3f6f9}
table.data tr.best th:first-child{box-shadow:inset 2px 0 0 var(--navy)}
.best-tag{display:inline-block;margin-left:8px;padding:0 5px;font-size:10px;color:var(--navy);
border:1px solid #c2d0dd;border-radius:2px;vertical-align:1px}
.muted{color:var(--muted)} .bad{color:var(--alert)} .ok{color:var(--ok)}
.sigwrap{display:grid;grid-template-columns:32px 1fr;gap:10px;margin:10px 0 0}
.sigy{display:flex;flex-direction:column;justify-content:space-between;align-items:flex-end;
font:10px/1 "IBM Plex Mono",monospace;color:var(--muted);padding-bottom:1px}
.signal{display:flex;align-items:flex-end;gap:2px;height:150px;position:relative;border-bottom:1px solid var(--rule2)}
.tick{flex:1;background:var(--navy);opacity:.32;border-radius:1px 1px 0 0}
.hits{display:flex;gap:2px;height:5px;margin-top:0}
.hits span{flex:1;background:var(--alert);border-radius:0 0 1px 1px}
.tick.hit{background:var(--alert);opacity:.62}
.thr{position:absolute;left:0;right:0;border-top:1px dashed var(--alert);opacity:.85}
.thr span{position:absolute;right:6px;top:-16px;padding:1px 5px;background:var(--paper);
font:10px/1 "IBM Plex Mono",monospace;color:var(--alert)}
.cap{color:var(--muted);font-size:11px;display:flex;justify-content:space-between;gap:12px;margin-top:8px}
.diag{margin-top:20px;padding-top:16px;border-top:1px solid var(--rule)}
.diag-head{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:11px}
.diag-head h3{margin:0}
.diag-head p{margin:2px 0 0;font-size:11px;color:var(--muted)}
.brier{flex:none;padding:4px 8px;border:1px solid var(--rule2);
font-family:"IBM Plex Mono",monospace;font-size:10.5px;color:var(--ink2)}
.diag-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
.diag-card{margin:0;padding:10px 11px 8px;border:1px solid var(--rule);background:#fffdf8}
.diag-card figcaption{display:flex;align-items:baseline;justify-content:space-between;gap:8px;margin-bottom:5px}
.diag-card strong{font-family:"IBM Plex Mono",monospace;font-size:10.5px;color:var(--ink2)}
.diag-card span{font-size:9.5px;color:var(--muted)}
.diag-card svg{display:block;width:100%;height:auto}
.diag-gridline{stroke:rgba(20,22,26,.1);stroke-width:.7}
.diag-axis{stroke:var(--rule2);stroke-width:1}
.diag-guide{stroke:var(--rule2);stroke-width:1;stroke-dasharray:3 3}
.diag-line{fill:none;stroke:var(--navy);stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.diag-tick{fill:var(--muted);font-family:"IBM Plex Mono",monospace;font-size:9px}
.leaks{display:flex;flex-direction:column}
.leak{display:grid;grid-template-columns:104px 1fr;gap:18px;padding:14px 0 14px 14px;
border-bottom:1px solid var(--rule);border-left:2px solid var(--rule2)}
.leak.high{border-left-color:var(--alert);background:linear-gradient(to right,rgba(164,38,44,.035),transparent 60%)}
.leak.medium{border-left-color:var(--amber)}
.leak:first-child{border-top:1px solid var(--rule)}
.leak .rule-name{font-family:"IBM Plex Mono",monospace;font-size:11.5px}
.leak .sev{display:block;margin-top:4px;font-size:10.5px;color:var(--muted)}
.leak p{margin:0 0 4px;font-size:13px}
.leak .fix{font-size:12px;color:var(--muted)}
.feat-list{margin:12px 0 0;display:flex;flex-wrap:wrap;gap:6px}
.feat{font-family:"IBM Plex Mono",monospace;font-size:10.5px;color:var(--ink2);
background:#f1efe9;padding:2px 6px;border-radius:2px}
.command{white-space:pre-wrap;overflow-wrap:anywhere;padding:12px 14px;border:1px solid var(--rule);
background:#f5f3ed;font:12px/1.6 "IBM Plex Mono",ui-monospace,Consolas,monospace}
.foot{margin-top:44px;padding-top:14px;border-top:1px solid var(--rule);font-size:11.5px;color:var(--muted)}
@media(max-width:720px){
body{padding:30px 16px 48px}
h1{font-size:30px}h2{font-size:21px;margin-top:34px}
.band{grid-template-columns:1fr 1fr}
.band .cell{padding:15px 12px 16px 0}.band .cell+.cell{padding-left:12px}
.band .cell:nth-child(3){border-left:0;border-top:1px solid var(--rule)}
.band .cell:nth-child(4){border-top:1px solid var(--rule)}
.band .v{font-size:29px}.band .v.mono{font-size:24px}
.risk{align-items:flex-start;flex-wrap:wrap}.risk .more{margin-left:0}
.leak{grid-template-columns:1fr;gap:5px}
.sc-list li{grid-template-columns:16px 1fr;gap:4px 9px}
.sc-list .ck-note{grid-column:2}
.verdict table.check th[scope=row]{width:72px}
.verdict table.check,.verdict table.check tbody,.verdict table.check tr{display:block}
.verdict table.check thead{display:none}
.verdict table.check tr{padding:8px 0;border-bottom:1px solid rgba(0,0,0,.06)}
.verdict table.check th,.verdict table.check td{display:inline;padding:0;border:0}
.verdict table.check td.st::before{content:" · "}
.verdict table.check td:last-child{display:block;margin-top:2px;color:var(--muted)}
.sigwrap{grid-template-columns:24px 1fr}.signal{height:120px}
.cap{flex-wrap:wrap}.cap span:nth-child(2){flex-basis:100%;order:3}
.diag-head{align-items:flex-start;flex-wrap:wrap}.diag-grid{grid-template-columns:1fr}
.command{font-size:11px}
}
@media(max-width:380px){
h1{font-size:25px}h2{font-size:20px}
}
@media print{body{background:#fff;padding:0}.wrap{max-width:none}
.table-scroll{overflow:visible}table.data.wide,table.data.flows{min-width:0}}
"""


def _e(v) -> str:
    return html.escape("" if v is None else str(v))


def _fmt(value, digits: int = 3, signed: bool = False) -> str:
    if value is None:
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{number:+.{digits}f}" if signed else f"{number:.{digits}f}"


def _threshold_source(v: ReportView) -> str:
    if v.threshold_source == "validation_f1":
        return "验证集 F1 自动选择"
    if v.threshold_source == "validation_fpr":
        target = (
            f"≤{v.threshold_target_fpr:.2%}" if v.threshold_target_fpr is not None else "目标值"
        )
        return f"验证集目标误报率自动选择（{target}）"
    return "人工指定"


def _signal(v: ReportView) -> str:
    if not v.curve:
        return ""
    HIT = 0.2  # 与网页版一致：窗内 ≥20% 的流超阈值才算命中
    hits_n = sum(1 for b in v.curve if b.get("h", 0) >= HIT)
    bars = "".join(
        f'<span class="tick{" hit" if b.get("h", 0) >= HIT else ""}" '
        f'style="height:{max(2, min(100, b.get("p", 0) * 100)):.1f}%"></span>'
        for b in v.curve
    )
    threshold = float(v.threshold)
    return (
        f'<div class="sigwrap"><div class="sigy"><span>1.0</span><span>0.5</span><span>0.0</span></div>'
        f'<div><div class="signal">{bars}'
        f'<div class="thr" style="bottom:{threshold * 100:.0f}%"><span>阈值 {threshold:.2f}</span></div>'
        f"</div></div></div>"
        f'<div class="cap"><span>{"按时间排序" if v.curve_basis == "time" else "按测试样本顺序"}</span>'
        f"<span>柱高＝该窗最高分；红色柱＝窗内 ≥20% 的流超阈值（{hits_n}/{len(v.curve)}）</span>"
        f"<span>共 {len(v.curve)} 个窗口</span></div>"
    )


def _curve_svg(
    points: list[dict],
    x_key: str,
    y_key: str,
    *,
    diagonal: bool = False,
) -> str:
    if not points:
        return ""
    width, height, pad = 320, 190, 23
    span = width - pad * 2
    yspan = height - pad * 2
    coords = [
        (pad + float(point[x_key]) * span, height - pad - float(point[y_key]) * yspan)
        for point in points
    ]
    polyline = " ".join(f"{x:.2f},{y:.2f}" for x, y in coords)
    grid = "".join(
        f'<line class="diag-gridline" x1="{pad + tick * span:.1f}" '
        f'y1="{height - pad:.1f}" x2="{pad + tick * span:.1f}" y2="{pad:.1f}"/>'
        f'<line class="diag-gridline" x1="{pad:.1f}" '
        f'y1="{height - pad - tick * yspan:.1f}" x2="{width - pad:.1f}" '
        f'y2="{height - pad - tick * yspan:.1f}"/>'
        for tick in (0.25, 0.5, 0.75)
    )
    guide = (
        f'<line class="diag-guide" x1="{pad}" y1="{height - pad}" x2="{width - pad}" y2="{pad}"/>'
        if diagonal
        else ""
    )
    return (
        f'<svg viewBox="0 0 {width} {height}" role="img">'
        f"{grid}{guide}"
        f'<line class="diag-axis" x1="{pad}" y1="{height - pad}" '
        f'x2="{width - pad}" y2="{height - pad}"/>'
        f'<line class="diag-axis" x1="{pad}" y1="{height - pad}" '
        f'x2="{pad}" y2="{pad}"/>'
        f'<polyline class="diag-line" points="{polyline}"/>'
        f'<text class="diag-tick" x="{pad}" y="{height - 7}">0</text>'
        f'<text class="diag-tick" x="{width - pad}" y="{height - 7}" text-anchor="end">1</text>'
        f'<text class="diag-tick" x="{pad - 6}" y="{pad + 3}" text-anchor="end">1</text>'
        f'<text class="diag-tick" x="{pad - 6}" y="{height - pad + 3}" text-anchor="end">0</text>'
        f"</svg>"
    )


def _curves_html(v: ReportView) -> str:
    if not (v.roc_curve or v.pr_curve or v.calibration):
        return ""
    cards: list[str] = []
    specs = [
        ("ROC", "FPR → TPR", v.roc_curve, "fpr", "tpr", True),
        ("PR", "召回率 → 精确率", v.pr_curve, "recall", "precision", False),
        (
            "校准",
            "预测概率 → 实际攻击比例",
            v.calibration,
            "mean_predicted",
            "fraction_positive",
            True,
        ),
    ]
    for title, caption, points, x_key, y_key, diagonal in specs:
        if not points:
            continue
        cards.append(
            f'<figure class="diag-card"><figcaption><strong>{title}</strong>'
            f"<span>{caption}</span></figcaption>"
            f"{_curve_svg(points, x_key, y_key, diagonal=diagonal)}</figure>"
        )
    brier = (
        f'<span class="brier">Brier {v.brier_score:.4f}</span>' if v.brier_score is not None else ""
    )
    note = f'<p class="cap">{_e(v.calibration_note)}</p>' if v.calibration_note else ""
    return (
        '<div class="diag"><div class="diag-head"><div>'
        f"<h3>排序与校准（{_e(v.best_model)}）</h3>"
        "<p>曲线来自测试集；PR/ROC 反映排序能力，校准只对概率输出有意义。</p>"
        f'</div>{brier}</div><div class="diag-grid">{"".join(cards)}</div>{note}</div>'
    )


def render_html(
    results: list[EvalResult], warns: list[dict], meta: dict, ablation: dict | None = None
) -> str:
    v = build_view(results, warns, meta, ablation)

    # 徽标措辞跟着结论走，避免"结论说端口无影响、表格说受泄漏影响"
    vd_level = (v.verdict or {}).get("level")
    if vd_level == "fail":
        port_col = next((w["columns"][0] for w in v.warnings if w["rule"] == "port_leak"), None)
        best_badge = f"受 {port_col} 影响" if port_col else "指标待复核"
    elif vd_level == "warn" and v.suspicious_auc:
        best_badge = "最高分 · 需换数据确认"
    else:
        best_badge = "最佳"
    best_tag = f'<span class="best-tag">{_e(best_badge)}</span>'
    model_rows = "".join(
        f'<tr class="{"best" if m.is_best else ""}">'
        f'<th scope="row" class="mono">{_e(m.model)}'
        f"{best_tag if m.is_best else ''}</th>"
        f'<td class="muted">{_e(m.kind_cn)}</td>'
        f'<td class="num">{_e(m.validation_auc)}</td>'
        f'<td class="num">{_e(m.auc)}</td>'
        f'<td class="num">{_e(m.pr_auc)}</td>'
        f'<td class="num">{_e(m.f1)}</td><td class="num">{_e(m.precision)}</td>'
        f'<td class="num">{_e(m.recall)}</td><td class="num">{_e(m.fpr)}</td>'
        f'<td class="num">{_e(m.threshold)}</td>'
        f'<td class="num muted">{_e(m.duration)}</td>'
        f'<td class="num">{_e(m.tp)}</td><td class="num bad">{_e(m.fp)}</td>'
        f'<td class="num bad">{_e(m.fn)}</td><td class="num">{_e(m.tn)}</td></tr>'
        for m in v.models
    )
    model_params_rows = "".join(
        f'<tr><th scope="row" class="mono">{_e(m.model)}</th>'
        f'<td class="mono">{_e(json.dumps(m.params, ensure_ascii=False, sort_keys=True))}</td></tr>'
        for m in v.models
    )
    model_params_html = (
        "<h3>模型参数</h3>"
        '<div class="table-scroll"><table class="data"><thead><tr><th>模型</th>'
        f"<th>参数</th></tr></thead><tbody>{model_params_rows}</tbody></table></div>"
        if model_params_rows
        else ""
    )

    warn_html = (
        "".join(
            f'<div class="leak {_e(w["severity"])}">'
            f'<div><span class="rule-name">{_e(w["rule"])}</span>'
            f'<span class="sev">{_e(w["severity"])} · {_e(", ".join(map(str, w["columns"][:2])))}</span></div>'
            f'<div><p>{_e(w["message"])}</p><p class="fix">建议：{_e(w["suggestion"])}</p></div></div>'
            for w in v.warnings
        )
        or '<p class="cap">未检测到明显的数据泄漏。</p>'
    )

    threshold_rows = "".join(
        f'<tr><td class="num">{row["threshold"]:.2f}</td>'
        f'<td class="num">{_e(_fmt(row.get("precision"), 4))}</td>'
        f'<td class="num">{_e(_fmt(row.get("recall"), 4))}</td>'
        f'<td class="num">{_e(_fmt(row.get("f1"), 4))}</td>'
        f'<td class="num">{_e(_fmt(None if row.get("fpr") is None else row["fpr"] * 100, 2)) + "%" if row.get("fpr") is not None else "—"}</td></tr>'
        for row in v.threshold_scan
    )
    threshold_html = (
        "<h3>阈值权衡（测试集诊断）</h3>"
        '<div class="table-scroll"><table class="data"><thead><tr><th>阈值</th>'
        '<th class="num">精确率</th><th class="num">召回率</th><th class="num">F1</th>'
        f'<th class="num">误报率</th></tr></thead><tbody>{threshold_rows}</tbody></table></div>'
        '<p class="cap">该扫描只用于展示部署权衡，不能拿测试集挑阈值；自动阈值只使用验证集。</p>'
        if threshold_rows
        else ""
    )
    curves_html = _curves_html(v)

    flow_rows = "".join(
        f'<tr><td class="mono">{_e(f.get("src_ip"))}</td><td class="mono">{_e(f.get("dst_ip"))}</td>'
        f'<td class="num">{_e(f.get("dst_port"))}</td><td class="muted">{_e(f.get("protocol"))}</td>'
        f'<td class="mono muted">{_e(f.get("timestamp"))}</td>'
        f'<td class="num">{_e(_fmt(f.get("score", 0)))}</td>'
        f'<td class="{"bad" if str(f.get("label", "")).lower() not in {"", "benign"} else "ok"}">'
        f"{_e(f.get('label'))}</td></tr>"
        for f in v.flows
    )

    label_rows = "".join(
        f"<tr><td>{_e(row.get('label'))}</td>"
        f'<td class="muted">{"误报率" if row.get("kind") == "benign" else "召回率"}</td>'
        f'<td class="num">{int(row.get("total", 0)):,}</td>'
        f'<td class="num">{int(row.get("flagged", 0)):,}</td>'
        f'<td class="num">{_e(_fmt(None if row.get("rate") is None else row.get("rate") * 100, 2)) + "%" if row.get("rate") is not None else "—"}</td>'
        f"</tr>"
        for row in v.by_label
    )
    source_rows = "".join(
        f'<tr><td class="mono">{_e(row.get("src_ip"))}</td>'
        f'<td class="num">{int(row.get("alerts", 0)):,}</td>'
        f'<td class="num">{int(row.get("true_attacks", 0)):,}</td>'
        f'<td class="num bad">{int(row.get("false_alarms", 0)):,}</td>'
        f'<td class="num">{_e(_fmt(row.get("max_score"), 3))}</td></tr>'
        for row in v.source_ranking
    )

    def _error_rows(rows: list[dict]) -> str:
        return "".join(
            f'<tr><td class="mono">{_e(row.get("src_ip"))}</td>'
            f'<td class="mono">{_e(row.get("dst_ip"))}</td>'
            f'<td class="num">{_e(row.get("dst_port"))}</td>'
            f'<td class="num">{_e(_fmt(row.get("score"), 3))}</td>'
            f"<td>{_e(row.get('label'))}</td></tr>"
            for row in rows
        )

    investigation_blocks: list[str] = []
    if label_rows:
        investigation_blocks.append(
            '<h3>按真实类型拆分</h3><div class="table-scroll"><table class="data">'
            '<thead><tr><th>类型</th><th>性质</th><th class="num">样本</th>'
            '<th class="num">判为攻击</th><th class="num">比例</th></tr></thead>'
            f"<tbody>{label_rows}</tbody></table></div>"
        )
    if source_rows:
        investigation_blocks.append(
            '<h3>先排查的源 IP</h3><div class="table-scroll"><table class="data">'
            '<thead><tr><th>源 IP</th><th class="num">告警</th><th class="num">真攻击</th>'
            '<th class="num">误报</th><th class="num">最高分</th></tr></thead>'
            f"<tbody>{source_rows}</tbody></table></div>"
        )
    for title, rows in (
        ("典型漏报（攻击但未过阈值）", v.false_negatives),
        ("典型误报（正常但被判为攻击）", v.false_positives),
    ):
        body = _error_rows(rows)
        if body:
            investigation_blocks.append(
                f'<h3>{title}</h3><div class="table-scroll"><table class="data flows">'
                '<thead><tr><th>源</th><th>目的</th><th class="num">端口</th>'
                '<th class="num">分数</th><th>标签</th></tr></thead>'
                f"<tbody>{body}</tbody></table></div>"
            )
    investigation_html = "".join(investigation_blocks)

    ab_html = ""
    if v.ablation:
        rows = "".join(
            f'<tr><td class="mono">{_e(x["model"])}</td>'
            f'<td class="num">{_e(_fmt(x.get("auc_with"), 4))}</td>'
            f'<td class="num">{_e(_fmt(x.get("auc_without"), 4))}</td>'
            f'<td class="num {"bad" if (x.get("delta") or 0) > 0.02 else ""}">'
            f"{_e(_fmt(x.get('delta'), 4, signed=True))}</td></tr>"
            for x in v.ablation.get("rows", [])
        )
        ab_html = (
            '<h2><span class="idx">04</span>消融：去掉 '
            f"{_e(v.ablation.get('column'))}</h2>"
            '<div class="table-scroll"><table class="data"><thead><tr><th>模型</th>'
            '<th class="num">AUC（含该列）</th>'
            f'<th class="num">AUC（去掉后）</th><th class="num">Δ</th></tr></thead><tbody>{rows}</tbody></table></div>'
            f'<p class="cap">{_e(v.ablation.get("note", ""))}</p>'
        )

    split_text = _e(v.split)
    if v.split_fallback:
        split_text = "随机切分（请求时间切分，已退化）"
    elif v.split == "temporal":
        split_text = "时间切分"
    elif v.split == "random":
        split_text = "分层随机切分"
    meta_rows = "".join(
        f"<tr><th>{k}</th><td>{val}</td></tr>"
        for k, val in [
            ("数据来源", f"{_e(v.source)}（{_e(v.fmt)}）"),
            (
                "样本量",
                f"{v.rows}（训练 {v.train} / 验证 {v.validation} / 测试 {v.test}）",
            ),
            (
                "攻击样本",
                f"训练 {v.attack_train} / 验证 {v.attack_validation} / 测试 {v.attack_test}",
            ),
            ("数据指纹", f'<span class="mono">{_e(v.hash)}</span>'),
            ("实验指纹", f'<span class="mono">{_e(v.experiment_fingerprint)}</span>'),
            (
                "运行环境",
                _e(
                    " · ".join(
                        f"{key} {value}"
                        for key, value in v.environment.items()
                        if value is not None
                    )
                ),
            ),
            ("切分方式", split_text),
            ("泛化场景", v.generalization),
            ("随机种子", str(v.seed)),
            (
                "判定阈值",
                f"{v.threshold}（{_threshold_source(v)}）",
            ),
            ("模型选择", "验证集 AUC（测试集只做最终报告）"),
            ("标签对齐", f"{_e(v.labels_mode)}（{v.labels_labelled}/{v.labels_total}）"),
            ("速率兜底", f"{v.min_duration_ms} ms"),
            ("类别分布", " · ".join(f"{c['label']} {c['count']:,}" for c in v.classes) or "—"),
            (
                "标签质量",
                (
                    f"缺失 {int(v.quality.get('missing_labels') or 0):,} · "
                    f"重复行 {int(v.quality.get('duplicate_rows') or 0):,} · "
                    f"同实体多标签 {int(v.quality.get('conflict_groups') or 0):,} · "
                    f"稀有类别 {len(v.quality.get('rare_classes') or [])}"
                )
                if v.quality
                else "—",
            ),
            ("训练特征", f"{len(v.features)} 列（编码后 {v.encoded_features} 维）"),
            ("生成时间", _e(v.generated_at)),
        ]
    )
    feature_chips = "".join(f'<code class="feat">{_e(f)}</code>' for f in v.features)

    risk = (
        f'<div class="risk"><span class="tag">{v.leak_count} 条审计提示</span>'
        f"<span>{_e(v.top_warning['rule'])}：{_e(v.top_warning['message'])}</span>"
        f'<span class="more">明细见第 03 节</span></div>'
        if v.top_warning
        else ""
    )
    five = "05" if v.ablation else "04"
    command = v.reproduction_command or (
        f"uv run flowlab demo --split {v.split_requested} --seed {v.seed} "
        f"--threshold {v.threshold} --threshold-mode {v.threshold_mode} "
        + (
            f"--target-fpr {v.threshold_target_fpr} "
            if v.threshold_mode == "fpr" and v.threshold_target_fpr is not None
            else ""
        )
        + f"--models {','.join(m.model for m in v.models)}"
    )
    source_note = (
        "上传文件的原路径不会写入历史；复现前请重新选择同名数据与标签文件。"
        if v.source_kind == "upload"
        else ""
    )
    small = (
        '<p class="cap">⚠ 测试集不足 50 条，指标波动很大，不能当作结论。</p>'
        if v.small_test
        else ""
    )

    def _verdict_box() -> str:
        vd = v.verdict or {}
        if not vd:
            return ""
        level = vd.get("level", "warn")
        icon = {"ok": "✅", "warn": "⚠️", "fail": "⛔"}.get(level, "•")
        label = {"ok": "可用", "warn": "需说明", "fail": "不可用"}.get(level, "")
        mark = {"pass": "通过", "warn": "注意", "fail": "不通过"}
        rows = "".join(
            f'<tr class="{c["status"]}"><th scope="row">{_e(c["name"])}</th>'
            f'<td class="st">{mark.get(c["status"], c["status"])}</td>'
            f"<td>{_e(c['detail'])}</td></tr>"
            for c in (vd.get("checks") or [])
        )
        table = (
            (
                f'<table class="check"><thead><tr><th>检查项</th><th>结果</th><th>说明</th>'
                f"</tr></thead><tbody>{rows}</tbody></table>"
            )
            if rows
            else ""
        )
        reasons = vd.get("reasons") or []
        # 只列不在检查表里的补充信息，避免把明细原句再抄一遍
        shown = {c["detail"] for c in (vd.get("checks") or [])}
        extra = [r for r in reasons if r not in shown]
        more = f'<p class="cap">另需注意：{_e("；".join(extra))}</p>' if extra else ""
        return (
            f'<section class="verdict {level}">'
            f'<p class="vl">{icon} {label}</p>'
            f'<p class="vh">{_e(vd.get("headline", ""))}</p>'
            f"{table}{more}"
            f'<p class="cap">判断依据：CICIDS 类数据集的常见区间（AUC 0.93–0.99、误报率 0.5%–8%），'
            f"只用于发现异常，不是评分标准。</p>"
            f"</section>"
        )

    def _checklist_box() -> str:
        if not v.checklist:
            return ""
        passed = sum(1 for i in v.checklist if i["ok"])
        rows = "".join(
            f'<li class="{"ok" if i["ok"] else "todo"}">'
            f'<span class="box" aria-hidden="true">{"✓" if i["ok"] else ""}</span>'
            f'<span class="ck-item">{_e(i["item"])}</span>'
            f'<span class="ck-note">{_e(i["detail"])}</span></li>'
            for i in v.checklist
        )
        tail = (
            '<p class="cap">未勾选的项补完再投稿；这些是审稿人最容易问到的。</p>'
            if passed < len(v.checklist)
            else '<p class="cap">全部通过，可以直接进附录。</p>'
        )
        return (
            f'<section class="selfcheck"><p class="sc-head">自查清单 '
            f'<span class="sc-count">{passed}/{len(v.checklist)}</span></p>'
            f'<ul class="sc-list">{rows}</ul>{tail}</section>'
        )

    verdict_box = _verdict_box()
    checklist_box = _checklist_box()

    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>FlowLab 实验报告 {_e(v.hash)}</title>
<style>{CSS}</style></head>
<body><div class="wrap">
<p class="kicker">RUN {_e(v.hash)} · {_e(v.fmt)}</p>
<h1>流量异常检测实验报告</h1>
<p class="sub">{_e(v.source)} · {v.rows} 条流 · 指纹 {_e(v.hash)}</p>

{verdict_box}
{checklist_box}

<div class="band">
  <div class="cell"><div class="k">验证集最佳模型</div><div class="v mono">{_e(v.best_model)}</div>
    <div class="n">{_e(v.best_kind_cn)}</div></div>
  <div class="cell"><div class="k">AUC</div>
    <div class="v {"warn" if v.suspicious_auc else ""}">{_e(v.auc)}</div>
    <div class="n {"warn" if v.suspicious_auc else ""}">
      {"接近满分且存在泄漏，先看下方提示" if v.suspicious_auc else "排序能力，1 表示完美"}</div></div>
  <div class="cell"><div class="k">F1</div><div class="v">{_e(v.f1)}</div>
    <div class="n">精确率 {_e(v.precision)} · 召回率 {_e(v.recall)}</div></div>
  <div class="cell"><div class="k">误报率</div><div class="v mono">{_e(v.fpr)}</div>
    <div class="n">正常流被误判的比例</div></div>
</div>
{risk}

<h2><span class="idx">01</span>测试集分数峰值</h2>
{_signal(v)}
{threshold_html}
{small}

<h2><span class="idx">02</span>模型对比</h2>
<p class="cap">最佳模型只按验证集 AUC 选择；AUC 及其后指标均来自未参与选择的测试集。</p>
<div class="table-scroll"><table class="data wide"><thead><tr><th>模型</th><th>类型</th>
<th class="num">验证 AUC</th><th class="num">测试 AUC</th><th class="num">测试 PR-AUC</th><th class="num">测试 F1</th>
<th class="num">精确率</th><th class="num">召回率</th><th class="num">误报率</th><th class="num">阈值</th><th class="num">耗时</th>
<th class="num">TP</th><th class="num">FP</th><th class="num">FN</th><th class="num">TN</th></tr></thead>
<tbody>{model_rows}</tbody></table></div>
{model_params_html}
{curves_html}

<h2><span class="idx">03</span>数据泄漏检查</h2>
<div class="leaks">{warn_html}</div>

{ab_html}

<h2><span class="idx">{five}</span>最可疑的流</h2>
<div class="table-scroll"><table class="data flows"><thead><tr><th>源</th><th>目的</th>
<th class="num">端口</th><th>协议</th>
<th>时间</th><th class="num">分数</th><th>真实标签</th></tr></thead><tbody>{flow_rows}</tbody></table>
</div>

<h2><span class="idx">{int(five) + 1:02d}</span>调查线索</h2>
{investigation_html}

<h2><span class="idx">{int(five) + 2:02d}</span>实验配置</h2>
<table class="data">{meta_rows}</table>
<p class="feat-list">{feature_chips}</p>

<h2><span class="idx">{int(five) + 3:02d}</span>复现方式</h2>
<pre class="command">{_e(command)}</pre>
<p class="foot">数据指纹 <span class="mono">{_e(v.hash)}</span> + 切分 + 随机种子决定指标；
实验指纹 <span class="mono">{_e(v.experiment_fingerprint)}</span> 用于核对两次实验的计算结果是否一致。
报告含生成时间，文件字节不保证完全相同，本文件可离线归档。{(" " + _e(source_note)) if source_note else ""}</p>
</div></body></html>"""
