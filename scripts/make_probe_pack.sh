#!/usr/bin/env bash
# 生成一份可以直接发出去试用的物料包（PoL 探针用）。
set -euo pipefail
cd "$(dirname "$0")/.."

OUT=${1:-dist/probe-pack}
rm -rf "$OUT"; mkdir -p "$OUT"

uv run flowlab sample --rows 3000 --out "$OUT/sample_flows.csv" >/dev/null
uv run flowlab demo --normal 4000 --attack 400 --html "$OUT/demo-report.html" --no-save >/dev/null

cat > "$OUT/试用说明.md" <<'TXT'
# FlowLab 试用包（15 分钟）

## 1. 先看效果（2 分钟）
双击 `demo-report.html`。这是一次合成数据的实验报告：
- 顶部是 AUC / F1 / 误报率
- 右栏是数据泄漏检查（本例故意留了一个端口痕迹）
- 底部有复现命令

## 2. 换成你的数据（5 分钟）
```bash
uv run flowlab run sample_flows.csv --split temporal --html out/my.html
```
`sample_flows.csv` 是样例格式：一列 `Label`，其余是特征列。
你的数据只要有一列标签（BENIGN / 攻击类名），其他列名不必一致，系统会自己映射。

先用体检脚本看一眼能不能用：
```bash
uv run python scripts/check_dataset.py 你的文件.csv
```

## 3. 告诉我三件事（3 分钟）
1. 你的数据是什么格式？（CSV / pcap / Zeek / 自己处理的 pkl / npz）
2. 跑出来跟你自己脚本的数字差多少？差在哪？
3. 如果这个工具明天消失，你会用什么替代？

把回答发给我即可，不需要填表。
TXT

cat > "$OUT/README.txt" <<'TXT'
FlowLab 试用包
- sample_flows.csv   3000 行合成流量（10% 攻击），用于验证流程
- demo-report.html   一次完整实验的 HTML 报告，可直接打开
- 试用说明.md        15 分钟的使用路径与三个问题

数据不出本机；报告是自包含 HTML，可以直接转发。
TXT

echo "物料包已生成：$OUT"
ls -lh "$OUT"
