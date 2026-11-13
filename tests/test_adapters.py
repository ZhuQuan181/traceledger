import numpy as np
import pandas as pd
import pytest

from flowlab.adapters import ShapeError, to_frame


def test_dataframe_passthrough():
    df = pd.DataFrame({"a": [1, 2], "label": ["BENIGN", "ATTACK"]})
    out, info = to_frame(df)
    assert list(out.columns) == ["a", "label"]
    assert info["shape"] == "DataFrame"


def test_dict_of_columns():
    out, info = to_frame({"a": [1, 2, 3], "b": [4, 5, 6], "label": ["B", "B", "A"]})
    assert out.shape == (3, 3)
    assert "列式" in info["shape"]


def test_sklearn_style_xy():
    out, info = to_frame({"X": np.arange(12).reshape(4, 3), "y": [0, 1, 0, 1]})
    assert out.shape == (4, 4)
    assert list(out.columns)[:3] == ["f_0", "f_1", "f_2"]
    assert out["label"].tolist() == [0, 1, 0, 1]
    assert "X/y" in info["note"]


def test_list_of_dicts():
    out, _ = to_frame([{"a": 1, "b": 2}, {"a": 3, "b": 4}])
    assert out.shape == (2, 2)


def test_2d_ndarray():
    out, info = to_frame(np.zeros((5, 4)))
    assert out.shape == (5, 4)
    assert list(out.columns) == ["f_0", "f_1", "f_2", "f_3"]


def test_list_of_lists():
    out, _ = to_frame([[1, 2], [3, 4], [5, 6]])
    assert out.shape == (3, 2)


def test_3d_flattened():
    out, info = to_frame(np.zeros((2, 3, 4)))
    assert out.shape == (2, 12)
    assert "展平" in info["note"]


def test_series():
    out, _ = to_frame(pd.Series([1, 2, 3], name="v"))
    assert out.shape == (3, 1)


def test_label_with_npz_style_dict():
    out, _ = to_frame({"data": np.ones((3, 2)), "labels": ["BENIGN", "DDoS", "BENIGN"]})
    assert out.shape == (3, 3)
    assert set(out["label"]) == {"BENIGN", "DDoS"}


def test_unknown_dict_raises_with_keys():
    with pytest.raises(ShapeError) as exc:
        to_frame({"foo": "bar", "baz": 1})
    assert "foo" in str(exc.value)
