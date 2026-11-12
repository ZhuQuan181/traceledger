# 06 · 验证实验（PoL Probe）

> 方法：`pol-probe`（Proof of Life：用最小成本拿最扎心的真相，不是做 MVP）

## Hypothesis

> 如果给做流量异常检测的研究者一个"**CICIDS2017 一键复现**"的工具（能自动识别字段、提示泄漏、跑 3 个基线出对比表），那么至少 **1/5 的试用者会主动要求接入自己的数据集**——这证明他们真正缺的是"实验管线"，而不只是"又一个模型"。

## Risk Being Eliminated

**最大风险不是技术，是需求真伪**：研究者可能只是想要更强的模型，而不是更顺的流程。
如果连"能不能加我的数据集"都没人问，说明痛点是伪的，整个产品不成立。

## Prototype Type

**能力型探针（Capability Probe）**，不是 UI 原型：

- 一个 Python 包 + 一本 README + 一段 90 秒录屏
- 能跑通：`pip install -e . && flowlab demo cicids --csv xxx.csv`
- 输出：终端里的对比表 + 一个 HTML 报告
- **不做 Web UI、不做 Docker、不做插件系统**

## Target Users / Audience

| 渠道 | 规模预期 | 为什么是这里 |
|---|---|---|
| V2EX「信息安全」节点 | 20–50 次浏览 | 中文开发者聚集，安全从业者多 |
| Reddit r/netsec / r/MachineLearning | 50–200 次浏览 | 英文研究者密度最高 |
| 学校/实验室群（3 个） | 10–30 人 | 最接近 Persona A |
| GitHub（发一个 repo，README 写清定位） | 长期 | 可被搜索到 |

## Success Criteria（Harsh Truth）

| 信号 | 阈值 | 含义 |
|---|---|---|
| **主动问"能不能加我的数据集/模型"** | **≥ 3 人** | ✅ 需求成立，继续做 M1 |
| star / fork | ≥ 20 / ≥ 3 | ✅ 有一定传播 |
| 试用后能跑出结果 | ≥ 5 人 | ✅ 上手门槛可接受 |
| 只有 star、没人提问 | — | ⚠️ 是"有趣"不是"有用"，重新定位 |
| 有人问"能不能实时抓包/拦截" | — | ❌ 说明被当成 IDS，定位失败 |

**判定时间**：发布后 7 天统计。

## Tools / Stack

- Python 3.11 + pandas + scikit-learn + PyTorch（只用一个 AutoEncoder）
- CLI：`typer` 或 `argparse`
- 报告：Jinja2 → 单文件 HTML
- 数据集：脚本下载 + sha256 校验，**不打包数据**

## Timeline

| 天 | 产出 |
|---|---|
| D1 | 数据加载 + 字段识别 + 泄漏检查（CICIDS 已知问题清单） |
| D2 | 3 个模型 + 切分 + 指标 + HTML 报告 |
| D3 | README + 90 秒录屏 + 发 4 个渠道 + 记录反馈表 |

## Disposal Plan

- 探针代码保留在 `probes/` 目录，**不进入正式产品代码库**；
- 拿到信号后，把"字段识别 + 泄漏检查 + 评估"三块重写进 v0.1；
- 没拿到信号：归档，写一份"为什么不成立"的复盘（这份复盘比代码值钱）。

## Owner / Status

- Owner：zq
- Status：**未开始**
- 前置条件：CICIDS2017 数据下载（约 5 GB，需要能访问 Kaggle 或镜像）
