# TAIL-479 过程资料／机械费工作区加载接入 · 实施与验证证据

- 票：[TAIL-479 过程机械工作区加载接入](../../tails/issues/TAIL-479-过程机械工作区加载接入.md)
- 共同规格：[spec.md](../spec.md)
- 复用样板：[TAIL-477.md](./TAIL-477.md)、[TAIL-477-acceptance.md](./TAIL-477-acceptance.md)、[spec.md](../spec.md) §60/§62，[frontend.md](../../../docs/architecture/frontend.md):19/27/29/31/33/35
- 工作树：`D:\dev\mtrl-workbench\var\worktrees\browser-session-loading-20261104`
- 分支/基点：`codex/browser-session-loading-20261104` / `9efebc87`（累计起点 `22cc48f8`）
- 记录时间：2026-11-04（本地时间；浏览器时区不可用，未做时区换算）

## 一、结论摘要

477 已经在 `apps/frontend/src/read-region.tsx` 做出六态读取呈现能力（`readPhase` / `ReadPlaceholder` / `ReadFailure`），在 `flow.tsx` 做出「网格之前的固定高状态槽」。本票不复用欠款的**形状**（`.debt-overviews` 三卡 + 8 行骨架是欠款页的几何），而是复用两者**实际适用的机制**：六态判定、无值占位、原位失败 + 重试、恒高状态槽；并把「数据区整体被一条读取提示替换」的控制流改成「工具区先就绪、数据区各自占位」。

改动落在两个页面的**加载门本身**，不重做页面：

1. **过程资料**：`apps/frontend/src/process.tsx:175-180` 原来是
   `{query.isPending?<p role="status" data-page-loading>正在读取过程资料…</p>:query.isError&&!matrix?null:!matrix?<p>暂无有数据的项目。</p>:<>…</>}`。
   三个缺陷都在这一行里：挂起时把工具区外的全部内容替换成一行 `data-page-loading`（`page-surface.tsx:34` 因此**不发布首帧**，整页连带工具区一起等）；读取失败且无矩阵时 `null`（静默空白）；无数据时只给一行裸文本、没有数据区几何。
   现在：固定高状态槽 + 数据区占位/终态二选一，`data-page-loading` 在本页彻底移除。
2. **机械费**：`apps/frontend/src/mechanical.tsx:297` 原本是**一条**同时表达两个查询（项目清单 + 月度工作台）错误/挂起/空态的段落，且它出现在内容之后，出现/消失会推移下方全部区域；明细（`:292`）与核对工作台（`:295`）在挂起或失败时**整块消失**。现在：两个查询各自在原位报告、恒高状态槽、明细/工作台/汇总都保留自己的位置，只有各自的区内容换成占位。

金额、权限、字段、排序、合计、导出、保存、撤销、列宽、字号主题、滚动策略、查询身份、草稿生命周期**均未改写**；没有新增轮询、缓存时长、延迟、重试策略、键盘增强或风格重做。

## 二、修改清单

| 文件 | 类型 | 内容 |
|---|---|---|
| `apps/frontend/src/process.tsx` | 修改（+17/−3） | 引入 `read-region` 三件；`:159` `readState=readPhase(query,(query.data?.projects.length??0)===0)`；`:161` `regionNote`（只有 `settled` 才表态：`empty` 或无矩阵且已选项目 → 「暂无有数据的项目。」，未选项目 → 「请选择项目查看资料。」，其余为空）；`:168` 新增 `.process-read-status` 恒高槽（`data-read-phase`/`aria-busy`，内含 `ReadFailure`/`read-announce`）；保存类提示（`error`/`uncertain`）与原「重新核对」按钮拆成独立 notice，不再与本区读取状态混用；`:175` `data-page-loading` 门替换为 `{matrix ? …grids… : <div className="process-read-body">{regionBody}</div>}` |
| `apps/frontend/src/process.css` | 修改（+5） | `.process-read-status`（`height:var(--control-h)`，恒高、不推移）、其内 `.notice` 单行省略号规则、`.process-read-body`、`.process-read-note` |
| `apps/frontend/src/mechanical.tsx` | 修改（+14/−5） | 拆出 `scopeMismatch`（范围不一致）与 `scopeError`（含读取错误文案）；新增 `monthRead=readPhase(state)`、`readBody=<ReadPlaceholder rows={6} quiet={monthRead==='error'} />`；新增 `.mechanical-read-status` 恒高槽（月度读取 + 项目清单读取各自 `ReadFailure`、`read-announce`）；明细区 `state.data ? <DetailsTable/> : <div className="mechanical-read-body">{readBody}</div>`；核对工作台同法；汇总区同法；旧的整体门段落删除；「暂无已保存月份」「请选择项目查看报表」改由读取终态门控 |
| `apps/frontend/src/mechanical.css` | 修改（+4） | `.mechanical-read-status`（恒高）、其内 `.notice` 单行省略号规则、`.mechanical-read-body` |
| `apps/frontend/tests/test_process_mechanical_loading.py` | 新增（148 行，4 例） | 本票具名行为检查：工具区先就绪、数据区自行报告读取、失败原位不推移、失败不冒充空态 |
| `.scratch/browser-session-loading-20261103/evidence/TAIL-479.md` | 新增 | 本文件 |

未触碰：`read-region.tsx`、`grid-presentation.tsx`、`page-surface.tsx`、`main.tsx`、`ui.css`、`style.css`、`package.json`、`mechanical-work.tsx`、`mechanical-details.tsx`、backend、fees 页、共享规格、票状态、索引、Git。

> `mechanical-work.tsx`/`mechanical-details.tsx` 在本票写域内但**未改**：两者都只消费已经读到的 `data`，自身的 `ReadGrid` 已各自负责测量、首显与局部失败重试。工作区消失是父级门控造成的，改父级即可，不需在这两个文件里复制形状。

## 三、控制与数据流依据

### 3.1 首帧门控

`apps/frontend/src/page-surface.tsx:34`：`if (node!.querySelector('[data-page-loading]')) return;` — 只要页内还存在任何 `[data-page-loading]` 后代，PageSurface 就**不发布首帧**，`page-view` 保持 `visibility:hidden`。`process.tsx`（改动前 `:164`）原来正好把这一标记用在自己的整页等待上，于是「工具框架可先用」在结构上不可能发生。

同时 `page-surface.tsx` 会在字体加载后比较全部 `[data-page-chrome]` 的文本集合，前后不一致就重新排期；因此新增的状态槽**必须放在 `[data-page-chrome]` 之外**。两页的工具条/筛选/页签仍各自保留 `data-page-chrome`，状态槽渲染在其后。

`docs/architecture/frontend.md:33` 要求「过程工具字体与自身数据并行，外框保持满内容区并等本表真实拟宽；过程矩阵沿同一字体与布局准备发布」——移除 `data-page-loading` 后正是这个边界；`:27` 对机械/材料报表要求「沿同一工具区/表区边界发布」，机械页本来就没有 `data-page-loading`，本票保持不加。

### 3.2 六态判定与「不冒充」

两页都用 `readPhase()` 而不是自己写 `isPending/isError` 判断：

- `reading`（`isPending && isFetching`）→ 槽内只放 sr-only `read-announce`，数据区放 `ReadPlaceholder`（`aria-hidden`，行条无金额/条数/百分比）。**短请求不会闪提示文字**：没有新增任何延迟或最短展示时间，占位本身就是纯空间。
- `error`：无历史数据时是 `error`，有历史数据时是 `stale`。两者都进 `ReadFailure`，`stale` 在文案上明说「更新未成功，保留上次结果」，`retained` 进一步把项目清单那条区分为「项目清单更新未成功，保留上次结果」。
- `empty` / `ready`：过程页用 `readState==='empty'||(settled&&Boolean(warehouse))` 决定是否写「暂无有数据的项目。」——`settled&&Boolean(warehouse)` 这一条是为了**不在尚未选定项目时就宣称没有数据**。机械页把「请选择项目查看报表」门控在 `monthRead==='ready'||monthRead==='empty'`，所以读取中不会被误报成空报告。

### 3.3 恒高槽（不推移、不遮挡）

477 的教训是「提示放在流内会推移、绝对定位会压标题/数值」，结论是恒高状态槽。两页照此：

```
.process-read-status / .mechanical-read-status{height:var(--control-h);display:flex;align-items:stretch;padding:0 16px;overflow:hidden}
… > .notice{flex:1;min-width:0;flex-wrap:nowrap;overflow:hidden;padding:0 10px;font-size:12px}
… > .notice > .read-failure-text{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
```

槽在任何阶段都占 `var(--control-h)`（`ui.css:1` 定义 `--control-h: calc(32px * var(--fscale))`），空/读取/失败三态高度相同，因此下方区域不移动，长文案被截断而不是换行增高，`重试读取` 按钮 `flex:none` 常驻可点。这是 `apps/frontend/tests/test_process.py:342-368`（首可见帧 30 帧几何必须完全一致）成立的前提。

### 3.4 主次依赖分别门控（机械页）

机械页有两个查询：`['projects','all']`（项目清单，次要）与 `['mechanical-state',month]`（月度工作台，主要）。原代码把它们合成 `const error = projects.error || state.error` 一条提示，且所有内容区都用 `!state.isError` 门控，于是**项目清单读取失败会清空整张报表区**。

现在：`scopeMismatch`（所选项目范围变化）单独保留、仍用原 notice；两个查询各在自己的槽位 `ReadFailure`（各自 `refetch`）；内容区只用 `state.data` 门控。项目清单失败时月度数据仍展示，槽内用 `retained` 说明保留的是上次结果。

### 3.5 编辑与保存不受影响

两页的 `useCellSaveQueue` 调用、`writable`/`disabled`/`paused` 判定、列定义、`measurement`、`scope`/`identity`、`reload()`/`readMonth()` 全部原样。特别地**没有**把工作区门控成 `!isFetching`：查询在后台重读时编辑器仍可输入，符合「编辑会话保当前列宽」「不覆盖下一格输入」。

## 四、验证

### 4.1 已执行（本机源码树，全部返回原始退出码）

| 命令 | 结果 |
|---|---|
| `cd apps/frontend && node ./node_modules/typescript/bin/tsc --noEmit --pretty false`（最终一次） | `tsc_exit=0`，无任何输出；之前一次（并行会话的 `notices.tsx` 尚未收敛时）为 `tsc_exit=1`，错误只出现在 `src/notices.tsx(30,10) TS6133` 与 `src/notices.tsx(99,9) TS6133`，过滤 `src/(process\|mechanical)` 为 `grep_exit=1`（无匹配） |
| `cd apps/frontend && node --import=tsx --test tests/unit/read-region.test.mjs tests/unit/mechanical-api.test.mjs tests/unit/grid-width-state.test.mjs` | `EXIT=0`，`tests 21 / pass 21 / fail 0`，`duration_ms 1720.3` |
| `cd apps/frontend && python -m py_compile tests/test_process_mechanical_loading.py` | `py_compile_exit=0` |

注：`node ./node_modules/.bin/tsc` 不可用（该 `.bin/tsc` 是 shell 垫片，Node 直接执行报 `SyntaxError: Invalid or unexpected token`），必须走 `./node_modules/typescript/bin/tsc`。

单元覆盖与本票直接相关的判定：`readPhase` 六态（含「已有结果后失败 → stale 并保留结果」）、机械工作台分页/合计/内租/历史起点、网格列宽状态。

### 4.2 新增具名行为检查（未在本会话执行）

`apps/frontend/tests/test_process_mechanical_loading.py`，4 例，用真实端点的「挂起 → 放行/503」而不是伪造业务数据：

1. `test_process_tools_appear_before_the_matrix_read` —— 挂起 `/api/m06/matrix` 与 `/api/m06/mech-screen`：工具条/项目选择/页签可见；槽 `data-read-phase="reading"` 恰好 1 个 `role=status`、0 个 `.notice`；数据区 1 个占位、0 个「暂无有数据的项目」；`.process-matrix` 不存在；放行后槽清空、矩阵 `data-layout-state=ready`、页签 `y` 位移 <1px。
2. `test_process_read_failure_reports_in_place` —— 两个真实读取各返回 503：槽内 `.notice[role=alert]` + `重试读取` 可见；无 `role=status`、无「暂无」；页签 `y` 位移 <1px；工具条仍在。
3. `test_mechanical_tools_appear_before_the_month_read` —— 挂起 `/api/m06/workbench/page`：工具条/月份/`表2 零租明细` 可见；槽 `reading` 恰好 1 个 `role=status`、0 个 `.notice`；**无**「请选择项目查看报表」「暂无已保存月份」；数据区 1 个占位；放行后槽进入 `ready`/`empty`、占位消失，出现真实汇总区或真实的「请选择项目」状态；工具条 `y` 位移 <1px。
4. `test_mechanical_read_failure_reports_in_place` —— 月度读取 503：槽内 `.notice[role=alert]` + `重试读取`；无 `role=status`；数据区仍保占位；无「请选择项目查看报表」；工具条与 `核对工作台` 按钮仍在。

这些用例故意不取 `disposable` 夹具（不写业务数据），只需 `server, browser_page`（第 1 例另需 `api, projects` 以选定真实项目）。

### 4.3 本会话无法执行、必须由主控在原登记环境跑

- 上述 4 个 Playwright 用例：`python -c "import playwright"` → `ModuleNotFoundError: No module named 'playwright'`（当前 python 未装 playwright，且启停预览服务超出本票权限）。
- 任何 GUI/浏览器实看、真实副本矩阵与汇总/明细的加载 + 编辑保存全过程（票验收第 4 条）。按约定统一由主控构建真实副本后执行，本会话不 `vite build`。
- 机械 i8 抓取**未执行**（票验收第 3 条明确要求不随 UI 验证执行）。

## 五、共享机制的最小建议（不由本票改）

1. **恒高状态槽 CSS 目前两页各写一份**（`.process-read-status` / `.mechanical-read-status`，规则体几乎相同），加上 `flow.css` 的 `.debt-overviews-status` 已是第三份。建议主控在 `read-region.tsx` 旁提供共用类（例如 `.read-status-lane` + `.read-status-lane > .notice`）并把三页改为复用；本票刻意没有动共享文件，也没有把页面专用类名塞进 `read-region`。
2. **`readPhase` 对「尚未选定范围」没有第七态**。过程页需要 `settled && Boolean(warehouse)` 这种页面级判断才能避免「还没选项目就说没有数据」。若后续票也有同类需求，可考虑在 `readRegion` 侧提供一个「enabled/ready 之前为 idle」的显式选项，而不是每页自己拼条件。
3. **`ReadFailure` 只接一个 `read`**。机械页槽内要同时表达两个查询的失败，只能并排渲染两个 `ReadFailure`；若主控希望槽内始终只占一行（目前两个同时失败会叠成两行、被 `overflow:hidden` 裁掉第二个），需要一个把多条失败合并成一行的组件或 `retained` 之外的 `merge` 约定。

## 六、未验项与限制

- 第 4.2 节 4 个用例**未运行**；因此「工具区在读取期间可操作」「失败不推移」「不冒充空态」目前只有源码控制流依据 + 单元层依据，没有本会话的浏览器实测。
- 真实副本上的矩阵、公司汇总、零租/包月明细的**加载全过程**与**编辑保存读回**（列宽保持、下一格输入不被覆盖、不主动滚动）未在真实副本上复核；这些路径的代码未被本票改写，但票验收第 4 条要求的代表场景仍需主控执行。
- 机械槽内两个 `ReadFailure` 同时出现时的单行约束（第 5 节第 3 条）未在任何真实故障组合下实看。
- 未做全站回归、窗口矩阵、真实 i8 抓取、部署或提交。
- `tsc` 最终整体退出码 0（并行会话的 `notices.tsx` 已收敛）；中途一次为 1 且错误全在 `notices.tsx`，与本票无关。

## 七、稳定源码窗口

- 基点 `9efebc87`；本票工作树内仅上述 4 个源文件 + 1 个新增测试 + 本证据文件改动。`git diff --stat -- apps/frontend/src/{process.tsx,process.css,mechanical.tsx,mechanical.css}` = `4 files changed, 37 insertions(+), 8 deletions(-)`；`git status --porcelain -- apps/frontend/tests/` = `?? apps/frontend/tests/test_process_mechanical_loading.py`（148 行）。
- 共享文件（`read-region.tsx`、`grid-presentation.tsx`、`page-surface.tsx`、`main.tsx`、`ui.css`、`style.css`、`package.json`）在 `9efebc87` 上未被本票触碰；主控串行整合时以该基点为参照。

## 八、第二轮窄集成修正（2026-11-04/05）

主控诊断复跑报出 `test_process_mechanical_loading.py::test_process_tools_appear_before_the_matrix_read` 的真实失败：选择项目使「增加历史月份」工具栏出现后，`.process-tabs` 的 `y` 由 209 变 211（2px）。这是**真实位移**，不是测试假设错误，故修产品、不放宽断言。

- 根因：`apps/frontend/src/ui.css:63` 的 28px 控件高度规则只覆盖各表格容器内的 `.ant-input/.ant-select`，`.process-filters`/`.process-history` 不在其列；原生 `input[type=month]` 于是落回 `apps/frontend/src/style.css` 的全局 `min-height:calc(32px*var(--fscale))`，加上自身 padding/边框后比同行 32px 按钮高约 2px，工具栏插入时把整行撑高、下面的 tabs 整体下移。
- 修法（`apps/frontend/src/process.css` 一处规则 + 三行注释）：`.process-history .ant-input` 由只控 `width` 改为再钉 `height/min-height: var(--control-h)`，与 `projects.css` 既有 `.filters .ant-input` 同款；不另加 `padding-block`，antd 的 Input 本身无固定高度，多写会与其运行时 padding 冲突。未给 `.process-filters` 固定高度（与真实内容高度冲突，试验后回退）。
- 测试侧未改：`test_process_mechanical_loading.py` 的 `abs(y差) < 1` 断言保持原样。

检查：`apps/frontend` 下 `node_modules/.bin/tsc --noEmit` = 0；`py_compile` = 0。未验：本轮**未在浏览器运行**该用例（本会话无 playwright），2px 是否归零须主控在登记真实副本复跑确认；机械费两例本轮未改动。
