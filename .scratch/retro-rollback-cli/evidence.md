# 写库测试回滚与选集CLI参数修复

范围：用户批准复盘第1、4项；第2、3项沿用现行执行规则。不修改个人技能或全局规则，不处理既有文档审计问题。

基点：`.scratch/local/retro-rollback-cli-start.json`，保留已有业务、依赖迁移及其他并行改动。

验收：
- 共享可选 rollback_db 夹具沿用现有外层事务＋保存点做法，接管 session_scope；正常退出、显式会话提交、断言失败均回滚样例。
- 迁移本次相关写库测试（TAIL-300三例、TAIL-281一例）；不改变生产事务、真实提交验证和其他测试的清理策略。
- _pytestscope.py 保留默认、--cover-only、--explain [-- PATH...]，支持--help；未知、缩写、冲突或用错位置的参数在选集计算前退出2。
- 定向回归后，因共享conftest变化跑一次最终完整pytest；其他检查按现有选择器执行，非零结果据实记录。

## 证据

- CLI回归在旧实现8失败/5通过：7类非法参数未拒绝，--help误入全量选集计算；默认、说明、显式路径、空路径及覆盖码保持原行为。
- 共享夹具及迁移用例定向21项通过；首次新增用例漏写工具自检@acc()已补齐，最终完整测试核对绑定。

- 新CLI真实子进程：--selftest退出2、--help退出0（.scratch/local/retro-rollback-cli/cli-live.json）。
- 建票工具先误用阶段“当前独立修复”触发T6，已改为受控词“立刻”；重跑仅剩既有T18缺失仓外归档目录，脚本回滚所有开票文件，未创建TAIL-350。不绕过审计或虚建归档目录。

- 最终入口第一次只进行选集预检，因本任务JSON/TXT/LOG证据误放非忽略目录退出2，未执行pytest或检查。已将原始输出移至.scratch/local/retro-rollback-cli并重跑；不改选择器边界。

- 完整核验入口中：doc_audit非零（既有T18及_doccheck计数）；mut_cover非零（生成台账未同步），_audit_face非零（已退役MOD-04无能力清单标题）。开工快照核对证明相关输入未由本任务修改，详细差异见.scratch/local/retro-rollback-cli/baseline-audit-failures.json。其余已执行检查通过，包含_gatescope自检0（514.21秒）。该入口在pytest阶段没有完成回执，原进程已不在运行；未计为通过，仅重新执行未完成的pytest。
- 首次可确认结束的完整pytest：1676通过、1失败（新CLI用例中的虚构文件名触发失效引用守卫）。仅将示例路径替换为实际存在的本测试文件；CLI与引用守卫复验16通过，原始失败日志/回执保留first-full-pytest.log/json。随后再次执行最终完整pytest。

## 最终结果

- 最终完整pytest：1677通过，退出0，814.46秒；本次7个运行/测试/使用说明文件在运行期间SHA未变，回执见.scratch/local/retro-rollback-cli/final-pytest.json，完整日志见同目录final-pytest.log。
- 测试后只读查询mtrl_workbench_test：项目、通知书、流水、合同、库存、调整单六类本次样例均0；见no-sample-leaks.json。
- 权威四态578＝绿577、红0、待建1、未绑定0；acc_report退出0。唯一待建仍为ACC-UI-SHELL-001/001-31。
- 第2、3项按现行规则执行，本次不改个人技能/全局规则；不操作生产事务或服务。
- 保留原有并行改动；本轮源码未提交、未推送。建票仍因既有T18被工具回滚，未伪造完成票。

- 最终状态资料同步后：状态计数守卫1项通过；doc_audit退出1，必须修仍仅既有T18（仓外归档根缺失），无新增红项。源代码和测试全套通过与文档/生成物入口整体非零分别记录。
