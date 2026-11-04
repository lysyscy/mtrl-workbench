# 稳定加载与 i8 会话复用执行交接

<!-- MTRL-HANDOFF-BEGIN PH-20261104-loading-i8-01 -->

## 交接登记

- 交接编号：PH-20261104-loading-i8-01。
- 源对话：01a19faa-1ec8-70c2-8d3a-11769ed8f3a7。
- 接手对话：01a1a5a9-0de0-75e1-af89-faf42b264768（hostId: local）。
- 状态：已接手。
- 当前修改权：接手对话 01a1a5a9-0de0-75e1-af89-faf42b264768；源对话已发送继续指令并停止修改。
- 目录：D:/dev/mtrl-workbench，同一已登记项目的 local 环境。
- 用户已确认动作：新建 Astra 统筹对话并开工，DSH 继续 DeepSeek V4.1 Flash；先推进 TAIL-476、477，477 完成后推进其余四票。
- 主对话请求配置：gpt-6-astra / high。执行子任务默认 DSH DeepSeek V4.1 Flash / high，实际模型与配置按当次工具返回核对，不擅自替换用户模型。
- 更新时间：2026-11-05。
- 最新有效状态（2026-11-05，优先于下方历史检查点）：候选已提交并推送`fcc1512a546608c31de0f3ad902880ed65d7d031`，远端SHA一致，CI41891441704成功。用户已明确批准安装固定包、开发人员模式、activeTab以及当前Edge站点2026-11通知书抓取，仅写可丢弃副本；随后明确希望Agent用Computer Use自行安装，因为人不在电脑前。授权有效，不能再写“待用户批准”。
- 安装仍未执行：当前Edge连接实例由3变4，原i8标签366065258仍为已登录业务页，已核可见账号/组织。原生窗口198336的getApp申请超时；随后浏览器工具对打开edge://extensions明确返回安全策略拒绝，并禁止用其他接口/界面绕过。因此不能转用原生Computer Use达到同一被阻止动作。已告知用户当前是工具限制，不是缺授权。没有安装扩展、没有真实抓取、没有新预览或数据库副本。
- 固定包c44568c2997b03de三文件散列重新核对一致。用户批准后的私有scope已创建在i8-daily-runtime-20261105/files/work/approved-notice-scope.json；只含月/站点/已核i8用户名，不进Git。首次创建遗漏父运行环境，嵌套登记遇锁失败未写范围文件；补齐MTRL_RUN_ID和MTRL_LIFECYCLE_OUTPUT后在原租约成功。后续若工具限制解除，沿已批准范围继续，不重复询问安装许可；实际安装入口仍须遵守当时工具策略。
- 最新接续点（2026-11-05 02:52）：第七轮扩展具名缺口已关闭，31协议测试和38隔离Chromium判据通过；主控补严格number代号后31项再过，完整集成回执/review-closure已更新。安装包已固定到主检出var/browser-extension/releases/c44568c2997b03de，三份文件SHA核一致，完整digest c44568c2997b03de594123eb1a243a90af80c227e3b3ccee0dc67acae4e233c6；属于待安装组件，不随测试日志清理。安装+当前Edge站点2026-11通知书日常入口验收已向用户异步询问，尚未收到回答时不得执行。范围见install-check-plan.md。当前无预览/活动DSH，准备提交推送候选；真实scope文件尚未创建。
- 最新接续点（2026-11-05 02:41）：两组closure修复已返回，主控四文件backend_verify退出0（组023713-386228-17256），统一构建通过，5项新前端GUI控制验证通过52.82s；预览exec90881已stop退出0，自建schema frontend_rewrite_397_25564e3c1ac84469913f1ceea6459575已清理。证据见TAIL-476-integration-final.md。无活动预览。真实安装/日常抓取尚未执行。
- 扩展回执存在具体缺口：execute实际未比较bound generation，bind允许缺identity，pending仅device未核sender。已交原476 Flash/high仅修apps/browser-extension及其证据，run hrun-mw2go9za-25ba26，等待cell g16:236；函数store extension-generation-closure。前后端/预览工具保持稳定。收结果后定向核闭环、准备稳定安装包再请求真实安装/范围批准；不再重复累计审查或24项UI回归。
- 最新接续点（2026-11-05 02:03）：加载UI已从固定已验快照精确暂存44份源码/测试+5份脱敏证据（projects.tsx仅暂存UI版本，工作树i8改动保留），真实钩子通过，提交并正常推送`90720465c3023fcf260447bca70658bf69a6c227`，远端SHA一致，CI41876511391成功。478–481已通过原票工具done，状态/索引文档更新尚未再次提交；477早已done。当前无预览或活动schema。
- 累计双轴审查已返回，原报告保留，主控逐项处置归[review-closure](evidence/review-closure.md)。已按固定消息协议拆后端/扩展与前端两个Flash/high修复：后端原476 session-cfff12b9-d363-4219-bc74-100137dd4348 / hrun-mw2djeye-d9131e；前端新session-a97d70df-bd13-498e-9bb6-0149be21fdd9 / hrun-mw2djif1-104df4。两者等待cell g16:206，未查看在途输出。原审查点与主控已核事实包括仓库查询漏模式、合同已核POST路径遗漏、200/60秒预算、停止假连、同账号失效后模式保持、每连接绑定隔离、缺连接disconnect异常等；不重构打印原策略。
- 主控新增测试入口候选（尚未真实启用）：tools/dev/frontend_preview_browser_check.py、preview_copy/server小装配、backend/tests/test_frontend_preview_browser_check.py、frontend-preview指南新节。仅显式参数+新建disposable副本+本run/work范围JSON，固定origin与测试账号、精确月份browser通知书；默认外呼仍拦，普通HTTP/打印与无获批请求上下文的浏览器传输均拒绝。实际范围JSON未创建，用户Edge安装/权限/真实外部验证均尚未获批。四项假ASGI边界已两次统一backend_verify通过（最新015338-285174-35924）；随后将正例改为同步handler以核线程上下文传播，最终该版和transport_guard一项待相关代码稳定后运行。普通sandbox pytest无输出已中止，不报通过；统一入口结果有效。
- 新测试入口的定向规范复核复用Standards会话Flash/high，仅审上述稳定工具/测试/指南，run hrun-mw2f4qfr-4edf3e，等待cell g16:221，独占报告review-preview-browser-check.md。这不是重跑累计审查。主控接续先收两个实施回执与此定向复核、修实质问题，再构建/定向验证；准备可审阅包与精确scope后才请求真实安装/测试批准。勿改源.env或正式配置，勿直接开owner.i8_enabled绕过范围。
- 最新验证（2026-11-05 00:58）：完整候选的公共身份/聚焦重核/本地读取9项通过，91.45s，日志i8-daily-runtime-20261105/files/logs/integrated-identity-r1.log。exec66759已由统一stop正常退出0，自建schema frontend_rewrite_397_386711eb74c04fc4a1b2d99d3547b98f已清理；当前没有活动预览/租约。独立双轴审查仍待g16:188。主控未改冻结产品源码，另行只读核验的待核发现保存在functions store键parent_daily_findings（不是审查员报告，不向其共享），两轴回执返回后逐项核实处置。
- 最新窗口（2026-11-05 00:47）：476第二轮hrun-mw29s0x9-4a29e3已返回，所有实施者空闲；累计规范/规格独立审查已各开新DSH上下文、Flash/high，只读不互看。Standards：session-dfc8e41f-2c5c-4344-ba30-9cbddb570540 / hrun-mw2c759f-edfb15；Spec：session-cf827380-14aa-43d8-b3f0-844390cd79de / hrun-mw2c78ha-abe4f7。等待cell g16:188，两份回执分别写review-standards-final.md与review-spec-final.md，审查未结束前不改产品源码。固定点22cc48f8，包含9efebc87及全部当前未提交/新增；排除继承规则差异与nul/debug.log。
- 476主控补充验证：统一backend_verify六个指定文件退出0，报告组003523-777316-30056；完整候选统一typecheck/build退出0。隔离Chromium+本机假站点确证已有HttpOnly测试Cookie自动携带、页面不可读、伪造Cookie头未使用，1次请求、无真实i8/用户Edge；扩展原包未改，测试副本仅增加假站点host权限与tabs定位，不能冒称activeTab真实点击或Edge验收。报告i8-daily-runtime-20261105/files/reports/extension-http-only-cookie-proof.json，worker sha256 ba5728b515c6c4051bc4df995745ba74954f8b00188ad38434721ea9f701c6af。首次probe遗漏identity消息而bind被拒，补齐协议后通过；均核目录边界后清理临时profile。
- 当前活动完整候选预览：exec66759，i8-daily-runtime-20261105组父租约持有，8065，schema frontend_rewrite_397_386711eb74c04fc4a1b2d99d3547b98f，disposable=true，product_digest 5d7bec7eb797ca41e4ce7395dda171a9df440c8652ba60c0d40906d72bf89d86。公共身份/聚焦重核/本地读取定向检查exec37466运行中，日志files/logs/integrated-identity-r1.log；未连接真实i8，外部动作保护保留。待检查结束正常stop，勿在父租约内申请新lease。
- 最新完成点（2026-11-05 00:28）：[478–481联合技术验证](evidence/TAIL-478-481-acceptance.md)已收拢，r2的17个通过项+ r3复验7/7，共24项；另900×600子表关闭/本地草稿保持通过。主控额外修合同批量条带预留16px和子表非居中固定顶部；BusinessModal新增centered可选参数、默认仍true。r3预览exec96134已正常退出0，schema `frontend_rewrite_397_b4e9ea30387a4c358f2d8159a5dd7efd`已清理，product_digest `f1084608b32c49e304521e1884d3c9eceb7206fe08ad50872c34ef9b6fb96f34`。当前无活动预览/租约，证据保留待累计审查。476修正仍在等待hrun-mw29s0x9-4a29e3（functions cell g16:161），未看在途输出。已登记后续隔离扩展测试组i8-daily-runtime-20261105，但未安装用户Edge、未启动该测试、未执行真实日常抓取；待476稳定后复核并运行。
- 最新现场（2026-11-05 00:14）：480窄修正`hrun-mw29jod9-6156b4`已完成，原session空闲；唯一产品源码修复为process历史月份输入固定`height/min-height:var(--control-h)`，测试按实际标题/状态/具名子表/可见油卡tabpanel纠正。主控已将这批及481共14份独立UI输入核SHA复制到固定验证检出，仍排除476在途连接源码。candidate-ui-r2统一构建退出0，当前唯一预览exec8344，8065，schema `frontend_rewrite_397_42e65bb0a7044070925d9efc3e2e988b`，revision oilmerge261103，disposable=true，product_digest `76a0458df7ba3e89ffee4db07d5f4cdfe03cfb84325c234908f6ce2b5cde6b45`。同受管组父租约在用，不新登记/嵌套lease。24个具名失败/未跑/新覆盖及少量编辑连续性检查运行中exec68188，日志files/logs/ui-r2-pytest.log，输出身份同时设置MTRL_RUN_ID与MTRL_LIFECYCLE_OUTPUT。476第二轮仍在等待，未查看其在途输出；不得把已有样机/单测当日常通过。
- 最新检查点（2026-11-04 23:27，优先于下方旧时间点）：当前并行写入者为476日常接入修正`hrun-mw29s0x9-4a29e3`（原session-cfff12b9-d363-4219-bc74-100137dd4348，Flash/high）与480界面窄整合`hrun-mw29jod9-6156b4`（原session-69db282a-6297-41b2-abb7-638ba9b65efa，Flash/high）。481首轮/steer已返回，六页源码与离线检查就绪但8项GUI未跑。476首版2329行新代码已返回，不能安装/验收：主控发现通知书月份正则双转义会阻断旧抓取、缺只读端点白名单、只在connect核身份、轮询没有正确处理身份暂停/停止回显、组织内部ID与可见短码混比、每弹窗重选HTTP不符统一浏览器模式目标。已一次下发实质修正与全日常入口接线要求，原始数据不入Git。
- 476现场身份适配依据（只读DOM，未安装/登录/取新业务数）：已有i8账号浮层为`[role=tooltip].ant-popover-inner`，其`.ant-popover-inner-content > div`内首行button头像旁div的第二个div为登录账号；含`[aria-label=cluster]`的直接行，其`span.nowrap`为组织名称与可见短码。可见短码109，与WH_PARAMS内部号不同；已把去敏结构/已核映射依据发476，禁止让普通用户手填选择器。CUA本轮已completion；原业务页保留，账号浮层仍可能展开，未声称恢复成功。
- UI候选r1已停止：固定验证检出`loading-ui-validation-20261104`，product_digest `05a7b5df0513c5fcb662af2ca378995226e116469d4b54b2204ff15c261fb6d7`，schema `frontend_rewrite_397_6800ffdb56444771b25a6b4411988208`在23:20正常清理，exec3859退出0。无在用预览。受管组`loading-ui-478-480-20261104`留存失败证据，不结项。
- r1结果：首轮17例在第11例失败清理时卡住，主控Ctrl+C仅终止测试（原PID24132/33340已不存在），不能报完整通过。主控修fixture失败时unroute(ignoreErrors)，随后8项诊断复跑135.35s全部失败：2个过早assert held、过程tabs实际209→211的2px位移、2处合同h1错预期、1处AG36旧容器选择器、2处油卡把隐藏页签DOM当可见内容。已给480精确清单；fixture改动与481项目重试按钮文案改动均保留。诊断大段业务ARIA值只在本地工具输出，不写Git。
- 主控额外真实验证：合同未读错误显示0条；项目清单pending时新增/抓取按钮enabled；油卡读取503表区下推60px。已在集成树修油卡五页固定槽、合同未知计数/项目依赖门控/项目错误入槽，未复验，交480保护并补测试。过程双错误在900x600两个重试都可命中。报告`ui-r1-targeted-findings.json`和`ui-r1-dependency-findings.json`及具名截图在同受管组，未入Git。无消费者ReadState已由主控退役。下一步等480稳定后把这些和481完整UI复制到固定检出，统一构建，复验失败/未跑项及最少编辑连续性代表；不要在476在途源码上启动产品预览。
- 当前用户修订（优先于下述旧阶段结论）：476必须让工作台日常抓取按钮直接复用Edge，不依赖Codex/DSH模型逐条转接。既有单据代表成功仅是中间证据，不关闭476。方案研究`hrun-mw25ylag-013d97`已返回；原476会话现实施`hrun-mw27mubi-48c4e6`，Flash/high：后端进程内连接中介、工作台页面和独立Edge MV3伴随扩展，先打通现有通知书抓取按钮的自动通路。身份比较沿工作台用户的i8_user，保现有401/身份门控，浏览器模式断开不回退登录。代码开发已授权；用户Edge安装、权限扩张、生产部署仍未授权，待可审阅包和隔离验证后再询问。i8.tsx/css归476，481排除。
- 当前UI检查点（2026-11-04 22:36）：478共用槽整合、479、480源码及离线检查已返回，真实浏览器联合验收未完。481已派Flash/high，session-701f2f66-a6e1-458a-b78b-972bc536543b，run hrun-mw27wt6x-0ac72e；写独立报表/维护页，不改i8或共享文件。实际工具回执配置均为workbuddy/deepseek-v4.1-flash/high。并行实施者为476与481。
- 固定UI验证窗口：新建detached检出`var/worktrees/loading-ui-validation-20261104`，基于9efebc87，逐文件复制并核SHA一致的31份已完成478–480源码/测试/适用规则，不带入476/481在途源码。受管组`loading-ui-478-480-20261104`，正在统一离线构建candidate-ui-r1，尚未启动副本。过程测试的异步held列表拼接丢引用已由主控修为共享列表append，非产品修复。禁止从DSH复制owner/record/version绕过环境差异。
- 当前完成点：477已完成[技术验收](evidence/TAIL-477-acceptance.md)，代码和证据已保存于已推送提交`9efebc87`，原票已done；最终r3预览已正常退出。478仍实施中；479代码与定向检查已返回，GUI未验，主控待与478一并核候选。480/481为ready-for-agent。476[当次真实会话验证已跑通](evidence/TAIL-476-live.md)，但尚未满足上方修订的日常抓取目标。下述旧运行过程按时间留存，不作为当前在用资源。
- 当前实施者：478会话`session-a5205900-e550-4e6f-81c7-76fa2cf90e60`、运行`hrun-mw23mu3b-85f779`；479会话`session-4bbac21a-b393-43ea-a797-0708f67d93b2`、运行`hrun-mw23ms2p-53fb6b`。各票新会话，回执确认`workbuddy/deepseek-v4.1-flash / high`，各自独立页面写域，共享文件只读并由主控串行整合，现场运行验证仅主控原登记环境执行。
- 后续批次：478/479上述首轮均已返回，GUI未验。478现作为唯一共用呈现写入者收拢read-region.css/状态槽与库存旧整页等待门，运行`hrun-mw267clk-88113f`；479暂无写入者。480新会话`session-69db282a-6297-41b2-abb7-638ba9b65efa`、运行`hrun-mw26d3fo-dc9bda`在独立集采/油卡文件实施；最多两个实施写入者，476另会话只写方案Markdown。回执均为Flash/high。481仍待派，依赖仅477，不增加虚假业务前置。
- 推送状态：首次提交`94a143e7`未曾推送；文字证据去敏后修订为`9efebc87`。用户已在当前对话明确授权将本任务脱敏源码/规格/票源/文字证据推送到公开`lysyscy/mtrl-workbench`的本任务分支；随后正常推送成功，`ls-remote`核远端与本地均为`9efebc87354b95237dc8e2044365bae377186560`。凭据、原始业务文件和截图未入Git，未部署。
- 476现场新情况：用户重新在Edge打开有效i8业务页，主控通过可见账号面板核身份/组织并选了一个页面对象。页面查询附带查询面板/组织树偏好保存接口，已停止用该按钮作纯只读验证，不把这些调用声称为完全只读；未执行业务单据保存/审批/付款/打印。已有严格客户端通过临时stdin浏览器中转适配，在当前配置站点检查处返回`StrictTargetMismatch`，尚未生成外部读取请求；浏览器站点与工作台配置不同，已向用户询问本次测试以哪一目标为准，不改配置或回退登录。临时适配在受管组`i8-browser-reuse-live-20261104/files/work/browser_relay.py`，无Cookie材料，进程已结束。
- 476后续已执行：用户明确“以当前Edge为准，仅测试，不改工作台配置”。仅在临时验证进程装配该目标，既有严格客户端产生精确请求→Edge CDP同源fetch（禁止重定向）→stdin返回真实字段投影→既有解析器，1条结果与页面单号/项目/日期/审批金额/状态一致。网络仅见目标读取与页面在线刷新，无登录/强踢；未导出Cookie或使用后端会话缓存。临时中转进程`58917`已退出0，去敏报告在该组`files/reports/live-reuse.json`；原始业务值不进Git。下一步持久化通用中转协议及复现说明，不扩为自动生产抓取。
- 推送后的CI：`Frontend checks`运行41830802568成功，对应完整SHA `9efebc87354b95237dc8e2044365bae377186560`。后续源码有新变化再核相应检查，不重复扩测。
- 接手核验：01a1a5a9-0de0-75e1-af89-faf42b264768 已只读确认目录、交接编号、十份材料散列、HEAD／未提交状态及六票依赖一致，无阻止接续的关键差异。
- 实施真源：`D:/dev/mtrl-workbench/var/worktrees/browser-session-loading-20261104`，分支 `codex/browser-session-loading-20261104`，基点 `22cc48f8`；后续任务记录与票源仅在此维护。已逐文件散列核对带入4份effort材料、475–481原票及两份共享索引。当前CONTRIBUTING及frontend-design作为适用规则带入，其既有修改不归本任务提交。
- 证据组：`browser-session-loading-20261104`，已登记于项目受管运行区；活动证据保留，预览及schema的实际退出状态见下项。
- 当前执行点（2026-11-04）：用户确认DSH更新完成并要求继续派发。已核新工具接口、模型列表及原会话空闲状态，沿原476/477会话完成[首轮修正](evidence/review-round1.md)；回执确认`workbuddy/deepseek-v4.1-flash / high`。476运行`hrun-mw20j8qt-051908`、477运行`hrun-mw20jaoy-3f57ec`均已返回；477随后进入候选GUI验证，运行`hrun-mw21rylb-71ff2e`，原会话`session-6e0fc861-97a6-4962-aace-1625a7c17274`。产品源码窗口冻结，写入仅测试副本；主控等待检查结果。478–481仍依赖477。
- 本任务基线预览已退出并清理自建schema。现候选`candidate-477-r2`已按Corepack统一构建、通过registered_preview身份核验，8065在用，schema `frontend_rewrite_397_6843f00abf424a429a7cf7d7f66e0dd4`，revision `oilmerge261103`，disposable=true，product_digest `8bdf5511c4b8a09f885e5b3d45df48a622998d2c336c66ba919353d3e6516c20`。本任务父进程仍持有证据组租约；owner在组`files/reports/real_owner.json`。GUI验收未结束，不能此时改源码或再次启动预览。无正式业务写入、提交推送或部署。
- 主控后端验证：`backend_verify.py --source-env D:/dev/mtrl-workbench/.env --test tests/test_i8_browser_session_reuse.py --test tests/test_i8_cookie_cache.py -- -q -o addopts=`退出0，临时schema和pytest目录清理成功。报告组`193938-527310-24624/files/reports/backend-verify.json`。2026-11-04再次只读查看Edge标签已无i8，已向用户询问其他日常浏览器是否有已有业务会话，真实复用继续未验。
- 最新检查点：477 GUI运行`hrun-mw21rylb-71ff2e`已返回，3项新读取检查及6项既有台账检查通过，但真实截图确认error/stale绝对定位提示遮标题和金额。已沿同会话Flash/high派出局部修正`hrun-mw22sg5u-871b96`，其只改源码，不再运行现场检查。候选r2已由统一入口正常停止；在用状态以上述最新检查点为准。未取到有效值的表体scrollTop不能算已验，修复后只补遮挡/失败恢复与这一缺口，其他有效证据复用。
- 环境差异：DSH报告曾把打包路径中的owner/version/record和candidate构建复制到普通AppData树，以供其非打包宿主读取。主控已禁止继续复制、要求只读清单及覆盖情况；副本保留待核，不作为新增合法运行登记。后续运行验证由Codex原登记环境负责。GUI证据侧车schema/product_digest与本任务r2已核身份一致，主控已实看`477-gui-stale-narrow-120129-712080.png`确认遮挡；不要删除这些失败证据。

## 权威入口与当前成果

- [正式规格](spec.md)：共同范围、已确认取舍、验收入口和明确不做的事。
- [实施票索引](ticket-plan.md)：六票的链接及依赖，只导航，当前进度看原票。
- [第一方案例与源码研究](research.md)：成熟加载方式的来源及证据边界；研究不是本项目已验。
- [总票 TAIL-475](../tails/issues/TAIL-475-i8会话复用与稳定加载.md)：本 effort 入口，拆票阶段未改总票。
- 各票沿本隔离工作树票源，TAIL-476（i8 验证）、477（欠款样板）为 in-progress，首版待修正及验收；478、479、480、481 为 blocked，均只依赖 TAIL-477。
- 规格、六票、依赖与文档链接已核；票源工具能读取实际状态，高水位为 481，TAIL-475 建票前后散列一致。
- 476/477首版代码与离线检查已返回，主控完成基线真实副本观察；候选尚未完成过程验收。未做真实i8抓取、源码提交推送或部署，不能把研究、离线检查或基线观察写成候选技术验收完成。

## 已确认决定与边界

- “浏览器登录态复用”指 i8 抓取使用日常浏览器已有 i8 会话，不是工作台 UI 自动化登录态。
- i8 先做最小只读可行性验证，沿既有取数及解析能力。会话缺失、失效或目标不符时停止，不能用重新登录／强踢后的成功冒充复用成功；测试不持久导入会话或写正式业务，材料不得披露凭据。
- 已有后端 Cookie 缓存不等于浏览器会话复用；目前客户端仍有原缓存及自动重登路径。严格复用模式与日常产品原登录恢复策略分开。
- 页面范围为全站同类加载问题，欠款台账先打样；允许筛选栏／页签先出现，表格随后出现，不要求全页同时到齐。
- 按成熟实践使用稳定分区、局部反馈和适当占位；同条件重访／刷新保原结果及上下文，切条件不得拿旧数据冒充新范围，关键与次要区域分别处理。
- 保现有金额、业务归属、权限、保存／草稿、滚动、列宽、字号及主题保护。不恢复旧性能 effort，不附带新轮询、任意缓存时长、业务键盘增强或风格重做。
- 用户已明确确认两处验收入口：i8 现有取数／解析链的只读真实代表；登记真实副本上的页面全过程，保护草稿与列宽。
- 实施写入代表只在已核可丢弃真实副本运行，预览外部动作熔断保持；真实 i8 验证与 UI 副本测试分别运行。生产业务写入、实际打印及正式部署仍不在本次授权中。
- 统筹负责范围、共用机制取舍、冲突整合和关键结果复核；Flash 按票实施。初期最多两个执行任务并行，工作区隔离后按写入边界安排，共享文件串行整合；每票包含自身必要验证，复用仍适用的证据。

## Git 与材料保护

- 交接核对时为 master，HEAD 22cc48f87dabd71f0d054675c3985e2980695762，与 origin/master 无已显示偏离。
- 本 effort 的目录及 TAIL-475–481 尚未提交；共享的票号高水位和 status 也有工作区修改。新建聊天使用 local，确保这些本机材料可见；不要只从默认分支另起而丢掉未提交票据。
- 主根另有他任务／用户未提交内容：油卡交接与部署文档、CONTRIBUTING、前端设计、Impeccable 资料、PRODUCT／DESIGN、临时 Python 文件与 debug.log 等。只核实际现状，不能暂存、覆盖、清理或带入本任务提交。
- 开工后选择隔离集成分支／工作树，完整保留上述未提交材料。任务 Markdown 和票源的迁移／可见性先解决；不要对主根做 reset、clean、stash 或粗放暂存。
- 无本 effort 的运行中预览、schema 或后台工作需要移交。旧 DSH 探查会话已完成，不能视作实施者；不沿用本对话的浏览器句柄或未验证的登录态。
- 本次交接未执行 Git 提交／推送、业务写入或服务切换；后续源码保存沿项目现行规则和实施范围处理，正式部署单独授权。

## 接续第一步与验收

1. 初始核验轮只读确认目录、交接编号、当前 Git／未提交状态、下列材料、六票状态及授权边界，返回差异和第一步；不先启动实施者或修改文件。
2. 收到源对话“交接登记已完成”的继续指令后取得修改权，在本记录登记“已接手”，并隔离实施资源。
3. 从 TAIL-476 与 477 开始，分别建立清楚的任务范围、写入边界与必要验收。DSH 每票新会话，显式选用户指定 Flash/high 并核实际返回配置；Astra 主持 i8 现场身份／会话判断与欠款样板关键设计及证据复核。
4. 476 仅在当次可用浏览器通道及实际已有 i8 会话核对后做最小只读取数；先核严格模式离线保护。缺少现场条件则记录未验，UI 票继续，不以新登录替代。
5. 477 形成真实可操作样板及共用能力，核初载、必要慢／失败、切条件、重访／刷新和编辑连续性；其完成后再按依赖领取 478–481。
6. 所有检查按共同规格与当前项目选测规则，达到必要检查及实质发现关闭后收尾。票的实施／技术验证、用户验收、源码保存与部署分别报告；不重复采访已确认工程方向。
7. 仅遇真实业务含义、缺少现场条件或授权边界时请用户处理；交接和实施启动已经获得确认，不重复索取同一批准。

## 核对材料指纹

下表是交接前十份关键材料的 SHA-256，供初始核验定位差异。允许按实际新变化解释差异，不把旧散列当作回滚指令；交接记录自身会随登记更新。

| 相对项目根的路径 | SHA-256 |
|---|---|
| .scratch/browser-session-loading-20261103/spec.md | c7e55b48be9a8dbbaf9fc0484bb16027ce929014784b1d1442eb97203d58ba66 |
| .scratch/browser-session-loading-20261103/research.md | b5889b4173e2ebf5999903a6fab6181eb444df688fd8a91ceb79e16164439a0b |
| .scratch/browser-session-loading-20261103/ticket-plan.md | b9230786bacfb801234566f3fcc0072a13877d5012614cfdde097784674cb460 |
| .scratch/tails/issues/TAIL-475-i8会话复用与稳定加载.md | e3de4f04654e34524e6bf2f064ec67436745da9d1054265c5c48959762100340 |
| .scratch/tails/issues/TAIL-476-i8浏览器会话复用验证.md | 98f49785348d9bbdb1dbdade47f2039c7b60d039a43205a6b901fe956d03c89a |
| .scratch/tails/issues/TAIL-477-欠款台账稳定加载样板.md | e5ae5c97029c36ac5e98eb585e90884aed4830d8e229a491f30fa09789dfac3d |
| .scratch/tails/issues/TAIL-478-通知书库存流水加载接入.md | afe0731e5e552de301462c6f13850f863877e044d013dba59048f022133a097a |
| .scratch/tails/issues/TAIL-479-过程机械工作区加载接入.md | 4119818c2c98d22873e84987a162d298ee95b6a9d5182419a44b18c0b5531046 |
| .scratch/tails/issues/TAIL-480-集采油卡明细加载接入.md | 1d6ebcf56a8c853a48d57287352cedbbfc66d8bb98c21279eb4885a17dbf5d57 |
| .scratch/tails/issues/TAIL-481-报表与维护页加载接入.md | d55665dd12ab4771fe547b353b28467d2395f4ad4d5c65463224a941f831b9f5 |

<!-- MTRL-HANDOFF-END PH-20261104-loading-i8-01 -->
