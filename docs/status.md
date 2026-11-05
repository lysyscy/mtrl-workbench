# 当前活动工作

## 当前运行与活动整改

2026-11-05 18:32按用户批准发布并重启：正式前端指向`var/frontend/releases/7540882ce5ff`，产品提交`7540882ce5ff400b566327e7e0b747c9c7e8b60a`。通知书、库存、收发结存、采购合同和机械费已共用前端抓取动作；正式收发结存月报的“抓取 i8…”入口可见。健康200、实际索引、44份资源和8000监听归属通过，回退保留`09137eb00b69`。发布回执归本机受管组`183114-343748-47096/files/reports/deployment.json`，本轮未执行真实i8抓取。前轮取消账号菜单限制的扩展0.1.1仍在`var/browser-extension/releases/fce4aa1d82143b81`，由用户自行安装；本轮无需更新扩展。源码HEAD与运行产物分别记录，不用最新源码替代部署身份。后续发布只更新此处现行指向，下面各节保留当次历史事实。

当前[加载结构与跨页残留整改](../.scratch/loading-structure-20261105/plan.md)已完成实施、双轴审查及[定向验证](../.scratch/loading-structure-20261105/verification.md)：八页首读、规则页残留，以及字体重载保护和异步测量归属等相关审计项。累计基线`9b8e0ccd`，任务分支`codex/loading-structure-20261105`，按贡献指南整合master；采用原生子代理，不用DSH。2026-11-05 13:34已按用户授权部署并重启，正式加载b8ee0b24，HTTP200、42份资源及监听归属核验通过；原i8配置保持。另发现的大表合同价/空产值重读错误已开TAIL-482并[单列](../.scratch/loading-structure-20261105/adjacent-finding.md)，不写成加载整改已修复。

## 11月3日油卡交付记录

2026-11-03 17:34，油卡管理已与同期机械费、集采及性能改进整合到master并正式发布，产品提交`a6fdd73a847c`，油卡原分支`a70ce4e7`亦已推送。[总票TAIL-452](../.scratch/tails/issues/TAIL-452-油卡管理与用油报表联动.md)为done。类型检查、84项前端单元检查、定向后端及CI通过，正式页面和油卡读取接口核验通过；原试用数据保留。见[发布记录](../.scratch/oilcard-management/release-20261103.md)。

真实旧台账尚未接续，独立由[TAIL-474](../.scratch/tails/issues/TAIL-474-油卡旧台账核对与正式接续.md)持有，状态needs-info，待用户确认接续期间、归属及旧金额等信息；开票不代表执行正式数据写入。

当次完整产物为`var/frontend/releases/a6fdd73a847c`，当次上一回退为`073aaedd1b16`；两库public已到`oilmerge261103`。油卡迁移前备份`var/backups/databases/20261103-173228-1042ea7d`已核归档、散列及大小，未做整库恢复演练。回退保留当前数据库和正常新业务，操作方法回[部署](guides/deployment.md)。本段仅记录当次版本与验证边界。

## 集采台账调整已正式加载

2026-11-03 16:07，按用户“上线”授权，正式前后端已加载`073aaedd`：合同默认日期升序、存档号虚位区分、填号后一次推进、寄回日期选择即保存、发票明细按可用高度展示与原生固定表头/合计、超过本侧合同额110%的预警，以及删除常驻重读并按原操作身份恢复。源码已推送并核远端SHA，[Frontend checks](https://github.com/lysyscy/mtrl-workbench/actions/runs/41600788415)成功；此前62项前端单测、6项真实副本浏览器及后端定向检查通过，本次标准发布重新完成类型检查/正式构建，实际索引、36份资源、健康200和监听进程归属通过。

当次两库已备份并迁移到`c7d4e2a9b1f3`，原集采合同/发票/付款表计数及内容摘要保持；正式新增结果查询及271条合同默认排序只读核验通过，未重录业务或调用i8。当次资源`073aaedd1b16`，回退`8e4512ce31b1`；具体备份、首次预检兼容问题、原始发布回执与未验边界见[上线回执](../.scratch/jc-ledger-refinements/deployment.md)。当时保留8065副本预览，未将技术验证当作正式库GUI业务验收。

## 11月5日i8会话复用与加载交付记录

共同范围与验收沿[正式规格](../.scratch/browser-session-loading-20261103/spec.md)，[总票475](../.scratch/tails/issues/TAIL-475-i8会话复用与稳定加载.md)为入口，[实施票索引](../.scratch/browser-session-loading-20261103/ticket-plan.md)仅导航，各原票持有状态。接手目录、运行编号和资源回[交接](../.scratch/browser-session-loading-20261103/handoff.md)。

2026-11-05，加载线的[欠款样板](../.scratch/browser-session-loading-20261103/evidence/TAIL-477-acceptance.md)及[其余页面代表](../.scratch/browser-session-loading-20261103/evidence/TAIL-478-481-acceptance.md)技术验证完成；提交`90720465`已按用户授权正常推送本任务分支并核远端SHA，[Frontend checks](https://github.com/lysyscy/mtrl-workbench/actions/runs/41876511391)成功。未部署，验证副本均已正常退出并清理自建schema。

用户已明确“日常抓取能用才算能用”：现有按钮必须无需Agent中转直接复用Edge。2026-11-05用户完成固定扩展安装后，[真实日常验收](../.scratch/browser-session-loading-20261103/evidence/TAIL-476-daily-live.md)通过：原工作台按钮抓取2026-11通知书17条、写入测试副本17条，逐条读回一致；观察无登录、强踢或跳转，已断开并清理副本。证据`5c573d21`已推送、远端SHA一致；[累计审查发现](../.scratch/browser-session-loading-20261103/evidence/review-closure.md)已修，产品候选`fcc1512a`的[Frontend checks](https://github.com/lysyscy/mtrl-workbench/actions/runs/41891441704)成功。六张实施票及总票技术完成；其它业务端点未扩大现场覆盖。当时尚未部署，随后正式加载结果见下段。

2026-11-05 08:59用户随后批准提交推送并重启，[正式加载](../.scratch/browser-session-loading-20261103/deployment-20261105.md)已完成：master产品`797dfe36`已推送，标准publish/restart为loaded，42份资源、实际索引、健康200及8000监听归属通过；正式i8页面新入口可见。部署过程中修复发布器旧产物目录限定，复用既有归属校验并通过28项发布/恢复检查。上一资源保留可回退，未迁移、未改正式i8站点、未执行正式业务抓取；无关未提交内容保持。

## 已关闭的性能优化

2026-11-03，用户确认关闭两个effort：机械页性能优化已于11月2日加载`fbb42d23`；全站性能优化TAIL-464–472均done，已于11月3日11:19加载`8e4512ce`。类型/构建、相应后端及真实副本代表、独立审查和正式资源/健康/监听核验已完成。当次正式资源`8e4512ce31b1`，回退`fbb42d23b0e3`；未进行现场人工交互验收。源码现已随油卡整合进入master。

两effort的临时预览、schema、工作树及构建已退出，受管证据已按原保留期结项，在用正式与回退包保持。部署原始回执分别归`.artifacts/archive/frontend-release/20261102-mechanical-performance`和`20261103-site-performance`。诊断、规格、各票结果、全部失败/未验边界及关闭前材料从Git提交`642725be3d8fcb157dbeb0b66ed205f2fb758869`的原路径`.scratch/mechanical-performance/`、`.scratch/site-performance/`及TAIL-464–472追溯，已退出活动目录。后续新问题按具体缺陷处理，不默认恢复性能effort或追加全站验收。

## 新项目机械费累计接续与空取数修复已正式加载

2026-11-02，核实旧历史入口退役后仍依赖累计参考，且首次全空i8来源未列候选。修复分支`codex/mechanical-derivation-fix-20261102`已补逐项目累计起点初始化、月值/逐列采用版本签名及来源检查状态；未知累计显示已录入金额，缺i6不遮已采用i8，首次无记录不写零快照。定向后端回归、前端接口单测、类型检查/构建和真实可丢弃副本正常保存/刷新回读通过；独立审查的旧月补类别、初始化前采用及并发新月漏计均已关闭。原明细、月额和已采用i8保持。

按当次用户确认已在一个事务补齐兰考、茂名零起点，并按原9月年度汇总表接续宜昌累计及固定i6；独立只读事务核三项目回读、原事实签名及源文件哈希。正式依据归各自`history`记录，短期计划与回读归已结项30天的受管证据组`mechanical-cumulative-20261102`。真实验证副本、schema与临时构建已退出，界面证据归`.artifacts/archive/mechanical-cumulative/20261102`。

2026-11-02 12:29，正式`/app`及后端已加载`e822612e`，修复提交已推送并核远端SHA，现已整合到master。[Frontend checks](https://github.com/lysyscy/mtrl-workbench/actions/runs/41388592235)通过；标准发布重新完成类型检查与正式构建，实际索引、37份资源、健康200及监听进程归属通过。正式HTTP `/api/m06/workbench`已返回新增累计起点合同，兰考/茂名/宜昌累计及固定i6与既有业务回读一致，后两项目i8当时仍为未知。当次资源为`var/frontend/releases/e822612e221b`，回退版本为`67a6dd171324`；回执归`.artifacts/archive/frontend-release/20261102-cumulative-continuation/reports/deployment.json`，临时发布构建已退出。本轮部署未迁移或重复补写业务数据，未重新抓取i8。

## 机械费显示项目复用已正式加载

2026-11-02 11:28，正式`/app`已加载`67a6dd171324`：机械费“显示项目”复用导出台账的`ProjectSelectionOrder`，共用勾选、全选/全不选及上下排序，显示名单与导出名单仍独立；清理旧列表样式并修正机械弹窗对复选框标签的样式覆盖。此前同一源码的22项前端单元检查、2项真实副本界面检查、1920/390宽度及1.12字号实看、CI均通过，本次沿标准发布入口重新完成类型检查和正式构建。实际索引、37份资源、健康及服务进程归属通过；回退版本为`eb4529129135`，未迁移或写入正式业务数据。发布回执归`.artifacts/archive/frontend-release/20261102-display-projects/reports/deployment.json`，界面证据归`.artifacts/archive/mechanical-display-projects/20261102`；本轮临时构建退出。

## 机械费旧明细衔接修复已正式加载

2026-11-02 09:45，正式后端已从主线基点`e296e816`加机械费修复`db54e008`重启加载；修复分支`codex/mechanical-derivation-fix-20261102`已正常推送并核远端SHA，现已整合到master。旧版仅存明细而缺整月金额载体时，同事务补齐零租、包月两类，已有手填空值和0保持保护。最终部署基线上的机械自动保存、技能录入、工作区及过程确认四文件回归通过，独立复核无实质发现。正式健康、37份前端资源及监听进程归属通过；当时前端仍为`eb4529129135`。回执在本机受管证据组`094452-330376-10660/files/reports/deployment.json`。

此前机械费缺失月值已按原明细补齐，部署后只读核对原明细及批次与月值一致。当次部署未迁移正式库或加载油卡功能。油卡分支及未提交内容保全在本机`var/worktrees/oilcard-management-20261031`，主根原无关文件也保留，212份文件哈希核对一致；清单归`var/state/worktree-preservation/oilcard-20261102.json`。原油卡试用schema、owner及恢复材料原位保留；当次未迁移或恢复试用实例。

## 油卡管理开发及隔离验证已完成

2026-10-31，已批准TAIL-453～463均完成技术验收、保存推送并done。业务及累计基线见[油卡需求](requirements/oil-cards.md)和[规格](../.scratch/oilcard-management/spec.md)，原阶段源码/资源及未确认边界见[接续登记](../.scratch/oilcard-management/handoff.md)，各原票及证据仍为进度主人。原实施分支为codex/oilcard-management-20261031，开发总票452现已关闭。累计独立[双轴审查](../.scratch/oilcard-management/evidence/final-review.md)已闭环，Spec一个P1已修、未关闭0；当次自建预览及schema均退出，8000/8801和无关成果保留。

首次接续核对工作簿已生成170项待核问题，真实309来源证据在专用副本中全为待确认、未计账；详见[463验证记录](../.scratch/oilcard-management/evidence/TAIL-463.md)。开发与隔离演练后，现已完成合并及正式加载；人工业务确认与真实接续归TAIL-474。共享筛选仅本期充值/发票消费，不扩为全站推广。

2026-10-31的[试用界面整改](../.scratch/oilcard-management/ui-revision.md)及后续三项评审反馈已随油卡整合上线：档案并排、油卡归档、格内维护、单一改票/可撤销删除及总台账。原用户试用数据、恢复点及构建继续保留，当前实例按接续登记核实，不与已退出的453–463可丢弃验证schema混用。


## React重写已验收，旧壳已退役

用户2026-10-28明确签收当前已上线React重写；[TAIL-423](../.scratch/tails/issues/TAIL-423-正式入口切换与运行核验.md)为done，后续具体问题按正常缺陷处理。

[TAIL-424](../.scratch/tails/issues/TAIL-424-旧前端退役与清理.md)为done：旧壳16件、入口与静态路由已退出源码并完成正式加载，混合测试保留有效后端检查，两棵冻结工作树在必要本机资料和证据保全后退出。原重写活动材料及已关闭任务票按Git追溯，423/424保留切换与退役回执。

2026-10-29 19:11，正式8000 `/app`已加载`eb452912`：修正通知书金额与集采备注保存时的横向跳动。根因是手调列的新定义先携自动min/max被AG夹紧，再由异步事件放宽并恢复手调宽度；现在React在发布前套用手调边界，删除命令式columnDefs重写，原生ColumnState仅应用实际差异。补齐首次拖窄时的flex交接及勾选控件不应阻塞列定义更新。完整列表、1.12字号、低于自动下限的持久手调列下，两条保存检查旧版明确失败、候选通过；首次拖至50px、重载/缩窗、账号隔离/复位、跨位数输入共6项定向GUI通过，类型检查、构建及CI通过。正式健康、37份资源及进程归属通过；发布回执归`.artifacts/archive/frontend-release/191055-669463-16440/reports/deployment.json`，红绿及补测证据归`.artifacts/archive/horizontal-save`。自有预览、schema和work已退出；未写生产业务或调用外部i8，不把这次具名覆盖扩称为所有交互均无位移。

2026-10-29 18:15，正式8000 `/app`已加载`cc5ea580`：共享表格数据改为AG Grid按稳定行ID直接增量发布，普通数值保存复用布局；删除测量后才发布数据、连续/离格拟宽、flex冻结恢复及自制滚动锚点。付款日期使用TanStack Query保留上次数据，核对中不插入状态行，当前日期核对完成前仍禁止提交；UUID统一采用官方uuid安全随机回退。公司汇总两类内租按用户新裁定离格/回车自动保存，删除两按钮和额外确认流程，保签名、采用和未知回执保护。旧版真实副本逐帧捕获过过程前格回旧值和付款日期高度变化；修复后22项单元检查、12项定向GUI及CI通过，含连续三格逐帧、保存期主动滚动、日期核对几何、跨位数列宽、手调/复位/缩窗、内租及丢回执保护；浏览器模拟缺randomUUID仍实际写入付款副本且不重复提交，未直接操作另一台电脑。正式健康、37份资源和进程归属通过，发布回执归`.artifacts/archive/frontend-release/181530-791537-21144/reports/deployment.json`，基线和候选证据归`.artifacts/archive/stable-editing`。全部自有预览、schema及work已退出；无生产业务写入、迁移或外部i8调用，不宣称全站所有操作均已人工验收。

2026-10-29 17:20，正式8000 `/app`已加载`b292cdc9`：普通行内保存静默，过程资料焦点说明和输入后新增提示行移除，取消修改留在固定工具行；共享保存队列在可靠读回后才撤掉已提交草稿，保留后续输入及未知回执锁。常规保存仍统一标脏缓存，仅立即重读当前工作区和操作历史，其他页面激活时更新；独立操作成功消息改为底部居中浮层。类型检查、构建、17项单元检查、CI及8项真实可丢弃副本定向GUI一次通过；通知模拟成功仅验证位置和表格几何，不实际剔除。正式健康、36份资源及进程归属通过，发布回执归`.artifacts/archive/frontend-release/172029-190911-34852/reports/deployment.json`；GUI与通知证据归`.artifacts/archive/quiet-editing/20261029-integrated/reports`。预览、临时schema和work已退出；无正式业务写入、外部i8调用或数据库迁移，未做全站回归，不据此宣称整体性能提速。

2026-10-29 16:31，正式8000 `/app`已加载`f7d903d0`：i8接入层新增电信、联通和内网服务器选择，复用现有设置接口、账号/版本校验及保存后缓存失效，正式当前选择未自动改变。类型检查、构建、CI通过；仅可丢弃配置副本实际保存联通/内网并从设置与连接配置接口读回一致，未访问外部i8。正式健康、36份资源及服务进程归属通过，回执归`.artifacts/archive/frontend-release/163053-304587-29724/reports/deployment.json`，GUI证据归`.artifacts/archive/i8-server/20261029-selector/reports/gui-server.json`，临时预览及work已退出。

2026-10-29 15:58，正式8000 `/app`已加载`828740aa`：通知书删除常驻统计和剔除/恢复的操作常识说明，普通成功改为不占布局、约3秒消失的App消息；缺失记录、归属未匹配等部分结果与失败保留警示和核对入口。类型检查、构建、CI、46项后端定向检查及1项首页既有回归通过；真实副本页面用拦截响应核成功/部分成功/失败呈现，成功提示前后表格Y均301px，未实际剔除、付款或调用i8。正式健康、36份资源及服务进程归属通过，未迁移或写正式业务数据。发布证据归`.artifacts/archive/frontend-release/155823-913189-6264/reports/deployment.json`，页面证据归`.artifacts/archive/notice-feedback/20261029-compact/reports/gui-feedback.json`；临时预览及work已退出。

2026-10-29 15:01，正式8000 `/app`已加载`d149881b`：通知书与集采区分自动/手工列宽，项目选择显示12项并使单选顺序跟随档案，修复批量付款方式文字遮盖及“周转物资”分类映射。真实副本验过代表列首次拖窄、放宽、持久化、复位、金额下限、项目顺序与付款方式显示；前端17项单测、构建及后端23项定向检查通过。用户重申不投入额外键盘操作工作，本次追加的键盘处理已撤回，未继续键盘验证。最终发布健康、36份公开资源散列、实际HTTP连接的服务进程归属通过；未执行迁移、正式业务写入、付款或i8调用，未做全站回归。发布回执归`.artifacts/archive/frontend-release/150038-375428-20160/reports/deployment.json`，副本交互证据归`.artifacts/archive/column-widths/20261029-verify/reports`；临时预览已停止，work已释放。此前机械费四表与逐月台账导出修正及真实下载核验继续沿用`.artifacts/archive/frontend-release/134934-355192-11780/reports`证据。

2026-10-29 15:35，按用户新裁定追加加载`5ed0045f`：通知书、集采及其已启用子表的可拖业务列取消手动业务min/max，金额、编号和状态控件同样由用户决定宽度，仅保AG原生技术底线；自动建议布局及固定不可拖列保持。原金额手动下限验收不再适用。类型检查、构建、2项定向单测及对应CI通过；真实副本存档情况113→50、存档号73→50、审批金额109→50，刷新保持50且复位回原宽。无业务写入或键盘专项。正式健康、36份资源与服务进程归属通过；发布回执归`.artifacts/archive/frontend-release/153448-089471-9116/reports/deployment.json`，GUI证据归`.artifacts/archive/manual-widths/20261029-unrestricted/reports/gui-unrestricted-widths.json`，临时预览及work已退出。

## 后续工作

[TAIL-450](../.scratch/tails/issues/TAIL-450-架构差额后续实证与深化.md)于2026-11-06完成有界整改并done；P1事务/严格停止、P3读契约、P4纯工具隔离及默认金额截断已修复，P2沿用已完成子票，其余候选有明确保留/暂缓结论。[实施与验证](../.scratch/audit-remediation-20261105/implementation.md)已本地保存；按用户要求不推送，未部署，不改变顶部现行服务指向。

## 集合筛选研究（暂存参考）

[可行性研究](../.scratch/share-feasibility/research.md)已完成官方接口与合成小样验证。用户2026-10-28确认只是了解、当前先不做，本effort原地保留，未进入实施排期。
