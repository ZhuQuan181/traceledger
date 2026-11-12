import pandas as pd
import pytest

from flowlab.ingest.csv import read_csv


def test_read_semicolon_with_bom(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("\ufeffFlow ID;Destination Port;Label\na;3333;DDoS\n", encoding="utf-8")
    df = read_csv(p)
    assert df.shape == (1, 3)
    assert "dst_port" in df.columns


def test_read_comma(tmp_path):
    p = tmp_path / "y.csv"
    p.write_text("Flow ID,Destination Port,Label\na,80,BENIGN\n", encoding="utf-8")
    df = read_csv(p)
    assert df.iloc[0]["dst_port"] == 80


def test_missing_file():
    with pytest.raises(FileNotFoundError):
        read_csv("/nonexistent/nope.csv")
