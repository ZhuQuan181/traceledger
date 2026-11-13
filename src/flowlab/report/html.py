"""单文件 HTML 报告：无外部依赖，可直接发邮件、贴内网、打印成 PDF。

视觉风格与 web 端一致：纸面、衬线标题、等宽数字、发丝线。
"""
from __future__ import annotations

import html
from datetime import datetime

from flowlab.eval.runner import EvalResult

CSS = """
:root{--paper:#fbfaf7;--ink:#14161a;--ink2:#3d444b;--muted:#616870;--rule:#e7e3da;
--rule2:#cdc7ba;--navy:#1b3b5f;--alert:#a4262c;--amber:#8a5a00;--ok:#1d6a4a}
*{box-sizing:border-box}
body{margin:0;padding:56px 40px 72px;background:var(--paper);color:var(--ink);
font:14px/1.65 "Inter","PingFang SC","Microsoft YaHei",system-ui,sans-serif;-webkit-font-smoothing:antialiased}
.wrap{max-width:1000px;margin:0 auto}
.serif{font-family:"Newsreader","Iowan Old Style","Songti SC",Georgia,serif}
.mono{font-family:"IBM Plex Mono",ui-monospace,Consolas,monospace;font-variant-numeric:tabular-nums}
h1{font-family:"Newsreader",Georgia,serif;font-weight:400;font-size:36px;line-height:1.15;
letter-spacing:-.015em;margin:0 0 4px}
h2{font-family:"Newsreader",Georgia,serif;font-weight:400;font-size:23px;margin:44px 0 14px;
padding-bottom:0;border:0}
h2 .idx{font-family:"IBM Plex Mono",monospace;font-size:11px;color:var(--muted);margin-right:10px;vertical-align:2px}
.sub{color:var(--ink2);font-size:13px;margin:0 0 6px}
.kicker{font-family:"IBM Plex Mono",monospace;font-size:11.5px;color:var(--ink2)}
.band{display:grid;grid-template-columns:repeat(4,1fr);border-top:1px solid var(--ink);
border-bottom:1px solid var(--rule);margin:22px 0 8px}
.band .cell{padding:18px 18px 20px 0}
.band .cell+.cell{border-left:1px solid var(--rule);padding-left:18px}
.band .k{font-size:11px;color:var(--muted);margin-bottom:6px}
.band .v{font-family:"Newsreader",Georgia,serif;font-size:34px;line-height:1;letter-spacing:-.02em}
.band .v.mono{font-family:"IBM Plex Mono",monospace;font-size:30px;letter-spacing:-.04em}
.band .n{font-size:11.5px;color:var(--muted);margin-top:8px}
table.data{width:100%;border-collapse:collapse;font-size:13px}
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
.sigwrap{display:grid;grid-template-columns:32px 1fr;gap:10px;margin:10px 0 4px}
.sigy{display:flex;flex-direction:column;justify-content:space-between;align-items:flex-end;
font:10px/1 "IBM Plex Mono",monospace;color:var(--muted);padding-bottom:1px}
.signal{display:flex;align-items:flex-end;gap:2px;height:150px;position:relative;border-bottom:1px solid var(--rule2)}
.tick{flex:1;background:var(--navy);opacity:.32;border-radius:1px 1px 0 0}
.hits{display:flex;gap:2px;height:4px;margin-top:3px}
.hits span{flex:1;background:var(--alert);border-radius:1px}
.thr{position:absolute;left:0;right:0;border-top:1px dashed var(--alert);opacity:.85}
.thr span{position:absolute;right:6px;top:-16px;padding:1px 5px;background:var(--paper);
font:10px/1 "IBM Plex Mono",monospace;color:var(--alert)}
.cap{color:var(--muted);font-size:11px;display:flex;justify-content:space-between;gap:12px;margin-top:8px}
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
.risk{margin:16px 0 0;padding:10px 14px;border-left:2px solid var(--alert);
background:rgba(164,38,44,.045);font-size:13px;display:flex;gap:10px;align-items:baseline}
.risk .tag{font-family:"IBM Plex Mono",monospace;font-size:11px;color:var(--alert)}
.risk .more{margin-left:auto;font-size:11.5px;color:var(--muted)}
.foot{margin-top:44px;padding-top:14px;border-top:1px solid var(--rule);font-size:11.5px;color:var(--muted)}
@media print{body{background:#fff;padding:0}.wrap{max-width:none}}
"""


def _e(v) -> str:
    return html.escape("" if v is None else str(v))


def _num(v, digits: int = 4) -> str:
    return "—" if v is None else f"{v:.{digits}f}"


def _signal(curve: list[dict], threshold: float) -> str:
    if not curve:
        return ""
    bars = "".join(
        f'<span class="tick" style="height:{max(2, min(100, b.get("p", 0) * 100)):.1f}%"></span>'
        for b in curve
    )
    hits = "".join(
        f'<span style="opacity:{0.35 + 0.65 * min(1, b.get("h", 0) * 3):.2f}"></span>'
        if b.get("h", 0) > 0 else "<span style=\"opacity:0\"></span>"
        for b in curve
    )
    return (
        f'<div class="sigwrap"><div class="sigy"><span>1.0</span><span>0.5</span><span>0.0</span></div>'
        f'<div><div class="signal">{bars}'
        f'<div class="thr" style="bottom:{threshold * 100:.0f}%"><span>阈值 {threshold:.2f}</span></div>'
        f'</div><div class="hits">{hits}</div></div></div>'
        f'<div class="cap"><span>测试集开头</span>'
        f'<span>柱高＝窗口最高分；红色短条＝该窗口含超阈值流</span>'
        f'<span>测试集结尾</span></div>'
    )


def render_html(results: list[EvalResult], warns: list[dict], meta: dict,
                ablation: dict | None = None) -> str:
    r0 = results[0] if results else None
    best = max(results, key=lambda r: (r.metrics.get("auc") or 0)) if results else None
    lab = meta.get("labels") or {}
    eng = meta.get("engineering") or {}
    fmt = meta.get("format") or {}

    meta_rows = [
        ("数据来源", f'{_e(meta.get("source", "合成数据"))}（{_e(fmt.get("format", "data"))}）'),
        ("样本量", f"{meta.get('rows', 0)}（训练 {r0.n_train if r0 else 0} / 测试 {r0.n_test if r0 else 0}）"),
        ("攻击样本", f"训练 {r0.attack_train if r0 else 0} / 测试 {r0.metrics.get('attack_support', 0) if r0 else 0}"),
        ("数据指纹", f'<span class="mono">{_e(r0.dataset_hash if r0 else "")}</span>'),
        ("切分方式", _e(r0.split if r0 else "")),
        ("随机种子", str(r0.seed if r0 else 42)),
        ("判定阈值", f"{r0.threshold if r0 else 0.5}"),
        ("标签对齐", _e(lab.get("mode", "embedded")) + (f'（{lab.get("labelled", 0)}/{lab.get("total", 0)}）' if lab else "")),
        ("速率兜底", f'{eng.get("min_duration_ms", "—")} ms'),
        ("生成时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    ]
    meta_html = "".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in meta_rows)

    warn_html = "".join(
        f'<div class="leak {_e(w["severity"])}">'
        f'<div><span class="rule-name">{_e(w["rule"])}</span>'
        f'<span class="sev">{_e(w["severity"])} · {_e(", ".join(map(str, w["columns"][:2])))}</span></div>'
        f'<div><p>{_e(w["message"])}</p><p class="fix">建议：{_e(w["suggestion"])}</p></div></div>'
        for w in warns
    ) or '<p class="cap">未检测到明显的数据泄漏。</p>'

    model_rows = ""
    for r in results:
        m = r.metrics
        model_rows += (
            f'<tr class="{"best" if best and r.model == best.model else ""}">'
            f'<th scope="row" class="mono">{_e(r.model)}'
            f'{"<span class=best-tag>最佳</span>" if best and r.model == best.model else ""}</th>'
            f'<td class="muted">{"监督" if r.kind == "supervised" else "无监督"}</td><td class="num">{_num(m.get("auc"))}</td>'
            f'<td class="num">{_num(m.get("f1"))}</td><td class="num">{_num(m.get("precision"))}</td>'
            f'<td class="num">{_num(m.get("recall"))}</td>'
            f'<td class="num">{"—" if m.get("fpr") is None else f"{m['fpr'] * 100:.2f}%"}</td>'
            f'<td class="num muted">{r.duration_s:.2f}s</td>'
            f'<td class="num">{r.confusion["tp"]}</td><td class="num bad">{r.confusion["fp"]}</td>'
            f'<td class="num bad">{r.confusion["fn"]}</td><td class="num">{r.confusion["tn"]}</td>'
            f"</tr>"
        )

    flow_rows = ""
    for f in (best.top_flows if best else [])[:15]:
        is_attack = str(f.get("label", "")).strip().lower() not in {"", "benign", "none"}
        flow_rows += (
            f'<tr><td class="mono">{_e(f.get("src_ip"))}</td><td class="mono">{_e(f.get("dst_ip"))}</td>'
            f'<td class="num">{_e(f.get("dst_port"))}</td><td class="muted">{_e(f.get("protocol"))}</td>'
            f'<td class="mono muted">{_e(f.get("timestamp"))}</td>'
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
            f'<h2><span class="idx">04</span>消融：去掉 {_e(ablation.get("column"))}</h2>'
            f'<table class="data"><thead><tr><th>模型</th><th class="num">AUC（含该列）</th>'
            f'<th class="num">AUC（去掉后）</th><th class="num">Δ</th></tr></thead><tbody>{rows}</tbody></table>'
            f'<p class="cap">{_e(ablation.get("note", ""))}</p>'
        )

    small = "" if (r0 and r0.n_test >= 50) else (
        '<p class="cap">⚠ 测试集不足 50 条，指标波动很大，不能当作结论。</p>'
    )

    curve = best.score_curve if best else []
    m = best.metrics if best else None
    five = "05" if ablation else "04"

    best_name = _e(best.model if best else "—")
    best_kind = (("监督学习" if best.kind == "supervised" else "无监督基线") if best else "")
    auc = _num(m.get("auc") if m else None)
    f1 = _num(m.get("f1") if m else None)
    prec = _num(m.get("precision") if m else None, 3)
    rec = _num(m.get("recall") if m else None, 3)
    fpr = "—" if not m or m.get("fpr") is None else f"{m['fpr'] * 100:.2f}%"
    signal = _signal(curve, r0.threshold if r0 else 0.5)
    risk = (
        f'<div class="risk"><span class="tag">{len(warns)} 条泄漏</span>'
        f'<span>{_e(warns[0]["rule"])}：{_e(warns[0]["message"])}</span>'
        f'<span class="more">明细见第 03 节</span></div>'
        if warns else ""
    )
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>FlowLab 实验报告 {_e(r0.dataset_hash if r0 else "")}</title>
<style>{CSS}</style></head>
<body><div class="wrap">
<p class="kicker">RUN {_e(r0.dataset_hash if r0 else "")} · {_e(fmt.get("format", "data"))}</p>
<h1>流量异常检测实验报告</h1>
<p class="sub">{_e(meta.get('source', ''))} · {meta.get('rows', 0)} 条流 · 指纹 {_e(r0.dataset_hash if r0 else '')}</p>

<div class="band">
  <div class="cell"><div class="k">最佳模型</div><div class="v mono">{best_name}</div>
    <div class="n">{best_kind}</div></div>
  <div class="cell"><div class="k">AUC</div><div class="v">{auc}</div>
    <div class="n">排序能力，1 表示完美</div></div>
  <div class="cell"><div class="k">F1</div><div class="v">{f1}</div>
    <div class="n">精确率 {prec} · 召回率 {rec}</div></div>
  <div class="cell"><div class="k">误报率</div><div class="v mono">{fpr}</div>
    <div class="n">正常流被误判的比例</div></div>
</div>

{risk}

<h2><span class="idx">01</span>测试集分数峰值</h2>
{signal}
{small}

<h2><span class="idx">02</span>模型对比</h2>
<table class="data"><thead><tr><th>模型</th><th>类型</th><th class="num">AUC</th><th class="num">F1</th>
<th class="num">精确率</th><th class="num">召回率</th><th class="num">误报率</th><th class="num">耗时</th>
<th class="num">TP</th><th class="num">FP</th><th class="num">FN</th><th class="num">TN</th></tr></thead>
<tbody>{model_rows}</tbody></table>

<h2><span class="idx">03</span>数据泄漏检查</h2>
<div class="leaks">{warn_html}</div>

{ab_html}

<h2><span class="idx">{five}</span>最可疑的流</h2>
<table class="data"><thead><tr><th>源</th><th>目的</th><th class="num">端口</th><th>协议</th>
<th>时间</th><th class="num">分数</th><th>真实标签</th></tr></thead><tbody>{flow_rows}</tbody></table>

<h2><span class="idx">{int(five) + 1:02d}</span>实验配置</h2>
<table class="data">{meta_html}</table>

<p class="foot">复现：<span class="mono">uv run flowlab demo --split {_e(r0.split if r0 else 'temporal')} --seed {r0.seed if r0 else 42} --models {_e(','.join(r.model for r in results))}</span><br>
同一数据指纹 + 同样的切分与随机种子，结果应逐位一致（浮点误差除外）。本文件自包含，可离线归档。</p>
</div></body></html>"""
