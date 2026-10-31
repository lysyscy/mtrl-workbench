---
version: 1
slug: "apps-frontend-src-oilcard-tsx"
primary_target: "apps/frontend/src/oilcard.tsx"
related_targets: ["apps/frontend/src/oilcard-reconciliation.tsx","apps/frontend/src/oilcard-ledger.tsx","apps/frontend/src/oilcard-invoices.tsx","apps/frontend/src/oilcard-invoice-dialogs.tsx","apps/frontend/src/oilcard-receive.tsx","apps/frontend/src/oilcard-linkage.tsx","apps/frontend/src/oilcard-date.tsx","apps/frontend/src/oilcard-export.tsx","apps/frontend/src/oilcard.css"]
---

# 油卡页可理解性与布局整改

2026-10-31，用户在d15c494c后试用并明确要求整改。当前任务只改油卡工作区及总台账出口，保主题/字号、AG Grid、静默自动保存、独立双表、金额/归属/历史及未知结果保护。总票452和已完成453–463不改状态，不重启旧累计审查。

用户已确认总台账是一份Excel，内含核对汇总、充值、发票、账户与油卡等分表。ab95d8c9后再次试用明确否定重复功能；首轮设计审查的ship不等于用户接受入口分类。本轮以[整改记录的再次试用反馈](../../.scratch/oilcard-management/ui-revision.md#再次试用反馈ab95d8c9后)及[当前油卡需求](../../docs/requirements/oil-cards.md)为准：账户/实体卡桌面横排，资料直接格内维护；发票只保一个修改表单与一个可撤销删除入口。

## Direction contract

THESIS：让材料科熟手直接看账、记账、维护用卡；四个明确工作区取代五个同款按钮，普通浏览只保当前任务的必要动作。

OWN-WORLD：继承材料工作台的MiSans、账号主题角色、轻边界与AG Grid。表格是主体，主题色只表达当前页、主操作和选中对象；不替换全站视觉世界或改根DESIGN.md。

STORY：先看账户充值/开票/差额，再去并排明细记账；维护用卡时在同一页看到账户和实体卡，新卡从卡表建立，账户行直接选择关联卡片，旧卡与用卡记录保留。

FIRST VIEWPORT：上方为账户核对、充值与发票、用油联动、账户与油卡四个原生工作区标签，右侧一个导出总台账。核对表直接显示记录与账户状态；双表各有标题及新增/收票，所选记录的次要操作在明确对象上下文内出现。

FORM：既有主题内的定向任务重排，用户已固定关键结构，无视觉世界抽签。维护资料直接格内修改；当时卡片为隐藏快照；发票只用一个修改表单和一个可撤销删除入口，不为同一结果再设弹窗或菜单分类。

FINISH：unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## 已落地的表面范围

- 模式为Operate。四个页头下划线标签组织工作区，右侧保留一个总台账出口。账户与实体卡桌面左右排列，900px及以下纵排；两表各有在用/归档筛选及新增入口。充值与发票保持左右独立表格、独立筛选和合计。
- 档案字段直接格内维护；账户行只保只读的“用卡记录”。关联卡片直接下拉更改，新卡先在相邻实体卡表建立；不另设换卡弹窗，不以改旧卡号模拟换卡。油卡可独立归档，原关联及历史保留。
- 充值项目、账户沿格内更改，退出冗余归属弹窗及其专属前端调用。充值当时卡片是隐藏快照，不加可见列，不把关系操作时间推作业务生效日期；同账户的日期/金额修订保旧卡，改账户取目标账户卡片。
- 所选发票显示查看、下载原件、“修改发票”和“删除”，右键提供相同适用入口。一个修改表单合并票面与项目/账户分配；单账户只填价税合计，多账户才分别填分配金额。单归属格内选择仍承担日常快捷修改，完整表单承担票面修订和多账户整体保存。查看原件、保存文件和从本地台账删除各有独立结果。
- 退出红冲、作废登记入口，既有后台兼容接口和历史事实保留。删除确认明确本地台账及开票金额的影响，原件保留，可用顶部全局撤销恢复；不另建恢复流程。
- 日期保留普通文本输入，并使用Ant Design日历入口。正常编辑沿静默自动保存；失败时就近显示原因与重试/放弃入口，未知结果保护沿原机制。
- 主题角色、MiSans、字号缩放、AG Grid和Ant Design控件继续沿既有系统。局部布局、标签和弹窗尺寸是本表面的组合，不新增全站令牌或视觉规则。业务口径与总台账范围归[油卡需求](../../docs/requirements/oil-cards.md)的工作区及试用后简化章节。

## 完成后的设计核对（2026-10-31）

- 对照[PRODUCT.md](../../PRODUCT.md)、[DESIGN.md](../../DESIGN.md)、[前端设计规范](../../docs/guides/frontend-design.md)、当前需求及再次试用反馈，直接检查主入口、油卡CSS、充值双表、发票与统一修改弹窗，并抽查收票组件。源码延用共享主题变量、继承字体、缩放控件及共用业务弹窗；现有设计系统仍适用，无新增全站令牌。
- 文档核对直接查看`20261031-user-preview/reports`中的`distill-archives-desktop.jpg`、`distill-edit-desktop.jpg`（深色、1920×1080、1.12档）、`distill-delete-user-1280.jpg`（松绿、1280×720、1档）、`distill-archives-mobile.jpg`和`distill-edit-mobile-bottom.jpg`（390×844），与源码及现有设计规则比较。桌面档案并排、统一票面/分配表单、删除后果、窄窗档案纵排与弹窗滚动后底部操作可达有直接画面依据；不据此宣称390宽台账选票全流程已经验证。截图位于项目`.artifacts/active/oilcard-implementation/`，本轮证据组为`oilcard-ui-distill-20261031`，随已登记证据的生命周期保存。
- 主控提供的新独立`impeccable_finish_distill`已完整完成五节复核、查看八张最终截图，结论为`ship`、无`material_fixes`。其逐项区分格内快捷分配与完整整体修改、查看/下载/删除、两类档案筛选及只读用卡历史的独立用途；此结论覆盖本轮简化，不沿用已被用户否定的首轮裁定。
- 工程及可丢弃副本的交互验证沿主控回执：前端44项、build-04类型检查与构建、后端29加2项通过；本轮一次检测为`[]`。实际归档/撤销、分配保存/读回/撤销及删除/撤销通过，测试副本已清理。原试用副本经有恢复点的增量升级保原58张业务表内容及用户试用状态；这不是正式业务写入、部署或用户验收的声明。
- 本次只更新本表面简报；根PRODUCT.md、DESIGN.md及`.impeccable/design.json`保持原样。既有sidecar drift沿主控已报告状态保留，不把漂移或本页组合写成新的全站规则。本次没有随产品交付的栅格素材。
