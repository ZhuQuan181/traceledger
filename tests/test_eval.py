from flowlab.eval.runner import dataset_hash, run_experiment
from flowlab.schema import normalize_columns
from flowlab.synthetic import generate


def _df():
    return normalize_columns(generate(n_normal=600, n_attack=100, seed=21))


def test_mlp_learns_synthetic_data():
    res, warns = run_experiment(_df(), models=["mlp"], split="temporal")
    assert len(res) == 1
    assert res[0].metrics["auc"] and res[0].metrics["auc"] > 0.9
    assert warns


def test_reproducible_same_seed():
    a, _ = run_experiment(_df(), models=["mlp"], seed=7)
    b, _ = run_experiment(_df(), models=["mlp"], seed=7)
    assert a[0].metrics == b[0].metrics
    assert a[0].dataset_hash == b[0].dataset_hash


def test_hash_changes_with_data():
    df = _df()
    h1 = dataset_hash(df)
    df2 = df.copy()
    df2.loc[df2.index[0], "dst_port"] = 9999
    assert dataset_hash(df2) != h1
