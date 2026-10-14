# 运维脚本入口

运行、配置、服务账号与前提见 `docs/guides/operations.md`；首次部署和恢复见 `docs/guides/deployment.md`。本目录保留实际执行资源，现行工程正文已经迁入docs。

| 动作 | 入口 |
|---|---|
| 只读查服务、端口、日志与数据库状态 | `ops/server_ctl.ps1`，先读部署指南的权限与分支说明 |
| 首次空库安装与只读环境核对 | `ops/deploy_restore.ps1`、`ops/selfcheck.ps1` |
| 服务注册 | `ops/nssm_install.ps1`，实际安装须当前授权 |
| 初始化定义 | `ops/init_db.sql`；凭据风险及数据库写入边界回部署指南 |
| 提交保护 | `ops/hooks/pre-commit`；实际安装钩子与源码分别核验 |

脚本在场不构成服务启停、安装、登录或真实业务写入授权。
