from flowlab.cli import main


def test_help_exits_zero():
    assert main([]) == 0


def test_demo_runs(capsys):
    code = main(["demo", "--normal", "300", "--attack", "40", "--models", "mlp"])
    out = capsys.readouterr().out
    assert code == 0
    assert "模型对比" in out
    assert "mlp" in out
    assert "PR-AUC" in out


def test_invalid_ablation_returns_clean_error(capsys):
    code = main(
        [
            "demo",
            "--normal",
            "300",
            "--attack",
            "40",
            "--models",
            "mlp",
            "--ablate",
            "label",
            "--no-save",
        ]
    )
    captured = capsys.readouterr()
    assert code == 2
    assert "实验失败" in captured.err
    assert "Traceback" not in captured.err


def test_serve_refuses_public_bind_without_explicit_opt_in(capsys):
    code = main(["serve", "--host", "0.0.0.0"])
    captured = capsys.readouterr()
    assert code == 2
    assert "--allow-remote" in captured.err
