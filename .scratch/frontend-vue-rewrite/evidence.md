# React 当前验收与复测证据

当前范围、批准与验收归[共同规格](spec.md)，大表分月决定归[当前确认](questions.md#2026-10-26大表分月口径已确认)。本页只保仍供验看/复测消费的结果和来源；本机原始输出不随Git提交，旧通过数不代表最新版本已经验收。

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
