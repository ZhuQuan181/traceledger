# FlowLab · 流量异常检测工作台

> 工作名（占位，可改）。一句话：**把网络流量异常检测的研究模型，变成能跑、能复现、能解释的系统。**

- 创建：2026-11-11
- 状态：**v0.4**（2026-11-13：多格式输入 + 界面重做 + 架构收敛；61 个测试）
- 负责人：zq（实现由 Hermes 完成）
- 文档语言：中文；代码与接口用英文

## 快速开始

```bash
cd /mnt/data/flowlab
uv sync --extra dev --extra api

uv run flowlab demo                        # 合成数据跑一次
uv run flowlab demo --report out/report.md # 同时生成报告
uv run flowlab run my.csv --split temporal # 跑自己的 CSV（需要 label 列）
uv run flowlab run cap.pcap                # pcap + 同名 cap.pcap.labels.csv 自动对齐
uv run flowlab run cap.pcap --labels l.csv # 或显式指定标签文件
uv run flowlab run feats.npz              # npy / npz / parquet / json / jsonl / pkl / xlsx
uv run flowlab run model_input.pkl --allow-pickle   # pickle 需显式许可
uv run flowlab score cap.pcap --top 20     # pcap 只打分（无标签）
uv run flowlab serve                       # Web 界面 127.0.0.1:8765
cd web && npm install && npm run build     # 改前端后重新构建
```

pcap 需要本机 `tshark`（Ubuntu: `sudo apt install tshark`）。

## 命令

| 命令 | 作用 |
|---|---|
| `flowlab demo` | 合成数据跑全流程（默认 5000 正常 + 500 攻击） |
| `flowlab run FILE` | 对 CSV/pcap 跑实验，要求有 `label` 列 |
| `flowlab score FILE` | 无标签数据的无监督排序，输出最可疑的流 |
| `flowlab run FILE --labels L` | pcap 旁挂标签（flow_id / 五元组 / 行序三种对齐） |
| `flowlab serve` | 本地 Web 工作台 |
| `flowlab formats` | 列出支持的数据格式 |
| `flowlab models` | 列出已注册模型 |
| `flowlab history` | 最近的实验（本地 SQLite，`~/.flowlab/flowlab.db`） |
| `flowlab show ID` | 回看某次实验，可导出 MD / HTML |
| `flowlab compare ID1 ID2` | 跨实验对比最佳指标 |

通用参数：`--models mlp,iforest`、`--split temporal|random`、`--seed`、`--threshold`、
`--ablate COLUMN`（去掉某列重跑，量化它撑了多少指标）、`--html PATH`（单文件报告）、
`--report PATH`（Markdown）、`--json`、`--no-save`。

## 架构

```
CSV / pcap
   ↓ ingest        列名标准化、分隔符/编码嗅探、五元组聚合
   ↓ features      泄漏检测 → 训练/测试分离的预处理
   ↓ models        registry 插件（mlp / iforest / autoencoder / 你的）
   ↓ eval          时间/随机切分 → AUC·F1·FPR·混淆矩阵
   ↓ report/api    Markdown / 单文件 HTML 报告 + FastAPI + React 界面
  ↓ store         SQLite 实验历史（本地，不上传）
```

加载管线（CLI 与 API 共用）：

```
读文件 → 列名标准化 → 旁挂标签（可选）→ 特征工程（速率兜底 1ms、bytes_per_pkt）
```

新增模型只要一个文件，放进 `src/flowlab/models/` 就会被自动发现：

```python
from flowlab.models.base import Detector
from flowlab.models.registry import register

@register("your_model")
class YourDetector(Detector):
    kind = "supervised"
    def fit(self, X, y): ...
    def score(self, X): ...   # 返回 [0,1]，越大越可疑
```

## 这个项目要解决什么

做流量异常检测研究的人，80% 的时间不在想模型，而在：找数据集 → 写预处理 → 对齐特征 → 复现别人的 F1。
做安全运维的人，拿到的是规则告警或一个分数，不知道"为什么可疑、该干什么"。

两边中间缺一层：**能把模型装进系统、把结果讲成人话、把实验做成可复现的那层。**

## 文档导航

| 文件 | 用途 | 对应 PM 方法 |
|---|---|---|
| `01-问题陈述.md` | 问题是什么、为谁、证据 | problem-statement |
| `02-用户画像与场景.md` | 三类用户、JTBD、现有替代方案 | proto-persona + jobs-to-be-done |
| `03-竞品快照.md` | 13 个相关项目逐条对比 + 空白判断 | competitive-research-snapshot |
| `04-PRD.md` | 目标、非目标、用户故事、验收标准 | prd-development |
| `05-MVP范围与里程碑.md` | 做什么/不做什么、6 周排期 | roadmap + user-story-splitting |
| `06-验证实验-PoL-Probe.md` | 3 天验证"有没有人真的痛" | pol-probe |
| `07-技术架构与数据流.md` | 系统怎么搭（补"没做过系统"的短板） | 工程文档 |
| `08-指标与成功标准.md` | 怎么算成功、怎么埋点 | derisk-measurement-advisor |
| `09-开放问题.md` | 还没定的决策，逐条待决 | — |

## 已确认的事实（不是假设）

- 现有开源项目在**采集层**（Zeek/Suricata/nDPI/ntopng）和**算法层**（Kitsune/Slips/论文代码）都很成熟；
- 但用 `ml nids platform` 搜索 GitHub，**最高只有 1 星**——"模型 → 系统"这层几乎无人做；
- 我们手上已有：SPIN-OW 的模型与基线实验（ISCX-APP / ISCX-SERVICE / ISCX-TOR / USTC-2016）、22 GB 显存工作站、单文件打包与本地部署能力。

## 已定决策（2026-11-11）

| 决策 | 结果 |
|---|---|
| 首要用户 | **安全方向研究者**（Persona A）；教师/中小企业为次要 |
| 许可证 | **Apache-2.0** |
| SPIN-OW 权重 | **不内置**，只提供接入模板 |
| 输入格式 | **CSV + pcap 都要**（pcap 用 tshark/nDPI 离线解析） |
| 项目执行 | **由 AI（Hermes）全程实现**，用户只做决策与验收 |

## 三条原则

1. **不替代 Zeek/Suricata，配合它们**（把它们的输出当输入）；
2. **先做"可复现"，再做"实时"**（研究者的痛点在复现，不在吞吐）；
3. **每个功能都要能回答"哪个用户会为它多花 30 分钟"**，否则砍掉。
