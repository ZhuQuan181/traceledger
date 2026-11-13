"""生成最小 pcap（不依赖 scapy），可指定流数量，并输出配套标签 CSV。

用法：
  uv run python scripts/make_test_pcap.py out.pcap --flows 60
  # 生成 out.pcap 与 out.pcap.labels.csv（五元组对齐）
"""
import argparse, csv, ipaddress, random, struct, time


def ip4(s):
    return ipaddress.IPv4Address(s).packed


def frame(src, dst, proto, l4_bytes):
    eth = bytes.fromhex("bb" * 6) + bytes.fromhex("aa" * 6) + struct.pack("!H", 0x0800)
    total = 20 + len(l4_bytes)
    hdr = struct.pack("!BBHHHBBH4s4s", 0x45, 0, total, 0x1234, 0x4000, 64, proto, 0, ip4(src), ip4(dst))
    return eth + hdr + l4_bytes


def udp(sport, dport, n):
    return struct.pack("!HHHH", sport, dport, 8 + n, 0) + b"x" * n


def tcp(sport, dport, n):
    return struct.pack("!HHIIBBHHH", sport, dport, 1, 0, 0x50, 0x18, 8192, 0, 0) + b"x" * n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--flows", type=int, default=3)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--label-out", default=None)
    a = ap.parse_args()

    rng = random.Random(a.seed)
    base = int(time.time()) - 7200
    packets, labels = [], []

    for i in range(a.flows):
        attack = (i % 7 == 3)   # 每 7 条一条攻击，保证时间上均匀分布
        src = f"10.0.0.{rng.randint(1, 60)}"
        dst = f"192.168.1.{rng.randint(1, 60)}"
        sport = rng.randint(20000, 60000)
        dport = 3333 if attack else rng.choice([80, 443, 53, 8080, 22])
        proto = 17 if attack else 6
        n_pkts = rng.randint(25, 120) if attack else rng.randint(1, 8)
        size = 1200 if attack else 400
        t0 = base + i * 5
        for k in range(n_pkts):
            payload = udp(sport, dport, size) if proto == 17 else tcp(sport, dport, size)
            packets.append((t0 + k, 0, frame(src, dst, proto, payload)))
        labels.append({"src_ip": src, "dst_ip": dst, "src_port": sport, "dst_port": dport,
                       "protocol": proto, "label": "DDoS" if attack else "BENIGN"})

    packets.sort(key=lambda p: p[0])
    with open(a.out, "wb") as f:
        f.write(struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1))
        for ts, usec, data in packets:
            f.write(struct.pack("<IIII", ts, usec, len(data), len(data)))
            f.write(data)

    lab_path = a.label_out or (a.out + ".labels.csv")
    with open(lab_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(labels[0]))
        w.writeheader()
        w.writerows(labels)

    print(f"wrote {a.out}: {len(packets)} packets / {len(labels)} flows -> {lab_path}")


if __name__ == "__main__":
    main()
