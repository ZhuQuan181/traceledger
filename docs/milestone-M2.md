# M2（v0.2）里程碑报告

日期：2026-11-13 · 状态：**完成**

## 这一版解决什么

M1 有两个会在真实使用中立刻暴露的硬伤：

1. **单包流速率失真**：`duration=0` 时 `bytes/s` 直接爆到 1e8 量级，同批数据里速率特征不可比。
2. **pcap 不能评估**：pcap 没有标签，只能打分，算不出 AUC——而研究者要的正是"这套模型在这段流量上到底行不行"。

v0.2 把这两件事补上，并让 CLI 与 Web 走**同一条**加载管线。

## 验收证据

| 项 | 结果 |
|---|---|
| 单元测试 | `uv run pytest -q` → **39 passed, 1 skipped** |
| 速率兜底 | 单包 1000B 流：`bytes_per_s` = 1e6（原为 1e11 级），并新增 `bytes_per_pkt` |
| 旁挂标签（五元组） | 120 条 pcap 流 → 120/120 对齐，11→18 条攻击 |
| 旁挂标签（flow_id / 行序） | 三种模式均有单测覆盖，错位时明确报错 |
| pcap 端到端评估 | `flowlab run big.pcap` → mlp AUC 1.0000 · iforest 0.8774 · autoencoder 0.9194 |
| 自动发现标签 | `big.pcap.labels.csv` 与 pcap 同名时无需 `--labels` |
| Web 上传 | 选 pcap + 标签 CSV → 摘要显示「标签对齐 src_ip+dst_ip+... (120/120) · 速率兜底 1 ms」 |
| 报告 | 新增「数据来源与特征」章节，写明对齐方式、标签文件、派生特征 |

## 改动清单

```
src/flowlab/engineer.py   速率兜底 + bytes_per_pkt + is_single_packet + 原始值保留
src/flowlab/labels.py     flow_id / 五元组 / 行序 三种对齐 + sidecar 自动发现
src/flowlab/pipeline.py   load_frame()：唯一入口（CSV、pcap、标签、特征工程）
src/flowlab/cli.py        run/score 支持 --labels；报告带标签与工程信息
src/flowlab/api/main.py   /api/upload 支持 labels 文件；payload 暴露 labels/engineering
src/flowlab/report/*      「数据来源与特征」+「测试集攻击样本」
web/src/*                 上传模式加标签框；摘要显示对齐方式与兜底参数
```

## 设计决定

1. **速率兜底 1ms 而不是丢掉单包流**：单包流恰恰是扫描、探测的主要形态，丢掉会漏掉最有价值的样本。用 `bytes_per_pkt` 保留绝对量，让模型自己学。
2. **原始速率不覆盖而是另存**：`raw_bytes_per_s` 保留下来，报告里可以对照"修正前后差多少"。
3. **标签按五元组聚合时"有一条攻击就算攻击"**：保守偏攻击，避免把攻击流误标成正常而虚高指标。
4. **管线唯一入口**：CLI 与 API 都走 `load_frame()`，杜绝"命令行能跑、网页跑出来不一样"。

## 已知限制

| 限制 | 说明 |
|---|---|
| 五元组标签会合并同元组的多条流 | 若同一元组内有正常/攻击混合，会整体标为攻击（保守） |
| 标签文件不含时间 | 同元组、不同时段的流无法区分，需要 flow_id 才能精确对齐 |
| 单包流 `bytes_per_s` 仍按 1ms 算 | 是约定而非实测值，报告里已注明 |
| pcap 解析仍是离线单文件 | 大文件（>1GB）建议先 `editcap` 切片 |

## 怎么验证

```bash
uv run pytest -q
uv run python scripts/make_test_pcap.py /tmp/big.pcap --flows 120
uv run flowlab run /tmp/big.pcap --report out/pcap-report.md   # 自动发现 .labels.csv
uv run flowlab score /tmp/big.pcap --model iforest --top 20
uv run flowlab serve   # 网页里选 pcap + 标签 CSV
```
