"""生成一个最小的 pcap（不依赖 scapy），用于验证 pcap 解析链路。"""
import struct, time, ipaddress, sys

def ip4(s): return ipaddress.IPv4Address(s).packed

def eth(src_mac, dst_mac, proto=0x0800):
    return dst_mac + src_mac + struct.pack("!H", proto)

def ipv4(src, dst, proto, payload_len):
    total = 20 + payload_len
    hdr = struct.pack("!BBHHHBBH4s4s", 0x45, 0, total, 0x1234, 0x4000, 64, proto, 0, ip4(src), ip4(dst))
    return hdr

def udp(sport, dport, payload):
    return struct.pack("!HHHH", sport, dport, 8 + len(payload), 0) + payload

def tcp(sport, dport, payload):
    return struct.pack("!HHIIBBHHH", sport, dport, 1, 0, 0x50, 0x18, 8192, 0, 0) + payload

MAC_A = bytes.fromhex("aa" * 6); MAC_B = bytes.fromhex("bb" * 6)

def frame(src, dst, proto, l4, payload=b"x" * 40):
    seg = l4(payload)
    return eth(MAC_A, MAC_B) + ipv4(src, dst, proto, len(seg)) + seg

packets = []
base = int(time.time()) - 3600
# 流 1：三条 TCP 包，同一五元组
for i in range(3):
    packets.append((base + i, 0, frame("10.0.0.1", "10.0.0.2", 6, lambda p: tcp(40000, 80, p))))
# 流 2：UDP DNS
packets.append((base + 5, 0, frame("10.0.0.3", "10.0.0.4", 17, lambda p: udp(5555, 53, p))))
# 流 3：同五元组但隔了 1 小时（超时应拆成新流）
packets.append((base + 3600, 0, frame("10.0.0.1", "10.0.0.2", 6, lambda p: tcp(40000, 80, p))))

out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/test.pcap"
with open(out, "wb") as f:
    f.write(struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1))
    for ts, usec, data in packets:
        f.write(struct.pack("<IIII", ts, usec, len(data), len(data)))
        f.write(data)
print("wrote", out, len(packets), "packets")
