# 付款原表核对台 · Mini App 规格

> **当前状态**：2026-10-28用户决定暂缓，尚未实施。规格与七票原地保留，当前不排期；七票统一为needs-info，待用户以后重新安排。下文保留2026-10-22规格基线，恢复时再核对主前端、后端接口及宿主变化。
> **读者**：接手实施或验收这个 Mini App 的人与 Agent。**回答**：它做什么、不做什么、界面长什么样、接口怎么接、怎么算做完。
> **何时读**：实施之前；或核实它与既有技能、系统口径、React 前端的关系时。
> **配套**：本规格（定位与边界）｜`skills/payment-plan-audit/SKILL.md`（核对口径的主人）｜`docs/guides/frontend-design.md`（界面口径的主人）｜`docs/guides/frontend-design.md`（上屏用词）｜`docs/status.md`（当前交接）。
> **探测基点**：仓库提交 `290d1e5`；本机 FastAPI 在运行（`/healthz` 200、`env=dev`）。基点只用于核对变化，**不代表测试通过或线上版本证明**。

## 1. 问题陈述

科室每月做「付款原表核对」（用户 2026-10-22 口述的现行流程）：

1. 微信收到各项目的付款计划 → 归拢成**一个 Excel**（下称**原表**）。
2. 把原表交给 agent，走既有技能「付款计划核对」：调系统接口取付款通知书，与原表核对，**核对结果落回原表**，同时把**匹配上的单据的付款方式写进数据库**。
3. 按核对结果修正原表，**再次调用技能**，看问题是否已正确匹配，并再次回写付款方式。
4. 付款时**复制单据号**到系统「付款通知书」页，快速勾选对应单据，打印或付款。

第 4 步用户明确满意，**保留不动**。费时的是第 2、3 步：它们现在要在**终端命令、磁盘上的中间文件（`context.json` → `project-map.json`）、口头确认**之间来回跳——项目归属要逐个判断，付款方式回写要「生成预览 → 口头确认 → 提交」。

**这个 Mini App 只解决第 2、3 步**：把它变成「一个页面里选文件 → 确认归属 → 确认回写」，每一步看得见、错了当场拦；第 4 步原样保留。

## 2. 已确认的决定

grill-with-docs 三轮对齐结论（2026-10-22，用户逐项确认）。**本表是这些决定的唯一真源**，别处只引用。

| # | 决定 | 依据 |
|---|---|---|
| D1 | **范围只做「付款原表核对」一条线**，闭环到「标注原表 ＋ 拟付款方式回写」 | 机械费每一步的成本是判断而非点几下，Mini App 省不了主要部分；它需要独立业务判断与范围，另按机械费任务处理 |
| D2 | 第 4 步「复制单据号」**原样保留**：仍在系统「付款通知书」页粘贴勾选，Mini App 只加一个「复制本批单据号」按钮 | 后端没有「按单据号勾选」端点，它是纯前端行为（`backend/app/web/shell/actions.js:729`），复刻会多出一份要长期跟着系统改的副本 |
| D3 | 「再核对一次」靠**手动重新选文件**拿到你改过的最新版（原表仍用 Excel 编辑） | 盯目录要处理「正改到一半被读走」的竞态；拖拽选择为主、点击选择兜底 |
| D4 | 界面口径**取交集**：技术基线用 miniapp-creator 的 `--mcode-*`（明暗双主题、语义化 HTML、可访问、加载/空/错态齐），业务布局与措辞按 `docs/guides/frontend-design.md` | `frontend-design.md` 是现行前端口径的唯一主人；前端设计的「以熟手为准」的前提是你已熟悉现有措辞，新界面你还没熟悉 ⇒ **反过来用**（用词按你的习惯定，不照抄现有页面） |
| D5 | 与 React 重做**并行长期存在**；功能上必须长期一致，后端行为变更时两边**同批同步** | 重做只是前端重做、功能上无变化；Mini App 与 React 前端覆盖同一批后端行为 |
| D6 | 通行凭证**各存各的**：Mini App 存宿主隔离的 `context.dataDir`，命令行技能仍用 `~/.mtrl-workbench/` 那份；跑脚本时用 `--session-file` 指过去 | `--session-file` 已贯通全部脚本（`audit.py:264`、`methods.py:45`、`snapshot.py:23`、`remote.py:85`）⇒ **一行现有脚本都不用改**，两边登录也不会互相顶掉 |
| D7 | 项目归属**要你把关**：Agent 提判定 → 页面逐行列出「对应哪个系统项目 ＋ 依据」→ 你改或确认后才继续 | 归属直接连着钱；既有硬约束本就是「AI 判 ＋ 必须给依据」（`skills/payment-plan-audit/scripts/projects.py:25`） |
| D8 | Agent 面板做成**通用提问侧栏**（流式回复），**不写死**「起草补正说明」 | 你的真实流程里没有「给项目经理写补正说明」这一步，写死等于造一个你不会用的功能 |
| D9 | 本规格持有定位、理由和边界 | 「为什么有第三个前端」「为什么不加后端端点」以后会被问到 |
| D10 | 全程**只跑零写库动作**；拟付款方式回写**只在你明确点头的那一次**执行 | 与本仓「真实业务写入按当前明确授权执行」一致 |

## 3. 范围与不做项

**做**

- 图形登录一次，凭证留在 Mini App 自己的数据目录（D6）。
- 拖入原表 ＋ 选计划月份（＋ 必要时选工作表）。
- 取系统快照，产出**项目归属判定表**，由 Agent 提候选、你确认（D7）。
- 跑既有技能脚本**就地标注原表**（问题格淡红／本月已付淡蓝／M 列写说明），写前自动备份。
- 拟付款方式：页面逐条列出「哪张单 / 现在是什么 / 要改成什么 / 依据」，**你点确认才提交**。
- 「复制本批单据号」按钮 ＋ 跳转系统「付款通知书」页（D2）。
- 通用 Agent 提问侧栏（D8）。

**不做（明确，写进验收）**

| 不做 | 原因 |
|---|---|
| 机械费归集 | D1。将来要做**另立 effort**，因为它要么改既有技能的「目录批次」口径，要么撞 `D26` |
| 全功能前端 | D5。只覆盖这一条线，不做第四套全功能界面 |
| 新增后端端点 | 只调既有接口，不改 `backend/`（见 §5） |
| 重写技能脚本 | 只**调** `skills/payment-plan-audit/scripts/`；匹配规则、核对口径、标注规则的唯一主人是 `skills/payment-plan-audit/SKILL.md` |
| 接管第 4 步的粘贴勾选 | D2。仍在系统页做 |
| 代你付款、打印、选付款对象 | 既有口径：技能不代替选择付款对象、打印或登记付款 |
| i8 抓取、集采、台账等其他模块 | 超出这一条线 |

**与 `D26`「导入只留通用面」不冲突**：本 Mini App 不碰 `/api/imp/*`，只碰 `GET /api/m03/plan-audit/snapshot` 与 `POST /api/m03/plan-audit/methods`。

## 4. 术语对齐

附件提示词用的词与本仓不是一回事。**本件与后续实施一律用右列**（`docs/requirements.md` 是术语的主人；本仓不单建 `GLOSSARY.md`）。

| 附件用词 | 本仓用词 | 出处 |
|---|---|---|
| 付款计划核对 | **付款原表核对**（技能对用户显示名仍叫「付款计划核对」） | `docs/status.md`「原表核对归skill」 |
| 付款计划台账 | **无此物**。m04 页面与写入口已退出 | `docs/status.md` |
| 通道一 / 通道二 | **流程**（本仓用「模块／域／流程」，不用「通道」） | `docs/requirements.md` |
| 待导入 | **快照**（通道一没有导入面） | `GET /api/m03/plan-audit/snapshot` |
| 系统现状 | **快照**（同上） | 同上 |
| 写库 / 落库 | **写入** | 前端设计的熟手文案 |
| 原表 | **原表**（你归拢出来的那份 Excel） | `skills/payment-plan-audit/SKILL.md` |

**另一处易混**：附件把「过程资料」和「机械费明细」混成一件事。实际是两个落点——`m06_proc`（过程资料·材料机械消耗汇总表，六个金额列）与 `/api/m06/workbench/import-preview`（机械费**明细**录入）。本 Mini App 两者都不碰。

## 5. 接口与脚本契约（均已实测）

### 5.1 只读端点

| 端点 | 用途 | 实测 |
|---|---|---|
| `GET /api/m03/plan-audit/snapshot` | 取核对快照：当前项目、全月份通知书、有效付款流水 | **需登录**（`backend/app/mod03_notice/plan_audit_api.py:17-24` 自己判会话，不是全局「读放行」那一条） |
| `POST /m15/login` | 登录，form `account`／`password`／`next` → `Set-Cookie: mw_session` | 存在（`backend/app/mod15_user/api.py:176`） |

⚠️ 全局鉴权门是「**读放行、写拦**」（`backend/app/main.py` 的 `auth_gate`）；未登录的写动作返回 401 `{"code":"unauthorized","message":"未登录：本系统未登录只能查看，改数据请先登录"}`。

### 5.2 写库端点（**唯一**，需你明确点头才调）

`POST /api/m03/plan-audit/methods`，体 `{preview_json: "<JSON 字符串>", approved_sha256: "<64 位 hex>"}`。

服务端校验链（任一不过 ⇒ **整批不写**，HTTP 409）：

1. `sha256(preview_json) == approved_sha256`
2. `preview.schema == 1` 且 `preview.changes` 非空
3. 每条 change 的 `new` 必须是合法付款方式、`old` 必须匹配
4. `preview.snapshot.database_fingerprint` 必须与当前库一致（**系统变了就拒**）
5. 写入时逐单复查：单据仍唯一且存在、`ownership_id` 与 `planned_pay_method` 原值未变、审批/已付金额未变 ⇒ 任一单变化则**整批回滚**

⇒ 这套「预览—确认—提交」本来就是后端设计好的三段式，Mini App 直接用，**不要另造一套确认逻辑**。

### 5.3 技能脚本 CLI（只调，不改）

解释器：材料工作台 `backend` 项目的虚拟环境（依赖由 `backend/pyproject.toml` ＋ `backend/uv.lock` 管理）；路径做成可配置。

| 命令 | 作用 | 关键约束 |
|---|---|---|
| `audit.py --prepare --source <原表> --month <YYYY-MM> [--sheet <名>] --output-dir <新目录> [--session-file <路径>]` | 取快照 ＋ 生成项目匹配上下文，**原表不标注** | 输出目录**必须新建且独立**（已存在即拒）；产出 `snapshot.json`＋`context.json` |
| `audit.py --source <原表> --month <YYYY-MM> --project-map <映射.json> --output-dir <新目录>` | 匹配、核对并**就地标注原表** | 写前自动备份；标注后原文件再变化 ⇒ 拒绝；产出 `audit.json`／`snapshot.json`／`method-preview.json` |
| `methods.py --preview <method-preview.json> --approved-sha256 <sha> --receipt <回执路径>` | 提交拟付款方式回写 | `--approved-sha256` 必须等于预览文件的 sha256；`--receipt` 路径必须不存在 |
| `remote.py --server <地址> --account <账号> [--session-file <路径>]` | 登录并存会话 | 密码隐藏输入、**只存会话不存密码**；Mini App 走图形登录，**不需要**用它 |

⚠️ **不要传 `--repo`**：那会让脚本改用仓库内的仓库规则与备份路径。默认备份落 `~/.mtrl-workbench/backups/payment-plan-audit`。

### 5.4 中间文件

| 文件 | 谁产出 | 内容 |
|---|---|---|
| `context.json` | `--prepare` | `{schema:1, project_catalog_sha256, projects[], plan_projects[{source_project, title_cell, notice_owners}], instruction}` |
| `project-map.json` | **Mini App 生成**（Agent 判定 ＋ 你的修正） | `{schema:1, project_catalog_sha256, decisions[{source_project, project_id, reason}]}`；必须**覆盖原表每一个项目**、每条带理由、不重复；项目清单变了要重新匹配；判到壳项目或已不存在的项目会被拒 |
| `method-preview.json` | 标注那步 | 待回写清单 ＋ `source_sha256` ＋ 快照指纹 |
| 回执 | `methods.py --receipt` | `{status, preview_sha256, source_sha256, changes, applied_at}` |

⚠️ **回写前原表必须没被改过**：`methods.py` 会校验 `sha256(原表) == preview.source_sha256`。你改了 Excel 就得**重新核对**——这正是第 3 步的循环，页面要把它讲清楚。

## 6. 界面规格

### 6.1 形态

**单页、单列纵向工作流**，五段，**每段完成才开放下一段**。⛔ 不做附件那套「左栏系统现状／中栏待导入／右栏 Agent」三栏并排——那是附件作者的设计，本项目口径是紧凑业务工作台（`docs/guides/frontend-design.md`“阅读与操作”），且通道一没有「待导入」可并排。

**Agent 侧栏**（通用提问、流式）在第 2 段兼任「跑归属判定」的角色，其余时候是提问工具。

### 6.2 五段

| 段 | 做什么 | 完成判据（用户视角） |
|---|---|---|
| ① 选批次 | 拖入原表（Excel）＋ 选计划月份（能从表头/文件名唯一确定就预填，否则让用户选）＋ 必要时选工作表 | 显示文件名、所在位置、字节、修改时间、月份；来源不明时**停下来问**，不猜 |
| ② 核对 | 「开始准备」→ 取快照 → 出**项目归属判定表**：每行＝原报项目 / 对应系统项目（仓库全名·展示名）/ 依据 / 你的修正 | 每行都有依据；你改完并确认才开放第 3 段；项目清单变了要提示重新匹配 |
| ③ 标注 | 跑标注（**就地改原表**，写前自动备份） | 显示问题格数、本月已付格数、备注文案；给「打开标注后的原表」入口 ＋ 备份位置；重跑只清本技能标记，人工说明与格式保留 |
| ④ 回写付款方式 | 逐条列出「哪张单 / 单号 / 现在是什么 / 要改成什么 / 依据」 | **不点确认就不写**；点确认后提交，回执的条数与列表条数一致；系统变了就明确拒绝并说人话 |
| ⑤ 交给下一步 | 「复制本批单据号」→ 剪贴板 ＋「打开系统付款通知书页」 | 剪贴板里是本批**完整**单据号；提示你去系统页点「粘贴单据号勾选」 |

### 6.3 状态与口径

- **状态齐**：加载／空／错误／部分成功／无变化五种都要有真实可见的样子（`frontend-design.md`“状态、颜色与反馈”）。出错时**保留页面结构**，不整页崩。
- **结论贴在对象上**：问题在哪行哪格、哪个单据有问题，写在那一行／那一格旁边，不只在页头说「有异常」（前端设计“状态、颜色与反馈”）。
- **异常与正常跳过异色异词并分别解释**（同上）；只有一类时不硬造分类。
- **关键数字带对象与时间口径**：金额写清是哪个项目、哪个月；未知值不显示成 0（同上）。
- **上屏用词**：熟手文案口径，但**反过来用**（D4）。⛔ 报错里不出现英文异常原文、文件路径、内部字段名（`project_input`、`bill_no`、`mw_session` 这类不上屏）；你自己选的文件名与位置可以显示。
- **视觉**：`--mcode-*` 15 个变量（`--mcode-bg`、`--mcode-bg-secondary`、`--mcode-surface`、`--mcode-surface-muted`、`--mcode-text`、`--mcode-text-muted`、`--mcode-text-subtle`、`--mcode-border`、`--mcode-border-strong`、`--mcode-accent`、`--mcode-success`、`--mcode-warning`、`--mcode-danger`、`--mcode-primary-action-bg`、`--mcode-primary-action-text`），`:root,[data-theme='light']` ＋ `[data-theme='dark']`，至少支持 `prefers-color-scheme` 映射到 `data-theme`，⛔ 不强制明暗、⛔ 不读宿主 `--bg_*`／`--text_*`。
- **可访问**：语义化 HTML、连续标题层级、交互元素有可见文本或 `aria-label`、可键盘访问、焦点清晰、状态消息用 `role="status"`／`role="alert"`、⛔ 不单靠颜色传达成功/错误/选中、⛔ 不用 emoji、⛔ 不用远程字体/图片/CDN、`prefers-reduced-motion` 下移除位移与连续动画。

## 7. 数据与安全边界

| 项 | 约束 |
|---|---|
| 通行凭证 | 存在 Mini App 自己的 `context.dataDir`；⛔ 不进包、不进页面 JS、不进日志、不进 SSE/WS 载荷、不进错误响应；密码只走一次登录表单，不落盘 |
| 与命令行技能 | 各存各的（D6）；跑脚本用 `--session-file` 指到 `context.dataDir` 里的那份 |
| 真实写入 | 只有第 ④ 段、只有你点确认的那一次会写库（D10） |
| 原表 | 标注是**就地改**；写前自动备份到 `~/.mtrl-workbench/backups/payment-plan-audit`；文件被占用或处理期间变化 ⇒ 拒绝覆盖 |
| 批次工作目录 | 每批新建独立目录，放 `context.dataDir` 下（不进仓库、不进你的文档目录）；标注后的原表通过下载交给你 |
| 后端 | 只读既有端点，⛔ 不改 `backend/`、不新增端点 |
| 技能脚本 | 只调不重写；⛔ 不改 `skills/payment-plan-audit/` |
| Mini App 包 | `miniapp.init` 返回的 `packagePath`（默认 `miniapps/<pluginId>/`），⛔ 不另造目录 |
| Agent 权限 | `agentAccess` 的**唯一合法值是字符串 `"session.run"`**（⛔ 不是数组）；页面侧跑的是**所在聊天会话的 Agent**（带科室技能），Node 侧跑主 Agent；⚠️ 宿主当前会话上下文**传不进去**（聊天历史不会自动进请求） |

## 8. 验收标准

做完＝下面每条都**有证据**（命令、截图、或回执），不是「应该能」。

1. 拖入一份真实原表 ＋ 选月份 → 页面显示文件信息，且快照**真实取到数**（非空、月份正确）。
2. `--prepare` 跑通 → 判定表出现，**每行有依据**；项目清单变化时提示重新匹配而不是硬跑。
3. 改一条判定 → 确认 → 标注跑通 → **原表被就地标注**（问题格淡红／本月已付淡蓝／M 列说明），且备份文件存在。
4. 重跑同一份已标注表 → 只清本技能自己的标记，**人工说明与格式保留**。
5. 拟付款方式：页面列出待改清单 → **不点确认就不写**（后端无写入痕迹）；点确认后提交成功，回执 `count` ＝ 清单条数。
6. 标注后手动改原表 → 回写被拒，页面说人话（不出现异常原文）。
7. 「复制本批单据号」→ 剪贴板得到本批完整单据号；**人工验证**系统页「粘贴单据号勾选」仍按预期勾选。
8. 未登录时页面明确要求登录；写入端点返回 401 时页面提示登录，⛔ 不显示英文原文。
9. Agent 侧栏跑通一个回合并显示流式回复；第 ② 段的归属判定由 Agent 产出且**可被你改**。
10. 明暗主题都可用；加载/空/错/部分成功状态齐；键盘可达；⛔ 报错里无英文异常原文、路径、内部字段名。
11. `publish` → `inspect` → `open` 三步走通；在 **`miniapp.open` 托管的那个标签页**里完成一次真实读取检查（普通 Browser 标签页无托管凭据，会 401）。
12. 交付报告区分**已验**与**未验**（写入、实体打印、第二台电脑、办公网访问一律按未验记）。

## 9. 未验边界与风险

| 项 | 状态 |
|---|---|
| 拟付款方式**真实写入** | 未验。验收只跑零写库动作；真写等你明确授权（D10） |
| 实体打印、第二台电脑、办公网访问 | 未验，不在本次范围 |
| Node 出网限制、凭据能否落盘 | **宿主技能文档里没有对应条款**（已搜 `egress|outbound|whitelist|internet` 及凭据落盘表述）⇒ 规格里不作断言，按「只落 `context.dataDir`」实现即可 |
| 与 React 前端的功能一致度 | 只到**约定**（D5）。React 重做尚未实施，实际一致度未验；维持靠「后端行为变更时两边同批同步」 |
| 附件提示词的接口契约 | **多处与本机不符**（对照表见 §11）。以本件 §5 为准 |

## 10. 实施分解

每步有完成判据；执行入口按 `docs/agents/workflow.md`（`implement-solo-spec` → `references/execution.md`），核验范围按该工作流。

| 步 | 做什么 | 完成判据 |
|---|---|---|
| 1 | `miniapp.init` 建包（`pluginId` = `payment-plan-audit-desk`，中文名「付款原表核对台」），`manifest` 声明 `agentAccess: "session.run"` | `miniapp.inspect` 能读到包身份与两个非空 payload 根 |
| 2 | Node 域服务：登录（存 `context.dataDir`）、跑脚本（`--session-file` 指向它）、每批新建输出目录、把标注后的原表交回页面 | 服务能独立登录并取到一次真实快照 |
| 3 | 页面骨架：五段工作流 ＋ `--mcode-*` 主题 ＋ 加载/空/错态 | 五段状态齐；明暗主题都可用 |
| 4 | 第 ①③ 段：拖拽选文件、选月份、跑 `--prepare`、判定表、标注、复制单据号 | 验收 1–4、7 通过 |
| 5 | 第 ④ 段：待改清单 → 确认 → 调 `methods.py` → 回执 | 验收 5、6 通过（**不点确认时不写**） |
| 6 | Agent 侧栏：通用提问 ＋ 第 ② 段跑归属判定 | 验收 9 通过 |
| 7 | 发布与真机检查：`publish` → `inspect` → `open`，在托管标签页里做一次真实读取 | 验收 10–12 通过 |

⚠️ 实施期**不要**改 `backend/`、`skills/payment-plan-audit/`、以及现行业务/前端口径正文；需要改时先回本件登记。

## 11. 附：附件提示词与本机实测差异表

附件是**别的机器上的 agent 写的提示词**，多处与本机不符。**本表是唯一对照处**，别处不重复。

| 附件写的 | 本机实测 | 依据 |
|---|---|---|
| `GET /api/m04/plans?year_month=` | **404**，无 `/api/m04/*` 路由 | 实测 404；`docs/status.md`「m04页面和写入口退出」 |
| `/api/imp/m04_plan/{schema,options,parse,preview,commit}` | **不存在**；`/api/imp/domains` 只有 `m06_proc`、`m06_mech_report` | 实测 |
| 读取端点「未登录一律放行」 | 全局门是「读放行写拦」，但 `GET /api/m03/plan-audit/snapshot` **自己要求登录**（401） | `backend/app/mod03_notice/plan_audit_api.py:17-24`；实测 401 |
| 通道一＝解析→差异→写入系统付款计划台账 | 真实＝**在原表 Excel 上就地标注**；写库的唯一动作是**拟付款方式回写** | `skills/payment-plan-audit/SKILL.md` |
| 通道二＝收一个 Excel→解析→写入 | 真实＝**给一个月总目录**，逐本盘点→提取→生成 JSON→录入预览→确认写入 | `skills/machinery-fee-consolidation/SKILL.md` |
| cookie 12 小时 | `mw_session`，浏览器持久 400 天，服务端签名票 | `backend/app/core/session.py:39-42` |
| 机械费字段 `in_*`／`out_*`／`mech_0..5` | ✅ **完全正确** | 实测 `/api/imp/m06_proc/schema` |
| （附件漏了） | `m06_mech_report` 域、`POST /api/m03/plan-audit/methods`、`/api/imp/m06_proc/rollback`、`/api/m06/workbench/{preview,export}`、`/api/m06/matrix` | 实测 OpenAPI |
| `agentAccess: ["session.run"]` | 唯一合法值是**字符串** `"session.run"` | `miniapp-creator/references/package-contract.md` |
| `open_tab` 不带凭据 ⇒ 401 | 方向对，**机制归因要改**：`open_tab` 是 Browser 工具动作、不是 Mini App 动作；依据是**回环守卫**（只有 Desktop 托管页面与托管 MCP 客户端带本轮凭据） | `miniapp-creator/references/security-and-state.md` |
| `minimax-code-visual-ui` 是可引用的基线 | 是技能内**一份参考文档**（非可安装包），含 15 个 `--mcode-*` 变量 | `miniapp-creator/references/minimax-code-visual-ui.md` |
| 密码/cookie「只能待 Node 内存、不许落盘」 | **官方无此硬规定**；原话是「凭据不得进 HTML／页面 JS／日志／SSE·WS 载荷／错误响应」，持久状态**允许落 `context.dataDir`** | 同上 `security-and-state.md`、`data-access.md` |
| 「页面上 Agent 能拿到聊天上下文」 | **拿不到**；`message` 命名空间不授予聊天历史，聊天框内容不会自动进请求 | `miniapp-creator/references/agent-interaction.md` |

## 12. 名称与标识

| 项 | 值 | 备注 |
|---|---|---|
| 中文名 | **付款原表核对台** | 附件原名「材料科归集台」暗示两条线，本次只做一条 ⇒ 按实际范围改名；要改回说一声即可 |
| `pluginId` | `payment-plan-audit-desk` | `miniapp.init` 的入参；包落 `miniapps/payment-plan-audit-desk/` |
| effort 目录 | `.scratch/miniapp-payment-plan-audit/` | 本件所在 |
| 定位与边界 | 本规格“定位与共用边界” | D9 |


## 定位与共用边界

本Mini App长期与旧前端/React并存，只编排付款原表核对，不扩大为全功能前端。省去终端、中间文件与口头确认之间的来回；核对口径仍归payment-plan-audit技能，不重写脚本。只复用既有snapshot/methods端点，预览指纹、快照指纹、原值、审批/实付及合同校验继续在原后端，不复制一套护栏。后端行为变化时相关客户端同步。

不接管实际付款、打印或选择付款对象，第4步复制单据号并去通知书页粘贴勾选保留。每个真实拟方式回写须用户明确确认，其余阶段零写库。机械费不在本effort，不因旧导入约束为它另造入口；本流程不碰/api/imp，不构成第二导入面。

宿主agentAccess使用字符串session.run；页面侧为所在聊天会话Agent，Node侧为主Agent，宿主当前聊天上下文不能假定传入。Mini App凭证存隔离context.dataDir，命令行技能沿自己的会话存储，--session-file复用既有脚本。归属判断须有依据并覆盖原表每个项目，经页面用户确认后才继续。具体实现仍按本规格原范围/验收及当次授权。
