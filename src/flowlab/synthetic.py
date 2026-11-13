"""合成流量数据生成器（不依赖任何真实数据集）。

生成 CICFlowMeter 风格的假数据，并且**故意**保留两类典型数据泄漏：
1. 攻击流的目的端口固定为 3333（端口泄漏）；
2. 时间戳可用于未来信息泄漏（需配合随机切分才会触发）。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

ATTACK_PORT = 3333
NORMAL_PORTS = [80, 443, 8080, 53, 22, 25, 110, 3306, 5432, 6379]


def generate(
    n_normal: int = 5000,
    n_attack: int = 500,
    seed: int = 42,
    attack_label: str = "DDoS",
    leakage_only: bool = False,
) -> pd.DataFrame:
    """生成带标签的合成流量，返回未标准化的原始列名（模拟 CICFlowMeter 导出）。

    leakage_only=True：攻击流与正常流在**所有行为特征上同分布**，只有目的端口不同。
    这是用来演示"端口泄漏"的极端构造 —— 去掉端口后模型应当掉到随机水平。
    """
    rng = np.random.default_rng(seed)
    n = n_normal + n_attack

    is_attack = np.zeros(n, dtype=bool)
    is_attack[n_normal:] = True

    # 时长（微秒）：正常流长尾；攻击流短（leakage_only 时与正常同分布）
    benign_dur = np.clip(rng.lognormal(13.0, 1.4, n), 1_000, 3.6e9)
    duration = (np.clip(rng.lognormal(13.0, 1.4, n), 1_000, 3.6e9) if leakage_only
                else np.where(is_attack, rng.integers(1_000, 120_000, n), benign_dur)).astype(np.int64)

    # 包数 / 字节数
    if leakage_only:
        fwd_packets = rng.integers(1, 60, n)
        bwd_packets = rng.integers(0, 80, n)
        fwd_bytes = (fwd_packets * 400).astype(np.int64)
        bwd_bytes = (bwd_packets * 800).astype(np.int64)
    else:
        fwd_packets = np.where(is_attack, rng.integers(20, 400, n), rng.integers(1, 60, n))
        bwd_packets = np.where(is_attack, rng.integers(0, 20, n), rng.integers(0, 80, n))
        fwd_bytes = (fwd_packets * np.where(is_attack, 1200, 400)).astype(np.int64)
        bwd_bytes = (bwd_packets * np.where(is_attack, 400, 800)).astype(np.int64)

    total_bytes = (fwd_bytes + bwd_bytes).astype(float)
    total_packets = (fwd_packets + bwd_packets).astype(float)
    dur_s = np.maximum(duration / 1e6, 1e-6)

    # 目的端口：正常流随机；攻击流 96% 打 3333（故意留 4% 噪声）
    dst_port = rng.choice(NORMAL_PORTS, n).astype(np.int64)
    dst_port = np.where(is_attack, ATTACK_PORT, dst_port)
    # 4% 攻击流换端口，避免"完美可分"
    flip = is_attack & (rng.random(n) < 0.04)
    dst_port = np.where(flip, rng.choice(NORMAL_PORTS, n), dst_port)

    protocol = (rng.choice([6, 6, 6, 17], n) if leakage_only
                else np.where(is_attack, 17, rng.choice([6, 6, 6, 17], n)))

    ts = rng.uniform(1_700_000_000, 1_700_086_400, n)  # 每行独立采样，避免标签与时间相关

    df = pd.DataFrame(
        {
            "Flow ID": [f"2026-11-11 10:00:{i % 60:02d} 10.0.0.{i % 250}.1-10.0.0.{(i * 7) % 250}.9-{int(dst_port[i])}-6" for i in range(n)],
            "Source IP": [f"10.0.0.{int(x)}" for x in rng.integers(0, 250, n)],
            "Destination IP": [f"192.168.1.{int(x)}" for x in rng.integers(0, 250, n)],
            "Source Port": rng.integers(10000, 65000, n),
            "Destination Port": dst_port,
            "Protocol": protocol,
            "Timestamp": pd.to_datetime(ts, unit="s").strftime("%Y-%m-%d %H:%M:%S"),
            "Flow Duration": duration,
            "Total Fwd Packets": fwd_packets,
            "Total Backward Packets": bwd_packets,
            "Total Length of Fwd Packets": fwd_bytes,
            "Total Length of Bwd Packets": bwd_bytes,
            "Flow Bytes/s": total_bytes / dur_s,
            "Flow Packets/s": total_packets / dur_s,
            "Label": np.where(is_attack, attack_label, "BENIGN"),
        }
    )
    # 按时间排序：保证 Timestamp 单调，同时让攻击/正常在时间轴上混合
    df = df.assign(_ts=ts).sort_values("_ts", kind="mergesort").drop(columns="_ts")
    return df.reset_index(drop=True)


def write_csv(path: str, **kwargs) -> str:
    df = generate(**kwargs)
    df.to_csv(path, index=False)
    return path
