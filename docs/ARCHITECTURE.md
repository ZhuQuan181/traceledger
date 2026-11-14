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
| `ingest/zeek.py` | Zeek conn.log 表头解析 + 字段映射 | 标签（交给 labels） |
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
| `report/view.py` | 把结果压成"可直接排版"的视图 | 排版细节 |
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
| 接自己的模型 | 复制 `models/_template.py` → 改名 + `@register("name")` | 不用（自动发现，`_` 开头的文件不加载） |
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
8. **只对真正进特征的泄漏报警**：`test_id_leak_on_dropped_column_does_not_block`
9. **消融能推翻泄漏判断**：`test_ablation_can_clear_port_leak`（Δ<0.05 时不该判死）
10. **结论 / 清单 / 徽标由同一个 verdict 驱动**：三处措辞不一致就是 bug
    （`test_unresolved_leak_blocks_even_if_not_hard` 盯这一条）
11. **跨站写请求必须被拒绝**：API 不接受任意 Origin 的 POST/DELETE
    （`test_cross_site_write_is_rejected`）
12. **HTTP pickle 需要同源会话令牌**：防止恶意网页借 localhost 触发反序列化
    （`test_pickle_upload_requires_session_token`）

## 六、这次重构做了什么（v0.4）

| 之前 | 现在 | 为什么 |
|---|---|---|
| CLI 和 API 各写一遍"跑实验 + 消融 + 报告" | 统一走 `service.execute()` | 两条路径必然漂移 |
| 只有 CSV/pcap | `ingest/` 按格式分发 + `adapters/` 处理形状 | 用户数据格式千奇百怪 |
| `prepare.py` 三份几乎相同的预处理构造 | 一个 `_make_preprocessor()` + 三个 4 行的公开函数 | 之前靠复制粘贴维护 |
| 报告两个渲染器各自推导"哪个模型最好/小数几位" | `report/view.py` 的 `ReportView` 是唯一来源 | 会出现"网页有、报告没有" |
| 历史库只增不减 | `store.prune(keep)` + `flowlab history --prune` + `DELETE /api/history` | 跑久了会撑爆 |
| 前端三栏比例固定、信息堆在一条长列 | 三栏实验台：配置 / 画布 / 上下文（含可执行建议） | 看结果时不用来回滚动 |
| 输出 payload 由 API 手拼 | `payload.py` 单一来源 | CLI/API/历史一致 |

## 七、已清掉的债务（v0.5）

1. ✅ `prepare.py`：三份预处理合成 `_features()` + `_make_preprocessor()`，
   三个公开函数各 4–6 行，行为由原测试锁住。
2. ✅ 报告：新增 `report/view.py::ReportView`，Markdown 与 HTML 只做排版，不再各算一遍。
3. ✅ 历史库：`store.prune(keep)`，CLI `history --prune N`，API `DELETE /api/history?keep=N`。

## 八、剩余债务

1. `store.py` 存整份 payload，历史库会随报告变长而变大；可只存结果 + 报告按需重建。
2. 泄漏规则是硬编码顺序，规则多起来应改成注册表 + 可开关。
3. 前端 `styles.css` 仍是单文件（21 KB），组件多起来需要按层拆成 `tokens/layout/components`。
