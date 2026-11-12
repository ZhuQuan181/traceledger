from flowlab.synthetic import generate


def test_shape_and_labels():
    df = generate(n_normal=800, n_attack=120, seed=42)
    assert len(df) == 920
    assert set(df["Label"].unique()) == {"BENIGN", "DDoS"}
    assert (df["Label"] == "DDoS").sum() == 120


def test_timestamp_monotonic():
    df = generate(n_normal=300, n_attack=50, seed=1)
    ts = __import__("pandas").to_datetime(df["Timestamp"])
    assert ts.is_monotonic_increasing


def test_port_leak_is_planted():
    df = generate(n_normal=2000, n_attack=500, seed=7)
    leak = (df.loc[df.Label == "DDoS", "Destination Port"] == 3333).mean()
    assert 0.93 < leak <= 1.0


def test_deterministic():
    a = generate(n_normal=100, n_attack=10, seed=3)
    b = generate(n_normal=100, n_attack=10, seed=3)
    assert a.equals(b)
