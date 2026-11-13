# 架构说明

> 目标：读这份文件的人能在 10 分钟内知道"新代码该放哪、能不能依赖别人、边界在哪"。

## 一、分层

```
                 ┌──────────────────────────────┐
   交付层         │ cli.py            api/main.py│   只做：参数解析、HTTP、打印、写文件
                 └───────────────┬──────────────┘
                                 │ 调 service.execute()
                 ┌───────────────▼──────────────┐
   编排层         │ service.py                   │   一次实验 = 跑模型 + 消融 + 组装 payload
                 │ payload.py  store.py         │   输出结构 / 历史库
                 └───────────────┬──────────────┘
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
┌───────▼───────┐      ┌─────────▼────────┐     ┌─────────▼────────┐
│ eval/         │      │ models/          │     │ report/          │
│ split/metrics │      │ registry + 插件   │     │ markdown / html  │
│ runner/ablation│     └─────────┬────────┘     └──────────────────┘
└───────┬───────┘                │
        │              ┌─────────▼────────┐
        └──────────────► features/        │  泄漏检测 + 预处理（只在训练集 fit）
                       └─────────┬────────┘
                                 │
                       ┌─────────▼────────┐
                       │ pipeline.py      │  load_frame()：唯一加载入口
                       └─────────┬────────┘
                       ┌─────────▼────────┐
                       │ ingest/          │  read_any()：按后缀分发
                       │ adapters/shapes  │  任意形状 → DataFrame
                       └──────────────────┘
```

**依赖方向只能向下**。`ingest` 不知道 `eval` 存在，`models` 不知道 `report` 存在；
`cli.py` 与 `api/main.py` 不允许出现模型训练、特征构造、指标计算的代码。

## 二、模块职责

| 模块 | 负责 | 不负责 |
|---|---|---|
| `ingest/csv.py` | 分隔符嗅探、编码回退 | 列名语义（交给 schema） |
| `ingest/pcap.py` | tshark 导字段、五元组聚合成流 | 标签（交给 labels） |
| `ingest/table.py` | json/jsonl/parquet/npy/npz/pkl/excel 读取 | 形状识别（交给 adapters） |
| `adapters/shapes.py` | 任意结构 → DataFrame + 说明 | 判断数据是否合理 |
| `labels.py` | 旁挂标签对齐（flow_id / 五元组 / 行序） | 标签语义解释 |
| `schema.py` | 列名标准化、BENIGN 同义词 | 特征选择 |
| `engineer.py` | 速率兜底、派生特征 | 模型选择 |
| `pipeline.py` | 把上面几步串成 `load_frame()` | 训练、评估 |
| `features/leakage.py` | 四类泄漏规则 | 自动删列（只提示，不替用户决定） |
| `features/prepare.py` | 训练/测试分离的预处理 | 切分策略 |
| `eval/split.py` | 时间/随机切分 + 类别覆盖告警 | 评估指标 |
| `eval/runner.py` | 一次实验的循环（多模型共用矩阵） | 报告格式 |
| `eval/ablation.py` | 去掉一列重跑并对比 | 决定该列该不该留 |
| `models/` | 插件注册与三个内置模型 | 特征工程 |
| `report/` | Markdown / 单文件 HTML | 实验逻辑 |
| `payload.py` | 统一输出结构（CLI/API/存储共用） | 计算 |
| `store.py` | SQLite 历史 | 报告内容 |
| `service.py` | 编排：实验 + 消融 + payload | 任何具体算法 |

## 三、三个契约

### 1. `LoadedFrame`（pipeline 的输出）

```python
@dataclass
class LoadedFrame:
    df: pd.DataFrame        # 列名已标准化，已加派生特征
    source: str             # "flows.csv（csv）"
    label_info: dict        # {"mode": "embedded|flow_id|五元组|row_order", "labelled": n}
    engineering: dict       # {"min_duration_ms": 1.0, "derived": [...]}
    format_info: dict       # {"format": "npz", "shape": "...", "pickle_object": "..."}
```

### 2. `EvalResult`（runner 的输出）

字段固定：`model / kind / metrics / confusion / duration_s / params / split /
dataset_hash / n_train / n_test / threshold / seed / attack_train / top_flows / score_curve`。

`score_curve` 是 `[{p: 窗口最高分, h: 超阈值比例}]`，前端与 HTML 报告共用这一份数据。

### 3. `payload`（对外的 JSON）

```json
{
  "dataset": {"source","rows","train","test","hash","split","threshold","seed",
               "attack_train","attack_test","labels","engineering","format"},
  "warnings": [{"rule","columns","severity","message","suggestion"}],
  "results": [EvalResult...],
  "best_model": "mlp",
  "top_flows": [...],
  "score_curve": [...],
  "ablation": {"column","rows","note"} | null,
  "report_md": "...", "report_html": "...", "run_id": "abc123"
}
```

**CLI、API、历史库、前端都只认这一个结构**。加字段要同时改 `payload.py`、`types.ts`、
`report/*`，否则会出现"网页有、报告没有"的漂移。

## 四、扩展指南

| 想做什么 | 改哪里 | 要不要动别的层 |
|---|---|---|
| 支持一种新文件格式 | `ingest/table.py` 加一个分支；`ingest/__init__.py` 加后缀 | 不用 |
| 支持一种新数据形状 | `adapters/shapes.py` 的 `to_frame()` | 不用 |
| 接自己的模型 | `models/your.py` + `@register("name")` | 不用（自动发现） |
| 加一条泄漏规则 | `features/leakage.py` 的 `detect()` 里 append 一条 | 不用 |
| 改指标口径 | `eval/metrics.py` | 报告会自动跟着变 |
| 加报告章节 | `report/markdown.py` + `report/html.py` + `App.tsx` | 三处都要改，这是已知成本 |
| 加实验参数 | `ExperimentSpec` → `cli._add_run_flags` → `api` 表单 → `Rail.tsx` | 四层都要改，参数少时优先复用现有字段 |

## 五、必须守住的不变量（都有测试）

1. **标签永不进特征**：`test_label_never_used_as_feature`
2. **预处理器只在训练集 fit**：`test_pair_uses_train_statistics`
3. **速率有兜底**：`test_single_packet_rate_is_bounded`
4. **同数据同种子结果逐位一致**：`test_reproducible_same_seed`
5. **数据指纹随内容变化**：`test_hash_changes_with_data`
6. **切分后类别缺失要告警**：`test_*coverage*` / runner 抛错
7. **未知格式要给人话错误**：`ShapeError` 带 keys/shape 描述

## 六、这次重构做了什么（v0.4）

| 之前 | 现在 | 为什么 |
|---|---|---|
| CLI 和 API 各写一遍"跑实验 + 消融 + 报告" | 统一走 `service.execute()` | 两条路径必然漂移 |
| 只有 CSV/pcap | `ingest/` 按格式分发 + `adapters/` 处理形状 | 用户数据格式千奇百怪 |
| `prepare.py` 里三份几乎相同的预处理构造 | 仍是三处，但共用 `CATEGORICAL_FORCE` 与同一个 pipeline 结构 | 待收敛（见债务） |
| payload 组装散在 API 里 | `payload.py` 单一来源 | CLI/API/历史一致 |
| 前端组件与样式耦合 | 设计 token 集中在 `styles.css` 顶部 | 换肤只改一处 |

## 七、已知债务

1. `prepare.py` 的 `build_matrix / build_matrix_pair / build_feature_matrix` 仍有三份相似代码，
   应抽出 `_make_column_transformer()`；暂不动是因为每条路径的丢弃规则略有差异，先靠测试锁住行为。
2. `report/markdown.py` 与 `report/html.py` 有重复的字段拼装，可抽 `report/model.py` 做中间视图。
3. `store.py` 存整份 payload，历史库会随报告变长而变大；v0.5 考虑只存结果 + 报告按需重建。
4. 泄漏规则是硬编码顺序，规则多起来应改成注册表 + 可开关。
