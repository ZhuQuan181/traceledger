# M1 里程碑报告

日期：2026-11-13 · 状态：**完成**

## 一句话

`uv run flowlab demo` 能从零跑通"合成数据 → 泄漏检查 → 三模型对比 → 可复现报告"，并且有一个能用的本地 Web 界面。

## 验收证据（都是实跑，不是描述）

| 项 | 结果 |
|---|---|
| 单元测试 | `uv run pytest -q` → 30 passed, 1 skipped |
| demo（5000 正常 / 500 攻击） | mlp AUC 1.0000 · iforest 0.9938 · autoencoder 0.9895 |
| 泄漏检测 | 正确报出 `id_leak`(flow_id) 与 `port_leak`(dst_port 3333 占 96.8%) |
| 随机切分 | 正确追加 `time_leak` 警告 |
| pcap 端到端 | 自建 5 包 pcap → 3 条流（含空闲超时切分），tshark 实测通过 |
| Web 界面 | `flowlab serve` → 拖数据/跑实验/看对比/下载报告，截图见 `screens/m1-workbench.png` |
| 预处理器 | 只在训练集 fit，测试集 transform（避免归一化泄漏） |

## 已实现

```
src/flowlab/
├── cli.py             demo / run / score / serve / models
├── synthetic.py       合成流量（故意植入端口泄漏与时间相关性）
├── schema.py          列名标准化（CICFlowMeter 风格 → 内部名）
├── ingest/csv.py      CSV：分隔符嗅探 + 编码回退
├── ingest/pcap.py     pcap：tshark 导字段 → 五元组+超时聚合成流
├── features/leakage.py  三类泄漏规则 + 常量列
├── features/prepare.py  训练/测试分离的预处理
├── models/            base + registry + mlp + iforest + autoencoder
├── eval/              split（时间/随机）+ metrics + runner + table
├── report/markdown.py 报告渲染
└── api/main.py        FastAPI + 静态站点托管
web/                   React + Vite（无 UI 库），设计 token 见 styles.css
```

## 关键设计决定（实现中做的）

1. **端口既当特征又当泄漏源**：默认保留 `dst_port` 作为特征，但泄漏规则会提示"某端口占某类 96.8%"。这样用户能亲眼看到"去掉它指标会掉多少"，比直接删掉更有教育意义。
2. **预处理只在训练集 fit**：`build_matrix_pair()` 是唯一入口，不给"全量 fit"留后门。
3. **切分缺类别时告警而不是静默**：时间切分后训练集没有攻击样本时，`RuntimeWarning` + 监督模型明确报错。
4. **未监督模型分数做分位标定**：IForest 用训练集 p50/p99.5，AutoEncoder 用 p99，避免分数尺度不可比。
5. **pcap 不做线速**：离线解析，超时切分，缺 tshark 时给安装提示而不是自动装。

## 已知限制（下一版处理）

| 限制 | 影响 | 计划 |
|---|---|---|
| 单包流 `duration≈0`，`bytes/s` 会失真到千万级 | 速率类特征在同批数据内不可比 | v0.2 用最小 1ms 或改用包数/字节绝对量 |
| pcap 无标签，只能 `score` 不能 `evaluate` | 无法直接算 AUC | v0.2 支持 sidecar 标签文件 |
| 报告只有 Markdown | 分享需要自己转 | v0.3 单文件 HTML |
| 无实验历史/持久化 | 关掉页面就没了 | v0.3 SQLite 本地库 |
| IForest 在 <50 样本时基本无意义 | 小 pcap 打分不稳 | 文档标注最低样本量 |

## 怎么跑

```bash
cd traceledger
uv sync --extra dev --extra api
uv run flowlab demo                       # 终端跑一次
uv run flowlab demo --report out/r.md     # 顺便出报告
uv run flowlab score x.pcap --top 20      # pcap 无监督排序
uv run flowlab serve                      # Web 界面 http://127.0.0.1:8765
cd web && npm install && npm run build    # 改了前端要重新构建
```
