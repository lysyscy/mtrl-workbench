# TAIL-458 验证记录

2026-10-31，分支`codex/oilcard-management-20261031`，起点`c5510c5744c1ba0f6139261c44c7e97a0f907d35`。PH-20261031-oilcard-02已接手，范围为PDF收票、持久原件、去重、账户开票核对及独立发票表；尚未实施460人工更正或459链接批次。

## 实现与接缝

复用现有油卡档案/全域事务锁、身份、AG Grid、共用列筛选、静默保存队列、HistoryControls及Excel出口。pypdf已声明并锁定6.21.4。可靠标注、金额算术及两种文本提取一致且完整卡号唯一匹配在用账户才登记；短尾号、不可靠、多候选和归档账户均待确认。代表真实PDF仅只读，未导入真实账务或改名原件。

原件按SHA稳定保存数据库bytea，票据索引与整体分配同事务保存，随既有pg_dump保管。首次收票是已有history barrier，原件不随撤销删除；备注更正接入安全撤销。重复原件不记第二次金额；同票号按票面事实及规范化全文SHA比较，只有元数据变化按补档重复，可见内容变化留冲突，原有效票据及金额保持。冲突原件下载名使用自身识别信息并标待核，不借用主票金额。后续460更正票号需延续原识别身份，防止重新收到旧来源重复计账。

## 自动验证

- `backend_verify.py --source-env .env --test tests/test_oilcard_invoices.py --test tests/test_oilcard_ledger.py --test tests/test_schema_drift.py --test tests/test_layering.py -- -q -o addopts= --tb=short`：34 passed in14.12s。报告组`121926-135867-27868`，退出0，schema及basetemp清理true。
- 最终受影响收票与显式`tests/check_oilcard_invoice_restore.py`：14 passed in9.98s。报告组`122558-785492-27392`，退出0，schema及basetemp清理true；与前项存在覆盖重叠，不相加冒称独立总数。
- 恢复专项显式`MTRL_PG_BIN=D:/pgsql/18.6/pgsql/bin`，工具与专用测试库均18.6。仅在backend_verify独占schema实际custom dump、清空三张发票表、data-only restore，再经API核PDF完整字节/SHA及开票3000.00。未调用生产备份任务或恢复真实库。
- 前端类型检查、发票定向4项单元、Impeccable detector（退出0/[]）及正式统一入口build-03均通过。主控直接核后端JSON/日志、实现接缝与下载文件；复用453～457仍有效证据，不重复整套检查。

自动报告归本机`AgentArtifacts/projects/mtrl-workbench/groups/<报告组>/files`；GUI与实际下载证据归`.artifacts/active/oilcard-implementation/20261031-458/reports`。

## 内置浏览器与实际文件

主控在1920×1080、预览账号large字号，从侧栏进入实际产品，registered_preview核源码、构建、数据库及schema一致；现有API准备合成账户和充值，不写正式数据。

1. 真实文件选择器上传有效PDF，完整合成卡号自动归唯一在用账户，开票3000.00。仅元数据不同的同票补档不加金额；短尾号票保待确认；同金额但购方内容不同的同票留冲突，原开票仍3000.00。
2. 发票主表票面只读，备注离格自动保存。刷新后备注保持，账户甲充值10200.00、开票3000.00、差额7200.00；另账户50.00不变。
3. 左表类型筛到调整合计200.00，右表仅待确认票合计0.00；清除右表后3000.00，左表仍200.00。“仅此项”及“清除筛选”自动关闭。右表票号排序不改左表条件；左右选择独立，右原件1→3不丢左选择；实际横滚左0/右139。初次尝试定位仅此项时按钮尚隐藏，先点击候选显出后操作通过，不把定位超时报功能通过。
4. 在上述筛选下实际下载两份全量台账：充值3条/10250.00，发票2条/已登记3000.00。票号和卡号仍文本，备注及原始日期标记保持。实际下载主原件和冲突原件均与上传字节一致，所有原件API SHA再核一致；查看入口实际打开内置PDF阅读器并看图可读。
5. 浏览器error日志为空。`gui-verification.json`绑定最终schema/PID；`download-verification.json`记录文件SHA。截图`independent-filters.jpg`、`receipt-readback.jpg`、`pdf-view.jpg`已实际查看。

## 资源与未验边界

最终预览8065，PID37232，专用`mtrl_workbench_test` schema`frontend_rewrite_397_001dbbee197c462cbf27cd23ffa2cb96`，revision`oil458261031`，synthetic=false/disposable=true。正常stop退出0，终端确认schema cleaned；两次修正前的短预览亦正常退出/清schema，未提前做GUI冒报最终版。8000及8801均未操作。

执行者派发实参为gpt-6.1-sol/xhigh/独立上下文，工具仅回任务名，实际运行配置无独立元数据回显。开发技术核验、人工签收、首次真实导入及生产加载分别判定；累计Standards/Spec独立审查尚未完成。
