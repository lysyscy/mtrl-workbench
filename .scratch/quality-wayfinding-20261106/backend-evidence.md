# 高后果链隔离基线

主人[高后果链隔离基线](../tails/issues/TAIL-492-高后果链隔离基线.md)。源码为已推送`1ae1543c526e8fd24c974341b0873e13d966bfff`，产品输入在运行期间固定，其他任务dirty保留。只使用明确来源与专用测试库、独占临时schema，不写正式业务、不调用外部i8/打印。

## 选择与结果

在具名基线的高后果缺口上选择15文件/节点，读取其夹具与有效断言后运行，未默认全库pytest。最新通知书81项及集采workspace/油卡接续深化的同输入历史证据继续复用。机械来源只选PostgreSQL实际API节点，没有以SQLite替代业务验证。

| 问题/消费者 | 本次选择 | 结果与含义 |
|---|---|---|
| 身份/真实装配 | `test_session_identity.py` | 假签名与临时账号，HTTP身份/普通用户拒管理、旧票/碰撞拒绝、本人偏好与在用策略保护通过；不改已有权限语义 |
| 项目删除/跨域引用 | `test_project_delete.py` | 选定对象、引用保护、查询失败/并发文本键重核及确认通过 |
| 操作历史/完整恢复 | `test_operation_history.py` | 真实handler、整批冲突、账号隔离、ABA/xmin/同actor竞争、父子关系及导出名单通过；独立engine仍继承本次单schema，不借正式库 |
| 库存原/有效值→过程 | `test_inventory_adjustment_values.py`、`test_inventory_projection.py`、`test_process_value_projection.py` | 数量/单价/金额、舍入/非法值、修改token、原单保全、调整映射、空0与来源通过 |
| 机械源/有效月值 | `test_mechanical_source_protection.py::test_postgresql_action_api_sources_switch_and_independent_net` | 真实PG的API来源切换、净额独立值与既有来源保护通过；其他纯规则/真实抓取不冒充本轮现场验证 |
| 油卡成对转账 | `test_oilcard_transfers.py` | 双边0净额、幂等、两边版本/归属、历史、异常原子性与完整导出通过 |
| 导出层 | `test_approved_report_exports.py`、`test_ledger_export.py`、`test_debt_export.py`、`test_big_export.py`、`test_jc_exports.py`、`test_oilcard_export.py` | 合成独立业务预期核金额/范围/顺序、公式缓存、月列、原始日期文本及完整历史；机械年度列数出现一个过期断言，见下节。没有Excel现场人工实看或物理打印 |
| 模型/隔离迁移 | `test_schema_drift.py` | 模型登记、现存模块与迁移后metadata比对通过；只升自建schema，不证明正式库或整机恢复 |

首次有效运行：**155 passed、1 failed，19.28s**，pytest退出1。`backend_verify_031fe5e45918428bad897d7588aa846c`及pytest临时目录清理均true。原证据保留为本轮受管组`quality-baseline-20261106/files/logs/backend-baseline-initial.log`、`reports/backend-baseline-initial.json`。

## 机械年度汇总失败：过期断言已修

失败节点`test_monthly_formulas_have_caches_and_preview_has_results`预期年度10列，实际11列。按现行[模板契约](../../docs/reference/template-export.md#机械原四页)和[GLOSSARY](../../GLOSSARY.md#机械费)，2026-10-29的`bfec641307b810f86d5fb8c3d6c54833fe0fbca3`已批准在“信息化消耗结算”后增加“班组使用-消耗结算”，不含i6。该提交修改导出与正文，未修改此旧测试。

最小无DB导出反例沿同一合成`data()`：两个月份C/D，E合计、F总班组、G i6、H i8、I差额、J信息化消耗、K新增差额；实际K6为`IF(COUNT(H6,J6)<2,"",H6-J6)`，缓存0。实际不是空白格式撑列，也不是误移原I6（原E6−F6、缓存0保持）；独立样例中的i6=10，不应计入新列。

只同步原测试为11列，并明确新列表头、公式及独立预期缓存0。没有改变导出或业务公式。仅重跑失败单例，**1 passed**、退出0；`backend_verify_fd2cc6ee1b9d41fab557fb927a0b722e`及临时目录清理true。原155项输入/预期未变直接复用，不声称整批重跑全绿。复测证据`logs/backend-verify.log`与`reports/backend-verify.json`；本机合成导出临时目录已自动退出。

## 环境失败与证据边界

有效运行前曾两次在`workspace_paths.output_dir → artifact_lifecycle.register → lock`遇PermissionError，均在连接和schema创建前停止，不是测试失败或产品问题。原因是本项目生命周期根级互斥被本轮preview的父lease持有；主控随后让后台验证作为同一已登记父run子消费者，显式继承MTRL_RUN_ID/MTRL_LIFECYCLE_OUTPUT，输出文件分工，保持同一父租约直到消费者结束。未移除锁、改公共技能或新建未登记目录。

现行声明/依赖/业务预期不变的旧保护维持，运行层只证明上述具体场景。真实i8多端点、物理打印、首次空库安装、全库备份恢复、旧油卡首次接续及缺非空样本的GUI仍按[基线分区](backend-baseline.md)具名未验。无需为本轮新增长期工具、全端点矩阵或全量安全认证。

规则新增的成功丢回执风险已由同轮前端真实副本注入取得API落行结果：原4行，第一次真实POST提交后丢响应变5行，同payload重试变6行，新ID分别77/78；原1261条通知书剔除标记保持。主控已读`reports/frontend-rule-fault.json`，它证明重复新增路径，不证明正式环境已发生或发生金融损害。合法同类/同内容多行保持，修复只处理本次未知意图的盲重投，交493；不另写重复反例。当前副本已正常退出并清理schema，两个诊断新增随之退出。详见[前端证据](frontend-evidence.md)。

本票所需事实已取得：高后果代表、导出过期断言处置和新规则风险分级均有具体依据；新产品风险需493修复，不能把本票完成写成规则已修或全库全场景通过。
