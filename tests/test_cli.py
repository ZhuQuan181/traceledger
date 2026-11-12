from flowlab.cli import main


def test_help_exits_zero():
    assert main([]) == 0


def test_demo_runs(capsys):
    code = main(["demo", "--normal", "300", "--attack", "40", "--models", "mlp"])
    out = capsys.readouterr().out
    assert code == 0
    assert "模型对比" in out
    assert "mlp" in out
