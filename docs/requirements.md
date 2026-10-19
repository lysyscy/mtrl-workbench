# 现行产品需求与业务定义

修改产品行为、字段含义或验收口径时，从本页定位对应主人；本次目录迁移保持业务含义、判据ID和规则正文。

| 需要判断什么 | 唯一正文或判据 |
|---|---|
| 业务规则、字段、金额、状态与边界 | `docs/requirements/材料科业务全流程说明书.md`，按章节读取 |
| 模块能力与追溯 | `docs/requirements/PRD/00-总览.md`、`docs/requirements/PRD/01-需求索引.md`及02-功能规格对应MOD |
| 完成判据 | `docs/requirements/PRD/验收/验收基线.json`；用例解释回同目录用例索引，实际结果由acc_report读取 |
| 非功能约束、范围外事项和阶段 | PRD的03/04/05/99分册，业务取值回说明书 |
| 技术选型约束 | `docs/requirements/技术栈选型分析.md`；当前实现与环境回docs/architecture.md和操作指南 |
| 产品材料取得与核验 | `docs/requirements/交付说明书.md`；旧建档推导仅在对应API/计划问题时读`docs/requirements/全自动建档-实施计划.md` |
| 交互要求及模板格式 | `docs/requirements/interaction-rules.md`、`docs/requirements/report-templates.md` |

旧demo的HTML、四检、导读及重复模板已按2026-10-19用户授权删除；交互要求和模板清单迁到本页所列现行主人。delivery仅保留第三方素材原件。运行模板的唯一实际位置由backend/app/report_export/resources.py定义；不移动正在运行服务可能读取的资源。当前交互基准回壳与前端守则，原型不作为当前运行界面基准。

验收设置PRD_ACCEPTANCE_BASELINE已切到本页所列唯一JSON；迁移只修配置路径，不改变判据数、ID或业务含义。文档检查使用tools/audit/doc_audit.py，正式壳与业务验证按开发核验指南选择；旧demo四检及--ui入口已退役。本机配置不提交，示例配置随仓更新。

历史目录核对与旧位置从Git基线7c37f89追溯；迁移详情见docs/adr/0033-document-layout.md。业务改变按当前用户授权，历史来源不提供新的写入或登录授权。
