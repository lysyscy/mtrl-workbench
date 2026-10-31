---
version: 1
slug: "apps-frontend-src-oilcard-tsx"
primary_target: "apps/frontend/src/oilcard.tsx"
related_targets: ["apps/frontend/src/oilcard-reconciliation.tsx","apps/frontend/src/oilcard-ledger.tsx","apps/frontend/src/oilcard-invoices.tsx","apps/frontend/src/oilcard-association.tsx","apps/frontend/src/oilcard-linkage.tsx","apps/frontend/src/oilcard-date.tsx","apps/frontend/src/oilcard-export.tsx","apps/frontend/src/oilcard.css"]
---

# 油卡页可理解性与布局整改

2026-10-31，用户在d15c494c后试用并明确要求整改。当前任务只改油卡工作区及总台账出口，保主题/字号、AG Grid、静默自动保存、独立双表、金额/归属/历史及未知结果保护。总票452和已完成453–463不改状态，不重启旧累计审查。

用户已确认总台账是一份Excel，内含核对汇总、充值、发票、账户与油卡等分表。移除“查看充值与发票”“取消未保存修改”“登记退款”常驻入口；换卡明确针对账户行，历史归属更正明确针对一笔记录，日期入口使用标准日历图标；账户/实体卡合到一页。

## Direction contract

THESIS：让材料科熟手直接看账、记账、维护用卡；四个明确工作区取代五个同款按钮，普通浏览只保当前任务的必要动作。

OWN-WORLD：继承材料工作台的MiSans、账号主题角色、轻边界与AG Grid。表格是主体，主题色只表达当前页、主操作和选中对象；不替换全站视觉世界或改根DESIGN.md。

STORY：先看账户充值/开票/差额，再去并排明细记账；维护用卡时在同一页看到账户和实体卡，换卡直接由相应账户行发起。

FIRST VIEWPORT：上方为账户核对、充值与发票、用油联动、账户与油卡四个原生工作区标签，右侧一个导出总台账。核对表直接显示记录与账户状态；双表各有标题及新增/收票，所选记录的次要操作在明确对象上下文内出现。

FORM：既有主题内的定向任务重排，用户已固定关键结构，非开放全页概念竞赛，无视觉世界抽签。标志性交互是“行内明确对象的换卡”和“所选账务的明确归属更正”，不是装饰。

FINISH：unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## 已落地的表面范围

- 模式为Operate。四个页头下划线标签组织工作区，右侧保留一个总台账出口；账户与实体卡在同页分区，充值与发票保留左右独立表格。
- 高频动作紧贴各表标题；所选记录的更正、查看、下载及票据处理显示在对象上下文中。换卡由账户行发起，弹窗标题及原卡说明明确账户；本笔归属更正明确记录、项目、账户和当时卡片的范围。
- 日期保留普通文本输入，并使用Ant Design日历入口。正常编辑沿静默自动保存；失败时就近显示原因与重试/放弃入口，未知结果保护沿原机制。
- 主题角色、MiSans、字号缩放、AG Grid和Ant Design控件继续沿既有系统。局部布局、标签和弹窗尺寸是本表面的组合，不新增全站令牌或视觉规则。业务口径与总台账范围归[油卡需求](../../docs/requirements/oil-cards.md)的工作区及试用后简化章节。

## 完成后的设计核对（2026-10-31）

- 对照[PRODUCT.md](../../PRODUCT.md)、[DESIGN.md](../../DESIGN.md)、[前端设计规范](../../docs/guides/frontend-design.md)与上述方向契约，检查主入口、油卡CSS及核对、双表、关联、联动、日期和导出组件。源码延用共享主题变量、继承字体、缩放控件及共用业务弹窗；现有设计系统仍适用。
- 文档核对直接查看`20261031-user-preview/reports`中的`final-overview-1920.jpg`（深色、1920×1080、1.12档）、`final-ledger-1280.jpg`及`final-replace-1280.jpg`（松绿、1280×720、1档），与源码及现有设计规则比较。截图位于项目`.artifacts/active/oilcard-implementation/`，随已登记证据的生命周期保存。
- 主控提供的独立finish review已查看九张最终截图，覆盖两种主题、1920/1280宽及390窄窗，并给出`ship`、无实质修复项的结论；该结论是设计审查结果，用户验收及正式部署仍分别记录。
- 本次只更新本表面简报；根PRODUCT.md、DESIGN.md及`.impeccable/design.json`保持原样。既有sidecar drift沿主控已报告状态保留，不把漂移或本页组合写成新的全站规则。本次没有随产品交付的栅格素材。
