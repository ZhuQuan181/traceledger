# Security Policy

## 支持范围

当前维护 `master` 和最新发布版本。旧版本不保证持续接收安全修复。

## 威胁模型

FlowLab 默认是**本地单用户研究工具**，不是可直接暴露到公网的多租户服务：

- 默认监听 `127.0.0.1:8765`，不提供账号体系；
- 实验历史保存在本机 SQLite；
- 上传文件会交给本机解析器处理，读取 pcap 时还会调用外部 `tshark`；
- `pickle` 反序列化可以执行任意代码，因此默认禁用，网页上需要当前页面的会话令牌显式开启；
- HTML/Markdown 报告包含用户数据的标签和流字段，分享前应自行脱敏。

## 部署建议

- 不要把 `flowlab serve --host 0.0.0.0` 直接暴露到公网；
- 如需远程访问，使用带身份认证的反向代理、TLS、请求体限制和网络访问控制；
- 不要以 root 运行服务；Docker 镜像默认使用非 root 用户；
- 只加载自己生成或确认可信的 pickle 文件；
- 定期清理实验历史，避免数据库无限增长。

## 报告漏洞

请优先使用 GitHub 仓库的 **Security → Report a vulnerability** 私密报告入口，
不要在公开 issue 中粘贴可利用细节、真实流量或个人信息。

报告中请包含：

- 影响版本和受影响组件；
- 最小复现步骤与影响说明；
- 建议修复方式（如果有）；
- 是否已经在公开环境披露。

## 供应链

- Python 依赖由 `uv.lock` 固定；
- 前端依赖由 `package-lock.json` 固定，CI 运行全量 `npm audit`；
- CI 在独立虚拟环境验证 wheel 安装与 CLI；
- Dependabot 每周检查 Python、npm、GitHub Actions 和 Docker 依赖。
