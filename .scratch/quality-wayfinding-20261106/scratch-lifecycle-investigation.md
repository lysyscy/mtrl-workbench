# `.scratch` 残留调查

2026-11-06，盘点发生在 16:46 正式发布之前，主检出 `master` 与本地远端跟踪引用 `origin/master` 同指 `b3ba025f373b113002c21fa2674266a4ce21883d`。调查核对实际文件、Git、票状态、文档和代码引用、安装的生命周期工具及 Windows 调度登记。数量以该快照为准，关键引用在发布回执追加后复核。文件去向为待核候选，本次只保存本调查。

## 主要原因

1. **完成票和运行证据结项以后，缺了一步项目文件退出。** 当前规则已明确 `.scratch/<effort>` 用于活动 Markdown 和票。唯一有效知识先进入现行维护源，已保存且无活动用途的旧文件可按 Git 提交和原路径追溯。`_tail_close.py` 有意只改原票状态和 Comments，产物工具也只关自己的运行组。近期任务完成了提交、关票和临时资源退出，但现行引用及 Git 工作树中的任务材料继续原样保留。`docs/status.md` 的多段历史发布记录还依赖当前 `.scratch` 链接，清理时必须一并处理这些引用。[项目工作流](../../docs/agents/workflow.md#目录与退出) · [贡献指南](../../CONTRIBUTING.md#审查与完成) · [票协议](../../docs/agents/issue-tracker.md) · [关票源码第 25–35 行](../../tools/oneoff/_tail_close.py) · [状态导航](../../docs/status.md)
2. **本机定时清理没有 `.scratch` 的扫描入口。** 项目包装器拒绝覆盖 `--root`，默认生产者将运行产物写到本机 `AgentArtifacts/projects/mtrl-workbench/groups/<run>/files`，固定旧运行仍可写 `.artifacts/active`。已安装实现只遍历指定登记根的 `groups`，按结项清单、期限、保护、锁和路径边界判断。`audit_work.py` 只报旧 `.artifacts`、`.scratch/local` 等提示。已安装的 `workspace_check.py` 有对具名旧任务的 `--phase closed` 只读检查，能发现该任务仍占 `.scratch/<effort>`，当前绑定仅对未迁移旧生产者或固定旧运行使用这套检查。它不会批量判断终态、业务依赖、独有信息或授权。因而等待 30 天不会让这里的 Markdown 或 TAIL 票自行退出。[产物接入](../../docs/guides/artifact-lifecycle.md#本项目实际接入) · [固定根包装器第 5–9 行](../../tools/artifact_lifecycle.py) · [生产者第 90–131、144–163 行](../../tools/audit/workspace_paths.py) · [旧目录只读提示第 18–55 行](../../tools/audit/audit_work.py) · [已安装 `workspace_check.py` 第 63–114、150–184 行](C:/Users/Administrator/.skills-manager/skills/setup-solo-workflow/scripts/workspace_check.py:63) · [已安装 `artifact_lifecycle.py` 第 174–234 行](C:/Users/Administrator/.skills-manager/skills/setup-solo-workflow/scripts/artifact_lifecycle.py:174)
3. **调度禁用是另一个问题，只影响受管产物的到期执行。** 宿主只读查询确认 `PersonalSkillArtifactCleanup` 已登记，`State=Disabled`、`Settings.Enabled=false`，上次运行 2026-10-31 17:08（北京时间）返回 1。上次回执中 mtrl-workbench 子进程报当时找不到登记标记。此次宿主读查该标记存在，未重跑任务。调度动作调用 `windows_cleanup.py`，代码固定调用六个 `AgentArtifacts/projects` 下的登记根。无法据当前状态保证质量组证据会在到期后自动回收，调度禁用也无法解释 `.scratch` 文档积累。[Windows 调度适配器第 10–30 行](C:/Users/Administrator/.codex/automations/automation/windows_cleanup.py:10) · [最近调度回执](C:/Users/Administrator/.codex/automations/automation/windows-last-run.json) · [实际接入边界](../../docs/guides/artifact-lifecycle.md#本项目实际接入)

## 规模和积累过程

盘点有 **12 个一级目录，0 个一级散文件，108 份 Markdown，合计 1,011,223 字节（约 0.96 MiB）**。其中 105 个路径已跟踪，3 个未跟踪，0 个忽略文件，无重解析点。索引路径集合与 `HEAD` 及本地 `origin/master` 一致，`.scratch` 没有暂存变更。一份已跟踪的油卡 `handoff.md` 有未暂存增量。三个未跟踪文件为油卡 `deployment-20261103.md` 和 `performance-architecture-audit-20261106/{audit,implementation}.md`，检查 `git log --all -- <原路径>` 未找到同路径可达记录。已跟踪文件的工作区增量和未跟踪文件须独立保全。工作树只登记主检出。仓库 `.gitignore` 仅为 `.scratch/local/` 保留专项忽略，活动资料正常随 Git 保存。[忽略边界第 39–46 行](../../.gitignore) · [油卡本机交接的 03 段](../oilcard-management/handoff.md#交接登记试用后界面收敛)

| Git 锚点 | 当时 `.scratch` 已跟踪文件 | 核实事实 |
| --- | ---: | --- |
| `642725be` → `f59b0f36` | 41 → 5 | 机械及全站性能两个已关闭 effort 已退出活动目录，`status` 留提交和旧路径。这证明已有可用退出做法。 |
| `050da993` → `ec8d0445` | 40 → 72 | 油卡和集采材料在场，随后增加 i8/加载 25 份和 7 张票。 |
| `b8ee0b24` → `6d01f996` | 76 → 80 | 加载结构整改、后续审计与两轮深化的回执继续在场。TAIL-473 在 `34f6bad8` 已定向退出，TAIL-482 在场且已修复。 |
| `6d01f996` → `b3ba025f` | 80 → 105 | 工程质量路线净增 11 份材料和 14 张已关闭票，占这一段净增的全部。 |

数字来自 `git ls-tree -r --name-only -z <rev> -- .scratch`、索引的 `git ls-files` 跟踪/忽略分流及磁盘不跟随重解析点的枚举。旧性能锚点 `642725be` 及所列发布、修复和关闭锚点均已核为本地 `origin/master` 的祖先。`87ccb47f`、`9aa89ee7` 和 `34f6bad8` 也有定向退出记录。结合当前票和引用，积累集中在近几轮交付后的文档收尾，而非目录存放时间或磁盘大小。[性能退出回执](../../docs/status.md#已关闭的性能优化) · [质量路线关闭回执](../tails/issues/TAIL-483-工程质量达标路线.md)

## 逐目录归类

| 目录 | 文件 | 当前身份与退出前置 |
| --- | ---: | --- |
| `architecture-deepening-20261106` | 1 | 三项深化已发布，隔离环境和短期构建已退出，历史实施及发布回执。16:46 新发布已替换 `status` 顶部的前轮链接。可用 `94ae7456` 和原路径保版本及未验收边界。 [实施与发布](../architecture-deepening-20261106/implementation.md) |
| `audit-remediation-20261105` | 2 | TAIL-450 已关闭、后续授权发布已完成。`completion.md` 保首轮历史，`implementation.md` 保最终裁定和授权演进；`status` 和原票仍消费后者。保现行裁定的所属规则及必要历史锚点后成批退出。 [最终处置](../audit-remediation-20261105/implementation.md) · [TAIL-450](../tails/issues/TAIL-450-架构差额后续实证与深化.md) |
| `browser-session-loading-20261103` | 25 | 规格、研究、交接、安装验证、证据和发布回执。475–481 全部 done，已上线；历史材料仍被现行 i8 契约、扩展 README、路由设计注释和 `status` 直接链接。只留现行会话身份、权限边界与已验范围在现行主人，把已验代表和其它历史详情改指可达 Git。 [i8 契约](../../docs/reference/i8-contract.md) · [扩展 README 第 80–88 行](../../apps/browser-extension/README.md) · [路由设计注释第 176–180 行](../../backend/app/mod02_i8/router.py) · [发布回执](../browser-session-loading-20261103/deployment-20261105.md) |
| `dsh-credential-output` | 0 | 未跟踪的空目录，未见重解析点或仓内同名消费。目录名无法证明原所有者。TAIL-473 的票和状态引用已由 `34f6bad8` 删除；不据目录名推定它就是该事件的全部现场。可在核归属和当前为空后单独退出目录，无需翻读凭据或 DSH 会话。 |
| `jc-ledger-refinements` | 3 | 集采调整已上线，保留旧裁定、失败恢复研究及发布/迁移回执。`status` 引用上线回执；当时的 8065 只是历史保留记录。本轮统一预览指针不存在，宿主查询 8065 无监听条目。业务规则、恢复边界和发布锚点应归现行需求/部署入口。旧预览 schema、迁移备份或兼容运行各按自身规则核用途。 [集采上线](../jc-ledger-refinements/deployment.md) · [状态记录](../../docs/status.md#集采台账调整已正式加载) |
| `loading-structure-20261105` | 4 | 已实施、审查、发布的加载整改，含另案反例。`status` 链计划、验证和相邻问题，TAIL-482 链反例。482 已修复并 done；先保留当前加载/失败边界及两件事分别完成的历史身份，原计划及复现用 Git。 [验证](../loading-structure-20261105/verification.md) · [TAIL-482](../tails/issues/TAIL-482-大表产值累计为空时保存非零合同预估价后重读失败.md) |
| `notice-amount-deepening-20261106` | 1 | 已发布的通知书金额维护回执。`status` 顶部已改指最新发布，TAIL-483 及质量分区材料仍引用前轮回执作为取证基线。该页尾部有后续独立扫描的范围裁定，先核扫描现时主人和候选交付。 [实施与发布第 19–29 行](../notice-amount-deepening-20261106/implementation.md) |
| `oilcard-management` | 20 | 已上线的开发材料与正在等待业务输入的旧台账接续混在一起。保护未暂存交接、未跟踪发布回执、TAIL-474 明确引用的 463 定位证据，以及经确认仍承担恢复用途的试用材料。`status`、油卡需求、备份指南及油卡设计简报直接引用该组；先拆出接续最小集合，逐份核哪些旧材料已有现行主人。 [油卡需求](../../docs/requirements/oil-cards.md) · [备份指南第 7 行](../../docs/guides/database-backup.md) · [油卡设计简报第 12、36 行](../../.impeccable/surfaces/apps-frontend-src-oilcard-tsx.md) · [TAIL-474](../tails/issues/TAIL-474-油卡旧台账核对与正式接续.md) |
| `performance-architecture-audit-20261106` | 2 | 报告自记审计、整改及正式发布已完成，产品 `a5c3b896` 在主线可达，两份独立工作文档均未跟踪。代码或 CI 可恢复，文档目前没有经核实的 Git 恢复依据。先由原任务确认独有裁定/实证去向和保存范围，原位保护。 [审计](../performance-architecture-audit-20261106/audit.md) · [实施与发布](../performance-architecture-audit-20261106/implementation.md) |
| `quality-wayfinding-20261106` | 11 | 技术路线和选定整改已完成。`status`、总票及子票仍以活动路径引用多份分区基线和验证。关键限制和重开条件先按实际用途归位，完整记录可在 `b3ba025f` 按原路径重读。详见下节。 [实施与退出](implementation.md) · [处置及边界](decisions.md) |
| `share-feasibility` | 1 | 用户 2026-10-28 明确暂不做、原地作参考。有具名保留理由。油卡后续局部采用共用筛选并不自动解除原研究的保留裁定。 [研究第 3 行](../share-feasibility/research.md) · [状态导航](../../docs/status.md#集合筛选研究暂存参考) |
| `tails` | 38 | 当前票务目录，须保留容器和高水位 496。`_list_tails.py --all` 成功，37 张 done，仅 TAIL-474 为 `needs-info`。474 的 `Blocked by: TAIL-452` 是实际脚本消费。不能移走 452 后把缺失依赖当作 done。 [票协议第 3–11 行](../../docs/agents/issue-tracker.md) · [依赖实现第 19–33、46–60 行](../../tools/oneoff/tail_common.py) · [TAIL-474 第 5–20 行](../tails/issues/TAIL-474-油卡旧台账核对与正式接续.md) |

其中 `browser-session-loading`、`oilcard-management`、`quality-wayfinding` 和 `tails` 合计 94 份，占盘点文件的约 87%。各个已关闭的子票之间仍有历史依赖和相对链接。退出时宜按真实依赖组成批次，先核剩余活票和 `--all` 的实际可读性，不能任意抽掉其中一张旧前置。

## 本轮质量路线的实际退出缺口

- 临时资源退出确实完成。原回执记录三个可丢弃预览和专属 schema 已退出，无附加工作树；直接核 `quality-baseline-20261106`、`quality-candidate-20261106`、`quality-final-20261106` 的登记，三组均为 `closed`、无 hold，`files/work` 不存在，封存清单分别 50、61、20 个文件，期限到 2026-12-06 15:50 左右（北京时间）。 [实施回执第 60–72 行](implementation.md)
- `.scratch` 退出没有做完。收尾记录关了 483–496 票、保存全部材料，`status` 第 5 行继续链接总票、实施和处置。该段的运行资源结论成立，但没有逐项核 `.scratch` 的消费者、归位、留存与退出。在场的 25 份历史材料没有列出全部继续使用的理由，不能以受管组 `closed` 替代这一步。 [项目退出规则](../../docs/agents/workflow.md#目录与退出) · [收尾提交 `b3ba025f` 的状态导航](../../docs/status.md#工程质量基线与本轮整改已完成)
- 盘点后按用户授权完成发布。16:46 正式加载 `b3ba025f`，健康、44 份资源及监听归属通过，`7156a5aef8d4` 保留回退。`status` 第 9 行现消费 `implementation.md` 新增发布段，这一工作区增量在盘点所用 Git 锚点之外，先独立保存并保留现行运行入口再审查该文件退出。隔离目标及指纹兼容已经进入代码、验证/发布指南；规则未知结果、项目读取、发票显示和大表边界按现行需求与代码核对已有覆盖。对非空用油金额加待核状态、真实 i8/打印、恢复、超出现有规模等具名未验边界，先确认有后续消费者的少数条目应落到哪个现行主人。完整判据、分区基线、候选和来源快照在可达提交追溯，保原始质量标准的独立身份。 [正式发布回执](implementation.md#用户授权后的正式发布与重启) · [现时运行状态](../../docs/status.md#当前运行与活动整改) · [处置与重开条件](decisions.md) · [固定参考](quality-standard-reference.md) · [项目需求入口](../../docs/requirements.md) · [验证指南](../../docs/guides/development-and-verification.md)

## 可执行的去向与保护边界

1. **先收敛已结束的历史段和引用。** 沿已有 `f59b0f36` 做法，先核 `status` 顶部唯一实际加载指向及活动导航，逐段把历史回执改用可达提交加原路径。首批候选是质量路线 25 份、i8/加载 32 份、加载结构和已修 482 共 5 份、审计及 450 共 3 份，再核两份深化回执和三份集采材料，共 **70 个已跟踪路径进入审查范围**。数字表示候选范围，保留项和替换链接须逐批核清。React 的 423/424 两张票有具名切换/退役回执，另按现行切换/恢复需求核最小历史锚点。 [性能退出先例](../../docs/status.md#已关闭的性能优化) · [React 签收与退役](../../docs/status.md#react重写已验收旧壳已退役)
2. **迁移真实消费者的最小信息。** i8 的会话信任和实际日常入口约束归 i8 契约及扩展 README，代码注释指向这些主人。已验通知书代表的限制可以保一行并引用 Git 中原验收。集采的当前业务和失败恢复边界归集采需求/共享契约，发布备份的当次身份通过原 Git 证据追溯。油卡的业务选择归油卡需求，界面试用裁定归设计简报和需求，发票原件恢复边界归备份指南；保持 474 对 452 和 463 的实际依赖，直到接续结束或按票协议完成可读的等效接续。 [i8 契约](../../docs/reference/i8-contract.md) · [集采付款共享契约](../../docs/reference/jc-payment-contract.md) · [油卡需求](../../docs/requirements/oil-cards.md) · [备份指南](../../docs/guides/database-backup.md)
3. **保护混合和未保存状态。** 当前油卡交接有独有本机改动。历史试用 owner 文件仍在，记 `ready` 和 `preserve_schema_on_stop=true`，但当前统一指针不存在，宿主查询旧 PID 未见进程、8065/8801 未见监听。保留 schema、恢复点、原始来源与核对表，不能据进程退出推定无恢复用途。本轮不连接数据库或读取业务原件。三份未跟踪 `.scratch` 文档，以及任务无关的 `frontend-design.md`、`oil-cards.md`、`status` 原空行、`.impeccable`、`DESIGN.md`、`PRODUCT.md` 等本机状态在独立处置前保持保护。共享筛选研究沿原具名决定留用。 [油卡交接第 93–110 行](../oilcard-management/handoff.md) · [旧接续票](../tails/issues/TAIL-474-油卡旧台账核对与正式接续.md) · [原地保留的研究](../share-feasibility/research.md)
4. **完成退出时沿原规则验收。** 在获准处置的批次重新核绝对路径、Git 实际可恢复性、余下票的前置及文档引用、当前预览/备份所有者和独有信息归位。随后按已有流程精确保存，并使用只读 `_list_tails.py --all` 与链接扫描核剩余入口。`tails/issues`、发号高水位和现有文件协议继续持有当前票。项目已经有退出规则和先例，无需新增清理台账或用调度按目录年龄扫 Git 工作树。 [贡献指南](../../CONTRIBUTING.md#审查与完成) · [票协议第 24–26 行](../../docs/agents/issue-tracker.md)

本次引用核对覆盖项目导航、正式文档、跟踪的源码/工具、原票及有关本机记录。未核历史聊天、外部脚本中的全部消费者，未核旧预览 schema、试用原件和备份可恢复性，也未触发计划任务或验证通知投递。油卡接续和未跟踪材料的保护结论仅用于确定本次调查边界。
