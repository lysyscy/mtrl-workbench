# TAIL-466 结果：库存读取校验（adjustments 存在性索引）

**执行者** DSH 新会话 `session-8af00c10-7649-42ad-9238-829a8f0f8a95`（B2），`workbuddy/deepseek-v4.1-flash/high`，新上下文。
**基线** HEAD `daf8a7fce9aaf932a7d971daa7db178ae7becaa4`，分支 `codex/site-performance-20261102`。未提交、未切分支、未动索引/stash/reset。
**性质** 纯离线前端：只读主控固定 JSON，Node 运行前端纯函数 + tsc。未接触任何配置/.env/凭据、DB、Python 应用、pytest、HTTP、浏览器、服务、i8、打印。

## 1. 改动清单（仅两文件）

| 文件 | 状态 | 内容 |
| --- | --- | --- |
| `apps/frontend/src/inventory-api.ts` | 修改（+4/-1 行，第 56 行） | `readInventory` 尾部校验：一次性建 `Set(row_id)` 复用，替代每行重扫 747 条 adjustments 的 `adjustments.some(...)` |
| `apps/frontend/tests/unit/inventory-api.test.mjs` | 新增 | 4 条具名断言：adjustments 双向对应、dangling 仍接受、重复 row_id/adjustment row_id 仍拒绝、金额与 id 校验先于对应检查 |

改后代码（`inventory-api.ts:56-61`）：

```ts
const rowIds = new Set(rows.map(r => r.id));
if (rowIds.size !== rows.length) throw invalid();
const adjustmentRowIds = new Set(adjustments.map(a => a.row_id));
if (adjustmentRowIds.size !== adjustments.length || rows.some(r => r.adjusted !== adjustmentRowIds.has(r.id))) throw invalid();
```

**需主控串行改 `package.json`**：把 `apps/frontend/tests/unit/inventory-api.test.mjs` 加入 `test:unit` 列表（我未改 `package.json`）。
未动：`cents` 金额规则、`effectiveValues`、响应形状、`coarseRows`/`filterRows`/`sumRows`、保存/刷新、列宽、分页、范围下推、token、gzip。

## 2. 输入指纹（主控固定派生 JSON）

- 内容 SHA256 `d4ba1ac1cc6ef58c85eba9ba123f62ef76dd00a4ec341e83d5d8fc8c8ffccf1b`，16,077,308 B
- 18,287 rows / 747 adjustments / 14 projects / 6 materialProperties；`adjusted:true` 恰 747 行；adjustments 的 `row_id` 全部存在于 rows
- `readInventory` 输出 13,716,395 B，SHA256 `6df80bf19bbd15290c1db8c0da30317f933e4d0491e2e7c8dfad2cf423476ad1`（修前=修后，字面全等）

**路径偏差（需主控核实）**：任务给的 `C:\Users\Administrator\AppData\Local\AgentArtifacts\projects\mtrl-workbench\groups\site-performance-first-wave-20261102\files\controller\inventory-body.json` **不存在**；实际命中在
`C:\Users\Administrator\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\AgentArtifacts\projects\mtrl-workbench\groups\site-performance-first-wave-20261102\files\controller\inventory-body.json`
（SHA/size 与主控值一致）。两个根的 `.lifecycle.json` 都声明 `root=...\AgentArtifacts\projects\mtrl-workbench`，但目录与 group `record.json` 不同（NonLocalCache 属 `dsh-tail464`，LocalCache 属 `site-performance-controller`），疑为重定向/副本写偏。我的产物按指示走 `tools/artifact_lifecycle.py lease`，落在 NonLocalCache 根的 `files/tail466-b2/`。

## 3. 前后指标（同一输入、同进程、交替配对 7 对取中位）

`ab.mjs`：HEAD 原文件（`git show HEAD:...` 逐字节 6,893 B，SHA `0b241f73…`）与当前 `src/inventory-api.ts` 同进程交替导入，配对顺序逐轮回转。

| 阶段 | 修前（HEAD 控制组） | 修后（当前） | 变化 |
| --- | --- | --- | --- |
| `JSON.parse`（对照，未改） | 53.59 ms | 59.86 ms | 波动项，未改 |
| `readInventory` 全程 | 170.07 ms | 74.08 ms | **−95.99 ms（−56.4%）** |
| 尾部校验孤立阶段 | 73.06 ms | 3.22 ms | **−69.84 ms（−95.6%）** |
| 配对差 `control−current` | — | 中位 60.23 ms | 7/7 对为正 |

复现 3 次（`ab.json`/`ab2.json`/`ab3.json`，中位 ms）：

| 运行 | parse | read 控制 | read 当前 | 配对差 | 尾部 控制→当前 |
| --- | --- | --- | --- | --- | --- |
| 1 | 53.59 | 170.07 | 74.08 | 60.23 | 73.06 → 3.22 |
| 2 | 45.20 | 133.87 | 76.49 | 57.39 | 50.01 → 3.16 |
| 3 | 50.29 | 174.30 | 93.22 | 79.90 | 72.53 → 3.58 |

`bench.mjs after`（9 轮，修后源）对照：read 中位 99.51 ms，尾部控制组 50.46 ms → 候选 3.18 ms，孤立差中位 48.01 ms。
**方向与量级在 3 次交错运行中一致；尾部为校验内主要成本，改后降到常数级。绝对毫秒随机器负载波动，不作为 SLO。**

## 4. 业务等值

- **字面全等**：同一 16,077,308 B 输入上，新旧 `readInventory` 结果的 `JSON.stringify` 完全相同（13,716,395 B，两侧 SHA 均 `6df80bf1…`），含字段顺序。
- **接受/拒绝集合与消息不变**（`before.json`/`after.json` 的 10 例矩阵逐项一致）：
  - 接受：原始载荷；**悬空 adjustment（row_id 无对应 row）仍接受**，未变成新错误；`count` 字段无效仍接受（该字段本就不校验）。
  - 拒绝并报 `库存读取不完整，请重读。`：重复 row_id、重复 adjustment row_id、`adjusted:true` 无对应 adjustment、有 adjustment 但行未标记、row_id 非安全整数、`adjustments` 非数组。
  - 拒绝并报 `金额读取不完整，请重试。`：adjustment `amount` 非法（消息与阶段未变）。
- **短路顺序保持**：`rowIds` 去重失败 → 立即抛；`adjustmentRowIds` 去重失败或对应不符 → 抛。与原先 `||` 链的求值顺序和 `invalid()` 出口一致。
- 测试有效性用 3 个语义变异体验证（`mutate.mjs`，均从 `apps/frontend` 运行）：dangling 变错误 → 2 条失败；去掉重复 adjustment row_id 检查 → 2 条失败；去掉重复 row_id 检查 → 2 条失败。变异文件只存在于 `tail466-b2/mutants/`，仓库未被写入。

## 5. 实际命令与退出码

工作目录 `D:/dev/mtrl-workbench/apps/frontend`（`OUT`=上述 `files/tail466-b2`，`J`=固定 JSON，`L`=`python -X utf8 ../../../tools/artifact_lifecycle.py lease --group site-performance-first-wave-20261102 --`）：

| 命令 | 退出码 |
| --- | --- |
| `node --import=tsx "$OUT/bench.mjs" before "$J" "$PWD/src/inventory-api.ts" "$OUT/before.json"` | 0 |
| `node --import=tsx "$OUT/ab.mjs" "$J" "$PWD/src/inventory-api.ts" "$OUT/control/inventory-api.head.ts" "$OUT/ab.json"`（+`ab2`/`ab3`） | 0 / 0 / 0 |
| `node --import=tsx --test tests/unit/inventory-api.test.mjs` | 0（4 pass / 0 fail） |
| `corepack pnpm typecheck` | 0（`tsc --noEmit` 无输出） |
| `$L bash -c "…ab.mjs…; …"` | 0（租约内，`ab=0`） |
| `$L bash -c "…bench after…; node --test…; pnpm typecheck…"` | 0（`unit=0`，`tc=0`） |

未运行：Python、pytest、`backend_verify`、任何 DB/HTTP/浏览器/服务/打印命令；未跑其余 29 项单测（按指示，同轮 CI 统一承担）。

## 6. 未验项与边界

- **未验证**：真实服务端构造/编码/传输耗时；浏览器端解析、React 派生、布局与滚动；首次进入与保活返回的真实体感；INP。本报告**不声称**网络、全页加载或滚动改善，也不将 Node 侧收益外推为端到端收益。
- 未测多账号/权限、调整保存与读回、其他页激活更新（本次无写入路径改动，`adjustInventory` 未动）。
- 金额规范（`cents`/`decimal` 唯一出口）、`numeric` 接受集合、null/0 语义均未改动，故未加重复数值单测。
- 未改 `package.json`，新测试文件需主控加入 `test:unit` 后才会进常规 CI 列表。
- 产物仅在 `files/tail466-b2/`（租约内写入）；未 register/close 父组，未另建散件，未清理他人目录。
