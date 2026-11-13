"""统一的加载管线：读文件 → 标准化 → 旁挂标签 → 特征工程。

CLI 与 API 都必须走这里，避免两条路径的特征不一致。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from flowlab.engineer import add_engineered_features, describe
from flowlab.labels import attach_labels, guess_sidecar
from flowlab.schema import normalize_columns


@dataclass
class LoadedFrame:
    df: pd.DataFrame
    source: str
    label_info: dict = field(default_factory=dict)
    engineering: dict = field(default_factory=describe)

    def meta(self) -> dict:
        return {"source": self.source, "labels": self.label_info, "engineering": self.engineering}


def load_frame(path: str | Path, labels_path: str | Path | None = None) -> LoadedFrame:
    p = Path(path)
    suffix = p.suffix.lower()

    if suffix in {".pcap", ".pcapng"}:
        from flowlab.ingest.pcap import read_pcap
        df, kind = read_pcap(p), "pcap"
    else:
        from flowlab.ingest.csv import read_csv
        df, kind = read_csv(p), "csv"

    df = normalize_columns(df)

    info: dict = {}
    sidecar = Path(labels_path) if labels_path else guess_sidecar(p)
    if sidecar is not None and "label" not in df.columns:
        df, info = attach_labels(df, sidecar)
        info["file"] = str(sidecar)
    elif "label" in df.columns:
        info = {"mode": "embedded", "labelled": int(df["label"].notna().sum()),
                "total": len(df), "matches": int(df["label"].notna().sum())}

    df = add_engineered_features(df)
    return LoadedFrame(df=df, source=f"{p.name}（{kind}）", label_info=info)
