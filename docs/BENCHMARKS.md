# 规模基准（合成数据）

机器：本机工作站（CPU 训练，无 GPU）。数据为 `synthetic.py` 生成，9:1 正常/攻击，时间切分 70/30。

| 行数 | 文件 | 读+标准化 | 特征工程 | MLP | IForest | 内存 |
|---|---|---|---|---|---|---|
| 50,000 | 8.4 MB | 0.09s | 0.01s | 未测 | 1.28s | 13 MB |
| 690,000 | 116 MB | 0.91s | 0.17s | **217.07s** | **7.84s** | 175 MB |

690k 两个模型合计 **226s（3.8 分钟）**，AUC：MLP 1.0000 / IForest 0.9659。

## 结论

1. **读入不是瓶颈**：69 万行 0.9 秒，PRD 里"30 秒内识别列"这条有大量余量。
2. **MLP 是瓶颈**：217 秒，占 96%；IForest 只要 8 秒。
3. **PRD 的"3 模型 5 分钟"在 69 万行上不成立**：MLP + AutoEncoder 各约 3.5 分钟，三个模型约 7–8 分钟。
   要么把验收改成 8 分钟，要么默认只跑 IForest + MLP（2 个模型约 4 分钟）。
4. **内存线性**：690k × 21 列约 175 MB，78 列的 CICIDS 预计 400–600 MB，仍在单机可承受范围。

## 复现

```bash
uv run python scripts/bench_scale.py --rows 690000 --models mlp,iforest
```

真实 CICIDS 未跑过：列数 78、含 inf、类别不平衡，预计比上表慢 1.5–2 倍。

## v0.9 读入与历史库

本轮把 CSV 读取从“整文件读入内存再交给 pandas”改为直接从路径流式读取，
并让评分只复制要展示的字段；历史 payload 改为 zlib 压缩存储，SQLite 开启
WAL、忙等待和缓存，并新增状态/数据指纹/模型/实验指纹索引。

本机合成基准（200 份报告，每份含约 60 KB Markdown/HTML 正文）：

| 指标 | 结果 |
|---|---:|
| 原始 payload | 12.27 MB |
| 压缩后 payload | 2.92 MB（23.81%） |
| 数据库主文件 + 受控 WAL | 3.15 MB（WAL 上限 1 MB） |
| 保存 payload p50 | 3.92 ms |
| 历史页查询 p50（40 次） | 2.08 ms |
| 单条实验读取 + 解压 p50 | 0.77 ms |

50,000 行合成流量（IForest）：

| 阶段 | 耗时 | tracemalloc 峰值 |
|---|---:|---:|
| CSV 读取 + 标准化 | 0.10 s | 1.1 MB |
| 特征工程 | 0.03 s | 8.1 MB |
| 最终 DataFrame 常驻内存 | — | 12.9 MB |

压缩率取决于报告内容，不可把 23.81% 当作固定承诺；含大量图表坐标和近重复文本
的报告通常压缩得更好，含随机 ID 的报告压缩率会更高。该基准用于比较存储策略，
不代表第三方数据集或真实 pcap 的性能。

```bash
uv run python scripts/bench_store.py --runs 200 --queries 40
uv run python scripts/bench_scale.py --rows 50000 --models iforest
```
