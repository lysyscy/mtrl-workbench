# TAIL-398: 历史台账连续编辑闭环

**What to build:** 查询并连续编辑历史台账，保存后读回真实结果，可处理拒绝、撤销和重做并导出。

**Blocked by:** TAIL-397

**Status:** claimed

- [x] 保存立即发起；连续输入、Tab/鼠标切格、中文合成、月份重排和按钮点击均保留目标行、焦点及后续草稿。
- [x] 项目/月度/账号切换后，旧读取、旧保存结果和旧错误不覆盖当前范围，原保存仍归原记录；活动编辑不被后台刷新打断。
- [x] 服务端拒绝、版本冲突、重复提交与保存成功但刷新失败分别呈现；合计适时更新，金额空/零语义保持。
- [x] 实际后端与隔离库验证写入、历史摘要刷新、撤销/重做、冲突及账号隔离，失败无部分写入；移植 TAIL-394/396 的有效保障。
- [x] 下载并读取实际台账导出，与同范围数据核对；记录首个编辑表格的适配证据和待复杂报表确认项。
- [x] 逐月台账导出可按实际身份/忙碌边界正常打开独立弹窗，多选项目和顺序独立于查看单选及总欠款导出；实际文件内容正确，预览输出不进入正式目录。

规格：[前端独立重做规格](../../frontend-vue-rewrite/spec.md)（User Stories 18, 19, 20, 21, 22, 23, 24, 25, 26, 41, 43）；业务口径：[MOD-05](../../../docs/requirements/PRD/02-功能规格/MOD-05.md)。

验证类型：浏览器可观察行为＋实际后端/隔离数据库；涉及导出时检查实际文件，涉及外部系统时使用明确替身边界。复用有效既有保障，按本票风险补缺，不重复整套检查。

---

## Comments

**2026-10-22 · 建票（agent）。** 来源：用户2026-10-22确认React前端28票及依赖｜不做会怎样：新前端该用户路径或累计交付缺少独立验收与接续依据｜落点：新前端独立副本；规格及本票验收｜阶段 / 时机：随时｜**排期四问**（`§14.3` 同源）：①按已批准依赖解锁后续②先验收再扩大迁移③同批共享隔离与交互边界④依赖和验收见本票

**2026-10-22 · 授权与执行入口。** 已批准建票及上述依赖，后续采用 implement-solo-spec 跨批统筹；本轮仅建票，尚未授权开始实施。ready-for-agent 仅表示任务已说清，仍需实施启动授权；外部真实动作、正式切换及退役各守规格授权门。

**2026-10-22 · 接续授权与开工。** 父任务授权仅398及397验收收尾，功能实现基点0485e20c1a0d607faa2b2d16c149db28b8569caa，分支codex/react-frontend-rewrite，指定worktree起点clean；不改原仓正式代码、不推送/部署/真实业务写入、不开始399及后续票。复用397账号子树、api.ts、QueryClient与隔离启动器；Ponytail5.3.2 full、Impeccable4.7.0 Operate。使用专用测试库和每轮独占schema，先核实际连接目标；本轮结束清自有数据与进程。父任务安排398后人工端到端验收，用户试用仍待验；交付短操作清单和安全启动方式，不留无主预览。宿主写根不含复用工作树，本次工作树读写均经正常提升审批，不改全局Git配置。


**2026-10-22 · 实现与逐条技术证据（待父任务及人工验收，不启动399）。** 固定本批基点0485e20，起点clean；397按父任务既有通过办理销号，14项旧Temp文件只读全部不存在。398沿账号子树、独立QueryClient、api.ts及隔离启动器接入，无后端业务规则、迁移或正式资源改动。

| 原票验收 | 本批实际证据 |
|---|---|
| 立即保存与连续输入 | 实际POST在离格后发起；延迟第一格真实回包时继续输入下一格，焦点及草稿保留。Tab、鼠标、中文composition事件、月份重排后排队结算/付款均真实读回原记录。长按按钮时节点不替换，实际删除及撤销通过；结束连续编辑后再发布表格/合计。20项398用例见apps/frontend/tests/test_ledger.py。 |
| 范围与账号归属 | 查询key含账号、项目、截止月份，草稿再含记录身份、原月份和版本，不取行序号。旧项目/月度读取和错误、同范围倒序读取、原范围保存归属、拒绝草稿跨截止月切换均通过。身份网络/500暂停不发保存，同账号恢复保草稿，换号/失效清旧树；旧账号迟到401不使新账号失效。 |
| 拒绝/冲突/刷新失败 | 真实非法金额/空字符串拒绝且保输入，显式0读回0.00；失败不部分改金额或备注。并发改下一格、旧token重投及实际撤销冲突均拒绝覆盖。保存已成功而读回500单独提示已保存、刷新核对，未重复POST；双击新增仅一条。金额来自后端字符串，合计按返回分值求和，缺失/错误不冒充零。 |
| 实际后端、撤销与394/396保障 | Alembic、FastAPI实际静态构建和PostgreSQL专用测试库，每轮随机独占schema且无public回退。真实保存/摘要刷新/撤销/重做/不同账号历史归属及冲突未部分修改通过。原394/396选集test_ledger_opening_ui.py、test_payment_ui_regressions.py共25项退出0；新网格另核实际滚轮、默认到底、32行虚拟窗口及保存时两侧/整页位置。 |
| 实际导出与网格适配 | 浏览器下载9991字节xlsx，openpyxl读取辅材/机械/特殊费用三表；逐行月份、结算、付款、欠款、备注与同项目/截止月后端行集合相等，包含页面隐藏的零月范围。最终实际下载文件位于.artifacts/archive/frontend-vue-rewrite/131742-960898-36304/exports/隔离项目欠款台账_2025年11月.xlsx。Community36.2.0单一网格承载冻结列、虚拟窗口、内滚、合计和直填；复杂报表/合并布局留399。 |

**命令、原始结果与复用。** 组件内corepack pnpm@12.14.0 install --frozen-lockfile、typecheck、build分别退出0；React19.3.1/TS7.0.2/pnpm12.14.0保持，新增AG Grid Community/React36.2.0（MIT基础版，无企业许可）。该包两处可选声明与exactOptionalPropertyTypes不兼容，pnpm受管patch只补undefined，不改运行时、不开skipLibCheck、不放宽strict。最终JS首屏index-BUSnIvwm.js 300.89kB，按路由延迟加载ledger-CUSEp18E.js 1175.60kB，CSS index-CUKrsxKD.css 5.53kB；保留Vite大分块提示，未关闭阈值，构建成功不代替类型检查。

仓根pytest apps/frontend/tests/test_ledger.py apps/frontend/tests/test_preview.py -q --tb=short最后组合原始退出1：28 passed/1 failed（77.49s）；唯一失败是鼠标夹具对未滚到的缓冲行按中心点击。保留真实中心命中和节点/写入/撤销断言，按实际滚轮定位，并补齐真实36.2视口的默认到底/虚拟窗口/保存位置。最后pytest apps/frontend/tests/test_ledger.py -k 'mouse_button or grid_scope' -q --tb=short为2 passed/18 deselected、退出0（10.49s）；其余28项代码、构建和断言未变，复用有效结果。故为30项分轮有效覆盖（398新增20、397受影响10），不把组合退出1改报整轮全绿。旧版25项另由collect-only核准15+10数量，未重复业务执行。唯一既有warning是Starlette/httpx弃用提示。

**失败关闭与审查。** 保存前先取得缺页红灯；后续真实反例修复身份恢复后新渲染格仍只读、自己月份保存后画面未重排期间新草稿误用旧月份、异步身份暂停后的写入防线及预览CLI仓根导入。曾发现测试异步谓词把Promise视作真值，已改同步布尔轮询并再直接断言实际HTTP读回，先前受影响数字不作通过依据；月份后续付款漏存由修正后的断言检出并修复。空字符串/HTTP400回执、虚拟滚轮/视口选择器等测试问题按真实契约修正，未删除业务保护。审查选择本执行者累计自查＋定向真实反例；父任务负责独立验收和整体审查，本票不冒称独立评审通过。

**视觉、人工关口与公共接线。** 已实际看1920、1024及深色1.12截图，表内横滚、冻结列及合计可读，无整页横向溢出；Impeccable检测[]。内置浏览器在8038合成数据完成筛选、连续结算/付款、中文备注值、撤销/重做，保存后辅材合计1800.25/193.45/1606.80正确。自动composition事件及程序输入中文不代替用户真实输入法/日常手感。人工短清单与已知差异仅在docs/guides/frontend-preview.md；父任务安排试用，用户未试仍待验，不据此解锁399。当前仅导出所选项目一本三表，旧多项目zip选择界面未迁移；网格适配不推定复杂报表已通过。

**环境、清理及文档。** 实际连接确认mtrl_workbench_test/mtrl，所有迁移和浏览器写入均在本轮schema。8038走查实例已Ctrl+C，收到ISOLATION cleaned（schema frontend_rewrite_397_26ae75e5e103433d84fabbe14f096b29）；此前一次CLI导入失败也finally清理。所有测试服务由夹具退出后drop自有schema；收尾READ ONLY核预览schema剩余0、8037/8038无监听，根.env不存在。导出只进本轮.artifacts；pnpm patch临时work已精确清除，无本批Temp脚本，无删除397名单操作；依赖与dist留给父任务验收。

文档按writing-for-agents/项目维护约束更新唯一预览指南、当前索引与票。首次审计3红中的两个T6是397索引误放表外，已移入表并调用既有ledger_counts/write_counts真源重算；复跑doc_audit退出1：必须修1/疑似33/豁免15，仅ops/nssm/nssm.exe工作树忽略资源差异，未安装/复制或放宽T3。公开PRD基线临时配置已核原字节并finally移除，无凭据复制。必要原始截图、实际文件和失败日志由workspace_paths保留30天；主体最终证据轮131742-960898-36304，补充滚动/鼠标轮另按自动run归档；无活动run。

**最小接续。** 父任务先按预览指南启动隔离实例并组织人工试用；可沿本次SHA核旧版共同调查基点33a9bb4之后的迁移面差异。确认后399复用apps/frontend账号树、api.ts、ledger-api.ts的边界和隔离启动器；AG Grid声明补丁只有两行，仍需验证机械复杂表格、合并布局、动态行高及许可边界，不建第二套网格。本执行者到398交接停止，不推送、不部署、不改原仓正式代码、不启停正式服务、不触发i8/打印或423/424。保存SHA及最终dirty由回执提供，不造自指提交。


**2026-10-22 · 末次自查与交接冻结。** 新网格补充滚动/鼠标命令最终2 passed/18 deselected、退出0（10.49s）；断言观察本次安装36.2的真实ag-grid-viewport，32行跨虚拟窗口、切项目默认到底及两侧/整页位置均通过。自查另发现匿名只读刷新被写入守卫提前返回，单行改为既有query.refetch，写入仍禁用；定向pytest apps/frontend/tests/test_ledger.py -k anonymous_ledger_refresh -q --tb=short最终1 passed/20 deselected、退出0（9.56s），检查无业务编辑器、实际GET成功，AG隐藏焦点input不作为业务编辑框。由此398为21项，连同397受影响10项共31项分轮有效覆盖；不改写此前组合非零结果。

末次只读分支修复后typecheck/build各退出0，最新产物index-DHRNdNi5.js 300.89kB、ledger-COUvfe6B.js 1175.61kB、index-CUKrsxKD.css 5.53kB。其余登录编辑分支、样式和有效断言未变，复用上述已验证证据，不重复整套检查。workspace_check run-closed退出0；整体effort仍含399以后活动范围，不执行closed。仅本地提交且不推送；父任务与人工验收仍待办理，本执行者停止于398。

**2026-10-22 · 保存格式修复。** 真实pre-commit首次语法检查通过、字节检查退出1；B1精确命中397票、398票和已销号索引各2个新增裸LF。仅将三件统一回原多数CRLF，内容与业务源码不变，不跳过钩子；最终提交结果由回执报告。


**2026-10-22 · 首次人工反馈后纠偏（仍待重新人工验收）。** 用户发现结构多处不同，父任务确认按spec第104行旧布局基线纠偏；此前技术绿灯和视觉记录不构成布局等价或人工认可，本票保持claimed，399不启动。原人工实例终端8523已正常Ctrl+C，回执清理frontend_rewrite_397_152431e355ef437a871e33d34f20ebe9；只读确认mtrl_workbench_test/mtrl中该schema为0、8037关闭后才修改构建。未操作用户浏览器或在试用数据上写入。

恢复双表上方共用项目选择、按顺序默认/保留当前项目及归档标记；账号子树内导航往返保项目和台账草稿，离页暂停后续查询/写入。恢复台账卡片标题、摘要（当前欠款/截至月/最新月新增及单位）、历史边界、机械列名、列序/宽度/密度、640px×字号的响应式排列、随内容高度及360px×字号上限、欠款/删除业务色、表头金额数值排序、顶部撤销/重做与回执。移除额外截止月份控件，读取按原数据自动末月；新增回辅材摘要，固定2025-11且按稳定记录ID定位排序后的真实网格节点并聚焦月份。普通月份金额仍只读，备注恢复填写/清空并可业务撤销；复用/m05/ledger/remark，新增可选Form token（旧调用不必传），与旧调用共用项目锁，新调用复用既有行token拒绝过期覆盖，无迁移或金额规则改变。

台账批量导出本批补齐：原卡头入口→独立多选项目（不切查看项目）→可排序确认清单→保存到本地；单项目三表xlsx、多个项目ZIP，报告月恢复北京时间上月。实际后端已支持，无需新依赖。总欠款汇总项目范围/行序选择、概览/付款统计/流水仍归405，已在原票Comments澄清且页面明确未接入；不是把缺口默认为今后必恢复，不提前实施405。导航恢复综合页全名，当前仅局部预览，不作为最终整页布局批准。

**本次实际验证与失败保留。** frozen install退出0（版本和锁未变）；最终严格typecheck与独立build按回执，保持strict/skipLibCheck=false。首次原有回归12 passed/1 failed：身份失效全页文本断言撞到前用例合法保存的同金额，改为核本用例准确记录及无旧草稿，写入阻断不删；续跑6 passed/1 failed：旧刷新尚未结束就拦截下一刷新，补明确等待可用后再持有响应。新用例首轮6 passed。最终组合pytest apps/frontend/tests/test_ledger.py apps/frontend/tests/test_ledger_layout.py apps/frontend/tests/test_preview.py -q --tb=short：38 passed、退出0、103.82秒（唯一Starlette/httpx既有弃用warning）。覆盖21项原398、7项纠偏与10项397；不抹去前述失败结果。末次小修（旧/新备注锁兼容、导航全名、排序后按ID新增定位）后test_ledger_layout.py：7 passed、退出0、28.23秒；其余未受影响结果复用，未扩大业务回归。

实际同一隔离项目与自动末月（辅材2025-12、机械2025-11），独立浏览器上下文，1920×1080/1440×1000标准字号与1024×900深色1.12，分别截图旧/app和新/preview/ledger；核双方字体/倍率、双表排列、摘要、正常备注及操作路径。旧、新导出确认也有实屏对照。最终证据目录及最后合计对齐的3组复验结果见后续回执。前一有效证据轮.artifacts/archive/frontend-vue-rewrite/141952-629515-7460，ZIP18266字节，内含隔离项目10045字节、长项目9544字节xlsx；zipfile/openpyxl实际读取每本三表，并与对应项目/报告月后端完整月份、备注逐行核对，单项目金额逐行核对沿组合回归通过。导出不只核HTTP200或文件存在。

**尚存可见差异与交接边界。** 单一AG Grid保留虚拟窗口/内滚与固定合计；字体、主题沿原主人。网格边框/排序图标、原生月份输入日历显示和像素间距不声称完全一致；确认清单使用原生dialog，须用户重新验收。缺失综合区域由405承接，不以局部页替代最终综合布局。实际输入法和手感尚待用户试用；技术证据不能替用户批准，本票不销号。


**2026-10-22 · 纠偏冻结回执。** 最后合计金额回欠款列、说明回备注列后，严格typecheck退出0，独立build退出0；产物index-DDHBH6A9.js 301.15kB、ledger-Dg2CtpQ6.js 1183.82kB、index-DILbdYNl.css 9.99kB，保留大分块提示。只对最后布局影响补跑pytest apps/frontend/tests/test_ledger_layout.py -k same_synthetic -q --tb=short：3 passed/4 deselected、退出0、16.33秒；最终三组新旧页面/台账截图与导出确认对照在.artifacts/archive/frontend-vue-rewrite/142235-542574-36608/screenshots，配套测量在logs。实际ZIP与7项末次业务验证保持上一有效轮141952-629515-7460；38项组合证据轮141451-683174-36732不改报为新一轮全跑。

收尾只读核mtrl_workbench_test/mtrl，frontend_rewrite_397_预览schema列表为空、8037关闭、active effort轮次为空；所有测试服务和数据已由夹具正常收尾。没有重新留下人工常驻实例，父任务核对后可按唯一指南安全开启全新合成预览；不是已失效URL冒称可用。无本批Temp辅助脚本、根.env或待清理项，不重试删除397旧名单、不改ACL、不碰正式服务。仅本地保存，SHA/dirty由提交回执提供；人工验收仍待，399不启动。


**2026-10-22 · 第二轮人工反馈（文案、右上角操作与业务副本）。** 用户明确不要求一比一还原，允许从用户视角精简说明；批准移除不读的解释、撤销/重做贴账号区左侧、取消日常刷新，并复制现有数据库用于本地隔离人工预览。先Ctrl+C关闭终端4343，收到准确schema frontend_rewrite_397_8efd82bf525e48cca418504a5a7fd0ab清理回执；只读复核旧schema0与8037关闭。原仓代码/服务未动，未开始399。

已移除台账目的、两类历史限制和局部页长段说明；金额/月度摘要保留并简为当前欠款、截至与新增。操作回执简短，撤销/重做仍只有一套，portal移到账号区左侧，状态/草稿留独立状态位，账号隔离和离页守卫不变。原刷新按钮是手动强制重读及失败恢复，不是保存步骤；现取消常驻按钮。进入/切项目、返回页面或账号核实恢复、保存成功自动读取；保存已取回完整结果后不再重复请求同范围，无轮询。失败/冲突才显示重新加载，允许读回而不丢草稿，不自动重投保存。

**复制机制与权限核验。** 源本机mtrl_workbench仅在REPEATABLE READ/READ ONLY事务内读取，实际transaction_read_only=on，版本c391261021；目标仍由TestDatabaseGuard确认mtrl_workbench_test，独占新schema且无public回退。复用原启动器、Alembic、生命周期与两测试身份，新增显式--copy-source；默认仍合成，自动写入回归不使用真实副本。复制前核版本/表列/主键/唯一/检查/外键，按关系与项目自引用顺序复制，按主键逐表比计数与内容散列，复制并核32序列，调用原build_ledger对比全部非壳项目行、金额和摘要。未修改源库/权限，未生成含凭据dump；用户数据只在本机测试库，不进Git、不上传业务明细/真实截图。原账号保留ID但停用别名，password/i8_user/i8_password在源读取投影中置空；app_setting/app_setting_log/operation_history/run_record不带入，测试登录仅在副本新增，旧生产撤销链不复用。HTTP副本模式白名单只开放台账本地读写/历史/登录/资产，其他路由403；i8/打印/抓取/配置修改不可触发，外部配置同时清空。应用真正连接池启动时核数据库、schema、search_path，不能只验证单独检查连接。

**真实结果。** 合成浏览器有效覆盖29项：首轮5 passed后仅旧长回执文本断言红；改短文案后失败恢复1 passed；迟到读取2 passed；余下21 passed/8 deselected、退出0（72.14秒），覆盖右上角位置、无常驻说明/刷新、自动同步不盖草稿/不发保存/无轮询、连续输入、冲突、撤销、账号暂停恢复及实际导出。不是一次聚合全绿；空回执与异步焦点检查的旧等待方式曾红，改为真实请求及持有标志，不删业务保障。复制安全test_preview_copy.py最终3 passed、退出0（6.01秒），两个独占合成schema验证业务一致、原凭据清除、序列可新增、同库拒绝和外发路由先拦截；此前合成夹具漏updated_at和独立工具未接core_bindings两红均修复，失败schema正常清理。

末轮严格typecheck退出0，build退出0；index-5Odx7rMv.js 301.32kB、ledger-BK23zCP_.js 1183.04kB、index-_wDILFg3.css 10.42kB，保留既有大分块提示；依赖版本和锁未改，冻结安装结果按保存回执。说明最后只缩短成功/空态文案，其余有效保障复用，无扩大审计。

**业务副本实际启动与归属。** 终端47258，Python14944→26784，schema frontend_rewrite_397_6a6141174b1741f3a62d9b90b1494a5b，目标mtrl_workbench_test/mtrl。启动时验证33表/32序列/16非壳项目台账一致；计数证据仅记录项目19、历史记录82、通知书1193、普通备注1，不转录明细或金额。实际应用池仅连测试库、search_path仅该schema，当前只有此预览schema，无前轮残留。资产HTTP逐字节等于最终dist，健康/ledger200，本机私有无头上下文布尔检查渲染/文案/按钮位置通过，不回传真实DOM或截图。仅测试身份登录更新时间在副本写入验证成功，未对复制的业务记录做自动写入；拦截探针用不存在的路径验证403，不尝试真实外发动作。末个元数据断言初红仅因PG把70字节application_name截到63字节，按实际标识复核已通过，不更改数据库权限或数据。

复制回执只含计数/散列，位于.artifacts/active/frontend-vue-rewrite/145721-859340-26784/logs/preview-copy-verification.json，正常退出后沿原机制归archive。预览http://127.0.0.1:8037/preview/ledger保留运行供用户验收；登录资料只查本机唯一指南。父任务协调结束后由本线程向47258发Ctrl+C，等待准确schema的ISOLATION cleaned再核消失及8037关闭；不硬杀、不按前缀删除，不删除用户已有数据库/文件。当前获准保留的有主副本不是清理遗漏。指南已同步新授权和交互，398仍待用户验收，不解锁399。


**2026-10-22 · 最后恢复守卫与现场状态更正。** 取消常驻刷新后的自查补充：撤销请求已生效但响应丢失时，错误状态提供重新加载；读回前按钮和Ctrl+Z/Ctrl+Y都不再执行下一条历史操作。只用合成夹具验证，不在真实副本做业务写入。为构建该最后修正，15:03:53已正常Ctrl+C关闭47258，收到frontend_rewrite_397_6a6141174b1741f3a62d9b90b1494a5b准确清理回执；只读确认该schema0、预览schema列表空、8037关闭。此前“保留运行”记录仅表示该次启动时状态，以此条为准。父任务随后要求容量恢复时不重复复制/启动，本线程遵守，未重建副本；继续独立完成验证/提交，当前没有可复用的活实例或有效入口。源库从未写入，不存在丢失生产数据；副本清理发生于对外重新交付人工前，只有本机测试身份登录写入，业务记录未被自动修改。最终启动须由父任务按真实状态另行协调，不冒称已失效URL可用。


**2026-10-22 · 第二轮保存冻结。** 最后恢复守卫的3项真实合成验证退出0：test_real_undo_redo_conflict_and_account_ownership、test_saved_but_refresh_failed_does_not_resubmit、test_uncertain_undo_requires_readback_before_another_history_action，共3 passed（17.28秒），已生效撤销丢回包后按钮与Ctrl+Z均不重复发起，重新加载读回原实际结果。其余本轮29项界面与3项复制安全结果按上文分轮复用，新增不确定撤销1项，因此本轮有效覆盖30项界面＋3项复制安全，不冒称一次聚合全跑。最后typecheck/build各退出0，产物index-Bp5Sr840.js 301.32kB、ledger-B1d1Lr2Q.js 1183.15kB、CSS index-_wDILFg3.css 10.42kB；frozen install退出0（33ms），锁未改。合成实屏在.artifacts/archive/frontend-vue-rewrite/145449-966726-33164/screenshots，实际查看1920整页确认说明删除与按钮位置；没有查看/回传真实副本业务截图。副本计数/散列回执已正常归档到.artifacts/archive/frontend-vue-rewrite/145721-859340-26784/logs/preview-copy-verification.json。当前无预览schema、8037已关闭、无根.env及临时脚本残留；不按最新恢复指令重复制/重启动。提交SHA和最终dirty由保存回执提供，父任务据此协调一次最终人工入口，未代用户验收。


**2026-10-22 · 父任务阻断修复：200正文未确认不按状态码放行。** 父任务只读复核发现ApiError保留HTTP200时旧控制错误分类未锁定，可能在撤销已生效但JSON损坏后再次撤销。先正常Ctrl+C关闭72726，收到frontend_rewrite_397_a802f6357acc4ce5b72677ffc538465d准确清理回执；只读复核schema0、8037关闭后才修改/构建，没有改活实例资产。

修复仅在ledger撤销/重做和可靠读回边界：POST发出后的错误、200截断JSON、合法JSON但缺明确ok:true确认，都设置账号子树内历史结果待核实锁；不把HTTP200映射为网络失败，也不再用0/409/500枚举猜结果。锁跨项目保留，按钮与Ctrl+Z/Ctrl+Y共用入口；对应范围提供重新加载。可靠台账读回后还必须用同一QueryClient严格取得并校验历史；不吞invalidate错误，结果待核实时先取消写前旧历史请求。历史正文仍损坏则锁不解除；两者可靠读回后才清对应不确定回执和锁，切回原项目不会再卡在旧锁。api.ts接口/其他业务路径未改，无后端业务规则或副本机制变更。

合成真实后端反例先取得红灯：test_applied_history_200...truncated-json-undo，1 failed/12 deselected、退出1（13.09秒），后端已成功undo再返回200截断正文，旧版确实无重新加载且撤销仍可用。新增4参数组合覆盖undo/redo × 截断JSON/缺成功确认；确认真实后端先完成、再损坏响应，锁内点击与两种快捷键不再POST，切项目仍锁，历史200损坏的恢复不提前复位，可靠读回后复位并核实际金额与单次写入，切回原项目也正常。

最终命令pytest apps/frontend/tests/test_ledger.py apps/frontend/tests/test_ledger_layout.py -q --tb=short -k 'applied_history_200 or uncertain_undo or real_undo or saved_but_refresh or continuous_edit or month_reorder or mouse_and_chinese or identity_pause'：14 passed/20 deselected、退出0（44.15秒），含原网络不确定、真实撤销冲突、保存成功读失败、连续Tab/中文/月份队列和4类身份暂停恢复；未删除真实保护、不在业务副本做破坏性测试。严格typecheck退出0，独立build退出0，产物index-BRGM6xHj.js 301.32kB、ledger-Dux9wIr-.js 1183.82kB，CSS未变；保留分块提示，锁和依赖未改，冻结安装按回执。其余未受影响结果沿原证据，不扩大其他范围或全站审计。

本地保存后按本轮明确授权重建一次最终真实只读快照副本，保持8037运行到父任务通知结束；新准确进程/schema归属由最终回执提供，不能沿用已清理72726。登录资料只查本机指南，不回传业务明细/真实截图；继续不推送、不部署、不碰源库写入、不启动399，398仍待人工验收。

**2026-10-22 · 最新反馈与完整页面关口（仅计划更新）。** 用户已明确导出是悬停即显示不能点击，尚未核实身份及其他禁用条件，不记录为保存后无反馈或猜测未登录。最新要求是页面功能与交互完整后再人工验收，不是每技术小批次或台账局部路由都叫用户试用；此前局部人工前置安排由共同规格[当前反馈与两批接续](../../frontend-vue-rewrite/spec.md#当前反馈与两批接续)的待裁定调度方案替代。A双导出/隔离出口、B读取UI反馈分别另开有界执行对话，内部核验后统一纳入完整流水欠款页（398＋405）人工关口，不在原398线程无限追加。项目完整维护回401，通知书完整页范围及399→400/401→402—405建议回共同规格；当前399仍暂停、398仍claimed，不虚报用户通过或改依赖。本次只维护文档并本地保存，未改代码、未操作预览；父任务已确认8037正常清理，新的启动须另按真实状态协调。


**2026-10-22 · A批内部交付：双独立导出与隔离出口。** 基点5163eee（业务65ad1de）；只实施398导出与405总欠款切片，B/399未启动，未代替完整页面人工验收。采用Ponytail full、Impeccable Operate及writing-for-agents；无依赖新增，身份、金额与历史写入确认口径保留。

根因证据：旧入口原生disabled由未登录、身份核验暂停、controlBusy三项驱动，却没有入口原因；control的草稿阻止/失败仅写弹窗后方回执；旧确认表排序未用于实际请求。正常登录读取、身份刷新同账号恢复和控制动作finally释放已实测，未重现永久busy，无法追溯用户原现场身份，不归因为“未登录”。现入口保留身份/忙碌/读取失败/不确定操作保护，给出就地原因；两个独立弹窗分别持有多选、选择顺序、项目排序/上移下移、确认与取消，取消后保留选择，查看仍单选。草稿保护覆盖本账号所选项目（含切走的项目），阻止原因和导出异常在弹窗内显示；导出GET失败可重试，不误置历史写入恢复锁。弹窗关闭先解除原生模态再返回对应入口焦点；换号/离页/身份暂停关闭模态，迟到文件不下载。

export_total_debt改用report_export.service.EXPORT_ROOT，正式默认仍为PROJECT_ROOT/exports，预览进本轮隔离目录。空选/缺仓库键不提交，不会把空projects误解释为全选；总欠款实际文件核单项目范围、两项目自定行序、数值金额，逐月核单本三表/ZIP项目、备注与月份，排序按确认清单真实发出。未改任何金额计算。

验证与首次失败（均保留，未删保护用例）：
- 修复前路径反例：pytest backend/tests/test_debt_export.py -k shared_export_root -q --tb=short，1 failed/4 deselected，退出1；修复前新弹窗反例1 failed，退出1。后者schema 883728c76ff74a9a947e311a10f63349正常清理，原服务日志归本机164200-750463-34768。
- 首轮新导出选集1 failed/5 passed，退出1，真实暴露下载后焦点竞争，已修复；完整原始日志 `.artifacts/archive/frontend-vue-rewrite/164525-161629-6028/logs/a-exports-first.log`。
- pytest apps/frontend/tests/test_export_dialogs.py apps/frontend/tests/test_ledger.py apps/frontend/tests/test_ledger_layout.py -q -s --tb=short：41 passed、退出0（127.61秒），覆盖真实单本/ZIP/总欠款、身份暂停/恢复/换号、草稿、错误、busy释放、焦点及65ad1de四类undo/redo坏正文、冲突和连续编辑；日志 `.artifacts/archive/frontend-vue-rewrite/164745-341217-25080/logs/a-exports-and-ledger.log`。
- 新增迟到下载换号/离页后，pytest apps/frontend/tests/test_export_dialogs.py backend/tests/test_debt_export.py -q -s --tb=short：9个浏览器＋5个后端用例全通过、退出0（后端配置叠加quiet故原始输出无计时总结，未虚构）；日志 `.artifacts/archive/frontend-vue-rewrite/165054-027737-11512/logs/a-final-edge-and-backend.log`。旧Path测试的PROJECT_ROOT替身同步改成EXPORT_ROOT；该旧替身首次留下的唯一默认目录合成文件经创建时间与固定自检行(1,2,3)确认，已精确删除文件及本轮新建空目录，无Force/递归或源库写入。
- 最后按截图修正窄屏搜索标签换行并删重复说明后，pytest apps/frontend/tests/test_export_dialogs.py -k dialog_layout -o addopts= -q -s --tb=short：2 passed/7 deselected、退出0（10.71秒）；最终浅色1440、深色大字号800两弹窗选择/确认截图归 `.artifacts/archive/frontend-vue-rewrite/165230-529245-19724/screenshots/`，已实际看图。日志为同run/logs/a-final-layout.log。
- corepack pnpm@12.14.0 install --frozen-lockfile退出0；最终typecheck和build各退出0，锁/声明未改。最终CSS index-DU0KB08V、主包index-dK56kNfW、台账ledger-BozIKtrH；保留已有大块提示。Impeccable限定三个UI文件detect返回[]、退出0；差异字节/语法由真实提交钩子再核。

本批按固定基点对调用者、状态流与后端出口自查；仅共享控制反馈返回值和导出根接合，无金额或写入协议改动，原写入/恢复保障已跑全，选自查而未假称独立审查。最终七个准确自有schema（883728c76ff74a9a947e311a10f63349、e3a4dd96296343b495dc4cb057693d9f、8526ccd212b54e169e385521ec62f77a、ce64a7933dd64f269cb12ce66e4642ce、8d5c4c2f3c234a2d92551a7112ace182、1d42ba0a838447698b6980bc454a057d、bf07b5b8baa44cf8a5f6bc9d8c4cf0da，均带frontend_rewrite_397_前缀）有正常cleaned回执，已只读核mtrl_workbench_test中全部消失；8037关闭，未建常驻真实副本。上述本机产物按现有retention保留最多30天，临时work由run主人正常收尾；整个effort仍由父任务继续，不能按本批完成清理共同规格。仅本地提交，不推送、不部署、不重启正式服务；历史原现场禁用状态未能追溯，完整流水欠款页面仍待后续实施后人工验收。
