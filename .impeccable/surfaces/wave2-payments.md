---
version: 1
slug: "wave2-payments"
primary_target: "apps/frontend/src/notices.tsx"
related_targets: ["apps/frontend/src/notice-entry.tsx", "apps/frontend/src/notices.css", "apps/frontend/src/notice-contract.tsx", "apps/frontend/src/notice-contract.css", "apps/frontend/src/notice-association.css", "apps/frontend/src/notice-fetch-jobs.tsx", "apps/frontend/src/notice-payment.tsx", "apps/frontend/src/notice-payment-grid.tsx", "apps/frontend/src/notice-print.tsx", "apps/frontend/src/ownership.tsx", "apps/frontend/src/payment-terms.tsx", "apps/frontend/src/flow.tsx", "apps/frontend/src/flow-revoke.tsx", "apps/frontend/src/flow.css", "apps/frontend/src/ledger.tsx", "apps/frontend/src/ledger.css"]
---

# 付款三页（付款通知书、欠款台账、付款流水）

模式为 Operate。PR-W2 沿用方向 A「精工深墨松绿」，统一三页工具区、表格和弹窗的视觉层次。设计与业务依据见[设计规范](../../DESIGN.md)、[前端设计与文案](../../docs/guides/frontend-design.md)、[桌面标杆](benchmark-home-and-contracts.md)和[当前需求](../../docs/requirements.md)。

## 桌面四档

| 视口 | 界面大小 | 主要核对内容 |
| --- | --- | --- |
| 2560 × 1440 | 大一点 1.12× | 欠款总览 `.debt-overviews` 居中限宽 1520px，三卡并排。双侧逐月表、通知书和流水用满可用宽度。工具栏单行，高 ≤48px。 |
| 1920 × 1080 | 标准 1.0× | 工具栏单行，高 ≤48px。表体 36px、表头 34px 为基准，金额完整可见。 |
| 1440 × 900 | 最大 1.4× | 打开外观面板。欠款卡片按 2+1 排列，第三卡横跨整行，周日期保持单行。 |
| 960 × 1000 | 标准 1.0× | 核侧栏收窄与展开两态。三页 `docOverflowX === 0`，表格承接必要横滚。 |

## 三页结构与精修

- **付款通知书（`/notices`）**采用齐平表面和紧凑工具栏，保留明面高频操作。关联、付款和打印弹窗沿用统一页脚。批量付款保留 65% 与 35% 的双表分配及 88dvh 高度上限。
- **欠款台账（`/debt`）**将总览三卡与双侧逐月表分开排布。条形图按名称、条形和金额对齐，金额右对齐，周日期单行。逐月表合计紧随末行，长表内部滚动。
- **付款流水（`/ledger`）**用左标签工具栏整理筛选，保持全宽表格与金额和合计的可读性。撤销弹窗收齐摘要、原因与操作区。项目导出继续沿用供 PR-W3 复用的 `.ledger-project-export`、`.export-project-actions`、`.export-project-list` 和 `.export-project-row` 类名。

## 业务护栏

| 编号 | 本波守住的约束 |
| --- | --- |
| R01 / R02 | 使用主题色，保留状态文字及金额正负。字号按档放大，金额完整显示，导出的空值、零、未知及两位小数规则照旧。 |
| R03 / R04 / R05 | 沿用页面与弹窗布局、弹窗限高和表内滚动。手调列宽按账号保存，恢复入口留在表头。既有单行策略与编号、日期保护保持。 |
| R06 / R07 / R08 | 保留静默逐格保存、失败处置和未知结果重读。保留离格保存、回车确认、输入法与原生复制粘贴。撤销重做保留 20 步，弃稿确认焦点落在「继续编辑」。 |
| R09 / R10 | 切页保留筛选、勾选、排序、滚动与草稿，离页关闭定位浮层。隐藏时改变宽度或字号后，返回页面使用新尺寸并恢复滚动。读态保留占位和状态提示，响应减少动态效果设置。 |
| R11 | 保留粘贴置顶、打印排序和单条打印后清选，勾选保留按原动作区分。一键关联集采合同、Excel 直下、后台抓取提醒及精简剔除回执沿原入口。 |
| R12 | 欠款与流水独立保活。三卡藏零保负，逐月表合计贴末行，切项目保高并隐藏旧结果，草稿或结果待核实时暂停导出。 |

## 验收证据

主检出受管目录 `.artifacts/runs/mtrl-site-polish-plan-20261127/w2-evidence/` 保存改前基线、采集脚本与提交后实拍。复审数据见 `after-review-fix/verification.json`、`after-review-fix/performance-final.json` 和 `after-review-fix/review-edge-cases.json`。

- **几何与交互**覆盖 15 个页面与视口状态、20 个网格、840 个金额单元格及 709 次焦点检查。文档横向溢出、金额裁切、焦点裁切和对比度告警均为 0。通知书和流水通过滚动恢复及隐藏期间改变尺寸的验证。
- **成对性能**在 2K 和 1080P 各交替跑 9 轮，每档比较通知书滚动、流水滚动和路由切换。6 项均通过，新增超过 100ms 的长任务为 0。路由切换均值和 p95 分别变化 −9.28% / −18.62%（2K）及 −6.86% / −14.83%（1080P）。
- **回归与扫描**通过类型检查、构建、302/302 单测和 52/52 Playwright 主回归。补充用例通过 6/7，多供应商用例另用真实数据核实 6 候选仍处于未提交状态。Impeccable 扫描 25 个源码文件及三条实机路由均返回空数组。
