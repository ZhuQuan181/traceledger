# M3（v0.3）里程碑报告

日期：2026-11-13 · 状态：**完成**

## 这一版做了什么

1. **单文件 HTML 报告**（自包含，可直接发/打印成 PDF）
2. **本地实验历史**（SQLite，`flowlab history / show / compare`，网页左侧可点回看）
3. **消融实验**（`--ablate dst_port`，量化"指标是不是靠某一列撑着"）
4. **修掉一个致命 bug**：标签列被当成特征喂进了模型

## 验收证据

| 项 | 结果 |
|---|---|
| 单元测试 | `uv run pytest -q` → **41 passed, 1 skipped** |
| HTML 报告 | 16 KB 单文件，无外链；含分数分布、泄漏、对比、消融、Top 流、复现命令 |
| 历史库 | `flowlab history` 列表 / `show <id>` 回看 + 导出 / `compare id1 id2` 对比 |
| 消融（真实数字） | 极端数据（攻击流只有端口不同）：mlp AUC **0.9858 → 0.5307（Δ +0.4551）** |
| 目标泄漏检测 | 新增 `target_leak` 规则，能识别"每个取值只对应一个标签"的列 |
| 网页 | 历史 6 条可点回看；消融下拉 + 消融表；下载 MD / HTML |

## 修掉的 bug（重要）

`build_matrix_pair()` 里 `drop.discard(label_col)` 的写法让 **label 列留在了特征矩阵里**——
模型直接看到了答案，所以所有模型 AUC 都恰好是 1.0000，消融也看不出任何变化。

- 现象：`feature_names` 里出现 `label_BENIGN` / `label_DDoS`
- 修复：`drop = (META_COLUMNS & df.columns) | {label_col}`
- 回归测试：`test_label_never_used_as_feature` 断言特征名里不含 `label*`
- 连带修正：`dst_port` / `protocol` / `src_port` 改为类别型 one-hot（端口是名义变量，"3333 < 5432"没有意义）
- MLP 的 `early_stopping` 耐心从 15 提到 30，避免在 9% 正样本上停在第 12 轮

## 消融实验怎么读

```
== 消融：去掉 dst_port ==
| 模型 | 含该列 AUC | 去掉后 AUC | Δ |
| mlp  | 0.9858     | 0.5307     | +0.4551 |
```

Δ 接近 0：这一列没在撑指标（或者本来就不重要）。
Δ 很大：模型学的是这一列，不是流量行为——换数据集就会失效。

## 命令

```bash
uv run flowlab demo --leaky --ablate dst_port          # 极端泄漏数据 + 消融
uv run flowlab run cap.pcap --ablate dst_port --html out/r.html
uv run flowlab history                                  # 最近实验
uv run flowlab show <id> --html out/one.html            # 回看并导出
uv run flowlab compare <id1> <id2>                      # 跨实验对比
```

历史库位置：`~/.flowlab/flowlab.db`（可用 `FLOWLAB_HOME` 改）。不上传、不联网。

## 已知限制

| 限制 | 说明 |
|---|---|
| 历史库无删除/清理命令 | 文件会一直长；v0.4 加 `history --prune` |
| compare 只对比最佳模型 AUC | 没有逐模型对比视图 |
| HTML 报告体积随 Top 流线性增长 | 超大实验建议只导出摘要 |
| 消融一次只能去掉一列 | 多列组合消融需要跑多次 |
