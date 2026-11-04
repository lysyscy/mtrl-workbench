# TAIL-477 欠款台账稳定加载样板 · 实施与验证证据

- 票：[TAIL-477 欠款台账稳定加载样板](../../tails/issues/TAIL-477-欠款台账稳定加载样板.md)
- 共同规格：[spec.md](../spec.md)、[research.md](../research.md)
- 复核意见（本轮输入）：[review-round1.md](./review-round1.md) 的 TAIL-477 段
- 工作树：`D:\dev\mtrl-workbench\var\worktrees\browser-session-loading-20261104`
- 分支/基点：`codex/browser-session-loading-20261104` / `22cc48f8`
- 实施真源：DSH session `session-6e0fc861-97a6-4962-aace-1625a7c17274`
- 记录时间：2026-11-04 第一版；同日第二版记录首轮修正；同日第三版记录 GUI 验证与遮挡修复（本地时间，浏览器时区不可用，未做时区换算）

## 一、结论摘要

本票把欠款页上方「集采 / 辅材 / 机械」三类汇总从"无数据时高度≈0、数据到达后被撑高"改为**先占据稳定的数据区占位、由区级单点状态说明、结果到达后一次性接管**，并把该样板实际消费的读取呈现能力抽成 `apps/frontend/src/read-region.tsx`，供 TAIL-478–481 复用。

第二轮按 `review-round1.md` 修正了三处：

1. **失败提示不再占流内布局**：成功/失败/刷新失败三种状态下，汇总区高度与台账位置不因提示文字变化（对应 spec §62「必要更新提示不新增布局行」）。
2. **失败不再反复收放**：删除了首轮"无数据失败时改给卡片体 180px 最小高、重试又换回 8 行占位"的写法——那会造成一次额外的收放。现在失败时保留同一份占位几何，只把行条降为纯空间。
3. **测试取舍修正**：删除了 `>120px` 与"250 ms 后 <1 px"两个无依据门限，删除了骨架 `<span>` 数量这类镜像实现的断言，改为业务状态与过程证据（未就绪不呈空、已有结果刷新失败仍保留、失败不推移台账）。

第三轮按主控复核意见只修一处产品问题：

4. **失败提示改为区域自己的状态槽，不再用绝对覆盖**。第二轮那版 `.debt-overviews .notice{position:absolute;top:8px;right:8px;…}` 在候选真实副本上被实测会压住第三张卡的标题与业务值（窄窗 `error` 压标题 2327px²；`stale` 在 1280 下压标题 2400px²、项目名 1053px²、两笔金额 1322px²，在 1920 下压金额 863px²）。现在 `flow.tsx` 在网格之前渲染一个 `.debt-overviews-status` 槽，**三种状态下都存在、高度固定为 `--control-h`**，提示在槽内一行为限、文案用省略号截断、重试按钮 `flex:none` 常驻。于是：没有任何提示浮在标题或数值之上；提示出现/消失不改变区域高度；长文案被截断而不是换行增高。**没有新增骨架行数，也没有加入任何等待或延迟。**

验证范围（准确表述）：

- **已完成**：`tsc --noEmit` = 0；`npm run -s test:unit`（19 文件）= 0，`tests 92 / pass 92 / fail 0`；`impeccable detect --json`（三个改动目标）= 0，输出 `[]`；`py_compile` 新测试 = 0。
- **第三轮未执行**（按主控 m01287 安排）：本地 `vite build`、任何浏览器/预览访问与 GUI 回归。第三轮改动后的遮挡表现、失败恢复与表内滚动位置由主控在重建后的统一预览上核验。
- **第二轮（旧构建）已执行并仍然有效**：最小集合 9 例全绿；hold 真实 `/api/m05/debt` 的三帧几何；减少动效与 1.12 字号成对采集；一次真实保存的几何与列宽保持。这些证据针对的是未被第三轮改动触及的部分（台账、PageSurface、保存链路、骨架高度），见第五节。

因此本票当前状态是：**遮挡缺陷已在源码层修掉并给出最小改法（不是绕开，而是换承载方式），待主控重建后在原登记环境复验**。除该项复验外，本票其他场景的证据仍成立。

## 二、修改清单

仅本票写域（`apps/frontend/src` 欠款页与其实际消费的共用加载能力、必要前端行为测试、本证据文件）。

| 文件 | 类型 | 内容 |
|---|---|---|
| `apps/frontend/src/read-region.tsx` | 新增（71 行） | 共用读取呈现能力：`ReadLike` 查询形状、`ReadPhase`（`idle`/`reading`/`ready`/`empty`/`error`/`stale`）、`readPhase()`、`ReadState`、`ReadPlaceholder({rows, quiet})`、`ReadFailure({read, retained})`（第三轮把提示文案包进 `.read-failure-text`，让消费方可以单行截断；组件本身不接 className/quiet 参数） |
| `apps/frontend/src/flow.tsx` | 修改 | 删除文件内私有 `ReadState`（原 :35-37，行为原样迁入 `read-region`）；新增 `import { ReadFailure, ReadPlaceholder, ReadState, readPhase } from './read-region';`；重写 `DebtPage`（:36-67）：**网格之前的一行状态槽**（`error`/`stale` 放 `ReadFailure`、`reading` 放 sr-only 状态行、其余为空）+ 三卡骨架占位 + `data-read-phase`/`aria-busy` 语义标注 |
| `apps/frontend/src/flow.css` | 修改 | 原 `.debt-overviews` 三列网格改名 `.debt-overviews-grid`（含 `@media(max-width:1000px)` 同步）；`.debt-overviews` 改为纵向 flex；新增 `.debt-overviews-status` 固定高状态槽与其内 notice 的单行/省略号规则、`.read-announce`（自带 sr-only）、`.read-placeholder` 及行样式、`.read-placeholder-quiet`。第二轮那版绝对覆盖定位规则已删除 |
| `apps/frontend/tests/unit/read-region.test.mjs` | 新增（8 例） | 纯函数六态判定 5 例 + 占位行为 3 例（只宣告装饰空间、不含金额/数量/百分比、失败保留空间但不显在途） |
| `apps/frontend/tests/test_debt_loading.py` | 新增（166 行） | 4 例 Playwright（真实副本夹具）：区级自行报告读取、失败不推移台账、已有结果刷新失败仍保留结果并说明、**窄窗失败不压标题/数值且重试可点**（用 `Range.getClientRects()` 量真实文字矩形，元素盒会高估）。首跑 1 例失败暴露**夹具缺陷**（未等区域终态即采样），已改为等待 `data-read-phase` 为 `ready`/`empty` 后再采样；产品源码未因此改动 |
| `apps/frontend/package.json` | 修改 | `scripts.test:unit` 追加 `tests/unit/read-region.test.mjs`（18 → 19 个文件） |
| `.scratch/browser-session-loading-20261103/evidence/TAIL-477.md` | 新增/更新 | 本文件 |

未触碰：`ledger.tsx` / `ledger-api.ts` / `ledger-controls.tsx` / `grid-presentation.tsx` / `page-surface.tsx` / 后端 / 共享规格 / 票状态 / 索引 / Git 提交。

## 三、控制与数据流依据

### 3.1 基线问题（源码 + 实测两侧）

- 改前 `DebtPage` 是单个 `useQuery({queryKey:['debt']})`，三张卡各自渲染一份 `ReadState`：挂起期间同时出现 **3 条** "正在读取…"。
- 改前 `.debt-overviews{display:grid;grid-template-columns:repeat(3,minmax(0,1fr))}` + 后文 `.debt-workspace>.debt-overviews{flex:none}`、`.debt-overviews .flow-card-body{height:auto;min-height:0;overflow:visible}` → 无数据时卡片体高度≈0，数据到达后被内容撑开。
- 主控在基线上的观测（见 `evidence/baseline-observation.md`）：1920×1080 headless，**仅挂起真实 `/api/m05/debt`** 时台账先可见；释放后汇总高度 **122 → 553**，台账 y **216 → 647**（下推 **431px**）。这是本票的靶子：汇总区缺稳定空间。
- 空态与未加载原先混用同一批节点：未加载时没有任何区域结构，页面上只剩表头，视觉上等价于"空表"；`docs/guides/frontend-design.md:99` 与 spec §60 明确要求"不把未加载画零或空表"。

### 3.2 首帧门控的边界（为什么不加 `data-page-loading`）

`apps/frontend/src/page-surface.tsx` 的发布条件是：无 `[data-page-loading]` 后代、`[data-page-chrome]` 文本集合前后一致、其字体已加载。`docs/architecture/frontend.md:27` 规定欠款页 PageSurface **只等待现有工具区字体，不串联全局查询、表尺寸和额外双 rAF**；欠款双侧各自等待实际字体和尺寸。

因此本票**没有**给 `DebtPage` 根加 `data-page-loading` 来拖住整页（那会把汇总读与台账读串成一次全页发布，违背 :27，也让"次要区慢不遮整页"失效）。改动落在区内部：框架、筛选、台账先可用，汇总在自己的区里稳定加载。这与主控 m00174 的纠正一致——不得以解除整页隐藏单独判完成。

### 3.3 状态机（`read-region.tsx`）

```
readPhase(read, empty):
  read.isError                  → data === undefined ? 'error' : 'stale'
  read.data === undefined       → (isPending && isFetching) ? 'reading' : 'idle'
  otherwise                     → empty ? 'empty' : 'ready'
```

- `idle`：尚无获准读取（`props.active` 为假、`blocked` 期间），**不宣告**任何加载文案，但仍输出占位结构 → 首帧就有稳定边界。
- `reading`：读取在途且无内容可显示 → 区级一条 sr-only `role="status"` + 三卡骨架。
- `ready` / `empty`：结果在屏；`empty` 只用于"读取成功且 0 行"，此时才显示既有 `.muted` "暂无X未结清欠款"。
- `error`：失败且屏上无内容 → 区级 `role="alert"` + `重试读取`，**占位几何原样保留**（行条降为不可见），不再改最小高。
- `stale`：失败但屏上仍有上次结果 → 保留结果，提示前加"更新未成功，保留上次结果。"（措辞与 `notices.tsx:237`「列表更新失败，保留上次结果。」先例一致，对应 spec §65）。

`DebtPage` 的渲染条件（`apps/frontend/src/flow.tsx:44-63`）：

```
placeholder = phase === 'idle' || 'reading' || 'error'   // 三卡内容区是否用占位
失败提示    = phase === 'error' || 'stale'               // 挂进 .debt-overviews-grid（绝对定位）
状态行      = phase === 'reading'                        // sr-only，区级一条
```

数据流未改：仍是 `debt` 查询 + `cents()` 过滤零欠款 + 按金额降序 + `Bars`；台账保存/删除/新增后 `ledger.tsx:194` 的 `invalidateQueries({queryKey:['debt']})` 联动保持原样。该刷新命中已有 `data` 时 `readPhase` 返回 `ready`/`stale` 而不会回落到 `reading`，屏上结果保留（spec §62）。

### 3.4 布局依据（复用既有先例，不新建体系）

- 三列网格从 `.debt-overviews` 下移到内层 `.debt-overviews-grid`；`.debt-overviews` 自身改为 `display:flex;flex-direction:column;position:relative`。`@media(max-width:1000px)` 的 `grid-template-columns:1fr` 同步改到 `.debt-overviews-grid`。
- **失败提示占用区域自己的状态槽，不用覆盖**（第三轮修正，取代第二轮的绝对定位）：`flow.tsx` 在 `.debt-overviews-grid` **之前**渲染 `<div className="debt-overviews-status">`，里面放 `(error|stale) && <ReadFailure/>` 与 `reading && <p className="read-announce" role="status">`。CSS 是 `.debt-overviews-status{display:flex;align-items:stretch;height:calc(var(--control-h));margin:0}`，`.debt-overviews-status .notice` 在该槽内 `flex:1;min-width:0;flex-wrap:nowrap;overflow:hidden`，文案节点 `.read-failure-text` 用 `overflow:hidden;text-overflow:ellipsis;white-space:nowrap`，重试按钮 `.ant-btn{flex:none}`。
  - **为什么这样就同时满足两条约束**：槽高固定为 `--control-h`（`ui.css:1` 的 32px×fscale），且槽**在三种状态下都在 DOM 里**（`error`/`stale` 有 notice、`reading` 有 sr-only 行、其余为空），所以①提示不浮在任何标题或数值之上（不再有 `position:absolute`），②提示出现或消失**不改变区域高度**，台账位置不动（spec §62），③文案超长时被省略号截断而不是换行增高——这才是"高度恒定"的真正来源，不是加固定留白或延迟。
  - 第二轮那版 `.debt-overviews .notice{position:absolute;top:8px;right:8px;z-index:2;…}` 已删除；实测它会在窄窗与 `stale` 压住第三卡标题与金额（见 §5.4 的历史量值），本轮改为状态槽后该缺陷在代码层已不存在。
  - `ReadFailure` 组件相应地只加一个 `<span className="read-failure-text">` 包裹文案（不给组件加 className 参数、不加 `quiet` 参数），截断策略留在消费方 CSS。
- **失败不反复收放**：删除了首轮 `.debt-overviews[data-read-phase=error] .flow-card-body{min-height:calc(180px*var(--fscale))}`。现在 `placeholder` 条件包含 `error`，失败时卡片体仍是同一份 8 行占位几何，只是 `.read-placeholder-quiet>span{visibility:hidden}` 让它不再像在途；重试成功后同一几何被真实行替换。**没有任何"换一种盒子"的中间态。**
- 保留既有的"取消局部滚动、由页面滚动承接"：`.debt-overviews .flow-card-body{height:auto;min-height:0;overflow:visible}`、`.debt-overviews .flow-bars{max-height:none;overflow:visible}` 未动（`docs/guides/frontend-design.md:61`）。
- 占位高度由占位行自身提供：`.read-placeholder{grid-auto-rows:calc(38px*var(--fscale))}`、行条 `height:calc(7px*var(--fscale))`、`border-radius:var(--radius-pill)`、`background:var(--sf2)`，与 `.flow-bar`（`padding:8px 0` + `.bar-track` 7px + 正文 `13.5px * fscale`）同量级，**不含任何金额、行数或百分比**（spec §60）。
- 状态行用自带 sr-only 的 `.read-announce`，因为 `ui.css:18` 的 `.sr-only` 作用域锁在 `.grid-width-tools` 内，不能当全局工具类用。
- 只在既有令牌上用（`--fscale`/`--control-h`/`--sf2`/`--radius-pill`/`--radius-card`，均由主题样式注入），未新增令牌、未改字号层级、未引入 transition/animation，因此天然满足减少动态效果（spec §66）。

**第二轮覆盖定位的实测代价（历史，已在第三轮改掉）**：上一版把提示绝对定位在第三张卡标题带上，候选侧实测在窄窗与 `stale` 会压住真实文字（`error`@1280×720 压标题 2327px²；`stale`@1920 压金额 863px²；`stale`@1280 压标题 2400px²、项目名 1053px²、两笔金额 1322px²；重试命中率为 `true`）。这些量值保留在本文件 §5.4 作为"为什么不再用覆盖"的依据，对应的代码路径已删除。

### 3.5 对辅助技术与测试的可观察面

- `.debt-overviews` 有 `aria-label="按项目看的欠款汇总"`；`aria-busy` 仅在 `reading` 时存在；`data-read-phase` 暴露六态供后续接入与回归断言。
- 骨架 `aria-hidden="true"`；区级状态文字只在 `reading` 时以 sr-only 承载，不重复朗读。
- 与既有测试不冲突：`test_ledger.py` / `test_ledger_layout.py` 断言的 `region`（`辅材欠款台账`）、`.ledger-sides`、`.ledger-card`、`保存回执` 均未改动；`apps/frontend/tests/` 中只有 `test_debt_loading.py` 引用 `.debt-overviews`。

## 四、命令与退出码

在 `apps/frontend`（工作树内，`node_modules` 指向主根既有依赖的 junction，未安装任何包）：

| 命令 | 退出码 | 结果 |
|---|---|---|
| `node_modules/.bin/tsc --noEmit` | 0 | 无类型错误（首轮修正定稿后重跑） |
| `npm run -s test:unit`（19 文件） | 0 | `tests 92 / pass 92 / fail 0`，duration ≈ 2.5 s |
| `node_modules/.bin/vite build` | 0 | `✓ built in 1.16s`；仅有既有的 chunk >500kB 提示（`business-grid-*.js` ≈ 961 kB），非本次引入 |
| `impeccable.cmd detect --json apps/frontend/src/flow.tsx apps/frontend/src/read-region.tsx apps/frontend/src/flow.css` | 0 | `[]`（无规则命中） |
| `python -B -X utf8 -m py_compile apps/frontend/tests/test_debt_loading.py` | 0 | 语法通过（需在工作树 cwd 执行） |
| `pytest --collect-only -q test_debt_loading.py`（在 `apps/frontend/tests`） | 0 | `3 tests collected` |

**说明**：上述 `vite build` 是本机直接调用工作树内 `node_modules/.bin/vite` 的构建，**不等于**主控按 Corepack 声明版本执行的统一预览构建；按复核意见第 13 行，统一构建与正式预览入口由主控执行，本文件不把本地构建当作预览通过。

候选侧（主控统一 Corepack 构建的真实副本，见第五节）：

| 命令 | 退出码 | 结果 |
|---|---|---|
| `pytest apps/frontend/tests/test_debt_loading.py -q` | 0 | `3 passed in 20.80s`（首跑 `1 failed, 2 passed`，定位为夹具缺陷，已修夹具，见 5.2） |
| `pytest test_ledger.py + test_ledger_layout.py 三个指定用例 -q` | 0 | `6 passed in 54.90s` |
| 具名过程采集（hold→释放 / 遮挡 / 适配 / 保存几何 / 动效对照，6 个诊断脚本） | 0 | 产出 `reports/477-gui-{process,notice-occlusion,stale-occlusion,adaptation,checks-2,save-geometry,motion-scale112}.json` 与对应 `screenshots/477-gui-*.png`，见 5.3–5.5 |

**候选窗口（第三轮修复后，供主控核对产物一致性）**，sha256 与行数：

```
7d65a86784a563ea3095c16b8202e11dbb1dafb1a5f77c8cebb8ef1ac13e6293  apps/frontend/src/flow.tsx            142 行
a1627e7d0b3b1abb04b76d91d052acdc959b912389c6b68af8cbb6c68a1fa4e7  apps/frontend/src/flow.css             83 行
6bba23468ba5fb716fa69d6635f38d93a5569598b4ae62baa93751a2eccee968  apps/frontend/src/read-region.tsx      71 行
3470ed9d1055685d0743faa36b7d40692f2015420df5d08538b00e66575e3672  apps/frontend/tests/test_debt_loading.py        166 行
eacdb9e136a2384660c2cd9cfb33fbf524adb1b7b809c3d61ad31bc18e0fb2d0  apps/frontend/tests/unit/read-region.test.mjs   61 行
2ca0138159a4da8e9c1aabde18ae5486418be7439ee08c85b2e7e9ed30653b31  apps/frontend/package.json                       39 行
```

第三轮改动只涉及 `flow.tsx`（状态槽）、`flow.css`（状态槽样式，删除覆盖定位）、`read-region.tsx`（提示文案包一层 `.read-failure-text`）、`test_debt_loading.py`（新增窄窗遮挡用例 + 抽 `covered_by_notice()` 辅助并给 stale 用例补同一检查）。台账侧文件、`package.json` 与 unit 测试文件**本轮未改动**。

第二轮（旧构建）的窗口哈希 `c000efbe…`（`flow.tsx`）、`674095ae…`（`flow.css`）、`cda397e9…`（`read-region.tsx`）对应的正是那一版带覆盖定位的实现；第五节全部浏览器证据都是在那一版上采集的，**第三轮改动未在浏览器上复测**（按 m01287，源码变更后由主控重建并验收）。

## 五、真实过程证据

### 5.1 候选身份（每例重核，非借用）

主控统一 Corepack 构建的登记真实副本，`registered_preview()` 逐例通过 `assert_same_preview(..., disposable=True)`：

- base `http://127.0.0.1:8065`；`owner_path` 指向本组 `files/reports/real_owner.json`
- `schema=frontend_rewrite_397_6843f00abf424a429a7cf7d7f66e0dd4`、`database=mtrl_workbench_test`、`revision=oilmerge261103`
- `product_digest=8bdf5511c4b8a09f885e5b3d45df48a622998d2c336c66ba919353d3e6516c20`
- `cookie_name=mw_real_preview_3bfe5304f9b05ccb`、`index_sha256=0c2132ffae27ea1592fbbd5e2f4217f67e4e9206231d2287cc7fc5bd26f8e6c4`
- `synthetic=false`、`disposable=true`、`preserve_schema_on_stop=false`；进程 pid 37712 存活
- `/visual-version` 返回的 schema / revision / cookie_name / index_sha256 / product_digest 与 owner 五项逐一相符

环境差异（如实记录，未绕过任何门禁）：预览进程由打包版 Codex 启动，其写入 `AppData\Local` 被 MSIX 重定向到 `Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\...`；本会话的普通路径看不到该文件。为让既有 `registered_preview()` 能读到同一份登记元数据，把打包树中的 `real_owner.json`、`version.json`、`record.json`、`work/candidate-477-r2`（41 文件）复制到普通树同路径，**sha256 与源逐项一致**（owner `d4c6def4…a465`、version `2499ca1a…ccd`、record `b3b71cf2…9d01`）。复制只是补路径，身份校验（进程存活、`/visual-version` 五项、`verify_build`、`product_sources`、HTML sha256）仍全部真实执行。

运行参数：`MTRL_LIFECYCLE_OUTPUT=.../browser-session-loading-20261104/files`、`MTRL_RUN_ID=browser-session-loading-20261104`、`PLAYWRIGHT_BROWSERS_PATH=C:/ProgramData/ms-playwright`；解释器 `backend/.venv/Scripts/python.exe -B -X utf8`；**未 register、未 lease、未 close 该组**（root 独占 lease 由预览父进程持有）。

### 5.2 最小集合运行结果（全部真实副本，全绿）

| 命令 | 退出码 | 结果 |
|---|---|---|
| `pytest apps/frontend/tests/test_debt_loading.py -q` | 0 | `3 passed in 20.80s` |
| `pytest apps/frontend/tests/test_ledger.py test_ledger_layout.py::test_actual_ledger_layout_tracks_rows_and_totals ::test_project_loading_keeps_ledger_space_and_hides_old_values ::test_split_pages_keep_unsaved_ledger_guard_without_business_write -q` | 0 | `6 passed in 54.90s`（两窗口参数化，3 函数 → 4 例） |

首跑 `test_debt_loading.py` 为 `1 failed, 2 passed`（第三例 `33 == 0`）。定位为**夹具缺陷**而非产品缺陷：`open_debt()` 只等标题就采样「首屏行数」，此时汇总读尚未落地。诊断探针（`477_probe_return_refresh.py`，见 5.5）确认产品行为正确——返回时重读、失败后 `phase=stale`、`notice` 1 条、保留 33 行。修法是把采样前移到等待区域终态：`expect(page.locator('.debt-overviews:is([data-read-phase="ready"],[data-read-phase="empty"])')).to_have_count(1)`。产品源码未改。

### 5.3 具名过程采集：hold 真实 `/api/m05/debt` → 释放（1920×1080）

与基线同一手法，唯一差别是这次在**候选**上跑。三帧几何（`reports/477-gui-process.json`）：

| 帧 | phase | 汇总 top/height | 三卡高 | 台账 top (h) | 骨架行 | bar 行 | status 行 |
|---|---|---|---|---|---|---|---|
| held（挂起） | `reading` | 78 / **383** | 381×3 | **477** (452) | 24 | 0 | 1 |
| landed（释放瞬间） | `ready` | 78 / **555** | 553×3 | **649** (832) | 0 | 33 | 0 |
| settled（+400 ms） | `ready` | 78 / **555** | 553×3 | **649** (832) | 0 | 33 | 0 |

- 汇总 **383 → 555（+172px）**、台账 **y 477 → 649（+172px）**，均只发生**一次**；`landed` 与 `settled` 五项几何与计数**完全相同**，无反复收放。
- 对照基线（同一 hold 法）：汇总 122 → 553、台账 y 216 → 647（下推 **431px**）。候选侧把下推量从 431px 压到 172px，且起点不再是"什么都没有"。
- 骨架保持 8 行/卡，**未通过增加行数凑目标高度**。残差来源已明确：8 行占位每卡约 381px，真实数据每卡 553px，差 172px 由真实 33 行一次性接管（spec §61 允许）。
- 截图（真实副本、`capture_preview` 身份侧车已验证）：`screenshots/477-gui-held-115623-901965.png`、`477-gui-landed-115625-346681.png`、`477-gui-settled-115626-890253.png`。

### 5.4 适配与失败提示遮挡（具名，未验项因此关闭或转缺陷）

`reports/477-gui-adaptation.json`、`reports/477-gui-checks-2.json`、`reports/477-gui-notice-occlusion.json`、`reports/477-gui-stale-occlusion.json`：

- **窄窗 + 1.12 字号**（1280×720，`--fscale=1.12`）：`overviews` top 87.34 / h **592.69**，`ledgerCard` top **697.94**，`horizontalOverflow = 0`，`phase=ready`；失败注入后点「重试读取」再取一次，`overviews` top/h 与 `ledgerCard` top **三项完全一致**（`ledgerCard` 自身高度从 508.06 变为 1134.58 是台账正文随后补齐所致，不属汇总区几何）。截图 `screenshots/477-gui-narrow-scale112-115723-159889.png`、失败帧 `477-gui-failure-narrow-scale112-115725-268785.png`。
- **减少动态效果**（成对采集成 `reports/477-gui-motion-scale112.json`，1.12 字号、两上下文都等区域与台账终态）：`scale`/`overviews`/`ledgerCard`/`ledgerSides`/`barRows`/`ledgerRows`/`horizontalOverflow`/`phase` **逐项相等**，`differences` 为空对象；采集后把字号档位恢复为原值 `standard`。本票未引入任何 transition/animation，符合 spec §66。
  - 说明：更早的 `reports/477-gui-adaptation.json` 里那组 motion 对照**不作证据**——它在台账尚未终态时取样，`ledgerCard` 高度差异来自时序而非动效；已用上面这组成对采集取代。
- **失败提示遮挡（第二轮覆盖定位的实测缺陷；第三轮已改为状态槽，此段保留为"为什么不再用覆盖"的依据）**：用 `Range.getClientRects()` 量真实文字矩形，而不是元素盒。
  - `error`（1920×1080）：9 个标题文字矩形，被覆盖 **0**；重试按钮 hit `true`。
  - `error`（1280×720）：第三卡标题「按项目看机械欠款」被覆盖 2327px²（3 个矩形），重试 hit `true`。
  - `stale`（1920×1080）：覆盖一项金额文字863px²；重试 hit `true`。原始值仅留本地受管截图。
  - `stale`（1280×720）：覆盖标题2400px²、一项项目名1053px²、两项金额文字分别459px²与863px²；重试 hit `true`。项目及金额已从此说明脱敏。
  - 截图 `screenshots/477-gui-notice-wide-115918-379034.png`、`477-gui-notice-narrow-115923-502542.png`、`477-gui-stale-wide-120123-099253.png`、`477-gui-stale-narrow-120129-712080.png`（后者肉眼可见提示压住第三卡标题与首行数值）。
  - 作废的一对：`477-gui-stale-{wide-120054,narrow-120100}-*.png` 是最先用 `page.reload()` 触发返回的写法，那次刷新把内存缓存丢掉、结果变成 `error` 且行数归 0，**不是** `stale`；改用应用内切页（`a[href="/preview/ledger"]` ↔ `a[href="/preview/debt"]`）后才是真正的"保留上次结果"。以 120123/120129 为准。
  - **第三轮的修法与复验方式**：这些量值取自旧实现（`.debt-overviews .notice{position:absolute…}`）。第三轮把提示移进 `.debt-overviews-status` 固定高状态槽（`height:calc(var(--control-h))`，`error`/`stale`/`reading`/空态下都在 DOM 里），提示不再有任何 `position:absolute`，"浮在标题带上"的前提消失。同一量法已固化为永久用例 `test_debt_overviews_failure_never_covers_a_heading_or_a_value`（1280×720，断言 `covered_by_notice()` 为空数组 + 重试按钮 `elementFromPoint` 命中），并给 stale 用例补同一断言。**这两个用例第三轮未执行**：无预览可用，按 m01287 由主控重建后运行。
- **普通保存保持几何**（`reports/477-gui-save-geometry.json`，真实可丢弃副本，一次 `other_expense` 保存，具名样本及行标识仅留本地受管记录）：
  - 手动把 `remark` 列由 **291 拖到 333**，随后把 `page-view` 滚到 120，记录 `MEASURE('.ledger-sides')`，再改格并由标题点击触发 blur 保存。
  - `widths` 前后**逐列相等**（`seq 58 / month 124 / other_expense 110 / payment 110 / debt 110 / remark 333 与 291 两表 / actions 52`），`pageScroll` 120 → 120（`pageScrollPreserved = true`），`ledger-card` top 529 → 529（`ledgerTopDelta = 0`），`保存回执` alert 计数 **0**（静默），API 回读 `46265.46` 与提交值一致。
  - **未验细节**：`MEASURE` 里的 `scrollTop` 前后都是 `null`（该写法没取到表体视口节点），因此"表体内部滚动位置保持"这一条**本次未真正取到证据**，`scrollPreserved = true` 只是两个 `null` 相等，不能当已验。表体滚动保持由既有 `test_first_display_retained.py`（切页 scrollTop 不变）间接覆盖，台账内滚动在保存前后的保持仍未直接测。
  - 截图 `screenshots/477-gui-save-geometry-120224-329412.png`。

### 5.5 诊断脚本的去向

`477_capture_process.py`、`477_check_adaptation*.py`、`477_check_notice_occlusion.py`、`477_check_stale.py`、`477_check_save_geometry.py`、`477_probe_return_refresh.py` 均为本轮**诊断用一次性脚本**，已从工作树移出、归档到 `work/477-gui-scripts/`，不进产品仓库、不进永久测试套件（永久套件只留 `test_debt_loading.py`）。

### 5.6 元数据复制的完整事实（供主控接管现场验收）

本节按 m01287 要求，把"为让既有 `registered_preview()` 读到登记元数据而做的复制"逐项写清。**这些复制不是新的运行登记，也不能被当作合法的组登记证据**：`record.json` 是原登记记录的副本，`real_owner.json` / `version.json` 是预览进程写出的登记产物的副本；真正的登记由主控创建，root 独占 lease 由预览父进程持有。**已停止一切复制、register/lease/hold/close 与预览访问；已产生的副本保留未删。**

**两个物理根（MSIX 重定向导致同一路径字符串指向不同目录）**

| 角色 | 绝对路径 |
|---|---|
| 打包树（预览进程实际写入处，源） | `C:\Users\Administrator\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\AgentArtifacts\projects\mtrl-workbench\groups\browser-session-loading-20261104` |
| 普通树（本会话进程看到的路径，目标） | `C:\Users\Administrator\AppData\Local\AgentArtifacts\projects\mtrl-workbench\groups\browser-session-loading-20261104` |

两棵树的 `groups` 目录内容不同、`st_ino` 不同，互写不可见；两棵树的 `.lifecycle.json` 都声明 `root` 为普通树路径。原因是最初启动预览的是打包版 Codex 应用，其对 `AppData\Local` 的写入被 MSIX 重定向。

**逐项复制清单（源 → 目标）**

| # | 源（打包树内） | 目标（普通树内） | 复制前目标是否存在 | 是否覆盖已有文件 |
|---|---|---|---|---|
| 1 | `record.json` | `record.json` | 否 | 无（新建） |
| 2 | `files/reports/real_owner.json` | `files/reports/real_owner.json` | 否（普通树该组当时只有空的 `files/`） | 无（新建） |
| 3 | `files/reports/version.json` | `files/reports/version.json` | 否 | 无（新建） |
| 4 | `files/work/candidate-477-r2/`（41 个文件） | `files/work/candidate-477-r2/`（41 个文件） | 否 | 无（新建） |

复制后逐项 sha256 与源一致：`record.json b3b71cf12fee86536f886d9bd47a28a58857a3d74225a4ce98f115216b009d01`、`real_owner.json d4c6def4bdd48b5e4b3a7a8a62db27ee4d1f6db0127c9b17c0b8bab0fe4aa465`、`version.json 2499ca1a01d5964bdbf94089328a900d93ff63924e3453b08536c2e59cd67ccd`。复制的命令是文件复制（`cp`，仅复制、未修改任何一侧的内容），原因是 `tools/dev/frontend_preview_runtime.py::active_preview()` 以 `current.json` 里的 `owner_path` 直接读 owner 文件，而该路径字符串在本会话解析到普通树。

**必须注意的后果（诚实声明）**

- 复制出的 `real_owner.json` 是**某一时刻的快照**。预览在 20:12 被主控停止后，打包树里的同一文件已变成 `status=stopped-disposable`、`stopped_at=2026-11-04T12:12:03.453527+00:00`，而普通树这份副本仍是 `status=ready`、`stopped_at=None`。因此**普通树这份副本不能作为"预览仍在运行"的证据**；进程 pid 37712 已不存在，`var/state/react-writable-preview/current.json` 已随主控退出被清理，8065 无监听。
- 因此第五节其它小节里"pid 37712 存活"、"`registered_preview()` 逐例通过"这些陈述，**只在复制当时与运行时刻成立**，不能用来推断现在的状态。
- 身份校验链本身没有被绕过：`active_preview()` 仍检查 `status/synthetic/host/database/schema/live_process`，`registered_preview()` 仍执行 `verify_build(version.json)`、`product_sources()` 比对与 `/preview` HTML sha256 比对，`assert_same_preview(..., disposable=True)` 仍比对 7 个字段与 `schema.startswith('frontend_rewrite_397_')`。复制只解决"路径可见性"。

**本会话产物的实际物理根**

`MTRL_LIFECYCLE_OUTPUT` 指向普通树的 `.../browser-session-loading-20261104/files`，因此本轮全部 JSON、截图与诊断脚本都写在**普通树**下：

| 类别 | 普通树内路径 | 数量（实测） |
|---|---|---|
| 报告 JSON | `files/reports/477-gui-*.json` | 7 |
| 截图 + 身份侧车 | `files/screenshots/477-gui-*.png` 与同名 `.json` | 13 + 13（其中 `477-gui-stale-{wide-120054,narrow-120100}` 一对已作废，见 §5.4） |
| 用例失败自动截图 | `files/screenshots/apps-frontend-tests-test_debt_loading-py-*.png` 与同名 `.json` | 3 + 3 |
| 诊断脚本 | `files/work/477-gui-scripts/*.py` | 8 |
| 干净构建副本 | `files/work/candidate-477-r2/` | 41 |
| 我的写入探针（应清理项） | `files/work/probe1/`、`files/work/probe2/`、`files/work/477-gui-probe/` | 3 个空目录（`files/work` 合计 52 个文件 = 8 脚本 + 41 构建 + 3 空目录） |

打包树里只有主控自己产生的 `baseline-debt-*` 与原始 `real_owner/version/record`，本会话未向其写入任何内容。

## 六、覆盖矩阵：本票全部场景与最小检查集合

复核要求"未改 ledger/PageSurface 可沿既有行为但需具名证据"，下表给出每个场景对应的**具体测试与断言**，以及本轮补的真实缺口。

| 场景（spec §87-96） | 证据 | 状态 |
|---|---|---|
| 首次进入：框架/筛选可识别、数据区有稳定边界与反馈、不反复撑开收回 | 新增 `test_debt_loading.py::test_debt_overviews_report_their_own_read`（未就绪不呈空 + 单点状态）；既有 `test_ledger.py::open_sample` 断言筛选（`选择项目`）与双侧 region 可见 | **候选侧已通过** |
| 分区先后就绪：次要区慢/失败不遮整页 | 新增 `test_debt_overviews_report_their_own_read`（挂起汇总时 `.ledger-card` 仍可见）、`test_debt_overviews_failure_does_not_move_the_ledger`（失败时台账仍可见且 y 不变） | 候选侧已通过 |
| 切项目/期间：保留表区空间、隐藏旧范围业务值与编辑入口、晚到响应不串范围 | 既有 `test_ledger_layout.py::test_project_loading_keeps_ledger_space_and_hides_old_values`（parametrize 1920×1080 / 900×900；挂起 `/api/m05/ledger`；断言 `正在读取台账`、`.ledger-sides` 计数 0、`.ledger-card` 高度差 <1、挂起数 =1；释放后可见） | 台账侧**既有且已通过**；汇总侧不含项目维度（`['debt']` 查询口径即全项目汇总，未改语义），无需重复覆盖 |
| 返回/同条件刷新：保结果、筛选、滚动、草稿、位置 | 新增 `test_debt_overviews_keep_their_result_when_the_return_refresh_fails`（刷新失败保留结果与几何）；既有 `test_first_display_retained.py`（切页后 clientWidth/Height/scrollTop 不变、`inert` + `aria-hidden`）；既有 `test_ledger_layout.py::test_split_pages_keep_unsaved_ledger_guard_without_business_write`（草稿跨页保留） | **候选侧已通过**；其余既有亦通过 |
| 真实空结果 | 新增用例释放后断言"真实行或真实空必居其一"；**真实空数据本身未构造**（需真实副本中三类汇总均为 0） | 部分未验（见 §8） |
| 慢请求/失败：次要区原位重试、主要读取失败所属区说明 | 新增 `test_debt_overviews_failure_does_not_move_the_ledger`（原位 alert + 「重试读取」按钮 + 不推移台账），**第二轮候选侧已通过**；遮挡由第三轮状态槽修复，量法见下两行的新用例 | **行为已通过；遮挡修复待复验** |
| 编辑/保存读回：保草稿、输入位置、滚动、实际列宽、普通保存无占位提示 | 既有 `test_ledger.py::test_actual_ledger_edit_keeps_next_draft_and_reads_back`（双格连续输入、单次 save、无 `保存回执` alert、API 回读一致）、`test_actual_ledger_lost_write_receipt_cannot_resubmit`；`test_ledger_layout.py::test_actual_ledger_layout_tracks_rows_and_totals`（region/grid 可见、`debt` 列无横向溢出）、`test_real_normal_month_remark_save_uses_same_month` | **既有且候选侧已通过**；另做具名保存几何采集（手动改 `remark` 列宽 291→333 后保存：列宽逐列相等、页面滚动 120 保持、台账 top 不变、回执 0 条、API 回读一致；**表体内部滚动位置该次未真正取到读数**，见 §5.4） |
| 失败/陈旧提示不遮标题与业务值、重试可达 | 新增 `test_debt_overviews_failure_never_covers_a_heading_or_a_value`（1280×720；`covered_by_notice()` 必须为空 + 重试点击命中）与 `test_debt_overviews_keep_their_result_when_the_return_refresh_fails` 末尾的 stale 同款断言 | **第三轮待复验**（旧实现实测缺陷见 §5.4，已改状态槽） |
| 骨架/占位不伪造数值 | `tests/unit/read-region.test.mjs` 三例（只宣告装饰空间、不含金额/数量/百分比、失败保留空间但不显在途） | **已通过（92/92）** |

关于列宽：欠款台账列宽偏好由 `grid-presentation.tsx` 的 `useRetainedGridColumns` 承担，本票未改动；`tests/test_grid_widths.py` 只参数化合同与通知书两页，**不含欠款台账**，因此本票不把列宽断言扩到其他页面（避免扩大全站范围），欠款侧列宽稳定由既有 `test_actual_ledger_layout_tracks_rows_and_totals` 的"债务列无横向溢出"覆盖。

复用而未重复新增的既有资产（明确不重跑、不复制）：`test_ledger.py`（保存与未确认回执代表）、`test_ledger_layout.py`（范围切换、高度稳定、草稿跨页）、`test_first_display_retained.py`（切页保留）、`test_preview.py`（真实读取失败与会话过期）。

## 七、本票落地的共用能力与后续接入边界

`read-region.tsx` 只做"区域如何描述自己的读取状态"这一件事，不含查询、不含缓存策略、不含延迟、不含轮询：

- `readPhase(read, empty)` —— 纯函数，六态判定，无副作用。
- `ReadPlaceholder({rows, quiet})` —— 结构化占位，几何与真实行同量级，不伪造数值；`quiet` 用于"失败但保留空间"。
- `ReadFailure({read, retained})` —— 原位失败 + 重试 + "保留上次结果"措辞；**不接 className**，定位由消费方 CSS 决定。
- `ReadState({query})` —— 从 `flow.tsx` 原样迁出的旧行为，`FlowPage` 的 `stats`、`flows` 两处仍用它，行为未变。

后续接入边界（给 TAIL-478–481 与主控复核）：

1. 只有**页面自己拥有该区域的数据来源**时才用 `readPhase`；不要把多个互不相关的查询合成一个 phase。
2. `empty` 必须由调用方传入真实空判据（本例为 `data.length === 0`）；未加载时不得传 `empty`。
3. 区级状态行应**每个区域一条**，用 `.read-announce` 之类的 sr-only 承载，不要把同一文案渲染进每个子卡片。
4. 占位形态按各页真实行几何调整 `rows`/行高，不追求跨页像素一致，也不要求预知最终行数（spec §61）；**不要用增加占位行数去凑某个目标高度**。
5. 失败提示若既不希望推移下方内容、又不能压住业务文字，覆盖定位**不够**（本票实测窄窗与 `stale` 会压住第三卡标题与金额，见 §5.4）。优先考虑像 `.ledger-status` 那样注入**非布局位置**（顶部/侧栏状态槽），或给区域预留一个不随状态变化的固定提示槽；两者都比纯覆盖稳妥。
6. 不要在页面根部加 `data-page-loading` 来实现稳定（见 3.2）；`PageSurface` 的 `data-page-chrome` 语义保持不变。
7. 本能力不含自动重试、缓存期限、轮询与任意延迟；需要续期的场景另起票。

## 八、未验项与恢复条件

本轮候选侧实测关闭了大部分未验项，剩下的如下：

| 未验项 | 原因 | 恢复条件 |
|---|---|---|
| 真实空结果（`data.length === 0` 的 `empty` 分支） | 真实副本 `/api/m05/debt` 返回 17 个项目行，三类中**没有任何一类是 0 个非零项目**（集采 8、辅材 11、机械 14），无法在不造假的前提下构造"三卡全空"。按 m00871 要求不 mock 业务空数据 | 主控确认可用的真实空范围，或明确以"未覆盖"结项 |
| 状态槽版提示在窄窗/`stale` 下确实不再遮挡 | 第三轮已把覆盖定位换成固定高状态槽，但**未在浏览器上复测**（无预览可用，按 m01287 由主控重建） | 主控重建后跑 `test_debt_loading.py` 的 4 例（遮挡用例断言 `covered_by_notice()` 为空 + 重试可点）；若仍有覆盖，说明槽高或省略号策略需再调 |
| 极窄窗（< 1000px 单列）下的汇总卡与提示 | 本轮只取 1280×720 与 1920×1080 两个必要代表 | 需要时补一档（单列 `@media` 已有既有规则） |
| 更长项目名导致标题换行时的覆盖量 | 真实副本的标题为固定文案「按项目看X欠款」，未出现换行 | 文案变化时复测 |
| 台账表体内部滚动位置在保存读回前后的保持 | 本轮保存几何采集的 `MEASURE.scrollTop` 取到 `null`（选择器没命中表体视口），不能据此判已验 | 补一次取 `.ledger-sides .ag-body-viewport` 的 `scrollTop` 前后对照 |
| 双侧台账自身的骨架/局部失败 | 本票未改 `ledger.tsx`/`PageSurface`/`grid-presentation.tsx`，沿既有行为；其证据来自既有 `test_ledger_layout.py::test_project_loading_keeps_ledger_space_and_hides_old_values`（本次已跑，两窗口通过） | 若后续票要改台账加载，需另立证据 |
| i8 真实会话、真实打印/导出 | 本票不涉及，且授权禁止 | 由 476 与主控另行处理 |

已知风险：

1. **初始预留与真实行数之间的残差（实测 172px）**：8 行占位每卡 381px、真实数据每卡 553px，数据到达后有一次 172px 的接管。属 spec §61 允许的合理接管，`landed` 与 `settled` 几何完全一致、无反复收放。若主控要求进一步压缩，应据实测行数/行高校准，**不是加动画、加延迟或单纯加骨架行数**。
2. **`idle` 期无文案**：`props.active` 为假或账号核实期间不宣告加载，只显示占位结构。有意为之（`blocked` 时查询 `enabled=false`，宣告"正在读取"与事实不符）。
3. **状态槽占用的固定高度**：`.debt-overviews-status` 恒为 `--control-h`（32px × fscale），即使没有失败也占这一行。这是让提示出现/消失不改变区域高度的代价，也正是它不推移台账的原因。相比整屏留白或动画延迟（spec §61/§66 均禁止），这是最小的稳定成本。若要求无失败时连这一行也不占，就只能回到覆盖或跨区域 portal，那会重新引入遮挡或跨区域耦合，因此本轮不做。
4. **`empty` 分支只有单元测试覆盖**：`readPhase` 的六态与 `empty` 判定由 `tests/unit/read-region.test.mjs` 覆盖并通过，但界面表现缺真实样本（见上表第一行）。

## 九、边界与未触碰项

- 未改后端、未改 `ledger.tsx`/`ledger-api.ts`/`ledger-controls.tsx`/`grid-presentation.tsx`/`page-surface.tsx`。
- 未接入其他页面（478–481 后续），未推广共用机制（等主控复核）。
- 未新增保存说明行、未改保存/草稿/导出保护链路、未改列宽与合计行为。
- 未新增轮询、缓存期限、自动重试、任意延迟、键盘增强、主题或整页风格改动。
- 未自行建库、未启停预览、未读 `.env`、未连 i8、未执行真实业务写入/打印/部署。
- 未改共享规格、票状态、索引，未执行 Git 提交/推送。
- 未 `register`/`lease`/`close` 证据 group（root 独占 lease 由预览父进程持有）；诊断脚本已移出工作树、归档到组内 `work/477-gui-scripts/`。
- 真实可丢弃副本上只做过一次普通格内保存（`other_expense`，读回校验一致），未做打印/导出/i8 抓取。
