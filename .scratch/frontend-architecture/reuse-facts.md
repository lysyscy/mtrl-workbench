# React 分支成熟能力复用：架构事实底稿

供父任务的 Astra high 路线评审与分批整改使用；这是只读调查与建议，不是批准后的架构规则或实施规格。用途结束、有效裁决已归现行主人后沿 Git 退出。项目规则仍以 [AGENTS](../../AGENTS.md)、[workflow](../../docs/agents/workflow.md)、[architecture](../../docs/architecture.md)、[requirements](../../docs/requirements.md) 及活动 React 规格为准。

## 1. 基线、覆盖与证据强度

- 实际目录：`D:/UserData/Documents/Codex/2026-10-22/task/mtrl-workbench`；Git common dir 在 `D:/dev/mtrl-workbench/.git`，后者工作树为 master，不能混用。目标分支 `codex/react-frontend-rewrite`。
- 初读 HEAD `d0413e6169a613750ae5d83aec960e9bed316425`，观察到 36 个 tracked 变动及并行任务的新文件；调查中该任务提交为 **`06ce32fd743e02ea60eadcb91c820dbf2b8bda39`**（`feat: link inventory adjustments and adopt native column sizing`）。本稿按该产品提交的最新文件重核；相对旧 HEAD 41 文件变化。收尾HEAD及origin跟踪均为 **`cd9d6f6b2e52bb38d7eacd18c243d82e0182caea`**，相对06ce32fd仅交付evidence一行变更。15:05 UTC tracked dirty为空，仅`.scratch/perf-review/`、`.workbuddy/`为既有未跟踪原件，保持原样；并行任务的inventory-adaptive活动目录已由其自身退出。
- 本机官方任务读取确认 `01a17c2a-1c9e-72f0-b414-4eef7a72dbaf` /「特殊费用模型接续 PH-20261027-fee-item-01」于15:04 UTC已 **idle / 最新turn completed**；其源码与交付记录已推送，审查关闭、原8065加载与资源收尾已完成，无未完成产品编辑。最终运行读取回执为backend_commit=06ce32fd、revision=invadj261027、source_latest=true；这是该线程的现场证据，本任务未操作预览。父任务可据此确定可编辑基线，不再误判它仍占用修改权。未发现另一个同题活动盘点；没有发消息、停止任务或启动代理。
- 检查了 15 个注册路由、全部 14 个 `*api.ts` 适配文件、共享状态/呈现/保存/历史链、构建锁与补丁、测试/审计入口，针对候选深入读源码及已安装依赖源码。覆盖地图是架构领域覆盖，不是每行代码审查、漏洞审计或全业务验证。
- `apps/frontend/src` 当时 99 个 TS/TSX/CSS 文件、约8156行；`apps/frontend/tests` 31个Python文件。仅帮助确定范围，不以行数证明需要重构。未导入应用、读取.env、连接业务库、运行产品测试/构建/预览、调用i8或打印。
- 下文“已证实”指静态源码/依赖来源事实；“推断”指可能后果；“试验”尚未运行。既有 evidence 的通过数与耗时仍属于原版本/数据/运行，不转换成本轮通过。

## 2. 实际版本与已有成熟能力

前端 `package.json`、pnpm锁与 node_modules 元数据相符：React/ReactDOM **19.3.1**，React Router **8.5.0**，TanStack Query **5.104.5**，AG Grid Community/React **36.2.0**，AntD **6.6.7**，dayjs **1.11.23**，Decimal.js **10.6.0**；TS **7.0.2**、Vite **8.3.5**、plugin-react **6.1.2**。包管理声明 pnpm **12.15.0**、Node **>=24.22.1**，未运行进程版本核验。

`backend/uv.lock` 与 `.venv/Lib/site-packages/*dist-info/METADATA`核对：FastAPI **0.143.1**、Pydantic **2.14.1**、Starlette **1.8.0**、SQLAlchemy **2.1.4**、httpx **0.28.1**；ItsDangerous不在锁/已安装元数据。后端声明Python>=3.15，未执行解释器或应用。OpenAPI TypeScript/Hey API尚未安装，本轮只查官方能力，不能称为兼容验证。

既有成熟库已经承担UI控件、日期面板、路由、查询缓存、虚拟窗口、十进制联算预览。不存在“全面换库”依据；新候选须证明能删除旧职责并降低持续维护成本。

## 3. 领域覆盖地图

路径缩写：`F=apps/frontend/src/`，`B=backend/app/`；行号按06ce32fd快照。业务细则不在本稿重复定义。

| 领域/页面 | 当前定位与关键源码 | 判定与后续边界 |
|---|---|---|
| 装配、路由、保活（15路由） | `F/main.tsx:21–51,73–108,115–168`；单注册表派生导航/标题/路由，lazy+Suspense，visited保留树，按账号重建QueryClient | 保留现有声明式Router与注册表。无需改Data Router或引入状态库；缺少页面错误边界见C2；Activity见C6 |
| 身份/网络/账号隔离 | `F/api.ts:5–89`、`main.tsx:115–164`；身份世代AbortController、核验门、旧401隔离；账号未知保树、隐藏/inert，同账号恢复 | 必须保留。Query取消不能替代“未发写入/已发未知”的分类；不设置新的核验宽限 |
| 查询、刷新与缓存 | 29个TSX文件消费Query；`main.tsx:75`关闭自动retry/focus；首页/通知书共用notices，全部项目共用projects/all；域使用invalidate+可靠fetchQuery | 保留全标脏策略，不新建写→读依赖表或乐观金额缓存。禁用查询不会立即重取，不能把invalidate完成当隐藏页已读回（C3） |
| 页面就绪/字体 | `F/page-surface.tsx:9–59`、`appearance-ready.ts:5–54`；7路由independent，工具区字体与本表就绪分开；其余仍查全局isFetching/DOM/双rAF | C1分批显式化；不把所有已独立页面重新列为待改，不用全局Suspense替换实际数据状态 |
| AG/原生表、虚拟化/合计 | `grid.ts`、`grid-layout.ts`、`grid-render-layout.ts`、`grid-presentation.tsx`、`bounded-table.tsx`；10处useGridPresentation调用（9页面文件，台账双侧复用后11表实例）；集采直接AG | 并行列宽任务已用原生拟宽/flex、浏览器布局，旧table-widths删除。富控件行高/锚点/编辑宽保护仍定制；不重复列宽研究或宣称整条测量链已退出 |
| 机械汇总/零租/包月/核对 | `mechanical.tsx:31–87,108–258`、`mechanical-details.tsx`、`mechanical-work.tsx`、`mechanical-import.tsx`、`mechanical-api.ts`；来源确认/批次/JSON/报表预览 | C4稳定renderer/列对象；来源签名、修订、确认有效月值和四页范围保留专有实现 |
| 台账/欠款与流水 | `flow.tsx`、`ledger.tsx:20–23,132–331`、`ledger-api.ts:15–80`、`ledger-controls.tsx`；双侧保活，row草稿+原月/token/串行+全页导出guard | 金额/版本/原月续接保留，不强行并入普通CellSaveQueue。`/m05/ledger/remark`仍是React消费的form写入口，API生成不能只数/api |
| 通知书/付款/关联/打印 | `notices.tsx`、`notice-payment.tsx`、`notice-maintenance.tsx`、`notice-contract.tsx`、`notice-auto-link.tsx`、`notice-print.tsx`、`payment-context.ts` | 后端整批重算、request_id、付款方式/账期预检及完整勾选保留；UI禁用不替代权限。打印/i8执行未在本轮触碰 |
| 过程资料/差异 | `process.tsx`、`process-api.ts:22–84`；原始/调整矩阵走浏览器表格，差异走共享AG；`B/mod06_proc/router.py:69,191–217`、`domain.py` | 共用CellSaveQueue，历史材料逐格expected、同月库存优先、机械确认继续属域；不重建已经退出的通用Excel导入 |
| 库存/调整 | `inventory.tsx`、`inventory-adjust.tsx`、`inventory-api.ts`、新增`inventory-calculation.ts`；`B/mod08_inv/{adjustment_values,repository,router}.py` | 并行任务已采用Decimal.js预览、旁路JSON和同原单锁，旧金额入口重读再合并；只标后端关联边界。等该任务释放后才安排任何触碰 |
| 费用/结存/年度提取/大表 | `fees.tsx:48–85`、`settlement.tsx:78–92`、`big.tsx:64–83`及各api | **费用现已纳入共享CellSaveQueue**，不能沿旧evidence再提“统一费用队列”；统一费用项/跨年名与月金额、空/零、自动项、固定月名单/顺序仍为域适配 |
| 集采主表/合同/三子表/导出 | `contracts.tsx:67–123,160`、`contract-dialog.tsx`、`contract-subtables{,-api}.tsx/ts`、`contract-tools.tsx`、`contract-export-api.ts` | 主表有专用fieldQueue及unknown门，子表有回执/来源核对；分页已用AntD。先评“状态分类一致性”，未证净收益不统一成大框架；维持付款/合同双域刷新 |
| 项目、i8配置/记录、规则、用户、首页 | `projects.tsx`、`i8{,-api}.tsx/ts`、`rules.tsx`、`users.tsx`、`home.tsx`；部分reader/写入仍内联页面 | C1/C5覆盖这些实际消费者；权限与抓取归后端，不把配置就绪当外部认证成功；不为拆文件本身实施重构 |
| 通用UI/主题/时间/关闭协议 | `ui-provider.tsx:9–42`、`styles.css`、`time-picker.tsx`、`business-modal.tsx:6–28`、`dialog-close.tsx:7–53`；主题真源`B/mod03_notice/page.py`经theme_react适配 | 已复用AntD。保单一主题角色、常驻MotionProvider、日期闭区间/周一/同年跨月、弃稿与安全焦点恢复；不恢复业务快捷键或另建设计系统 |
| API输出与前端校验 | 14个`*api.ts`＋页面内reader；`B/mod01_projects/schemas.py`已有输出模型，m05/m06/m08/m09等多为dict | C5渐进式契约试验；保金额字符串、范围身份、唯一键、来源、回执及ok:false语义，不把TS类型当运行校验 |
| 后端事务/安全历史/外部与文件 | `B/core/{money,history}.py`、`history_bindings.py`、`history_api.py`、各域service/repository；i8/client，report_export/resources | 属必要定制或本次无关业务边界；只核调用契约，不全面重构后端，不以通用undo或xlsx roundtrip替换 |
| 构建、依赖、资产与补丁 | `apps/frontend/{package.json,pnpm-workspace.yaml,pnpm-lock.yaml,tsconfig.json,vite.config.ts}`、`patches/`、`F/styles.css`；`B/core/frontend.py` | 精确依赖/严格可选、6份仅.d.ts补丁保留；CSS入口为首帧顺序；离线构建版本/完整资源核验已有工具，不再建平台 |
| 测试/测量/审计/旧壳 | `apps/frontend/tests`、`backend/tests/{db_guard,conftest}.py`、`tools/dev/{backend_verify,frontend_preview*,frontend_measure}.py`、`tools/audit`、`tools/mut` | C7先按实际消费者裁退；隔离守卫与真实业务保护保留，不把源码形状/全量变异变为每批门禁 |

## 4. 可供裁决的候选（含官方依据与真实差额）

### C1 页面显式就绪：建议优先整改，按页组推进

已证实：`main.tsx:104`只对 notices/debt/mechanical/settlement/big/process/fees 开independent；其余8路由仍在`page-surface.tsx:21–24,42`用无过滤`client.isFetching()`推首显，并订阅全账号QueryCache和MutationObserver。读其他保活页的未完网络可影响首次页面显示，这是代码路径推断，未故障注入。现有`test_startup_styles.py:122,144,160`已经保护通知书/费用工具并行及过程页不等保活i8，故不是全站从零改。

成熟能力：各页已有Query的pending/error/data状态；字体用浏览器FontFaceSet；表区已有自身preparing/ready/error。官方[Query禁用行为](https://tanstack.com/query/latest/docs/framework/react/guides/disabling-queries)与[失效重取](https://tanstack.com/query/latest/docs/framework/react/guides/query-invalidation)不承诺“账号所有请求静默=本页就绪”；本机query-core `src/queryClient.ts:494–553`也明确标脏后只默认重取active，过滤disabled/static。

真实差额是“本页首次哪些区可用”，适合由页面提供显式局部准备状态，逐页退出全局抓DOM/QueryCache判断。保留首次字体准备、局部重试、旧画面/草稿/焦点及切范围遮旧数据。先从home/i8/projects/rules/users等非网格页一组试行，再接inventory、ledger(flow)、contracts；只移除该批无消费者的兼容分支。不要新增全站状态总线。

### C2 lazy分包/页面错误边界：建议小批补齐

已证实：`main.tsx:27–48,104`lazy+Suspense，src搜索未发现ErrorBoundary/componentDidCatch/errorElement；当前`BrowserRouter`为声明式模式。官方[React lazy](https://react.dev/reference/react/lazy)说明加载Promise拒绝抛给最近Error Boundary，并缓存加载Promise。**推断**：网络失败/版本资产失效或页面render异常可能使账号树整体退出；本轮没有重现。

用React原生错误边界保护单页面，允许继续导航并保留其他已挂页面草稿；无需引包、改Router模式或自动reload整页。“重试”必须考虑lazy已缓存失败，不能简单重渲染同一lazy宣称恢复；刷新动作需明确会清本地草稿。验收故障注入一个未访分包失败、另一页草稿仍存在、导航可用、恢复入口准确。不要把所有异步写失败都交给边界。

### C3 保存/读回/草稿/撤销：建议保留，先做一致性核对

已证实：`cell-save.ts:29–135`已经抽出快照→串行→ack保后续稿→可靠read→未知锁；`use-cell-save.ts:6–25`仅适配React/history，过程/大表/年度历史结余/费用消费。台账仍有版本/原月续接，机械有批次与来源确认，库存/合同有自己的专用写队列。`api.ts:125–128`对网络、5xx、坏回执判未知；history使用预期历史头与全局guard，后端同事务全批校验。

TanStack的[mutation能力](https://tanstack.com/query/latest/docs/framework/react/guides/mutations)可以托管请求状态，但未证实能减少这些业务代码；尤其disabled隐藏页的invalidate不会形成可靠读回。**不建议引XState/全局草稿库/通用undo或整体迁useMutation**。后续只在实际漏项出现时统一结果分类，不扩大CellSaveOptions变成覆盖全部域的协议；新增/删除ID恢复、项目切换和unknown锁各自保持。现有纯队列/身份门测试已经直接装载真实TS函数，无需新测试平台。

### C4 稳定AG列与renderer：建议列宽释放后做有界试验

已证实：`mechanical.tsx:61–77`列定义useMemo依赖`rows`，内部匿名cellRenderer随rows/detail/scale重建，`defaultColDef`内联；`grid-layout.ts:19–33`用useRetainedGridColumns把替换延迟到离开输入；`grid-presentation.tsx:26–35`将列引用变化传到定义/测量准备。本机AG React36.2.0 `dist/package/index.esm.mjs:4214–4232`按prop引用不等判变化。官方[React最佳实践](https://www.ag-grid.com/react-data-grid/react-hooks/)建议稳定列/对象属性和组件引用。

可先把机械汇总的renderer与defaultColDef稳定，动态数据/编辑权限通过已有ref或context读取；金额完整下限与分组仍可随真实数据变化，因此“columns完全不依赖rows”不是前置目标。**未测量故不声称已导致可见卡顿或一定能删guard**。试验须看同范围重读时输入组件是否重挂/光标丢失，列宽及合计是否保持，再判断guard能在该消费者退出；证明全消费者无需要才删除共享hook。无需新Renderer注册DSL、深比较器或遍历全部页面机械加memo。

### C5 后端输出模型→OpenAPI→TS：建议两步试验，不立即全站生成

用Python AST静态合并各文件APIRouter常量prefix，得到147个`/api/`方法装饰器：57个GET，其中13显式response_model、27返回类型含dict、15无返回注解；全方法30显式response_model、94含dict返回。计数不是运行OpenAPI清单，动态注册、PRG和文件语义须另核；**不能沿“所有端点都无模型”的旧判断**。m01已有ProjectOut，但其project_type/status是宽str，前端仍校验合法枚举；生成TS不会自动补业务约束。

官方[FastAPI输出模型](https://fastapi.tiangolo.com/tutorial/response-model/)会校验并过滤字段；[Pydantic Decimal](https://docs.pydantic.dev/latest/api/standard_library_types/#decimals)JSON默认字符串，但不自动保证现有两位格式，本机2.14.1 `json_schema.py:717`也区分validation/serialization。官方[FastAPI生成SDK](https://fastapi.tiangolo.com/advanced/generate-clients/)支持Hey API；[openapi-typescript](https://openapi-ts.dev/introduction)只生成无运行时类型。两者未安装/运行，尚无TS7及本项目输出兼容证据。

先在已有完整输出模型的只读`GET /api/m01/projects`做离线类型生成对比，保`readProjects`语义校验与统一requestResponse身份门。若确认净收益，再选择`GET /api/m05/ledger`做完整输出DTO与旁路对比，逐字段保token/editable/counts_in_total、null/空/0、项目ID和行键唯一；然后才让DTO参与响应过滤。错误envelope和HTTP200 ok:false也须保，不丢未知字段来换类型绿灯。首批不生成付款/撤销/抓取客户端，不绕过requestJson/file与写回执确认。

生成器优先评“类型层”方案，完整SDK仅在可复用同一身份门且确实删除手写传输时考虑。验收同输入JSON字段集合、值、金额字符串、nullable与顺序完全一致，生成结果可复现；只删实际被生成替代的形状声明，保来源/账号/范围/回执语义，不能同时长期维护两套类型。若只搬一份复杂配置而未减少维护点，保留现状。

### C6 React Activity与会话签名：暂缓，无紧急缺陷证据

官方[Activity](https://react.dev/reference/react/Activity)隐藏会清Effects。当前`use-cell-save.ts:14`cleanup调用dispose，清队列/abort；`history.tsx:35–37`cleanup注销guard；main缓存cleanup亦有cancel/clear。因而用Activity替换CSS保活会改变写入与unknown生命周期，不能仅以“保存state”推安全。先保当前visited+hidden/inert/active方案，只有真实隐藏页成本证据出现才用独立只读页试验；数据/草稿所有权外提的复杂度必须计入收益。

`B/core/session.py:113–158`的v2账户票是base64+HMAC SHA256+compare_digest；时间字段签名但服务器不按其过期，400天浏览器cookie与账号停用检查已有测试。官方[ItsDangerous Serializer](https://itsdangerous.palletsprojects.com/en/stable/serializer/)能承担签名/序列化，但fallback_signers不自动兼容现有v2票格式。本机Starlette1.8.0 `middleware/sessions.py:16–54`用TimestampSigner、默认14天且通用session字典；ItsDangerous未安装。直接换中间件会改变格式/时效/续签语义。新依赖、兼容迁移与登录风险目前未证明比短签名代码有净收益，**建议保留，后续如因依赖或具体缺陷再单独裁决**；不改密钥、cookie设置或真实凭据。

### C7 旧壳解析/变异与验证工具：随真实生命周期裁退

`tools/audit/jslex.py`是旧shell_api的手写扫描器；直接消费者包括`tools/audit/shell_api.py:39`、`backend/tests/test_acc_jc_shell.py:20`、`test_ux_text.py:175`及`tools/mut/_mut_shellapi.py`。旧`/app`仍由`B/main.py`托管，正式切换与旧版退役尚未获本轮授权，因此现在不能删，也无价值另建TS/JS AST平台。退役时按消费者一并退出；Python layering/money/history等有效检查不随旧壳退出。

`tools/mut`有104个Python模块，既有脚本会改源码并finally恢复；本轮未运行。在并行工作树执行这类全量变异会碰他人修改，不能作为每批通行证。先按当前业务风险与真实目标逐个评价值；旧壳目标退役才删，后端金额/隔离/撤销反例保留有效部分。测试源码形状、纯文案/布局与同一实现镜像断言按workflow“够用即止”裁减，不为替换平台新增维护负担。

## 5. 需保住的业务不变量与明确保留项

| 不变量/已合理定制 | 当前证据与不得丢失的原因 |
|---|---|
| 金额/空/0/精度 | `B/core/money.py`为业务计算出口；两位HALF_UP、numeric(18,2)，机械原报精度在合计后舍入；F的BigInt只处理已归一2位展示/加总，新增Decimal.js只作库存预览。无需全站统一成一种数值库 |
| 身份/归属/范围 | `api.ts`世代取消与gate、账号独立QueryClient；ledger/project核对、payment-context唯一ID/完整集合校验；名字只展示或受控匹配，多命中不猜；权限仍由后端决定 |
| 写入结果分类 | 明确拒绝、未知、已成功读回失败、未发出写入分别保持；unknown锁靠可靠读回+确认解除，弃稿/切项目不自行解除；付款request_id防重复，UI abort不等于服务器回滚 |
| 草稿与连续编辑 | 草稿属账号/项目/月/记录，保存快照与后续草稿分开；鼠标离格保存/IME/输入位置、两侧滚动、切页保活继续；F5/换号才按既定语义清本地；不恢复已退役键盘增强 |
| 撤销/重做 | `B/core/history.py`、`B/history_bindings.py`、`history_api.py`：同账号锁、同事务全批校验、完整值/xmin/父子顺序/barrier；不是浏览器通用undo；旧费用历史不猜重放 |
| 源与人工/来源确认 | 库存原字段不改、调整JSON旁路、原单锁与版本；机械明细保存和有效月值确认分开；过程材料库存优先历史覆盖；不能用一般表单库消除这些判定 |
| 导出与外部协议 | 文件用完整选集与排序，非虚拟DOM；模板原字节、公式缓存/透视缓存和i8版式有真实消费者，普通openpyxl roundtrip会破坏部分模板（[模板合同](../../docs/reference/template-export.md)）；i8/IPP/SM2按[已核契约](../../docs/reference/i8-contract.md)，不泛化重试或重复登录 |
| UI与工程适配 | 单主题真源、MiSans/字号、常驻MotionProvider、业务日期包装、弃稿确认与安全焦点有明确用途；6份patch均仅.d.ts（AG2目标，AntD6目标，四rc包），不是自写运行时能力，升级时重新核适用性 |

源码是平铺的约百文件，现有域API/子组件边界已可定位；没有证据要求按目录层数重新分包、引入状态平台或替换整个组件库。`notices-api.ts:2`重导出公共金额工具属兼容入口，普通消费可随实际触碰渐进转api.ts，不为这次盘点做无行为批量清理。

## 6. 建议批次、具体验收与回退

本节为裁决前候选顺序；实施以第8节取舍及最小首批为准，不累计执行两套路线上所有事项。

顺序是评审建议，父任务/Astra裁决后再形成获准切片。各批先核HEAD/dirty/文件所有权；保留原8065及其试用数据，不把“测试需要”当切换或复位授权。

| 批次 | 内容与依赖/避让 | 最便宜有效验收 | 回退与停止条件 |
|---|---|---|---|
| B0 基线收口（事实已具备） | 列宽线程completed，产品06ce32fd、最终HEAD/origin为cd9d6f6b，后者仅交付记录；父任务固定该基线及分配文件。复用列宽结果 | 线程回执31后端/15浏览器代表通过；1项既有机械测试夹具失败保留。当前tracked干净；本任务未代跑或核验服务 | 之后若有新编辑重新核所有权；41表检查是40非账号表一致、user_account正常登录差异，不能说全表一致 |
| B1 页面故障边界 | C2单页面React边界，不改router/缓存/草稿所有权，可作为首个小切片 | 现有startup测试加代表：分包失败、另一页草稿/导航仍存、恢复入口不重复读写；严格typecheck/build | 单独提交可回退边界；若恢复必须自动丢稿则重新设计，不自动reload |
| B2 页面就绪 | C1先非表页，再inventory/ledger(flow)/contracts；依赖B0，避让所有在用grid文件，复用已独立7路由 | 延迟一个无关保活页读取，本页工具/正确空错态可用；一次字体失败重试；切回保旧内容/焦点。扩展现有test_startup_styles代表即可 | 按页回退显式接口；只退出该页已替代分支，未迁页暂留兼容，无第二套全站就绪系统 |
| B3 稳定AG引用试验 | C4只机械汇总起步，B0释放后；不改金额下限/列宽分配/富行高协议 | 一次正常与同范围重读，跟踪输入挂载/焦点、用户列宽、固定合计；仅有成本疑问时同条件采样；不复跑84组 | 无可见/维护收益则保留guard，撤回试验；有证据才扩消费者并退出旧补偿 |
| B4 API只读试验 | C5先m01已有模型类型生成，成功再m05 ledger输出DTO旁路，最后逐读域；写端点与C3专用协议暂留 | 字段/值/金额格式/null/行序对比、生成可复现、现有wrong-project/unique-key/坏回执保护继续；仅补缺口，核现有reader不是删掉所有校验 | DTO启用前对比失败不接路由过滤；单端点可回退。生成未减少手写维护点则不引入；不留长期双写模型 |
| B5 验证/旧实现减负 | C7按退役授权与真实消费者；C3只在实际分类差异有业务影响时局部收敛 | 已有隔离守卫、金额/撤销/归属代表与必要浏览器连通；删除工具先核调用者，不新设全量审计门禁 | 旧/app未退役则相关解析保留；不能借此删除业务历史/模板或放宽db_guard |

与新增视觉/动效工作的依赖：本稿不重复视觉走查。视觉整改将共享`main.tsx`、`page-surface.tsx`、`grid-presentation.tsx`、`ui-provider.tsx`、`styles.css`/主题CSS及各页面TSX；C1/C2/C4不能与这些文件的视觉改动并写。父任务先串行确定共享入口负责人，再按页面或提交批次交接；C5的后端只读DTO试验可独立准备，但同一页面reader接入仍须协调。视觉与动效可自主处理普通取舍，必须保业务入口、数据/草稿/焦点及减少动态效果；不借品质优化重做已确认使用方式，也不以“与业务无关”取消API/保存风险保障。没有为本轮调用CDP或处理权限拒绝。

C6默认暂缓；不是所有建议都要变成任务。C1/C2/C4可独立验收，不与API生成、后端认证或业务重写绑在一起。每批完成后只同步被改变的现行主人并退出已替代实现，已有可信证据足够即止；不得把“代码减少/库更多/类型检查通过”单独作为业务完成。

## 7. 来源核对与本轮边界

已查官方文档并与采用版本的本地源码交叉核对：AG React引用比较、QueryClient invalidate/refetch及disabled过滤、Pydantic decimal schema、FastAPI response_model推导/序列化、Starlette session机制、AntD6.6.7 Modal focusable/destroyOnHidden声明。在线AntD文档当前显示6.6.8，故未把其新增行为当6.6.7事实；其他latest文档也不替代锁版源码。

未核实：候选运行收益、故障注入结果、生成器版本/TS7适配、全站API完整OpenAPI、Activity安全迁移、签名替换兼容、正式切换/旧版退役、物理IME/打印/外部i8。未跑昂贵测试、未起新预览、未改产品代码、未引依赖、未写记忆、未推送/合并/部署。Git读取曾遇属主与sandbox访问问题，使用单次safe.directory参数及正式只读提权成功，未改持久Git配置。

本稿沿已安装writing-for-agents技能组织为单一阶段材料：现行规则用指针，事实/推断/建议分开，每批有完成及停止条件；research技能的委派步骤被本次明确“不启动代理”限制覆盖。只保存本稿，不新增票、状态副本或权威规则。
## 8. Astra路线裁决：先消除已定位的耦合，不为审计增加框架

本节覆盖第4、6节建议优先级，不修改权威规则。2026-10-27复核仍为`cd9d6f6b2e52bb38d7eacd18c243d82e0182caea`、tracked干净；本轮只抽查决定取舍的源码和官方机制，没有重做全仓盘点、产品修改、浏览器操作或测试。全领域审视不等于全领域必须整改；保留也是结论。

### 8.1 七项候选的明确取舍

| 候选 | 裁决 | 理由及重新开启条件 |
|---|---|---|
| C1 页面就绪 | **接受问题定位，缩小实施** | PageSurface将首次显示绑定全账号fetching，已有7页独立通路，库存已有自身Query与PreparedGrid。首批仅库存复用现有通路，不另建显式状态总线。先用现有延迟真实GET模式复现无关请求阻塞；不复现则停补丁，核对缓存/取消行为，不宣称已修。其余7个未独立页面不机械批量迁移。 |
| C2 错误边界 | **拒绝作为首批；暂缓增加** | 没有实际chunk失败、render崩溃或部署资产错配证据。“没边界”不足以证明需要立即加层。边界会卸载失败子树，不能默认保住其草稿和队列；lazy失败缓存也不是重渲染即可恢复。以后出现真实失败，再按源头选择资源发布修复或最小边界，不顺手加自动刷新、重试和恢复平台。 |
| C3 保存/读回/草稿/撤销 | **保留；拒绝单立整改批次** | CellSaveQueue已共享，专业队列和unknown/版本/原子组有业务理由。仅具体改动暴露偏差时局部处理，不再开无目标全站一致性项目，不用useMutation/XState全盘替换。 |
| C4 机械renderer/列定义 | **缩为单页、可放弃的试验** | 官方稳定引用建议与重建路径相符，尚无性能或丢焦点实证。先看同范围重读是否有不必要挂载/编辑影响；有证据再稳定Summary renderer/defaultColDef，或能直接减少闭包且无需新抽象时做小清理。rows参与真实宽度计算，保留；useRetainedGridColumns不在首试删除范围。无可说明的净收益就保留现状。 |
| C5 OpenAPI→TS | **暂缓接入，仅留窄试验入口** | m01有输出模型不等于新生成链值得维护，窄str也不能替代业务reader。当前不加依赖、不增DTO、不启用response_model过滤。视觉完成后若重复维护有实证，再做m01类型生成临时对比；确实删除手写结构、可复现且TS7适配通过才接入。拒绝把ledger影子DTO设为自动下一批。 |
| C6 Activity/会话签名 | **保留，退出本轮路线** | Activity清理Effects与队列dispose/guard注销冲突；没有后台成本证据支持迁移。会话没有已知缺陷，迁移引入票据兼容和时效风险。登录、权限、cookie、凭据不动。 |
| C7 旧解析器/验证工具 | **保留有效消费者；随实际替换清理** | /app仍在、jslex有消费者；不另建AST/变异平台，不批量删测试。实现被完整替代才核清调用者并同批退出；旧壳退役须独立范围。既有机械测试夹具失败单列，不归咎本批、不顺手扩修。 |

版本证据沿用第4节本地源码核对。本轮再次核对[React lazy](https://react.dev/reference/react/lazy)的拒绝传播和缓存、[Activity](https://react.dev/reference/react/Activity)的Effect清理、[AG React最佳实践](https://www.ag-grid.com/react-data-grid/react-hooks/)的稳定引用建议。官方文档证明机制，不证明本项目已发生故障或改造已有收益。

### 8.2 原六批的取舍与实际执行顺序

| 原批次 | 裁决后的安排 |
|---|---|
| B0 基线 | **接受，已完成。** 列宽成果保留；实施前仅核一次HEAD/dirty/所有权。视觉取证期间冻结产品源码。 |
| B1 错误边界 | **取消本轮实施。** 不以假设风险增加保护层或故障注入平台。 |
| B2 页面就绪 | **提前为首个架构小批，缩至库存。** 按8.3执行，完成先交还视觉整改。其他页按真实同类阻塞逐页处理，不新建公共就绪API。 |
| B3 稳定AG引用 | **后置、有条件。** 视觉机械页交接后做C4单页试验，不触碰宽度、虚拟化、保存协议；不能说明净收益即结束。 |
| B4 API生成 | **暂缓，不占今晚产品整改主线。** 以后有重复维护实证才评m01类型层；reader、HTTP行为、后端输出模型、ledger暂不动。 |
| B5 工具/旧实现 | **取消独立大清理，合入实际替换。** 本轮不退役旧壳，保留业务门禁和有效审计工具。 |

实际顺序：视觉基线取证完成并释放 → 库存最小批复现/实施/验证（不复现则跳过）→ 视觉统一/动效整改 → 按证据决定机械试验及其他页面同类问题。API、认证、状态管理、旧壳均不成为视觉任务前置。每批一次针对性自验即可，不增层层审查或每批Astra全审。

### 8.3 可直接交Sol的首批最小任务

**目标与前置复现。** `main.tsx:103`未将`/inventory`列为independent；`page-surface.tsx:21,42`令库存首次读取完成后仍可能被保活i8页GET记录读取阻塞。沿用`tests/test_startup_styles.py:160–172`：首次开i8，暂缓`/api/m02/fetch/records*`，转到首次进入的库存，确认库存自身读取完成而页面仍不可见；finally继续请求并解除route。只延迟真实读取，不造业务响应、不抓取/调整/写入。先记录旧行为失败；若因缓存/取消等未复现，不改变生产配置制造失败、不继续预设补丁。

**最小文件集合。** `apps/frontend/src/main.tsx`只把库存接入现有independent选择；`apps/frontend/src/inventory.tsx`以`data-page-chrome`标记现有工具/必要摘要字体范围，以已有Query状态和加载提示表达自身首次读取依赖；`apps/frontend/tests/test_startup_styles.py`补对应行为验证。无需改PageSurface公共算法、CSS、grid系列、API、后端、依赖或草稿/历史模块。禁止为单页解耦增加query-key映射表、Context状态总线、ready注册表或第二套测量协调器。

**保持自身依赖和业务前置条件。** 目标只去掉无关请求等待，库存和项目的首次读取仍须完成后再开放首次交互：沿用现有`data-page-loading`约定覆盖这两项pending，成功/失败由本地状态呈现；不混入“提前开放全部工具”。`inventory.tsx:91`项目选项同时依赖projects和inventory.projects，不能只等projects就开放空选项。PreparedGrid继续负责尺寸/错误；未读显示加载态，不显示假0/假空结果。后续刷新保留旧数据和错误，已显示页面不再次全页隐藏。调整/抓取unknown、导出前置条件、金额、筛选/定位、行键、原生列宽、保活均不变。

**够用的验证。** 上述回归先在旧行为失败、补丁后通过；再用相同真实GET暂缓模式核本页库存/项目首次读取完成前没有提前开放依赖控件，释放后可见、失败仍有原重试提示。复用库存只读检查核一次筛选切出切回、表格/合计和原列宽，不做真实调整、抓取、打印或全量业务回归。运行项目现有typecheck/build。浏览器验证须针对与源码匹配且经协调的唯一预览，不能拿旧8065的成功冒充新补丁通过；本轮无加载候选版本授权时，明确记录“代码检查完成，浏览器验证待授权”，不自行更新/重启原8065或新建预览。

**停止/回退。** 未复现原问题，或必须改保存/读取契约、公共grid、宽度策略、认证、依赖才能完成时，停在事实并缩回，不扩架构凑完成。焦点/IME、保活筛选、首次字体/表格发布或列宽回归时回退这个小补丁，再交还视觉任务。只还原本批自有diff，不reset/stash/覆盖他人修改。无净收益时保留现状是合格结果。

### 8.4 与视觉任务的串行交接

视觉只读审计任务`01a17de6-4afc-7009-90c8-3394c4338008`完成取证前，**任何产品源码修改都须等释放，不只是避免同名文件**。`tools/dev/frontend_preview_runtime.py:110–115,147–154`核前端构建及产品源散列；改不同TSX也会让原预览验证过期。本轮只改scratch不触及该范围。父任务取得取证完成/基线和写权交接后，Sol才动手；不得绕过require_latest检查，候选预览加载/更新按当次授权另行安排。

库存小批持有main.tsx、inventory.tsx及对应测试；结束交接确切HEAD或dirty diff、验证版本、未验证项，然后释放给视觉。视觉持有共享CSS、ui-provider、page-surface及所涉页面/组件期间，架构不同时改产品源码；若视觉已开始写入，库存顺延，不插入同工作树编辑。机械试验在视觉机械页定稿后接手，不靠临时stash调度。

C4另有具体适配边界：`grid-render-layout.ts:22–32`测量仅提供data/value、pinned、colDef/context及selector.params，**没有展开普通cellRendererParams**。不能按AG运行时惯例迁移参数而让测量失真；优先复用已有上下文/元数据通路，若小试验要求扩公共适配器，先停下重新衡量收益。不得删除真实rows宽度依赖或刚完成的列宽成果。

本轮无权限拒绝；后续实施前置为视觉取证/源码写权交接，以及候选版本的预览加载授权。没有运行测试不代表通过，静态推断也不冒充故障复现。本轮不推送、合并、部署，不操作真实业务数据，不改个人工作流。


**最新串行交接（父任务后续回执，覆盖第一阶段释放状态）。** 视觉第一阶段完成且未改产品，材料为`D:/UserData/Documents/Codex/2026-10-27/task-10/visual-audit/audit.md`及前图；Terra现已启动第二段有限补验：勾选同步真伪、最大字号/主题/reduced-motion及动效。**第二段结束并明确释放前，继续冻结全部产品源码**，本轮不重复审计或路线评审。释放后父任务切Sol，将main.tsx、inventory.tsx及启动测试写权交给库存最小批；未复现则不改，直接释放。完成后交接准确diff、验证版本和未验证项，再进入视觉整改；不并行写共享工作树，不自行更新原8065。

通知书勾选摘要与checkbox DOM不同步仍属待复核行为线索，不当作已确认视觉缺陷；外观辅助文字、发票子表高度、关联窗滚动、草稿日期裁切由视觉批后续处理。库存阻塞验证严格限制为测试/浏览器拦截或隔离副本中的请求延迟模拟；不得发起真实i8外部业务操作，不借复现调用抓取、同步、打印或业务写入。

**覆盖与完成状态。** 第3节各架构领域已完成事实审视；C3保存/草稿/撤销、C6保活与会话、C7仍有消费者的工具，以及列宽任务既有成果为“已审视、保留”。C1库存解耦、C4机械稳定引用为“待运行证据，尚未整改”；C5类型生成和C2错误边界为“暂缓，尚未整改”，不计为已修复。其余页面就绪/契约边界均已定位，不等于逐页运行验证通过。全站视觉的第二段证据及之后修复仍未完成。本任务交付是路线裁决与串行交接，没有实施任何产品整改。


## 9. 库存就绪首批实施与初次保存（后续验收见第10节）

父任务后续确认Terra第二段完成并释放源码；通知书勾选问题已撤回，不修不存在的bug。第二段已核代表reduced-motion运行时过渡为0、弹层关闭焦点返回触发按钮；最大字号/深色完整态尚未验。这些是视觉任务回执，非本批重新验证。父任务确认架构目标为成熟方案承担通用问题、定制保业务差额；视觉目标为全站成熟产品级一致性，不限审计列出的几处瑕疵。

本批基点cd9d6f6b，只有自有改动；库存阻塞回归在原8065真实副本上返回退出码1（12.01s）：本地`/api/m08/inventory`成功，而`库存核算期间`不可见，aria仅有“正在读取库存单据与调整单…”。测试只暂缓`/api/m02/fetch/records*`本地读取，finally释放；未发起外部i8动作或库存写入。第一次工具调用遗漏了进程会话返回，结果不作证据，重新执行所得明确退出码作为复现依据；没有将未知结果当通过。

实施复用既有independent通路：main仅加入/inventory；inventory工具和摘要标记data-page-chrome，根节点data-page-loading仍等待inventory及projects自身首次pending。PageSurface、CSS、grid/列宽、API、保存/撤销均未改。本地保存包含对应启动回归及两项自身读取延迟保护，不新增框架。后续刷新不再隐藏仍由原PageSurface complete语义持有。

验证：项目pnpm12.15.0/Node24.22.1，Corepack入口执行现有typecheck和build均退出0；构建只有大chunk提示。启动测试Python语法检查通过。最初统一prepare-build因PATH无pnpm shim退出1；随后一次日志目录不存在使命令未运行，均不计通过；创建本批日志目录后Corepack执行成功。日志及离线候选位于`.artifacts/active/frontend-architecture/inventory-ready-20261027/`，构建在work/build，尚未登记为运行候选。

**未完成验收与具体约束。** 新版的旧失败/新通过、自身延迟保护、读取错误重试、筛选保活、合计/列宽尚未在候选浏览器实测；新测试不能仅凭收集/语法算通过。登记8065仍运行旧产品，来源变动后新鲜度检查会拒绝冒充最新。项目CLI强制同仓跨工作树排他；保持原8065不动时，现行入口不能同时创建候选服务。本批不绕过锁/require_latest、不更新/停止原8065、不把旧版测试算新版本验证。父任务后续须安排允许的唯一实例验证窗口或批准既有隔离入口的具体切换，再运行新增3个case及库存既有只读代表；无需真实业务写测。本批尚未执行机械夹具测试，不新增机械失败归因。

自查按小范围可逆修改完成，不新增独立审查平台。架构写权交还父任务；视觉实施须先处理上述验证窗口与精确版本，不能把源码已提交等同整改验收完成。临时离线候选保留给该窗口使用，父任务接手后按既有run生命周期退出；无推送、合并、部署。


## 10. 库存首批浏览器验收完成及原副本保全

父任务后续明确授权独占窗口：允许通过既有唯一入口正常更新/重启本地8065，保护原数据/schema，不迁移、不重置、不触碰其他服务。此授权解除第9节候选验证限制，不扩为推送/合并/生产部署。先通过active_preview核旧进程归属，保存原owner/version及旧构建路径；专用目标核为mtrl_workbench_test、原schema `frontend_writable_61e11b3fd1fb471483b8131cb0e762e7`、修订invadj261027，等于迁移头，无需升级。保存全部41张原表摘要与列结构后才正常停止。

复用现有prepare-build入口（临时进程PATH使用Corepack pnpm转发，不改全局配置），再次typecheck/build并生成完整version清单。正常stop后，同一原run `react-writable-preview/20261025-admin-i8`以--existing、8065启动，无--upgrade-existing、--copy-source或disposable。registered_preview已核实际HTTP、构建散列及产品源码一致，产品提交为`8cf52b802d7fec184f7cce263b60ce4651f728a1`，product_digest=`5a669d472c0302146a62d3adb07cb0b792474dfecaabaa2f44987eddbce75c81`。原试用私有目录、schema和旧产品资源保留；不绕过锁或新鲜度。

实际验证：

- 新增库存无关i8 GET延迟回归、两项自身首次读取延迟保护，以及既有库存本地筛选、长行滚动/锚点/手动列宽代表，**5 passed in 33.54s**。旧行为已在第9节失败，现同一回归通过。
- 补充只读操作通过：全部库存原金额合计与真实API的Decimal汇总一致；物料筛选切出到项目档案再切回值与计数保留；首次库存GET失败显示原错误/重试入口，释放拦截后重试能显示表格。保存两张带真实预览身份的截图。无抓取、调整、导出、打印或外部i8调用，未改账号外观设置。
- 结束重读原schema/revision、全部列结构及41表摘要：**40张非账号业务表全部一致**；仅user_account有差异，本轮发生登录，账号差异单列；不宣称41表全一致。没有迁移或业务数据重置。数据库和旧产品恢复材料保持私有，不提交凭据或业务原件。

本批run为`.artifacts/active/frontend-architecture/inventory-ready-20261027/`：reports/browser.xml、readonly-extra.json、data-before.json、data-after.json及version.json绑定本次结果；logs含正式typecheck/build与启动日志；recovery保原owner/version；work/verified-build当前被8065引用，必须保留。首次未登记重复work/build与临时pnpm shim已退出。当前预览供后续视觉整改及用户查看，保持运行；旧产品构建仍是恢复点，不清理他人资源。

库存最小批至此完成技术验收；没有改共享就绪算法/CSS/grid/列宽/API/保存。采用现有通路退出了库存首次显示对全账号fetching的依赖，其余未迁页保留现状。没有运行机械测试，不冒报既有夹具已修。视觉实施仍待父任务下一批派发；最大字号/深色完整态等未验事项继续由视觉任务持有，不借库存通过宣称全站完成。
