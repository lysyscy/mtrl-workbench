# TAIL-465 过程资料布局与切换提速（离线批次）

Status: 离线批完成，等待主控串行整合与 preview 时段。写域仅 `apps/frontend/src/process.tsx`。
本票未做 DB/HTTP/浏览器/preview/build/backend_verify（469 独占）；只做 Node 纯计算与 typecheck。

## 固定条件（真实输入，哈希复核通过）

- 矩阵 `process-matrix-body.json` 487885B sha256 `b94c1baeca3f64773b698fd5e0b04058929348d3eb05a123850220ec36c25662`
- 机械屏幕 `process-screen-body.json` 93288B sha256 `76a95bd3034521e1875e26cc8a06e20962be56d6df87889386bf78b71cd8883f`
- 目录 `…/site-performance-first-wave-20261102/files/controller/`（探针每次运行先核 sha256，不符即 exit 2）
- 视图：16 仓 × raw/adjusted = 32 视图、8000 个金额格；默认仓 `S1新疆普康机电设备安装工程仓库` 14 行 × 16 列 = 224 个可编辑格，默认 tab = `useState(1)` → adjusted。
- 字号/视口/缓存：离线段不产生浏览器字号与视口，未用自动等待冒充交互指标；字号 1.12、1920×1080 只出现在待执行的 preview 脚本参数里。
- 源码基线 HEAD `3c5712ed`；改前 `process.tsx` sha256 `8d6043bd…d221b`（216 行），改后 `c5c15fa3…2ff97`（219 行）。

## 热点排序（先量后改，含反证）

1. **确认热点：measurement signature 整 row 序列化。** `process.tsx:195` 原式
   `JSON.stringify([row, pinned?'':messages.get(keyOf(...))??''])` 把整行 16 个金额 + ym + materialEditable
   每行每列重复序列化（17 列 × 每行 → 每格一次）。
   实测（300 次中位）：整行 0.7456ms / 候选表达式 0.1239ms（**6.0×**，观测字节 73264→4671）；
   同文件内等价复刻 0.644→0.0423ms（15.2×）。经 `new Function` 包装，取值偏保守。
2. **确认连带：每格一个 DOM 测量单元。** render 列无法走 canvas 快路径（`grid-layout.ts:169-172` 要求 `!job.column.render`），
   所以 16 个金额列全部进 128 格一批的测量 DOM，每批 2 次 `flushSync` + 1 次 `loadElementFonts` + 1 批 `getBoundingClientRect`。
   `plan.md` 的 `measured=256` 与 16 列 × 16 行（14 行 + 2 固定行）预测**完全吻合**，说明该标记即本路径。
3. **反证（不算热点，不该改）**：`cellClass` 每格 `matrix.raw.some()` 扫描 0.066ms（预计算 0.0124ms，绝对差 <0.06ms）；
   `errors` JSON 往返 0.0003ms；`displayRows` 排序 0.0032ms；每击键 drafts 浅拷贝 0.0004ms；14 行规模下都无净收益。
4. **未定性（需 preview，不在本批改）**：224 个受控 antd `Input`（每格 `useState(focused)`）的 React 协调与绘制。
   离线能覆盖的纯 JS 部分只有 0.268ms/击键（见下），剩余必须在真实浏览器测。

## 改动（唯一写域，measurement-only）

```diff
-import type { Confirmation, Difference, ProcessRow } from './process-api';
+import type { Confirmation, Difference, ProcessData, ProcessRow } from './process-api';
-        <MatrixGrid matrix={matrix} rows={displayRows} kind={kind} warehouse={warehouse} scale={scale}/>
+        <MatrixGrid … sources={query.data?.sources[warehouse]}/>
-function MatrixGrid({matrix,rows,kind,warehouse,scale}:{…}){
+function MatrixGrid({matrix,rows,kind,warehouse,scale,sources}:{…;sources:ProcessData['sources'][string]|undefined}){
     const messages=new Map<string,string>(JSON.parse(errors));
-    return {signature:(row,column,pinned)=>JSON.stringify([row,pinned?'':messages.get(keyOf(warehouse,row.ym,column))??''])};
-  },[errors,warehouse]);
+    return {signature:(row,column,pinned)=>pinned?JSON.stringify([row,'']):JSON.stringify([row[column]??null,row.materialEditable??null,messages.get(keyOf(warehouse,row.ym,column))??'',sources?.[row.ym]?.[column]?.mode==='detail'?'detail':''])};
+  },[errors,warehouse,sources]);
```

`signature` 只被 `grid-layout.ts:154` 的 `cellKey` 使用（测量批缓存键），不进单元格渲染、不进业务数据、不进导出。
候选键恰好覆盖该格的测量渲染实际读的东西：本列金额、可编辑与否（决定渲染 Input 还是纯文本）、`明细确认` 标记、本格错误文案、列 id/列宽/字重（原键已有）。
固定行（合计/总求和）仍用整行键，`colSpan` 与 `process-segment-total` 布局键不变。

## 独立业务等值（不是自证）

- **保真性**：直接抽取发布源码里的 signature 表达式（探针从 `process.tsx` 读取该行，`new Function` 注入，非复刻），
  对 16 仓 × raw/adjusted 8000 格重新计算两套键，逐组比对"该格真实测量渲染指纹"：
  `shippedGroupsMergingDifferentRenders = 0`，`previousGroupsMergingDifferentRenders = 0`
  → **候选键不会把两个渲染可能不同的格并成一个键**（候选更粗的地方只在"金额文本相同且同为输入/纯文本、同为有/无明细标记"的格之间）。
- 金额语义未变：不使用 `money()/cents()` 结果做键，键里放的是原始字符串（比显示文本更细，只会更少合并、不会更多）。
- 错误路径未变：错误文案来自同一 `messages`（`keyOf` 同源），错误格仍单独成键，`role=alert` 的 `.process-cell-error` 仍在行内被 `grid-layout.ts:94` 采到。
- 合并/虚拟行/固定合计：`totals` 分支保持整行键；`rowMinimum=56*scale`、`domLayout="normal"`、`suppressColumnVirtualisation` 均未动。
- 未验：真实浏览器里首次显示/切项目/输入保存的等值（本批无 preview 时段），脚本已备。

## 量化（release 表达式，同一固定输入）

| 指标 | 改前 | 改后 | 比值 |
|---|---|---|---|
| 32 视图测量格数（DOM 单元） | 8000 | 4559 | 1.755× |
| 128 格测量批次数 / 字体 await 次数 | 74 | 52 | 1.423× |
| signature 采集 CPU（S1 adjusted，14×16） | 0.7456ms | 0.1239ms | 6.0× |
| 观测键字节 | 73264 | 4671 | 15.7× |
| 默认视图 S1 adjusted 键数 | 256 | 162 | 1.58× |
| 默认视图批次数 | 2 | 2 | 1.0（真实：该仓无减少） |

逐仓样例（格数 → 键数，批次数）：S1新疆普康 adjusted 256→162（2→2）；焦作百利 raw/adjusted 352→82（**3→1**）；
未建仓-2 336→94（3→1）；沭阳热电厂 288→94；内蒙古三峡储能 464→260；兰考金不换 64→64、广东茂名 48→48（**无去重，也无回退**）。

每击键纯 JS（224 格全量重算 + context 值）：0.268ms 中位（p90 0.65ms，1.2µs/格）；
`keyOf` 0.0865ms、显示管线 0.1901ms、drafts 浅拷贝 0.0004ms。**这 0.268ms 不是 INP**，不含 antd/React 提交与绘制。

## 实际命令与退出码

- `corepack pnpm typecheck`（apps/frontend）→ **EXIT=0**（`tsc --noEmit`，无输出）
- 探针（均经 `python tools/artifact_lifecycle.py lease --group site-performance-tail465-20261103 --owner dsh-tail465 --reason "本票固定输入与候选对照" --kind evidence -- node <abs>`）：
  probe1/2/3/4/5/6 → 全部 **EXIT=0**，JSON 回执落证据目录。
- 预览脚本仅**语法编译**核过：`backend/.venv/Scripts/python.exe -B -X utf8 -c "compile(...)"` → **EXIT=0**；未运行。

## 证据与产物（组 `site-performance-tail465-20261103` / owner `dsh-tail465`）

`C:\Users\Administrator\AppData\Local\AgentArtifacts\projects\mtrl-workbench\groups\site-performance-tail465-20261103\files\`
- `tail465-probe.mjs` / `-result.json`（分阶段 CPU、键数、载荷）
- `tail465-probe2.mjs` / `-result.json`（逐列去重、批拆分、风险扫描）
- `tail465-probe3.mjs` / `-result.json`（跨 32 视图保真验证）
- `tail465-probe4.mjs` / `-result.json`（批次数与字体等待折算）
- `tail465-probe5.mjs` / `-result.json`（**直接抽取发布源码表达式**复核，本报告主证据）
- `tail465-probe6.mjs` / `-result.json`（每击键离线可测部分）
- `tail465-preview-ab.py`（未执行，下一时段用）

## 未验 / 失败 / 后续

- 未验：真实浏览器首次显示、切项目、输入保存的 ready_ms / 长任务 / 事件时长；DOM 测量与 antd 协调的真实占比。
- 未验：现有 red 用例与本次改动无关（未跑 `test:unit`，本批不扩大检查面；改动不触及被测模块）。
- 失败：无。probe2 首版有语法错误已修（未计入交付证据的 v1 结果未覆写）。
- 下一步最小代表（需 preview 时段，一条命令）：
  `tools/artifact_lifecycle.py lease … -- backend/.venv/Scripts/python.exe -X utf8 <证据目录>/tail465-preview-ab.py --preview-run <run>/reports/real_owner.json --width 1920 --height 1080 --scale 1.12 --rounds 3`
  读 `summary.firstDisplayMedianMs / projectSwitchMedianMs / measuredCells / layoutTimingFirst`，与 baseline 构建（`git stash` 不可用 → 用对照构建目录）同条件比对。
- 需要共享机制改动时（`grid-layout.ts` 的 render 列快路径、签名默认值）只交具名 patch，本次未改任何共享文件。
- 资源去向：`apps/frontend/src/process.tsx` 已改并 typecheck 通过，未 commit；证据组 active，等主控判 close/hold。
