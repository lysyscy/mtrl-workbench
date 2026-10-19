# 提醒修复、effort归档与目录审计（2026-10-19）

本轮范围来自用户五项明确指令。项目起点2da4c94，已有dirty和并行成果保留；不推送远端，不重启服务，不访问i8或写真实业务。使用project-handoff、improve-workflow、manage-skills及writing-for-agents；日常文档规则沿本项目workflow绑定。本文是本轮唯一结果记录，原始回执和前字节在.artifacts/handoff-lifecycle-20261019；该目录被Git忽略。

## 提醒机制：事实、根因与修复

Skills Manager 1.42.2登记project-handoff ID为ff2270cd-155e-440a-8f2d-0c15665b26bf，source_ref是duoduoler-ops/Table-skills/tree/main/project-handoff。它不属于My-Skills。本轮取得真实源到D:/dev/Table-skills；修改前SHA为715985054d180ca7b46c78646240f7dd36fced4f，技能内9份文件均与中央库字节一致。用户级.codex/hooks.json四个事件直接调用中央库compaction_reminder.py；配置与旧状态均已在本机保存前字节。

用户指定旧会话01a152c3-39f9-7281-bb6e-05cc954a8998状态：auto_count=4、reminder_count=0、next_reminder_at=3、muted=false、last_notified_at=null；未进入冷却。旧状态原始SHA-256为97548a22484a00af2a4444e7451e39037aad43076e1bfd3a5e4fc94ccc5823fc。核真实轨迹中CommandExecution回执：多轮以“本轮完成/等待新材料”为skip，并采用next_compaction；之后又以讨论技能本身skip。状态和轨迹均只读，不把旧会话写入新会话。

规则歧义与程序缺口叠加：旧“任务已结束”没有限定完整当前范围；evaluate只要求defer/skip、note和next_check，负面判断可跨用户回合复用。Stop只检查有无评估，不验证任务状态矛盾。cancel同样能写跨回合skip。旧测试甚至明确要求skip压住下一次prompt，故不是一句“以后注意”能修复。

已在真实源修复5份文件（SKILL、计数参考、脚本及两组测试）：

- 区分continuing、phase_complete、finished、qa、skill_discussion。阶段收拢且第一步明确时属于有后续；仅讨论技能的混合任务不能豁免其他工作。
- evaluate必须声明完整范围状态；finished必须给scope_evidence。存在next_step/has_next或状态为持续/阶段完成时拒绝skip；首次到期且safe、有后续时拒绝defer，应prepare。
- skip仅覆盖当前回合；旧版skip记录下一回合也会失效，不迁移或重置计数。真正无后续、纯问答、仅技能讨论仍允许本回合skip。正常同阶段暂缓、冷却、静默及用户节点继续保留。
- cancel不再隐含“评估已完成”，撤销后仍需按事实评估。提醒只由真实Stop首段核验计数，prepare不算送达；一次补漏上限不变。

程序校验的是Agent声明之间的矛盾及过期，不能独立证明“整个范围已完成”的业务真实性；没有增加历史正文扫描、模型调用或强制交接。

新增隔离测试在旧版先红：旧skip跨新阶段未出现decision，阶段完成带后续未拒绝；修复后68项project-handoff回归通过，9项Claude适配回归通过，Windows模板经PowerShell实跑通过。系统quick_validate.py使用uv离线缓存的PyYAML环境通过；起初几个现有解释器缺yaml，未改项目依赖。真实状态未被测试调用，全部模拟事件使用独立临时状态。

首次修复在上游真实源的codex/handoff-skip-scope分支本地提交abcd34f531fbb93e4e489a6fc05077c08fadd293。Manager隔离试验确认同名install --local会新增project-handoff-2，set-source拒绝file://，因此未把本地候选伪装成同步完成。用户随后明确授权改为个人技能、推送My-Skills并共用维护源。

完整技能、MIT来源说明、维护入口与77项回归已迁入D:/dev/My-Skills/skills/project-handoff及根tests，不在中央库或Agent副本编辑。My-Skills本地原为4b92573，远端已有6个后续提交；保存本轮后整合到远端3328051，架构说明冲突按双方有效内容解决。最终个人源提交c7cdb8aa92f3a1b66a307bb2d5e7c969673b3d45已推送并核远端SHA相同；相对远端只新增交接技能、两组测试和必要入口，未修改其他个人技能。4个真实技能结构检查通过，本地147项回归通过；整合后新增的4项源CLI及1项真实结构检查通过，4项要求专用现场目录的环境试验按其原规则跳过，不算实测。对应push CI及安装结果见本轮最终保存记录。

精确提交的[push CI](https://github.com/lysyscy/My-Skills/actions/runs/39264161129)成功，confirm-source输出source_verified后才安装。迁移前对中央库与6个安装目标逐资源核旧9件基线并固定选择；官方Manager set-source干跑content_changed=true后，按用户个人化新授权正式替换来源，保留原ID、空标签、两个preset及6个部署目标。来源为https://github.com/lysyscy/My-Skills/tree/main/skills/project-handoff，新增维护页与许可，完整11件资源已通过包工具installation_verified；只读预检在来源迁移后生成，未冒充迁移前预检，迁移前保护另有原始快照。官方更新检测为up_to_date，未更新其他技能。宿主hooks.json命令仍指向同一中央库位置，无需另建钩子或改信任状态。

本轮临时Table-skills克隆已清理，初始修复分支abcd34f及完整来源历史保存为本机initial-handoff-fix.bundle并git bundle verify通过；不保留第二个维护源。普通删除先留下隐藏/只读.git对象，核仅余自建.git后用同一PowerShell路径清理成功。My-Skills源干净。Manager备份查询显示本地有2项变动、ahead/behind均0；本轮新推送授权仅用于My-Skills，没有向skills-manager-backup另行提交推送，不宣称云备份已经包含新来源。

真实宿主验证边界：旧会话的计数/登记是实证；新修复只有源码、结构、CLI与模拟生命周期证据，尚无真实新宿主压缩→状态注入→Stop最终提醒链。未伪造正式提醒、用户已看到或/hooks信任成功；旧会话计数保持原值。

## 两份旧设计及归档

逐项核代码、现行说明书、票及原验证。六项审查的R1/R2/R5由4ddcfd5实施，R3/R4/R6为TAIL-282/284/283且均done；PAY_OV会话草稿、真实flow_no/created_by及导出、delete-impact及同事务拒删实现均在。文档保留了旧测试与部署边界；未因此重做部署或重新开发。

界面整改的逐项判断归.scratch/legacy-active/README.md：业务主线已完成或被后续裁定替代，旧文头“一项未决”失效；仅§5历史原型退出清单仍挂起，现有导读、四检及变异靶消费者仍存在。保留这份原文及具体缺项，不另扩开发任务。当前doc_audit --ui归档前rc0（607/31/377/114项四检通过），旧_doccheck失败已经不存在。

按授权迁移42项旧路径：14份独有Markdown进docs/archive/completed-efforts-20261019；28项JSON快照/恢复输入映射至.artifacts/recovery/effort-archive-20261019/payment-plan-workflow，其中一对完全相同的before/preflight只存一份，总计41个实体。逐件核SHA，清单见归档manifest.json；本轮额外重复保护ZIP已移除，旧证据没有伪改今天状态。两项effort活动目录已退出；原表、源码、运行ZIP、交付skill、共享tools、仍用.skill-releases、历史恢复资料保留。

运行链核查：payment-plan-audit从技能内resources/audit-runtime.zip读规则；开发--repo从backend源码取规则；_build_plan_audit_runtime.py生成资源及交付包；sync_business_skills.py读取skills/payment-plan-audit及现行询价共享参考。扫描源码、测试、维护说明、生成包、ZIP内成员、中央库及5个Manager登记安装目标，共206成员，无payment-plan-workflow/business-skill-deployment路径依赖。不需要搬动运行资源。34项技能测试通过；首轮本地HTTP夹具受沙箱连接限制导致1失败，获准本地夹具复验后34通过，未连接生产接口。归档与现场验收分开，实体第二电脑及真实拟方式回写、实际付款仍未验。

## .scratch、scratch、.scratch/local职责与整理方案

本轮初查：根scratch不存在；.scratch存在，含legacy-active、tails、local及三个effort。初查元数据计.scratch共7941文件/约1.71GB，其中local 7746文件/约1.68GB，包含旧测试副本、日志、截图、前字节及恢复脚本。这是当时盘点值，不是长期阈值。

local体积大项主要是旧字节基点：retro-rollback-cli-start.json约87.5MB，pending-20261016-entry.json约66.0MB，tmp-slop-cleanup-entry-20261016.json约66.0MB；并非仅几份Markdown重复。完整元数据盘点见本机local-directory-inventory.json。它们可能服务旧恢复，先核原消费者及可重建性；本轮不因旧任务已结束就批量删除这些独有输入。

形成依据为D33及CodeBuddy退出记录：新effort采用.scratch/<effort>，旧00-scratch与宿主工作现场在2026-10-15整体迁入.scratch/local；更早.workbuddy/scratch退出见audit_work历史说明。Git无根scratch的跟踪历史不能证明过去从未有过未跟踪目录；本轮不推测其创建者。

现行消费者：TAIL开销票和审计读取.scratch/tails/issues；文档扫描/降档读取legacy-active；多份UI测试截图、_impactscope、_gatescope和隔离变异TemporaryDirectory使用.scratch/local。应用业务与付款技能不把这些effort作运行源。scratch作为测试变量/临时目录参数出现，不等于存在根scratch目录。

职责有重叠的是“必要任务证据”和local散件：同一任务曾把规格放effort、脚本及截图放local，容易遗漏共同收尾。独立用途是tracked活动范围/票仓与ignored本机现场，不能将local整合进tracked effort或按日期删除。

建议仅三步（本轮除两个明确effort及六项审查外不实施）：新持久证据按现行规则进effort，临时输出按需进.artifacts；local逐任务核实际引用、失败/恢复用途和是否可重新生成，再迁必要原件或删已证重复件；根scratch保持不存在，若再出现先查创建者和真实消费者。不新增第二套同义临时目录、全库目录迁移或TTL清空。frontend-visual-audit与TAIL-356～368仍活跃，保持原位。

## improve-workflow审计：为何没有自动归档

| 分类 | 可证事实与判断 |
|---|---|
| 执行偏离 | business-skill-deployment有完成与更新回执，原会话后段也承认“spec未归档，是收尾遗漏”。原轨迹第25/1390/2746行的实际命令回执均包含“effort全部范围完成…在同一次收尾实际移出活动目录”；说明规则已可达且多次读到，不能归因为没规则或没读到。现中央库与2026-10-17的5d80b2d已发布规则同样明确；本机旧源4b92573曾落后，不把旧文本冒充最新主人 |
| 明确保留授权 | payment-plan-workflow的2026-10-15规格、状态和cleanup-manifest明确“暂不结项，保留新包安装与实体局域网验收”；此前不归档不能统一归因为漏做。本轮新归档授权只变更资料安排，不把现场待验抹掉 |
| 入口/反馈缺口 | T26的DOWNGRADE_ZONES仅legacy-active，状态只认已定稿/已实施且要落地位置；普通.scratch/<effort>不在对象内。源码已变绿没有对应“所有结束effort已退出”的反馈，不能说自动检查兜底 |
| 工具限制 | _doc_downgrade.py只支持旧设计→仓外归档，规则明确不用于新的docs/archive批量迁移；没有监听“工作完成”的调度器。测试、提交、Stop均不会自动调用归档。工具可人工受控搬运，不等于能自动判断业务已结束 |
| 历史迁移 | D33有意保留未决原件与本机现场；旧UI文头没跟后文§6同步，通用扫描又不理解这些语义。遗留不等于新effort全部尚未完成，也不构成批量删除证据 |

最小改进建议：恢复执行已有唯一收尾，以本轮拥有的effort实际去向、活动余项与可恢复映射交付反馈；当前规则已明确，拒绝再加一句同义提醒。本轮42项映射、活动目录退出与SHA复核就是可检出的反馈。若之后仍有同类遗漏，才考虑在项目现有T26内增加对明确声明已结束effort的只报候选能力，以运行依赖、归属及未验边界作为人工判定输入。验证应有“已完但留活动区→候选、用户明确保留→不催迁、仍有运行依赖→阻止处置、归档后引用/恢复均可用”四个隔离场景；本轮只交候选，未改工具或其他个人技能。整合My-Skills远端已有成果不记为本轮审计改造。

这次修复提醒、处置授权资料并审计归档流程是不同完成条件，不能用一次测试或一句“完成”互相替代。本轮授权的修复、个人化发布、安装及资料处置完成后，本文退出活动目录；真实宿主链和现场能力未验是明确边界，不冒充本轮还有授权中的开发步骤。

## 最终核验与保存

归档后42个恢复映射逐件SHA通过，原路径均退出；旧会话状态与hooks.json对修改前备份字节相同。运行依赖复扫206成员仍为0命中，运行ZIP和skill交付包SHA不变。文档/字节检查必须修0，git diff --check通过；归档前已通过的交付面四检输入未变，结果复用。相关82项测试通过（文档迁移、项目安全删除、拟付草稿、流水装配导出、付款技能）；它们使用独立局部结果出口，没有更新权威四态。付款技能34项为独立分发测试，插件提示无项目acc绑定，未据此添加产品判据或修改规则。

没有跑完整pytest、现场整套自检、真实付款/打印或第二台实体电脑；没有做独立Agent审查，本轮为实现者自查。My-Skills源发布与安装已完成，真实宿主新链路及Manager备份远端仍按上文边界分别报告。材料工作台只本地保存本轮变更，不推送；共享文档中的原有dirty分块保护。
