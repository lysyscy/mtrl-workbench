# architecture · 架构总览（指针页）

> **读者**：新会话 Agent ＋ 想快速把握全局的人｜**回答**：系统由什么组成、数据怎么流、去哪读权威版
> **何时读**：冷启动 / 动结构前｜**状态**：已定稿（2026-09-22 · 指针页，⛔ 不复制正文 —— 真源见下）

## 真源（唯一）

| 想知道 | 去读 |
|---|---|
| 运行时拓扑 / 仓库目录 / 分层边界 | 计划 `§2`（`.workbuddy/plans/开发计划-主文档.md`） |
| 15 个模块 → 工程包 → 壳切片归属 | 计划 `§3` ＋ `§0.3` 逐模块状态 |
| 链路（谁调谁 · 断在哪） | `tools/chain_expected.txt`（`chain_audit` 守，102/102） |
| 状态与进度 | 计划 `§0` 现状快照（数字由机器核） |
| 前端壳（唯一前端） | `backend/app/web/`（`index.html` ＋ `shell/{core,actions,legacy,print-export}.js`） |

## 一图（30 秒版）

```
i8（浏览器抓取 API-01/03/04 · I8Client 单点登录）
   │ 抓取（fetch_service 各域：幂等 upsert · 调整单/手动行保护）
   ▼
PostgreSQL（alembic 迁移 · 测试库物理隔离）
   │ JSON API（/api/m01…m15 · PRG 写路径 · preview_store 预览暂存）
   ▼
FastAPI 服务（NSSM `mtrl-workbench-server` · 单 worker · 8000）
   ├── 服务端渲染仅剩登录页；⭐ 唯一前端壳 = backend/app/web/
   │     （V.* 切片与 demo 原型逐行一致 = ui_parity U1）
   └── 导出：naive_export 内核（xlsx）/ tpl_fill（模板法）/ zip 字节替换（路径②）
```

## 关键纪律（详文回计划）

- **旁路与手改保护**：手改/调整单/手动行**永不被抓取或导入覆盖**（计划 §6.3）。
- **金额**：`core.money` 唯一出口；快照保留原始精度（§6.1）。
- **幂等**：同源重跑 = 更新不重复；减行不留残影（§6.4）。
- **统一导入**：`backend/app/import_kit/`（读表/解析/校验/暂存通用层；域判定留各域 —— `TAIL-69`）。
