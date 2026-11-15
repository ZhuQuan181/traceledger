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
| `compare.py` | 跨实验可比性审计与差值计算 | 模型训练 |
| `quality.py` | 标签覆盖、重复、冲突与稀有类别诊断 | 修复原始数据 |
| `service.py` | 编排：实验 + 消融 + payload | 任何具体算法 |

## 三、三个契约

### 1. `LoadedFrame`（pipeline 的输出）

```python
@dataclass
class LoadedFrame:
    df: pd.DataFrame  # 列名已标准化，已加派生特征
    source: str  # "flows.csv（csv）"
    label_info: dict  # {"mode": "embedded|flow_id|五元组|row_order", "labelled": n}
    engineering: dict  # {"min_duration_ms": 1.0, "derived": [...]}
    format_info: dict  # {"format": "npz", "shape": "...", "pickle_object": "..."}
```

### 2. `EvalResult`（runner 的输出）

字段固定：`model / kind / metrics / confusion / duration_s / params / split /
split_requested / dataset_hash / n_train / n_test / threshold / seed / attack_train /
features / encoded_features / top_flows / score_curve / by_label / false_positives /
false_negatives / source_ranking`。

`score_curve` 是 `[{p: 窗口最高分, h: 超阈值比例}]`，前端与 HTML 报告共用这一份数据。
`by_label`、典型错误样本和 `source_ranking` 只在开启解释时生成，用于调查视图。

### 3. `payload`（对外的 JSON）

```json
{
  "dataset": {"source","rows","train","validation","test","hash","split",
               "threshold","threshold_mode","seed","attack_train","attack_validation",
               "attack_test","labels","engineering","format","classes","quality",
               "features","experiment_fingerprint"},
  "experiment": {"models","split","split_effective","test_size","seed","threshold",
                 "source_kind","source","command"},
  "environment": {"flowlab","python","pandas","numpy","scikit_learn"},
  "generated_at": "...", "experiment_fingerprint": "...",
  "warnings": [{"rule","columns","severity","message","suggestion"}],
  "results": [EvalResult...],
  "best_model": "mlp",
  "top_flows": [...],
  "score_curve": [...],
  "verdict": {"level","headline","reasons","checks"},
  "checklist": [{"item","ok","detail"}],
  "investigation": {"by_label","false_positives","false_negatives","source_ranking"},
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
| 加实验参数 | `ExperimentSpec` → `cli._add_run_flags` → `api` 表单 → `ConfigRail.tsx` | 四层都要改，参数少时优先复用现有字段 |

## 五、必须守住的不变量（都有测试）

1. **标签永不进特征**：`test_label_never_used_as_feature`
2. **预处理器只在训练集 fit**：`test_pair_uses_train_statistics`
3. **速率有兜底**：`test_single_packet_rate_is_bounded`
4. **同数据同种子指标与指纹稳定**：`test_reproducible_same_seed`；
   报告含生成时间，不承诺整个文件逐字节一致
5. **数据指纹随内容变化**：`test_hash_changes_with_data`
6. **切分后类别缺失要告警**：`test_benign_aliases_are_recognized_in_coverage_warnings`；
   测试集缺任一类别时 runner 直接抛错
7. **未知格式要给人话错误**：`ShapeError` 带 keys/shape 描述
8. **只对真正进特征的泄漏报警**：`test_id_leak_on_dropped_column_does_not_block`
9. **消融能推翻泄漏判断**：`test_ablation_can_clear_port_leak`（Δ<0.05 时不该判死）
10. **结论 / 清单 / 徽标由同一个 verdict 驱动**：三处措辞不一致就是 bug
    （`test_unresolved_leak_blocks_even_if_not_hard` 盯这一条）
11. **跨站写请求必须被拒绝**：API 不接受任意 Origin 的 POST/DELETE
    （`test_cross_site_write_is_rejected`）
12. **HTTP pickle 需要同源会话令牌**：防止恶意网页借 localhost 触发反序列化
    （`test_pickle_upload_requires_session_token`）
13. **未标注流不得默认当成攻击**：缺失标签会在训练前失败
    （`test_missing_labels_are_rejected_instead_of_treated_as_attacks`）
14. **消融列必须真实参与训练**：元数据列和不存在列返回可读错误
    （`test_ablation_must_target_a_feature_used_by_the_model`）
15. **伪造 Host 不能绕过本地写保护**：所有 API 请求先校验 Host 白名单
    （`test_forged_host_is_rejected`）

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

## 八、v0.6 加固

1. ✅ 标签缺失、未知模型、阈值、种子和测试集比例在训练前校验。
2. ✅ 时间切分退化会进入警告、结论、清单和报告，不再只存在于日志。
3. ✅ 报告记录真实来源、复现命令、数据/实验指纹和切分方式。
4. ✅ 新增 PR-AUC、类别召回/误报率、典型 FP/FN 和源 IP 告警排序。
5. ✅ 移动端提供配置/历史/报告抽屉，历史可恢复完整配置；上传文件明确要求重选文件。
6. ✅ wheel 内置 Web UI，Docker 与独立 wheel 安装均有 CI 冒烟测试。
7. ✅ 测试集必须同时包含正常与攻击样本；Docker 严格按 `uv.lock` 安装并检查运行时健康接口。

## 九、v0.7 方法学与运行安全

1. ✅ 训练 / 验证 / 测试三段式；验证集选模型和自动阈值，测试集只做最终评估。
2. ✅ 时间戳泄漏不再按照“列是否进入特征”过滤；随机切分带时间戳会直接阻断结论。
3. ✅ 跨集重复行、实体重叠诊断；新增 `--split group` 与 `--threshold-mode f1`。
4. ✅ 历史库 schema v2 原位迁移，记录验证指标、模型列表和实验指纹，并支持单条删除。
5. ✅ 配置修改后 Web 明确提示结果过期；移动抽屉有焦点陷阱、`aria-modal` 和焦点归还。
6. ✅ 发布打包改为条件构建 hook；源码 checkout 无 `web/dist` 也能安装。
7. ✅ tag 发布流水线生成 wheel、sdist、依赖清单、SHA256 和 GitHub Release。
8. ✅ CLI 默认拒绝非回环绑定；远程暴露必须显式 `--allow-remote`，但仍需外部鉴权。

## 十、v0.8 可比性与数据质量

1. ✅ 跨实验对比会先核对数据指纹、特征矩阵、切分、验证集规模和阈值策略，再计算差值。
2. ✅ 历史工作台支持搜索、筛选、分页、备注、状态、删除和按保留数量清理。
3. ✅ 标签质量与模型性能分开报告：覆盖、重复、实体多标签冲突、稀有类别与少数测试类。
4. ✅ 诊断曲线补齐 ROC/PR、校准、Brier score、目标 FPR 阈值和阈值来源。
5. ✅ 报告记录运行环境与模型参数，并把环境纳入实验指纹。
6. ✅ 本地 API 使用 Host 白名单与安全响应头；伪造 Host 无法绕过同源写保护。
7. ✅ 320px 窄屏顶栏与分数图不再产生页面级横向溢出；自查清单默认折叠。

## 十一、v0.9 任务化与无标签工作流

1. ✅ 本机单执行位后台队列：job id、排队/运行/取消/完成阶段、进度和耗时。
2. ✅ 刷新恢复与离线执行：任务在服务端继续运行，页面可通过本地存储或活动任务接口恢复。
3. ✅ 协作式取消与失败边界：取消/失败不写入不完整历史；消融复用基线结果。
4. ✅ Web 无标签评分：无监督模型、Top N、分数摘要、排行与 CSV 导出。
5. ✅ 评分与评估语义分离：不读取标签、不计算 AUC/F1，分数不宣称为概率。
6. ✅ 上传预检：列映射、特征质量、时间戳、标签覆盖与切分后类别数量；
   阻断项与注意事项分开呈现。
7. ✅ 历史 payload zlib 压缩、SQLite WAL/索引、单次历史页查询和 GZip 响应。
8. ✅ CSV 读入与评分路径去除不必要的整表复制，并补充读入内存基准。
9. ✅ Playwright + axe 覆盖首屏、上传预检、390px 配置抽屉和一次小型合成实验；
   CI 使用独立 Chromium 任务。自动检查只覆盖关键页面的 serious/critical 规则，
   不等同完整 WCAG 认证。

## 十二、剩余债务

1. **统计可信度**：尚未提供 bootstrap 置信区间、模型差值区间或时间块交叉验证。
2. **特征贡献**：尚未接入 permutation importance / SHAP，报告无法给出原始列级贡献。
3. **前端结构**：`styles.css` 仍是单文件，组件继续增加后应拆分为 tokens/layout/components。
4. **远程模式**：没有内置鉴权；`--allow-remote` 只表示用户确认风险，不提供访问控制。
5. **基准复现**：公开数据集与 pcap 端到端仍未进入固定 CI；`tshark` 路径目前以跳过为主。
6. **浏览器覆盖**：E2E 目前只跑 Chromium；可访问性检查未覆盖屏幕阅读器和全部键盘路径，
   Firefox/WebKit 仍需后续补测。

下一步的优先级和验收标准见 [`OPTIMIZATION-ROADMAP.md`](OPTIMIZATION-ROADMAP.md)。
