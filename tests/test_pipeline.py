from flowlab.cli import main
from flowlab.pipeline import load_frame
from flowlab.synthetic import generate


def test_csv_without_label_uses_sidecar(tmp_path):
    df = generate(n_normal=400, n_attack=80, seed=8)
    flows = tmp_path / "flows.csv"
    df.drop(columns=["Label"]).to_csv(flows, index=False)
    labels = tmp_path / "flows_labels.csv"
    df[["Label"]].rename(columns={"Label": "label"}).to_csv(labels, index=False)

    loaded = load_frame(flows, labels)
    assert "label" in loaded.df.columns
    assert loaded.label_info["mode"] == "row_order"
    assert "bytes_per_pkt" in loaded.df.columns


def test_cli_run_with_labels_flag(tmp_path, capsys):
    df = generate(n_normal=400, n_attack=80, seed=12)
    flows = tmp_path / "flows.csv"
    df.drop(columns=["Label"]).to_csv(flows, index=False)
    labels = tmp_path / "lab.csv"
    df["Label"].rename("label").to_csv(labels, index=False)

    code = main(["run", str(flows), "--labels", str(labels), "--models", "mlp"])
    out = capsys.readouterr().out
    assert code == 0
    assert "模型对比" in out
