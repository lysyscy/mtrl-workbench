# 工作资料、历史与恢复

读者：产生、接续或整理工作资料的Agent。回答：唯一落点、生命周期与项目例外。何时读：创建独立工作资料或处置旧材料时。现行目录标准来源回docs/agents/workflow.md，迁移恢复回docs/adr/0033-document-layout.md。

## 一、产出物与唯一落点

| 内容 | 落点与主人 |
|---|---|
| 新任务的实质规格、调查和持久证据 | `.scratch/<effort>/`；按实质需要建立spec.md、evidence.md，不复制现行业务正文 |
| 现有TAIL工单与状态 | `.scratch/tails/issues/`，沿既有真实票仓契约；索引为docs/status.md §15，开销票工具及协议回docs/agents/issue-tracker.md |
| 稳定工程结论或操作方法 | docs/architecture.md、docs/guides或docs/reference对应唯一主人 |
| 重要取舍 | 新ADR放docs/adr；旧D件在docs/adr保留编号和原文 |
| 已结束且有独有价值的过程 | docs/archive，保留原路径、固定SHA和必要证据；已有仓外原件按归档索引追溯 |
| 开发验证输出 | .artifacts/active/<effort>/<run>/<kind>；本轮结束释放work，选留必要原始证据至.artifacts/archive/<effort>/<run>，写retention.json，最长30天 |
| 临时命令、提交草稿与编辑恢复点 | 本轮work/recovery；完成验证与保存后释放，独有未提交恢复点按有限期限选留 |
| 程序运行数据与原件 | var/data不可随意丢弃，var/state保存凭据/有效预览；var/cache才是可重建缓存；var/log按配置轮转；var/backups保留业务恢复点；用户原件data/source、长期参考data/reference、成品exports |

## 二、生命周期与决策原文

活动资料沿其固定规则、授权和范围继续；迁移目录不重解释任务。任务结束后把有效规则归现行主人，过程按独有价值选择归档；普通检索限定当前资料、活动任务和直接依赖，历史只有明确追溯才展开。

旧D件只追加替代关系，原文与编号保持，实际位置统一为docs/adr；被取代时文头标Superseded by并更新既有索引，不进入旧_doc_downgrade工具。该工具只适用于其已登记旧分区并使用仓外归档契约，不用于新的docs/archive批量迁移。

历史源文件保持当时含义，原路径引用按固定SHA解释；来源索引为docs/archive/index.md。销号时原排期作为引用行追加到已销号历史索引，状态页只保留活动排期及历史入口；工具用原子替换写历史，失败时恢复状态页与票面。已关闭票保留原票面；默认内容扫描排除done/wontfix，但T6仍校验全票仓的编号、字段、状态及索引一致性。没有状态或状态未知的票保持严格检查，不能当历史略过。

## 三、删除与恢复边界

删除先核独有信息、活动引用、机器消费者和可恢复来源。本批仅退役已被新正文完全替代的薄入口；独有历史归档，未知或仍有任务用途的材料保留。日期、目录名或零引用不能证明可以删除。

本机备份、凭据、原始业务文件和忽略材料不靠Git恢复；本次整体迁入新位置并保留字节与元数据。恢复只还原本批拥有的路径，出现后续新内容时保护双方，不用全仓重置或清空。

## 四、文头与落地位置

旧分区仍沿其五档词与文头契约：读者、回答、何时读、状态；状态为草稿、在研、已定稿、已实施、已归档。新任务按真实需要写最小范围与验收；不为格式创建空文档。

旧设计声明结论落地时仍用下面格式，供T26读取：

```text
**落地位置**：`<结论真正落到的文件>`、`<另一处>` · 同批改：`<它变了要一起改的文件>`
```

路径写实际仓内位置；该声明不替代状态、验证或归档判断。

## 五、保留的项目例外

现有票仓是已采用的真实本地tracker；旧D件是长期决定来源。本项目CodeBuddy的MEMORY、RULE和仓内技能接入已退出；项目约束由AGENTS按操作指向docs/agents/project-rules.md，文档审计由普通指南和tools/audit工具承接。运行模板和delivery中的第三方原件由现有程序或来源契约消费；其余旧混合目录已经本轮专项迁移，不再作为新输出入口。这些例外不持有另一份现行产品Markdown或工程正文，退出条件见workflow §六。

历史00-scratch已按内容与消费者核查，独有字节和新旧对应关系从本轮迁移证据追溯；不得从旧文引用重新创建.scratch/local。旧逐日日志已在docs/archive/journal，不再作为常载入口。

## 六、当前旧设计资料

六项只读审查来源已随docs/archive/completed-efforts-20261019归档；TAIL-287按历史导入退出后的撤回结论保存。界面整改主线已完成或被后续裁定替代，§5原型退出已于2026-10-19按用户授权完成，原件及完成证据在docs/archive/old-demo-retirement-20261019；旧活动目录已退出。

文件拆分判据已在docs/guides/file-splitting.md，写动作刷新依据已在docs/architecture/write-refresh.md；其原来含义不因迁移改变。其余已结束设计与排障证据从docs/archive/index.md明确追溯。

## 七、运行状态与收尾接线

服务配置：ARTIFACTS_DIR=var/data、LOGS_DIR=var/log；业务导出exports；i8源Excel在var/data/i8_source（含i8透视对象，保留），导入映射var/data/import_profiles.json，凭据var/state/i8_cookie，未确认预览var/state/import_preview（本轮不增设到期删除），仓库缓存var/cache/i8_warehouse，签名缓存var/cache/signatures。NSSM输出与Python日志都在var/log。数据库计划任务调用ops/backup_databases.py，默认var/backups/databases；付款原表标注备份var/backups/payment-plan-audit。

权威验收结果var/state/verification/acc_results.json仅显式全量刷新，子集仍写独立局部档；回执及pytest输入同目录，源码、环境或路径变更不冒充旧通过。shell-baselines保存原5份壳基线；没有基线仍失败。新旧路径清单和内容校验见docs/archive/workspace-migration/。

每次任务结束先提炼现行结论，必要正文归docs/archive/<effort>；实际退出.scratch/<effort>及active中的effort，再执行workspace_check的closed。其他活动任务继续保留；运行结束与任务结束分别判断。到期证据每次开始和收尾检查，有独有长期用途则转正式数据/样本，否则清理；无后台自动删除承诺。
