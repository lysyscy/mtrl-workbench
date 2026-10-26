# React 当前验收与复测证据

当前范围、批准与验收归[共同规格](spec.md)，大表分月决定归[当前确认](questions.md#2026-10-26大表分月口径已确认)。本页只保仍供验看/复测消费的结果和来源；本机原始输出不随Git提交，旧通过数不代表最新版本已经验收。

## 通知书页最小视觉试点

PH-20261026-notice-visual-01已人工恢复；基线`18842da8`，设计文档`193b8b97`，页面`17340172`及金额输入强调修正`e9e47fe4`。已在原8065加载`e9e47fe4`产品，等待用户视觉确认；未推广全站或恢复449。自查范围为基线至当前的通知书样式和展示文案，局部可逆且未改业务逻辑，采用自查与实际浏览器验看，未新增永久测试或冒称独立审查。

- 先写设计文档局部试点，再固定原源码/完整在用构建清单。只改notices.css/tsx，沿原主题角色、MiSans及字号档位，轻边界、小圆角、弱阴影、表头/关联状态12px及精简文案；本次付款输入有主题强调底色和500字重。表格字段/列序、导航、业务入口、关联按钮完整名称与状态及两步弹窗保持，弹窗实现未改。
- 原run `.artifacts/active/react-writable-preview/20261025-admin-i8`的owner/version为实际运行主人；最终构建`work/notice-visual-20261026-final`，原`work/project-picker-shell-fix`保留。`registered_preview()`已核进程、HTTP、完整资源和产品输入；不新建schema、不seed/重拷/迁移、不触及8000。
- 指定Node24.22.1、pnpm12.15.0下typecheck/build退出0，原件`logs/{typecheck,build}.log`；首轮误取宿主附带旧工具链虽退出0但有engine警告，保留`logs/notice-visual-{typecheck,build}-initial-toolchain.log`，不作为最终环境证明。初轮Impeccable检测为空、退出0（`reports/notice-visual-detector.json`）；随后仅修正金额样式优先级并通过最终构建和实际computed-style核验，不把初轮检测伪称覆盖最终新增差异。
- IAB由原根入口、侧栏到通知书，1280×720真实长数据，实际核246条当前列表、全部18列定义、勾选摘要和清空、供应商关联进入第一步/第二步后取消、金额会话内编辑再恢复原值与明确编辑外观；未提交关联/付款/分类/打印/i8动作。深色主题与最大1.4字号查看控件换行、表格/页面滚动后，已恢复原中性浅色/标准字号并重读。截图在同run `screenshots/notice-{before,after,dark,dark-large}.jpg`及`notice-association-step2.jpg`；before/after同视口、主题、字号和筛选，未作性能对比。最后金额强调修正仅在默认主题重验，其他样式未变，复用此前深色/字号观察，不称全主题矩阵或449通过。
- 换装前后38表集合一致、37张非账号表摘要全部一致。user_account摘要含正常本地登录及临时外观试验，主题/字号已恢复；未把它写成38表逐字节不变。`reports/notice-visual-preservation.json`为最终摘要；原始修改前摘要在`recovery/notice-visual-20261026/data-fingerprints.json`。
- 快速回退入口及守卫回[交接](handoff.md#当前验看与快速回退)，`logs/notice-visual-rollback-check.log`退出0；只读检查通过，未执行apply完整往返。原构建/最终构建、回退脚本和截图保留供本次用户验看，两个本轮中间构建及临时工具链shim已退出。静态demo保持既有待用户对照用途，本轮未增第三个预览。
- 目录检查仍有独立未通过项：`workspace_check --effort react-writable-preview --phase active`退出1，扫描到既存`.artifacts/archive/notice-association/20261026/{20261026-final,20261026-validation,20261026-verified}`临时目录分类及缺retention元数据。未改该历史原件或检查器；本次页面/构建/原run检查可复用，**全局归档治理检查保持未通过**。原件`logs/notice-visual-workspace-check.log`；不将它算产品失败或掩盖为全绿。

## 表格稳定与MOD05拆页

本轮实施基点`d927de0e76b84206c2e09c2894fac7c4e1978b02`，用户已确认完整方案及原8065更新授权。已实现并加载，停在用户实看；当前行为回前端设计/付款需求，实际运行仍由下节唯一owner持有。没有新增schema或另一预览，也未执行真实业务保存/撤销、i8外呼或实体打印。

- 修复前真实复现：搜索34→1条导致流水420→124px；切欠款项目535→177（加载）→427px，下方流水往返但节点/opacity保持；取消drop的连续拖拽测得每行最多4个叠加动画。修复分别处理三个已证机制，不称同一根因，也不把自动测高当作已定位根因。
- 初轮新增回归非零，旧标题/未拆页断言失败；此前真实几何测量已证明搜索高度缺陷。首轮构建取到内置旧Node/pnpm，之后用本机Node24.22.1/项目固定pnpm12.15.0重新typecheck/build通过。原件为原run `logs/table-stability-red.log`、`logs/drag-motion-before.json`、`logs/{typecheck,build}-initial-toolchain.log`；不抹除失败和工具链警告。
- 最终6项只读浏览器回归通过（29.46s），显式排除1项真实备注保存用例：主表高度/筛选跨页保留/列宽，桌面与900宽度加载占位不显示旧项目，台账内容与金额可读，浏览器本地拦截保存的草稿/跨页导出guard及API原值回读，通知书直接定位不加载欠款页。最后表头最小高度对齐现有32px按钮后，受影响3项几何/加载定向补验通过（16.45s）。日志分别为 `logs/table-stability-browser-final.log`、`logs/table-stability-alignment-final.log`；不是9个不同用例。
- 取消drop拖拽复测每行最多1个并发动画；1920×1080、1366×768、900×900布局检查通过，最终截图为原run `screenshots/{debt,flow}-table-stability-final.png`。另实测双侧表头对齐、按月统计图筛选流水及取消恢复，见 `reports/table-stability-preservation.json`。取消拖拽未发出排序保存；本地拦截的台账保存未到达后端。没有宣称全站所有页面/全部字号/实体IME/真实写入均通过。
- 七个界面源码Impeccable机械检查退出0、无发现，原件 `reports/table-stability-detector.json`。独立Standards/Spec均已收拢、无未关闭发现；Standards指出新增测试使用客户端派生key定位API原行，已改为record_id/row_kind/month并经原审查者复核关闭及最终测试通过。摘要 `reports/table-stability-review.json`；最后只读最小表头尺寸修正复用其余有效审查。
- 最终release构建的完整资源、前后端输入、HTTP及进程身份已核；沿原run/owner/schema/revision/私有状态原位更新8065。更新前后38表集合不变、37张非账号表逐表摘要一致；user_account摘要随本地正常登录改变，未将它计为全表内容完全不变。原始摘要 `reports/table-stability-before.json`，最终核验 `reports/table-stability-preservation.json`。试用库未重拷、重建或迁移。
- 本轮三个未投入使用的中间构建已核无消费者后删除，原回退构建与最终在用release保留；本run仍为用户验看主预览，当前截图/日志继续由它持有。源码提交、远端SHA、服务加载和用户验收分别判断；本轮正常保存沿既有授权，用户实看及正式切换尚未完成。

## 当前真实副本与治理执行

用户2026-10-26批准文档生命周期方案及N1–N6，React改造基点`8629a33df9d182669b70c29f7c5ec2deceecd49f`。个人方法最终源`0b251b0286ff8508f18ae1924c00171cb3a3c971`的[精确CI](https://github.com/lysyscy/My-Skills/actions/runs/40256562119)通过；179项本机检查完成（其中4项原平台条件跳过），结构核验通过。官方Manager原位更新、完整本机资源/原ID/标签/Preset/部署集合、更新检测及远端备份均已核验，备份`a2568470cc7090c076cbbc6324166772dcc18d1c`。当前任务已实际读取安装后规则并在原规格采用；其他实体设备及宿主重载未实测，新设备恢复后须按官方Manager update/check校准。包核验原件由主检出本轮`.artifacts/archive/docs-lifecycle/20261026/reports`持有。

唯一用户试用归属为`.artifacts/active/react-writable-preview/20261025-admin-i8`，当前实际进程、端口、schema/revision、前后端输入及构建都查该run的`reports/real_owner.json`、`version.json`和共享current指针；不复制PID或Cookie会话值到本页。用户副本已从c432261023仅目标升级至bmonth261026，升级前后37张原有表内容/行数摘要一致，`reports/target-upgrade.json`保存恢复点目录校验及摘要；未重新复制生产覆盖试用修改。私有配置/i8会话与用户数据在停止时保留。原始准备的33表/32序列与16非壳项目台账核验、初始计数只证明当时快照，不能当用户修改后现值。

原8066/8067模拟预览已逐一核PID、创建时间、命令后从原入口正常退出。自动写入验证先停并保留用户实例，在同一8065端口串行使用可丢弃真实来源副本；这些副本停止后只清自己的schema。验证副本均已正常停止并核自有schema删除，原用户试用入口已恢复。恢复后36张非账号原表摘要与升级前一致，账号内容对私有恢复点复核仅正常登录时间字段变化。当前状态以owner与最终回执为准，不能把验证副本误当用户数据或冻结性能条件。8000正式服务不在停止/迁移范围，本轮无新的真实i8或物理打印动作。

### 本次验证与覆盖边界

本轮原件在`.artifacts/archive/frontend-vue-rewrite/docs-lifecycle-20261026`。最终类型/完整构建日志归用户run的`logs/{typecheck,build}.log`，产品输入和完整资源清单归version；纯文档提交不要求重建。预览工具守卫/复制合同13项通过，覆盖跨进程/跨端口排他、异常释放、旧factory退役、缓存写入授权不能跟随新实例、HTML输入、待用构建不阻止正常停止、只读一致复制/投影/序列及旧结构复制后仅升级目标、已知全部i8/物理打印入口阻断。

最终真实浏览器41项与纯算法1项共42项通过（0失败/错误/跳过，203.209秒）；真实页采集器及其纯/保护检查13项通过（6.481秒），不等同完整84组。结果由`reports/real-release.xml`与`logs/real-release.log`持有。最初真实浏览器40项为29过/10失败/1连带路由错误，定向修复11项后8过/3失败；下一轮41项37过/4失败，原非零日志及XML均保留，不能概括一直全绿。费用同月同名多记录代表随后定向2项通过（26.21秒）；首次指定旧浏览器路径的2个装配错误及复用现有浏览器后的通过原件均保留。失败分别按实际接口包装、控件定位、页内导航、异步就绪与请求缓存归因，必要独立运行链问题另修并保反例。

| 退役的固定样例组合 | 当前有效保护与本轮取舍 |
|---|---|
| 历史台账金额、归属、同月多行及token组合 | `test_historical_balances.py`等域/事务保护仍在；真实浏览器保连续保存/焦点、未知回执、普通月备注、实际撤销/重做与下载范围。 |
| 集采金额/日期/重复付款/关联组合 | `test_acc_jc_domain.py`、`test_acc_jc_pay_link.py`、`test_jc_payment_terms.py`及`test_jc_exports.py`承担对应域/接口/文件组合；真实浏览器保字段与子表写读、子表未知、草稿往返、精确筛选排序ID及真实XLSX。 |
| 大表派生金额和模板组合 | `test_acc_rpt_big.py`、`test_big_export.py`及分月操作历史保护仍在；真实浏览器保宽度、按月固定/继承/POST导出，以及暂停和丢响应时历史/名单保护。 |
| 库存筛选、金额与调整原值组合 | `test_acc_inv.py`域保护仍在；真实浏览器保本地筛选及同一稳定行的调整保存/读回/撤销，原始金额不改。真实源XLSX缓存导出未验单列，不能由表行证明缓存存在。 |
| 费用月度金额和用户管理组合 | `test_acc_fee_mon.py`、`test_acc_usr_mgmt.py`、`test_acc_usr_admin.py`、`test_react_appearance.py`保其实际纯/域/进程内部分；旧壳ui_page断言不冒充React。真实浏览器保原费用记录ID/月份/其他记录不变、权限及账号外观隔离。 |
| 粘贴编码例外 | 原匹配函数原样移入既有notices-api，纯计算直接执行真实函数覆盖非法月份/部分号/重号/重复/已付清/剔除/撤单；Vite不监听HTTP、不渲染页面。浏览器保真实单据正常勾选。 |

未用合成业务数据补场景：真实能力探测核32个项目年度范围（2025/2026）：未见同展示名不同仓库机械跳转及年度费用同名自动/手填非零并存；同月同名多记录实际存在，费用代表已优先选用。正式来源确有10份库存XLSX缓存，本轮未复制缓存并核其浏览器导出，故该文件链仍未复验；手动通知书/合同新增、费用新增和外观未知回执等独立状态机本轮未新增真实浏览器复验，不称被字段保存等效覆盖。实体IME、全主题/字号与200%宿主缩放、实体打印、真实i8/生产业务写入和用户全站试用仍未验。本次不重跑84组性能矩阵。

## 445–448界面与分月增量

UI批累计起点`f15d4b8d33ff63485bfc2295e31fdc89499a3a8e`；445–448技术实现/技术验证和当前人工验收分别回原票。原UI候选的合成结果仅为历史证据，按最新真实副本约定不再开放其HTTP样例。用户已确认447名单/排序分月、继承/固定/归档边界，原全局名单只作基线；当前业务唯一正文在材料报表需求，不再保“待裁定”旧结论。

历史UI原件在`.artifacts/archive/frontend-vue-rewrite/ui-polish-20261026`：A首轮57过5失败及修复复测，B19过、费用最终9过；项目丢稿/Esc未知解除/可靠GET旧值丢稿、自动费用同名额隐藏、搜索漏列和新增行未成行的红灯→修复→定向通过保原日志与原两轴发现。不把多次有效覆盖相加伪称单次全过；最终项目5项10.32s、合同7项30.91s及费用离线35项只对应当时固定输入，当前真实验证另计。

月度增量原件在`.artifacts/archive/frontend-vue-rewrite/big-month-selection-20261026`：独立类型/构建通过，分月读写、继承/固定和POST导出、丢回执/暂停保护按各次修复后选择有效结果；`reports/backend-execution-receipt.md`区分早期67项工具输出与持久原件，`logs/backend-output-isolation-final.log`及对应XML才是最终21项原始通过记录。旧版→新版→降级→再升级的原名单/手填保全回原迁移回执，不外推为正式库已升级。

旧workspace active曾因architecture-repair文件名退出1，原`ui-polish-20261026/logs/workspace-active-final.log`及月度run的`reports/workspace-active.log`保留；本次知识归位并修消费者后才处理原文，不改检查器/白名单把旧失败说成通过。

## 历史性能复测来源

这些版本/数据身份用于已接受退化的追溯和最终候选复测，均为历史，不说明现在有额外服务。冻结原副本保持原修订与38表指纹；真实业务副本升级不改它。原始证据保留窗口仍按已有2026-11-24约定，不因整理整棵续期。

| 固定历史输入 | 原件及限制 |
|---|---|
| 422签收3197ff1 | `.artifacts/archive/react-tail422/20261025-01/reports`。旧主线e55ff048与React在同合成schema/账号/Chromium、1920×1080/DPR1、交替三轮比较；index cfa44d699913a59290f77bf51d61921f53ab810456e3a9aef512ea107e5ee698。新版冷项目/首次通知与滚轮帧明显退化，用户收到结果后签done；不代表性能修复或正式切换。该旧合成条件不再作为可开放预览。 |
| 98d2d66完整基线 | `.artifacts/active/react-performance-baseline/20261025-full-98d2d66/reports/{baseline.md,samples.jsonl,summary.json,api-direct.json,environment.json,resource-sizes.json}`。index bb2d734a60afd358c617ac4b38bfc4b8f83e6eefc4a68c42d3f0b52935a8d840；manifest dd60831310cae73cebe22cb4e44e452857578cccb3ac969551478601bf7eca34。固定旧真实副本c2a261023/38表，非当日生产新鲜度承诺。 |
| 5dc133e7优化后 | `.artifacts/active/react-performance-polish/20261025-435-440/reports/{delivery.md,samples-final.jsonl,summary-final.json,environment-final.json,comparison-final.json,api-final.json,version.json}`。index 250bf8addaa047a5786b49591767c7d9d8423d5556d7af23ef31fa6cf9a85037；原基线未改。 |
| 09697808流畅度后 | `.artifacts/active/react-smoothness-implementation/20261025-442-444/reports`，delivery/version/data-unchanged及samples/summary/environment/comparison-final-r2。index 89ad45e8b928320d90f39e5196b54fa1c61566511c9c8383c05d43d0430d2c18；manifest 6f519b0fe7298e27731757e070ff262534a041c41b46c348aeb077a0d53f0ede。 |

上述三真实基线同旧副本19项目/1193通知书/265合同/18198库存，38表前后指纹一致。Chromium156.0.8078.4/headless、1350×940/DPR1、zh-CN/Asia-Shanghai、默认主题/标准字号、无人工限速，14入口各3冷3热共84组。就绪是标题/networkidle/fonts/双rAF代理，主线程另含约100ms观察排空，不是现场INP、热SPA LCP或Lighthouse TBT。

09697808的84组无脚本/HTTP/资源失败，但warm ledger/big/rules首条FontFaceSet仍loading，只能称81条loaded；原样保留这3条。40交互原件interactions-before-clean/interactions-final-r2：输入148→96ms、清筛选240→164ms，无API；insertText非实体IME/RUM p75，导航两帧包含约11MB自动化响应体传输，不当用户延迟。热库存518→385ms但仍有356–713ms离群；付款417→453ms未改善，规则冷CLS中位.218/最大.342等残余及较差样本保留。API仅顺序5次，库存410→417ms不称后端优化；普通MiSans完整Regular回退约6MB仍在。最终候选仍需按届时变更补验，不用历史签票覆盖。

## 历史交互诊断

2026-10-25诊断只用于解释442优先级：固定只读历史副本、Chrome156、1350×940，先加载库存。原件`.artifacts/archive/react-smoothness-research/20261025-diagnosis/reports/{interactions.json,interpretation.json}`及traces保留至2026-11-24。仅前4动作窗口有效，后4导航未等接口/懒加载就绪，排除归因。全部期间、输入“钢”、清筛选最长任务254/190/228ms，getElementSize自耗时约133/106/114ms，自动行高链归组130.25/104.42/110.73ms；只见12/24渲染行DOM（含固定副本），有效窗口无API。setupCellAutoHeight→setupAutoHeight→setComp支持该次热点，不外推全站唯一根因。脚本insertText可能interactionId=0，非实体IME或有效INP；少量动作和profiling开销不支持RUM p75或无Profiler绝对耗时承诺，自动两帧不作纯浏览器响应指标。初次observer失败日志保留、不计通过。

## 本轮资料处置

预览指南的独有知识已归现行业务/架构/设计/部署主人，旧外观访谈退出、当前月度确认保留。architecture-repair和research的独有信息/活动引用处理后以Git原路径追溯；原审计156个连续区段已核职责、独有知识和活动消费者，报告已从当前树退出，原文均可从8629a33及原路径恢复，不建关闭索引。独立Standards/Spec两轴对同一累计范围均无实质发现；运行/资源收尾由主Agent另核，不把审查代替现场。旧模拟run与临时真实验证run已退出work，原件移至既有frontend-vue-rewrite归档，沿既有2026-11-21期限，不整体续期；冻结性能原件保持其原2026-11-24用途/条件。用户run仅保当前构建、统一薄启动/停止入口、私有状态/数据及升级恢复点至试用结束裁定。整个React effort仍有用户验看、最终候选、423/424等活动范围，没有冒报已关闭。

## 通知书供应商与合同统一入口

2026-10-26用户先接受现有两弹窗合并模板，再确认第一步参考侧栏、下一步合同预览、多供应商滚动候选，最后明确“OK，按这个落吧”。实现提交`5ceff8d1`：主表统一按钮显示完整供应商与关联状态；两步共用固定外框，第一步仅筛选，可单独记住未关联供应商，第二步保留既有合同/发票/推荐和金额核对。关联合同决定供应商；后端锁行核项目/分类/有效状态，历史不一致关系仍可读取。撤单/剔除保留查看和解除，解除后供应商保作待关联线索。不涉及TAIL-449，不迁移或重启正式8000，不发起i8/打印外呼。

实际验证：TypeScript及官方离线构建通过；定向后端27项（推荐、双向/更换/解除、金额、自动关联、批量取数、草稿/供应商权威/状态保护）通过，供应商历史撤销的现有参数用例另通过。真实副本浏览器两条代表路径分别通过：实际保存后强制503回执失败、锁定与可靠读回、实际关联/解除；真实6命中供应商的滚动单选、不取第一家、取消不落库，以及1366×768两步坐标/尺寸一致且底部操作可见。未伪造业务响应；503只破坏实际保存后的回执。最初几何断言读到入场过渡中间值，改为等过渡结束；六候选实机检查暴露旧输入100%宽度覆盖，已修正为16px并由回归保护。另一次虚拟表定位超时改用公开搜索定位，未放宽行为断言。

独立Standards/Spec双轴以开工HEAD`8dd15f16`与本次全部修改/新文件为范围。Standards指出未知回执保护缺口，已复用uncertainWrite并保持锁定至可靠读取，原审查者定向确认关闭；Spec无实质遗漏。Impeccable本次三UI文件检测返回空结果；真实提交钩子的语法、字节和凭据文件检查通过。

原8065用户run仍为`.artifacts/active/react-writable-preview/20261025-admin-i8`，实际构建`work/notice-association-final`，版本`bmonth261026`；进程/HTTP/产品输入/完整构建经registered_preview核验。恢复后、验看登录前全部38张试用表摘要一致；本次登录只按正常账号逻辑更新登录时间，不向试用副本写测试业务。原schema、用户试用修改和私有i8状态保留。原run/reports/notice-association-verification.json为本机核验回执。

三个一次性真实验证schema均经官方停止后核to_regnamespace为空，已释放其自建构建work，有限报告归本React工作树`.artifacts/archive/notice-association/20261026`。被接受的静态模板30959已退出，work/site释放；模板及最终原8065截图有限保存在主检出`D:/dev/mtrl-workbench/.artifacts/archive/notice-dialog-reuse/20261026/reports`，当前用户浏览器已转向8065正式弹窗。旧在用构建以owner为准，不删除其他任务或用户资源。

源码已本地保存，尚未推送：此前自动审批已拒绝将新增业务决定资料发布到公开远端，原因是这部分具体公开内容尚无明确授权；本次不重复发起同一推送。用户正式界面验收、合流、423切换与424退役均未代办。

### 取消误报与通用确认提示修复

2026-10-26用户指出未操作取消也提示，要求提示尺寸、标题、说明和按钮统一用集采台账通用版本。原8065真实浏览器两条回归先复现失败：自动单命中带入后取消未退出；提示仍为“放弃本次选择？”。根因是自动带入与已保存字段共用dirty对比基线，以及确认区继承两步窗固定高度。

实现将自动推荐的初始界面基线与已保存供应商分开；推荐仍须明确保存，不伪装成已保存。通知书与集采编辑器复用同一DiscardConfirmation，公共BusinessModal统一弃稿和轻量确认的420px字号缩放宽度、自适应高度、排版与间距，保留各业务操作真正需要的说明（如解除关联），工作窗本体尺寸不受影响。

原8065只读浏览器定向验证：自动匹配后未操作取消、下一步再返回后关闭、真实修改后的通用标题/说明/两个按钮与宽高对照集采版本、继续编辑保稿及多供应商往返。初次整段文字比较受innerText换行与textContent差异影响，改为按可见标题/说明/按钮逐项等值核对，不放宽内容或尺寸要求。TS/官方构建与Impeccable定向检测通过；本轮未写试用业务，不触发i8/打印、不新增预览或恢复449。运行身份和数据摘要核验归原run/reports/cancel-confirmation-verification.json。
