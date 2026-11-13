# CICIDS2017 复现指南

> 目标：拿到官方 CSV 之后，**30 分钟内**跑出一份可对比的报告，且知道自己的结果"正不正常"。
> 这里不内置数据集（法律与体积原因），只给下载、校验、体检、运行、对照五步。

## 一、下载

官方来源（加拿大网络安全研究所，需填表后获得直链）：

- 页面：<https://www.unb.ca/cic/datasets/ids-2017.html>
- 机器可读镜像（社区维护，**下完必须核对列名与行数**）：
  - <https://www.kaggle.com/datasets/cicdataset/cicids2017>
  - <https://huggingface.co/datasets/c01dsnap/CICIDS2017>

推荐先只用一天的数据：`Wednesday-workingHours.pcap_ISCX.csv`（约 69 万行，DDoS + DoS 为主）。

```bash
mkdir -p ~/data/cicids2017 && cd ~/data/cicids2017
# 把你下载的 8 个 CSV 放进来
ls -lh
```

## 二、校验（不要跳过）

```bash
cd /mnt/data/flowlab
uv run python scripts/check_dataset.py ~/data/cicids2017/Wednesday-workingHours.pcap_ISCX.csv
```

它会告诉你：行列数、标签有几类、正常样本占比、有没有 `inf`/`NaN`、重复行多少。
**出现 ✗ 就别急着训练**——CICIDS 原始 CSV 常见三个坑：

| 坑 | 症状 | 处理 |
|---|---|---|
| `Flow Bytes/s` 含 `Infinity` | 读取后大量 inf，标准化报错 | 我们已把 inf 当缺失（`_features` 里 `notna().any()` + 中位数填充）；先跑体检确认 |
| 列名前后有空格 | `Destination Port` 变 ` Destination Port` | `schema.normalize_name()` 已处理 |
| 标签有空格/大小写混用 | `BENIGN`、` Benign`、`BENIGN ` | `is_benign()` 已归一 |

## 三、跑实验

```bash
uv run flowlab run ~/data/cicids2017/Wednesday-workingHours.pcap_ISCX.csv \
  --split temporal \
  --models mlp,iforest,autoencoder \
  --ablate dst_port \
  --report out/cicids-wed.md \
  --html out/cicids-wed.html
```

要点：

- **一定用 `--split temporal`**：CICIDS 的攻击集中在特定时段，随机切分等于把答案泄漏进训练集。
- **`--ablate dst_port`**：CICIDS 里攻击常打固定端口，消融能立刻看出模型是不是只学了端口。
- 报告里的「数据指纹」是内容哈希，换一份数据一定变。

## 四、结果对照（判断"正不正常"）

以下区间来自公开论文与我们的合成基线，**只用于发现异常，不是评分标准**：

| 指标 | 合理区间 | 明显偏高说明什么 |
|---|---|---|
| AUC | 0.93 – 0.99 | > 0.995：先怀疑泄漏（Flow ID / 端口 / 时间戳） |
| 误报率 FPR | 0.5% – 8% | < 0.1% 且召回接近 1：几乎一定是泄漏 |
| 召回率 | 0.85 – 0.99 | 1.000 且 FPR 极低：同上 |
| 去掉 `dst_port` 后 AUC 下降 | 0 – 0.1 | > 0.2：模型主要靠端口，报告里必须说明 |

如果三个模型 AUC 都是 0.999+，不要庆祝，先看右栏的泄漏检查。

## 五、把结果变成"可复现"

1. 报告里已有：数据指纹、切分方式、随机种子、阈值、特征清单、类别分布、每模型超参、混淆矩阵。
2. 附上你用的原始文件名 + 下载日期 + 校验值：

```bash
sha256sum ~/data/cicids2017/Wednesday-workingHours.pcap_ISCX.csv
```

3. 写论文时，把「数据指纹 + 命令 + 版本」三样一起贴进附录的 reproducibility 小节。

## 六、我们还没验证的部分（诚实说明）

- **690k 行的真实耗时**：目前只有合成数据基准（见 `scripts/bench_scale.py`），真实 CICIDS 尚未跑过。
- **78 列全特征**：我们只验证到 15–26 列；全列会显著拉长 one-hot 维度与训练时间。
- **类别不平衡处理**：未做重采样/代价敏感，`iforest` 在 9% 攻击率下 F1 偏低是预期行为。

跑完之后把 `docs/CICIDS-复现指南.md` 里的数字改成你实测的，这份文档才算完成。
