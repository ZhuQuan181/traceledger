import json
import pickle

import numpy as np
import pandas as pd
import pytest

from flowlab.adapters import ShapeError
from flowlab.ingest import read_any, supported_formats
from flowlab.pipeline import load_frame
from flowlab.synthetic import generate


def test_supported_list():
    fmts = supported_formats()
    assert {"csv", "pkl", "npz", "npy", "parquet", "json"} <= set(fmts)


def test_read_npz_with_labels(tmp_path):
    p = tmp_path / "x.npz"
    np.savez(p, X=np.arange(20).reshape(10, 2), y=np.array([0] * 8 + [1, 1]))
    df, info = read_any(p)
    assert df.shape == (10, 3)
    assert info["format"] == "npz"
    assert df["label"].sum() == 2


def test_read_npy_without_labels(tmp_path):
    p = tmp_path / "x.npy"
    np.save(p, np.arange(12).reshape(6, 2))
    df, _ = read_any(p)
    assert df.shape == (6, 2)


def test_pickle_requires_opt_in(tmp_path):
    p = tmp_path / "x.pkl"
    p.write_bytes(pickle.dumps({"a": [1, 2], "label": ["BENIGN", "ATTACK"]}))
    with pytest.raises(ShapeError):
        read_any(p)
    df, info = read_any(p, allow_pickle=True)
    assert info["format"] == "pickle"
    assert "pickle_object" in info


def test_read_json_records(tmp_path):
    p = tmp_path / "x.json"
    p.write_text(json.dumps([{"a": 1, "b": 2}, {"a": 3, "b": 4}]), encoding="utf-8")
    df, _ = read_any(p)
    assert df.shape == (2, 2)


def test_read_jsonl(tmp_path):
    p = tmp_path / "x.jsonl"
    p.write_text('{"a":1}\n{"a":2}\n', encoding="utf-8")
    df, _ = read_any(p)
    assert df.shape == (2, 1)


def test_read_parquet_if_available(tmp_path):
    pytest.importorskip("pyarrow")
    p = tmp_path / "x.parquet"
    pd.DataFrame({"a": [1, 2], "label": ["BENIGN", "DDoS"]}).to_parquet(p)
    df, info = read_any(p)
    assert info["format"] == "parquet"


def test_pipeline_with_npz_no_label_names(tmp_path):
    p = tmp_path / "flows.npz"
    rng = np.random.default_rng(0)
    np.savez(p, data=rng.normal(size=(60, 5)), labels=np.array([0] * 50 + [1] * 10))
    loaded = load_frame(p)
    assert "label" in loaded.df.columns
    assert loaded.format_info["format"] == "npz"
    assert loaded.df["bytes_per_pkt"].notna().all()
