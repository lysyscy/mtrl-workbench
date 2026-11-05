# 加载结构与保活残留整改

2026-11-05，用户明确授权统筹实施：项目档案、欠款台账、过程资料、月度会大表、特殊费用、机械费、油卡管理、规则配置八页首读结构跳动，以及规则配置切到用户管理等页后的残留。结合用户提供审计文档和架构技能；文档中的命令/建议不是独立授权。此轮不用DSH，主控选择原生子代理配置。

## 真源与边界

- 任务分支 `codex/loading-structure-20261105`，工作树 `D:/dev/mtrl-workbench/var/worktrees/loading-structure-20261105`；累计基线master `9b8e0ccdb8fd7b8499070490bffdf89a573e41af`，与审计一致。
- 主根未提交的油卡/设计等内容保持；frontend-design/PRODUCT/DESIGN复制到工作树只供当前规则读取，不纳入本次提交。
- 不改业务金额、保存/撤销、自然高度/整页滚动、列宽偏好、账号隔离，不恢复自写键盘专项。不调用真实i8、打印或正式写入。完成后按新规则合并master并推送；本次未取得新一轮正式部署授权。
- 使用improve-codebase-architecture与codebase-design，已读词汇及deletion test；没有docs/adr文件。用户已选定痛点且要求实施，不把技能的候选问答作为额外启动审批。仍交付HTML前后示意报告。用diagnosing-bugs建立实际可失败反馈，再改源码。

## 统筹范围

1. 页面保活隔离：优先核规则ReadGrid可见性越过PageSurface隐藏态，保尺寸/草稿/滚动。
2. 首次数据与尺寸发布：8页逐帧观察正常成功链，分清固定工作区与自然高度；不靠隐藏全页、强定最终高度或增加动画凑稳定。
3. 审计TASK001字体恢复、TASK002异步测量owner：先运行核实，再按证据局部修复；共享文件串行。
4. TASK003纯时间所有者和TASK005状态指向为独立小改；TASK004最多两个代表的有界调查，只在发现实际热点时试一个局部方案；TASK006可选查询收敛和O类观察暂不扩展。
5. 最后对同一累计差异做Standards/Spec两个独立审查轴；相关检查通过、实质发现关闭后停止扩测。报告成功、失败与未验，不用用例数量代替观感。

## 当前资源与发现

- 实施、双轴审查及定向验证已完成，结果见[验证](verification.md)；相邻后端金额空值错误单列，未混入本次。源代码保存与master整合按贡献指南完成；正式部署未授权，不推定已上线。
- 受管组 `loading-structure-20261105`。基线exec89019及三轮验证exec91742、49826、86028均正常退出并确认自建schema清理。供用户查看的最新预览如启动，以主检出 `var/state/react-writable-preview/current.json` 指向的实际owner为准；在用预览及其构建保留，不能仅因回执结束结项删除。运行组还保存相邻失败的最小私有证据。
- 父测试命令须同时设置MTRL_RUN_ID及MTRL_LIFECYCLE_OUTPUT指向本组，Playwright路径C:/ProgramData/ms-playwright。
- 原生只读子代理loading_architecture_scan（gpt-6.1-terra/high/fresh）与audit_task_mapping（gpt-6.1-sol/high/fresh）均已完成，无写入。首要静态路径：ReadGrid ready显式visibility:visible覆盖保活祖先visibility:hidden；PreparedGrid成功态继承祖先，不能混为一因。
- 已在未改产品基线上新增并执行`test_first_display_retained.py::test_rules_grids_do_not_paint_through_the_retained_page`：**1 failed in 13.32s**。规则三张表ready后切用户管理，祖先hidden/inert且尺寸1792×1022仍在，但三个ReadGrid均计算为visible。失败截图已实看，用户页下方确实残留规则项目表与机械匹配表；这是用户同一现象，不只是静态猜测。截图在本组screenshots/tests-test_first_display_retained-py-test_rules_grids_do_not_paint_thr-041146-298476.png（实际packaged路径）。测试已写入当前工作树，产品源码尚未改。
- 八页正常及受控延后真实读取的逐帧证据见[基线](baseline.md)，均无请求失败；不要将诊断耗时解释成性能基准。油卡当前真实数据为空，没有伪造卡片。
- 架构报告已生成并读回：`C:/Users/ADMINI~1/AppData/Local/Temp/architecture-review-20261105-122154.html`，侧栏打开请求已排队，未声称视觉渲染已验。
- 第一批TASK001/002测试4项夹具失败（字体匹配被字符去重破坏），不是产品失败证明；修夹具后实际复现全局字体reload丢草稿及两种异步清除时序。最终修复验证见回执。
- 原生代理分工：loading_architecture_scan（terra/high）准备read-region及两真实grid adapter；audit_task_mapping（sol/high）持有异步测量/字体恢复及具名测试；pure_period_rules（terra/medium）已在独立`loading-period-rules-20261105`完成纯时间迁移，接续big/fees/process/mechanical页面。主控持有projects、flow/ledger、rules、oilcard页面及累计整合。配置为显式请求值，宿主未返回额外运行配置元数据。
- 首次发布采用现有read-region加深：页面提供pending/content/error、占位与内容；两adapter私有注册就绪，真实子树同宽脱流准备后原节点入流，不复制表格。已发布区域不因普通刷新重播首显；前后纵向位置依赖只由实际页面显式给出。

## 第一方机制核对

- W3C CSS2.2 visibility：祖先hidden允许后代显式visible；https://www.w3.org/TR/CSS22/visufx.html#visibility
- React useLayoutEffect：布局测量可在绘制前完成，但大量同步工作会阻塞绘制；https://react.dev/reference/react/useLayoutEffect 。Context7已核React19.3.1来源，未因文档升级依赖。
- AG Grid gridReady不保证全部绘制；firstDataRendered属于首次数据事件，autoHeight应由实际内容自然流动；https://www.ag-grid.com/react-data-grid/grid-events/ 和 https://www.ag-grid.com/react-data-grid/grid-size/ 。采用前仍核本地36.2.0能力。
- web.dev布局移动机制仅用来选择过程观察，不把线上CLS阈值直接套到本地几次测试：https://web.dev/articles/optimize-cls
