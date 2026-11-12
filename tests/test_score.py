from flowlab.cli import main
from flowlab.synthetic import generate


def test_score_csv(tmp_path, capsys):
    p = tmp_path / "flows.csv"
    generate(n_normal=300, n_attack=60, seed=4).to_csv(p, index=False)
    code = main(["score", str(p), "--model", "iforest", "--top", "5"])
    out = capsys.readouterr().out
    assert code == 0
    assert "可疑流" in out
    assert out.count("\n") >= 5
