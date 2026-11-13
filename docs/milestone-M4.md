# v0.4 里程碑：多格式输入 · 界面重做 · 架构收敛

日期：2026-11-13 · 状态：完成 · 测试：61 passed / 2 skipped

## 一、多格式输入

新增 `ingest/table.py` + `adapters/shapes.py`：前者按后缀读，后者把"任意形状"压成表。

| 格式 | 说明 |
|---|---|
| csv / tsv / txt | 分隔符嗅探 + 编码回退（已有） |
| pcap / pcapng | tshark 导字段 → 五元组聚合（已有） |
| json / jsonl | 记录式、列式、`{X, y}` 三种都认 |
| parquet | 需要 pyarrow（`uv sync --extra data`） |
| npy | 1D/2D/3D，多维自动展平为 `f_0..f_n` |
| npz | 多数组字典；`X/y`、`data/labels` 自动配对 |
| pkl / pickle | **默认禁用**，`--allow-pickle` 或界面勾选；会写明反序列化风险 |
| xlsx / xls | 需要 openpyxl（同 extra） |

形状识别覆盖：DataFrame、Series、2D/3D ndarray、list[list]、list[dict]、
dict[str, array]、dict{X,y}、torch tensor、多个 DataFrame 拼接。
识别失败时抛 `ShapeError`，信息里带**实际看到的键名/形状**。

标签语义统一：`BENIGN / normal / 0 / False / no` 都算正常样本（`schema.is_benign`）。

实测：`sk.pkl`（sklearn 风格 X/y）、`flows.npz`（data/labels）、`flows.json`、
`flows.parquet`、`flows.pcap`（含旁挂标签）全部跑通。

## 二、界面重做

方向从"仪表盘"改为"研究台账"：纸面背景、衬线标题（Newsreader）、等宽数字（IBM Plex Mono）、
发丝线分节、无卡片网格、无阴影、无渐变。

- 版式：左侧 336px 配置栏（sticky）+ 右侧文档流，最大宽度 1120px
- 首屏：一句主张 + 四步说明 + 次要 CTA；不再用大数字卡片
- 结果：文档头（run/指纹/样本）→ **指标带**（最佳模型 / AUC / F1 / 误报率）→ 风险提示行 →
  01 分数峰值 → 02 模型对比 → 03 泄漏 → 04 消融 → 05 可疑流
- 分数图：柱高＝窗口最高分，底部红色短条＝该窗含超阈值流，两种编码分开
- 表格：等宽数字、右对齐、千分位、最佳行左侧竖线、FP/FN 标红
- 报告 HTML 同步到同一套视觉（自包含，可打印）

## 三、架构收敛

- 新增 `service.execute()`：CLI 与 API 共用同一套编排（原来各写一遍）
- 新增 `payload.build_payload()`：CLI / API / 历史库 / 前端只有一个输出结构
- 新增 `ingest.read_any()` + `adapters.to_frame()`：格式与形状解耦
- `cli.py` 从 240 行降到 ~210 行且只剩"解析参数 / 打印 / 写文件"
- 依赖方向写进 `docs/ARCHITECTURE.md`：ingest 不知道 eval，cli/api 不允许出现算法

## 四、仍未做

- `prepare.py` 三处相似预处理未合并（见 ARCHITECTURE 第七节债务）
- 报告 MD / HTML 字段拼装仍有重复
- 历史库无清理命令
