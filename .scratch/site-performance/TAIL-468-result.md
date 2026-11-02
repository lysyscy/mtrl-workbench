# TAIL-468 集采搜索与勾选提速（离线候选，未做浏览器/预览验证）

日期 2026-11-03 · 分支 codex/site-performance-20261102 · 基点 3c5712ed（未提交）· 执行 DSH 单票
交付范围：`apps/frontend/src/contracts.tsx` 单文件补丁（+28/−9），未改 package.json、原票、plan、status、高水位。

## 1. 真实输入与固定条件

| 项 | 值 |
|---|---|
| 输入 | `contracts-body.json`（真实 `/api/m11/list` 响应体）139089 B |
| SHA256 | `7c3acd2982d239e1938c37bb778cc10f26cc8e72f6786f7e70a150d2602a4659`（实测一致） |
| 行/列 | 266 行；21 列（7 个金额列，240 个 `trade_contract_amt` 为 null，其余金额列 0 个 null） |
| 默认视图 | `filters.tag='纳入台账'` → shown 259 行；合计 contract_amt `90350572.50` |
| 视口/字体/缓存 | **无浏览器**：本次 469 独占 DB/HTTP/浏览器/preview 时段，未启动服务、未开页面 |
| 运行环境 | Node v24.22.1，`node --import=tsx`，`apps/frontend` cwd |

## 2. 先量后改：热点与原码

原 `contracts.tsx:157-181` 的 `baseColumns` useMemo 依赖 `shown` 与 `picked`，内部对每个金额列执行：

```
:163 const values=numeric?[...rows,...totalRow].map(row=>row[key]===null?'未确定':money(row[key]??'0')):[];
:164 const measured=numeric?numberColumnWidth(values,scale):undefined;
:165 const amountWidth=measured?completeColumnWidth(values,header,scale,三列?56:0):undefined;
:166 if(amountWidth&&measured)amountWidth.minWidth=amountWidth.initialWidth=Math.max(...);
```

`numberColumnWidth`（`grid.ts:37-45`）与 `fullTextWidth`（`grid.ts:48-53`）每次调用都
`document.createElement('canvas').getContext('2d')` 并对 `new Set(values)` 逐值 `measureText`；
`completeColumnWidth`（`grid-text.tsx:36-40`）内部调用 `fullTextWidth` 两次（值 + 表头）。
实测 7 个金额列的格式化串各 240–266 个唯一值（去重几乎无效），一次重建共 **1869** 个金额串、
**21** 次 canvas、**1920** 次 measureText。

## 3. 补丁（最小、沿既有 useMemo，未建 store/未改共享 grid）

| # | 改动 | 作用 |
|---|---|---|
| 1 | `totalRow` 加 `useMemo(...,[shown])` | 口径不变（仍按 shown 的 cents 求和→decimalCents），消除每渲染重算 |
| 2 | 新增 `moneyWidths` useMemo，依赖 `[query.data?.columns,rows,totalRow,scale]` | 把 :163-166 的 values/measured/amountWidth 移出选择/搜索状态；`baseColumns` 只查表 `moneyWidths[c.key]` |
| 3 | 新增 `selectionColumn` useMemo，依赖 `[scale]`；`headerComponent` 改传稳定组件引用 `ContractSelectionHeader`（原来每次重建都是新内联箭头 → 必然重挂表头） | 勾选不再重建列定义 |
| 4 | 模块级 `ContractSelectionContext` + `ContractSelectionHeader`（`useContext` 读实时 shown/picked），JSX 用 `ContractSelectionContext.Provider` 包住 grid | 表头照 `notices.tsx:176-184 / :42-45` 既有正确模式改为「观察实时选区」，不再靠重建列来刷新 |
| 5 | `baseColumns` 依赖去掉 `shown`/`picked`，改 `[columns,trade,scale,projectRows,projects.isPending,completeWidths,moneyWidths,selectionColumn]` | 勾选时 `columnDefs` 保持同一引用，AG Grid 不再整列对账 |
| 6 | 新增 `useEffect(()=>{if(active)grid.current?.refreshCells({force:true,columns:['select']});},[active,picked,shown])` | 列定义稳定后仍需刷新复选框单元格，避免勾选态显示陈旧 |

保留未动：搜索合计仍按 `shown` 求和（合计行仍参与测宽）；勾选/全选/顺序、金额 null→`未确定`、
所有金额与标识列、贸易公司三列显隐、五个内联编辑列与子表按钮、`manualGridColumns`/`useRetainedGridColumns`
手调宽与「恢复自动列宽」链、`state.current` 实时读取。

## 4. 业务等值（原/候选同源独立复算）

- 几何等值：`geometryEqual true`，`mismatch []` —— 7 列 `minWidth/initialWidth/suppressAutoSize` 与原式全等；
  候选宽度 contract_amt 113 / inv_sum 169 / trade_contract_amt 106 / trade_inv_sum 155 / settle 113 / pay_sum 162 / debt 106。
- 合计口径：`totalsStillFromShown = 181401652.72`，与响应体 `totals.contract_amt` 一致。
- 选择语义：9 个场景（全选、全选幂等、单勾、全选后取消单行、搜索「洛阳」后全选、全选→搜索→再全选、
  清空、先勾列表末行再全选、列表外勾选保留）逐场比对改前/改后 `picked` 集合、`selected` 数、`hidden` 数、
  `totalRow` 序列化 → `allEqual true`、`failures []`。

## 5. 指标（分项，含未验）

| 指标 | 改前 | 改后 |
|---|---|---|
| 一次纯勾选：canvas 创建 / measureText | 21 / 1920 | **0 / 0** |
| 一次纯勾选：Node 侧测宽+格式化耗时（canvas 桩） | 6.13 ms | **0 ms** |
| 一次纯勾选：金额 `money()` 格式化（纯 JS，真实测量） | 1.54 ms（中位，21 次，min 1.06） | 0 |
| 一次纯勾选：合计行 cents reduce（纯 JS，真实测量） | 0.69 ms（中位，21 次，min 0.32） | 0 |
| 冷建列几何（首次数据到达，应当发生） | 9.87 ms / 21 canvas / 1920 measureText | 同量（未变，必要） |
| 一次搜索（shown 收窄）几何重建 | 6.16 ms / 21 / 1920 | **未改善**：合计行按 shown 变化，测宽仍须重做 |
| 一次搜索 haystack（纯 JS，真实测量） | 1.17 ms（中位，命中 122 行） | 未变（本票不改搜索语义） |
| SQL / 网络 bytes / 浏览器绘制 | 本次无 DB/HTTP/浏览器时段 → **未验** | 同 |

- canvas 测量耗时由桩函数（`measureText = 字符数×7.2`）产生，只能作**相对对照**，不能当真实字体排版耗时；
  纯 Node 收益不等于 rAF/INP 改善，浏览器侧收益留主控统一 preview 复测。
- 同一探针两次运行冷建为 8.56 ms 与 9.87 ms，说明绝对毫秒随机器负载波动，**不作为 SLO**，也未设新阈值。

## 6. 实际命令与原码位置

```
cd apps/frontend && node ./node_modules/typescript/bin/tsc --noEmit            # exit 0
cd apps/frontend && node --import=tsx --test tests/unit/{cell-save,identity-gate,notice-codes,
  contracts-api,flow-api,mechanical-api,project-picker-order,grid-width-state,random-id,
  inventory-api}.test.mjs                                                     # tests 33 / pass 33 / fail 0, exit 0
node --import=tsx <group>/files/probe-contracts-columns.mjs                    # exit 0
node --import=tsx <group>/files/probe-selection-equivalence.mjs                # exit 0
node --import=tsx <group>/files/probe-money-format-only.mjs                    # exit 0
```

证据（group `site-performance-tail468-20261103`，owner `dsh-tail468`，未改动父 first-wave 组）：
`C:/Users/Administrator/AppData/Local/AgentArtifacts/projects/mtrl-workbench/groups/site-performance-tail468-20261103/files/`
- `probe-contracts-columns.mjs` + `probe-contracts-columns.run-20261103T0312.json`
- `probe-selection-equivalence.mjs` + `probe-selection-equivalence.run-20261103T0312.json`
- `probe-money-format-only.mjs` + `probe-money-format-only.run-20261103.json`

## 7. 结论与边界

- 结论：勾选路径的重复全量测宽/格式化已被证实并消除（21→0 canvas、1920→0 measureText、~2.2 ms 纯 JS 归零），
  几何与选择语义逐项等值。
- 反证/保持：**搜索路径无净收益**。`totalRow` 依 `shown` 变化，金额列宽度必须容纳新的合计值，
  故每次搜索仍要重建一次几何；搜索 haystack 未改动。不对搜索作提速声明。
- 未采纳的进一步方案：把「rows 部分最大宽」与「合计行最大宽」分组缓存再取 max（数学上与原式等价，
  可把每次搜索的 1920 次 measureText 降到约 7 次），但需在 contracts 内复制 canvas 测宽逻辑或改共享
  `grid.ts` 接口——前者重复共享实现，后者属主控拥有的共享 Grid 范围，本次不做。
- 未验：浏览器真实 INP/rAF、真实 canvas 字体排版耗时、滚动与绘制、SQL、HTTP bytes、preview 回归。
- 资源去向：无长期服务启动、无后台任务、无 DB/HTTP 占用；探针脚本与 JSON 仅在上述 group 目录，未写
  scratch 散件（`.scratch/site-performance` 只增本文件）；未触碰任何他人改动或未知已有文件。
