"""报告视图：把结果对象压成"已算好、可直接排版"的一份数据。

Markdown 与 HTML 两个渲染器都只读这个视图，避免两边各自推导
"哪个模型最好 / 小数几位 / 哪条泄漏最严重"。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from flowlab.eval.runner import EvalResult

KIND_CN = {"supervised": "监督", "unsupervised": "无监督"}


def fmt_num(v, digits: int = 4) -> str:
    return "—" if v is None else f"{v:.{digits}f}"


def fmt_pct(v, digits: int = 2) -> str:
    return "—" if v is None else f"{v * 100:.{digits}f}%"


@dataclass
class ModelRow:
    model: str
    kind_cn: str
    auc: str
    f1: str
    precision: str
    recall: str
    fpr: str
    duration: str
    tp: str
    fp: str
    fn: str
    tn: str
    is_best: bool
    params: dict = field(default_factory=dict)


@dataclass
class ReportView:
    source: str
    fmt: str
    hash: str
    rows: int
    train: int
    test: int
    attack_train: int
    attack_test: int
    split: str
    seed: int
    threshold: str
    labels_mode: str
    labels_labelled: int
    labels_total: int
    min_duration_ms: str
    best_model: str
    best_kind_cn: str
    auc: str
    f1: str
    precision: str
    recall: str
    fpr: str
    models: list[ModelRow]
    warnings: list[dict]
    flows: list[dict]
    curve: list[dict]
    ablation: dict | None
    small_test: bool
    leak_count: int
    classes: list[dict] = field(default_factory=list)
    features: list[str] = field(default_factory=list)
    encoded_features: int = 0

    @property
    def top_warning(self) -> dict | None:
        return self.warnings[0] if self.warnings else None

    @property
    def suspicious_auc(self) -> bool:
        """AUC 接近满分 + 有泄漏 → 提示"先别信这个数字"。"""
        return bool(self.warnings) and self.auc != "—" and float(self.auc) >= 0.995


def build_view(results: list[EvalResult], warns: list[dict], meta: dict,
               ablation: dict | None = None) -> ReportView:
    r0 = results[0] if results else None
    best = max(results, key=lambda r: (r.metrics.get("auc") or 0)) if results else None
    m = best.metrics if best else {}
    lab = meta.get("labels") or {}
    eng = meta.get("engineering") or {}
    fmt = meta.get("format") or {}

    models = [
        ModelRow(
            model=r.model,
            kind_cn=KIND_CN.get(r.kind, r.kind),
            auc=fmt_num(r.metrics.get("auc")),
            f1=fmt_num(r.metrics.get("f1")),
            precision=fmt_num(r.metrics.get("precision")),
            recall=fmt_num(r.metrics.get("recall")),
            fpr=fmt_pct(r.metrics.get("fpr")),
            duration=f"{r.duration_s:.2f}s",
            tp=f"{r.confusion['tp']:,}",
            fp=f"{r.confusion['fp']:,}",
            fn=f"{r.confusion['fn']:,}",
            tn=f"{r.confusion['tn']:,}",
            is_best=best is not None and r.model == best.model,
            params=r.params,
        )
        for r in results
    ]

    return ReportView(
        source=meta.get("source", "合成数据"),
        fmt=fmt.get("format", "data"),
        hash=r0.dataset_hash if r0 else "",
        rows=int(meta.get("rows", 0)),
        train=r0.n_train if r0 else 0,
        test=r0.n_test if r0 else 0,
        attack_train=r0.attack_train if r0 else 0,
        attack_test=(m.get("attack_support") or 0) if best else 0,
        split=r0.split if r0 else "temporal",
        seed=r0.seed if r0 else 42,
        threshold=f"{r0.threshold:.2f}" if r0 else "0.50",
        labels_mode=lab.get("mode", "embedded"),
        labels_labelled=int(lab.get("labelled", 0) or 0),
        labels_total=int(lab.get("total", 0) or 0),
        min_duration_ms=str(eng.get("min_duration_ms", "—")),
        best_model=best.model if best else "—",
        best_kind_cn=KIND_CN.get(best.kind, best.kind) if best else "",
        auc=fmt_num(m.get("auc")),
        f1=fmt_num(m.get("f1")),
        precision=fmt_num(m.get("precision"), 3),
        recall=fmt_num(m.get("recall"), 3),
        fpr=fmt_pct(m.get("fpr")),
        models=models,
        warnings=warns,
        flows=(best.top_flows if best else [])[:15],
        curve=(best.score_curve if best else []),
        ablation=ablation,
        small_test=bool(r0 and r0.n_test < 50),
        leak_count=len(warns),
        classes=meta.get("classes") or [],
        features=(meta.get("features") or {}).get("used") or [],
        encoded_features=(meta.get("features") or {}).get("encoded") or 0,
    )
