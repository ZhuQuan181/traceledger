import pandas as pd

from flowlab.schema import normalize_columns, normalize_name


def test_normalize_name():
    assert normalize_name(" Destination Port ") == "destination_port"
    assert normalize_name("Flow-ID") == "flow_id"
    assert normalize_name("Total  Length of Fwd Packets") == "total_length_of_fwd_packets"


def test_normalize_columns_mapping():
    df = pd.DataFrame(columns=["Flow ID", " Destination Port ", "LABEL", "custom_metric"])
    out = normalize_columns(df)
    assert list(out.columns) == ["flow_id", "dst_port", "label", "custom_metric"]


def test_duplicate_after_mapping_dropped():
    df = pd.DataFrame({"dst_port": [1], "Destination Port": [2]})
    out = normalize_columns(df)
    assert list(out.columns) == ["dst_port"]
