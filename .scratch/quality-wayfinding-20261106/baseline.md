# 全库基线与接手事实

本记录服务[全库覆盖与旧证据](../tails/issues/TAIL-484-全库覆盖与旧证据.md)，质量结论按具名范围读取，不把清单存在、旧测试数量或一次健康检查写成全库达标。主控为 Codex chat `01a1af77-36ae-7cb0-9ae8-65fa971d389b`，最新授权及临时模型档归[地图](../tails/issues/TAIL-483-工程质量达标路线.md)。

## 现场身份（接手时，2026-11-06）

- Git：主检出 `D:/dev/mtrl-workbench`，`master@6d01f996dd46a86c204aeb2568aad58d82c2034d`；`git worktree list --porcelain`仅一棵。正常 `ls-remote origin refs/heads/master`核同 SHA；远端 `git@github.com:lysyscy/mtrl-workbench.git`。
- 暂存区初始为空。原有 tracked dirty：油卡handoff、前端设计指南、油卡需求、status、票高水位。高水位482→490及status质量路线入口属于接手effort；status另有无关空行，提交时仅取本effort段。其他dirty及 `.codex-remote-attachments`、`.impeccable`、旧性能审计、临时脚本、DESIGN/PRODUCT、debug.log保持原位，不归本任务提交。
- 源码起点与历史正式产品分开：status记录产品 `7156a5ae`、资源`7156a5aef8d4`；retention登记它与上一版`17495586c2a1`。本轮已用正式只读status核服务 Running/Automatic、GET `/app` 200，并比较实际索引与配置发布目录的SHA256相同；该命令未取得监听进程，不能报归属已核。尚未对全部实际资源重做散列核验。
- 初次沙箱status误表现为服务不存在/连接失败；同命令在正常权限返回上述成功，不能把沙箱结果诊断成生产宕机。沙箱Git SSH因MSYS对象权限失败，正常权限只读远端成功。保留失败原因，不隐藏或改绿。
- 无当前预览登记`var/state/react-writable-preview/current.json`；没有停止任何服务或试用实例。明确来源文件中正式与测试身份区分有效，当前有效配置与文件中的两目标一致；只读TCP探测专用测试库在正常权限可达。尚未据此执行DDL。
- Python实际`backend/.venv/Scripts/python.exe` 3.15.1；Windows 11 10.0.26220；pydantic-settings 2.16.0、pytest 9.1.1、SQLAlchemy 2.1.4。前端精确依赖归package/lock，分区记录核其适用性。
- 聊天列表快照中，本质量路线为active；来源chat及最近架构扫描idle，其余相关chat notLoaded。快照只能证明当次可见状态；共享文件每次写入仍重核，不凭此取得其他dirty所有权。

## 共享记忆核验

项目绑定明示 bank `project-3379fef93fbada35`。本轮实际调用list_banks按精确ID查询，返回“项目：材料工作台”；实际recall带该bank返回TAIL-450、性能审计等历史事实，证明显式召回可用。历史仍含不同阶段的未完成/完成描述，均回原票与源码核现状。

知识页search/list/read实际只返回“工作树用后退出与只读收尾检查”，没有本effort页；它不提供本次质量结论。未独立验证本轮自动recall注入或会话结束自动持久化，不声称这两个机制已通过。未迁移历史、未改变bank绑定或写个人记忆。

## 具名分区

| 分区主人 | 必须覆盖 | 本轮边界 |
|---|---|---|
| [前端基线](frontend-baseline.md) | 所有实际路由、共享表格/读写/主题/网络、导入导出消费与相关测试 | 静态实际入口和旧证据逐项核；运行缺口明确 |
| [后端基线](backend-baseline.md) | 每个自有业务包、core/auth、API、i8、金额/写入/恢复/导入导出及迁移 | 不把同包其他端点随代表链签通过 |
| [工具与规则基线](tooling-baseline.md) | 运行/部署/开发/验证、CI/hooks、文档、第三方/生成/退役/未知 | 工具保护本身也要有证据；用途未知不清理 |

分区调度：前端与后端先按当时指示派`gpt-6-astra/high`、全新上下文；用户更正后既有运行继续，工具分区派`gpt-6.1-sol/xhigh`、全新上下文。调用参数已核，工具返回仅任务路径，未提供运行模型元数据。写边界分别仅上述三个Markdown；票务、共享规则、源码和Git由主控持有。

## 旧证据复用判定

按“版本/实际依赖→输入/场景→预期→证据存在与边界”核，不以日期或done自动判定。相同代码输入与业务预期的定向结果可复用；跨共享依赖变更须核影响。历史真实副本验证不证明今日正式数据或所有GUI场景。旧正文未提交不代表本轮拥有它；引用其路径与必要事实，保原归属。

已核旧性能审计/实施：通知书连续编辑、三列textOnly、关联恢复单次列表，库存及油卡普通备注确认范围已有实施；保留A3列宽装配与A4台账/动效决定。油卡真实备注样本为0的缺口仍保留，模拟接口证据仅解释UI。新候选不得重复当成未修；细节归分区。

## 已取得的有界新反例

2026-11-06主控在系统临时目录写合成`.env`，来源为`source_a`、明确目标`target_a_test`，进程仅覆盖目标为`target_b_test`；patch `sqlalchemy.create_engine`在连接前捕获参数并抛固定标记。调用真实`isolated_database`得到`target_b_test`，标记异常如期捕获；没有数据库连接、DDL或真实凭据输出。当前父隔离器在准备schema前未验证“有效目标=明确来源文件目标”，子pytest随后拒绝太晚。它是已证实的选错配置路径，不声称发生过真实误写。

实际`product_inputs`探针同时确认：`frontend_preview_browser_check.py`、`apps/frontend/pnpm-workspace.yaml`及patches未进入指纹。实际消费者与缺口影响由工具分区追踪；这是版本保护缺口，不声称历史部署产物错误。

外部机制参考（2026-11-06）：[Pydantic官方settings文档](https://github.com/pydantic/pydantic-settings/blob/main/docs/index.md)明确环境优先于dotenv，Context7同源查询已核；本机2.16.0上的上述反例决定实际适用性。[pytest官方环境变量](https://pytest.org/en/stable/reference/reference.html)说明PYTEST_ADDOPTS/PYTEST_PLUGINS改变选项和插件装配，具体风险回本机9.1.1及实际runner。已有框架能力可满足修复，不引入配置框架。

## 资源与后续

证据组已按项目入口登记：`quality-baseline-20261106`，owner `codex-01a1af77`；回执目录`C:/Users/Administrator/AppData/Local/AgentArtifacts/projects/mtrl-workbench/groups/quality-baseline-20261106/files`。当前用途未结束，后续产物经lease写入；系统临时反例目录已由TemporaryDirectory退出。未创建附加工作树、未部署、未迁移正式库、未调用真实i8或打印。未依赖定时器存在或保证自动删除。
