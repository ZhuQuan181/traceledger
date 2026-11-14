import json

from flowlab.cli import build_parser, main


def test_all_argparse_help_strings_are_valid():
    seen: set[int] = set()

    def visit(parser):
        if id(parser) in seen:
            return
        seen.add(id(parser))
        formatter = parser._get_formatter()
        for action in parser._actions:
            if action.help:
                formatter._expand_help(action)
            choices = getattr(action, "choices", None)
            if isinstance(choices, dict):
                for child in choices.values():
                    visit(child)

    visit(build_parser())


def test_help_exits_zero():
    assert main([]) == 0


def test_demo_runs(capsys):
    code = main(["demo", "--normal", "300", "--attack", "40", "--models", "mlp"])
    out = capsys.readouterr().out
    assert code == 0
    assert "模型对比" in out
    assert "mlp" in out
    assert "PR-AUC" in out


def test_demo_supports_target_fpr_threshold(capsys):
    code = main(
        [
            "demo",
            "--normal",
            "300",
            "--attack",
            "40",
            "--models",
            "mlp",
            "--threshold-mode",
            "fpr",
            "--target-fpr",
            "0.05",
            "--json",
            "--no-save",
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    assert '"threshold_source": "validation_fpr"' in captured.out
    assert '"threshold_target_fpr": 0.05' in captured.out


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


def test_compare_json_and_markdown_use_shared_output(monkeypatch, capsys, tmp_path):
    comparison = {
        "status": "comparable",
        "comparable": True,
        "warnings": [],
        "runs": [],
        "markdown": "# 对比\n\n| 实验 |\n|---|\n| a |",
    }
    monkeypatch.setattr("flowlab.compare.load_comparison", lambda ids: comparison)
    report = tmp_path / "compare.md"
    code = main(["compare", "a", "b", "--json", "--md", str(report)])
    captured = capsys.readouterr()
    assert code == 0
    assert json.loads(captured.out)["status"] == "comparable"
    assert report.read_text() == comparison["markdown"]
