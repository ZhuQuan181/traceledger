import pandas as pd

from flowlab.engineer import add_engineered_features


def _frame(rows):
    return pd.DataFrame(rows)


def test_single_packet_rate_is_bounded():
    df = _frame(
        [
            {
                "duration_us": 0,
                "fwd_packets": 1,
                "bwd_packets": 0,
                "fwd_bytes": 1000,
                "bwd_bytes": 0,
            },
        ]
    )
    out = add_engineered_features(df)
    # 1ms 兜底：1000 B / 0.001 s = 1e6，而不是 inf 或 1e11
    assert out.loc[0, "bytes_per_s"] == 1_000_000
    assert out.loc[0, "duration_ms_effective"] == 1.0
    assert out.loc[0, "is_single_packet"] == 1


def test_bytes_per_pkt_and_raw_preserved():
    df = _frame(
        [
            {
                "duration_us": 2_000,
                "fwd_packets": 4,
                "bwd_packets": 4,
                "fwd_bytes": 400,
                "bwd_bytes": 800,
                "bytes_per_s": 999999,
                "packets_per_s": 12345,
            },
        ]
    )
    out = add_engineered_features(df)
    assert out.loc[0, "bytes_per_pkt"] == 150.0
    assert out.loc[0, "bytes_per_s"] == 600_000  # 1200 B / 2 ms
    assert out.loc[0, "raw_bytes_per_s"] == 999_999  # 原始值保留
    assert out.loc[0, "is_single_packet"] == 0


def test_missing_columns_do_not_crash():
    out = add_engineered_features(pd.DataFrame({"duration_us": [1000]}))
    assert "bytes_per_s" not in out.columns
    assert "bytes_per_pkt" not in out.columns


def test_existing_rates_are_not_zeroed_without_component_columns():
    df = _frame([{"bytes_per_s": 1234.5, "packets_per_s": 12.5, "duration_ms": 10}])
    out = add_engineered_features(df)
    assert out.loc[0, "bytes_per_s"] == 1234.5
    assert out.loc[0, "packets_per_s"] == 12.5
    assert out.loc[0, "raw_bytes_per_s"] == 1234.5
    assert out.loc[0, "duration_ms"] == 10
