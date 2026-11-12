import numpy as np

from flowlab.features.prepare import build_matrix, build_matrix_pair
from flowlab.schema import normalize_columns
from flowlab.synthetic import generate


def _df():
    return normalize_columns(generate(n_normal=300, n_attack=60, seed=5))


def test_binary_labels_and_no_meta_columns():
    p = build_matrix(_df())
    assert set(np.unique(p.y)) == {0, 1}
    assert p.y.sum() == 60
    assert p.X.shape[0] == 360
    assert all("flow_id" not in n for n in p.feature_names)


def test_pair_uses_train_statistics():
    df = _df()
    tr, te = df.iloc[:250], df.iloc[250:]
    a, b = build_matrix_pair(tr, te)
    assert a.X.shape[0] == 250
    assert b.X.shape[0] == len(te)
    assert a.feature_names == b.feature_names
