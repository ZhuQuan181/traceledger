# Contributing

感谢愿意改进 FlowLab。这个项目的核心目标是“可复现的实验证据”，所以代码正确性、
数据边界和报告一致性比功能数量更重要。

## 开发环境

```bash
git clone https://github.com/ZhuQuan181/traceledger.git
cd traceledger
uv sync --extra dev --extra api --extra data
cd web && npm ci
```

需要 Python 3.11+；前端开发需要 Node.js 22.12+；pcap 相关测试/功能需要 `tshark`。

## 本地检查

```bash
uv run pytest tests/
uv run ruff check .
uv run ruff format --check .
cd web && npm test && npm run build && npm audit --audit-level=high
```

涉及打包时再运行：

```bash
cd web && npm run build && cd ..
uv build
docker build -t flowlab:local .
```

## 提交原则

- 不提交真实敏感流量、私有标签、模型权重或包含个人信息的数据。
- 测试默认使用合成数据或小型 fixture；公开数据集只在本地验证，不进入仓库。
- 修改结论、清单、报告或前端徽标时，必须同时检查四处是否使用同一个 verdict。
- 新增 API 写入入口必须考虑跨站请求、文件大小和失败时的用户提示。
- 新增实验参数需要同时更新 `ExperimentSpec`、CLI、API、前端类型和报告。
- 修改公开行为时同步更新 `README.md`、`README.en.md` 和 `CHANGELOG.md`。

## 提交前

- 确认没有密钥、绝对路径、数据库、`node_modules`、`web/dist` 或构建缓存；
- 为修复写回归测试，为边界条件写失败用例；
- PR 描述写清“问题、改动、验证命令、已知限制”；
- 若报告结论发生变化，附一份最小复现命令或合成数据样例。

## Issue

报告 bug 时请提供：

- FlowLab 版本、Python/Node 版本、操作系统；
- 输入格式与规模（不要上传敏感原文）；
- 复现命令、预期行为、实际行为；
- 相关报告指纹或错误堆栈。
