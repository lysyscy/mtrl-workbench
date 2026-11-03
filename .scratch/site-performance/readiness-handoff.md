# 首显缺陷交接：项目档案→付款通知书 卡死

状态：诊断闭环 + 候选 WIP 已验证；**未集成、未提交**。本文只描述现状，不把候选补丁称为已验收修复。

## 1. 结论（已证）

**根因**：`apps/frontend/src/page-surface.tsx:46` 用 `hidden={!active}` 承载留存页，`apps/frontend/src/style.css:26` 的 `.page-view[hidden]{display:none}` 让留存页塌成 0×0。留存页内的 AG Grid 在 0×0 容器上无法收敛行高/视口几何，以约 150 rAF/s 持续自旋（`ensureRowHeightsValid → scheduleViewportGeometryRefresh / queueContainerHeightSync`），把渲染预算吃满；下一个页（付款通知书）的 Suspense 子树因此反复渲染却始终提交不出 primary：`fiberRoot.pendingLanes=37748736`（两个 RetryLane，`callbackNode.id` 递增）、提交树与工作树都 `sawNotices:false`、CPU 约 49% 在 `measureText`。`.page-view` 保持 `inert` + `visibility:hidden`，`.page-loading` / `[data-page-loading]` 一直显示「正在读取付款通知书…」。

**不是**这些原因（均已在红态排除）：lazy 未 resolve（全树仅 2 个 lazy，`_payload._status=1`）、React ping 丢失（`pingCache` 里的 thenable 已 fulfilled）、网络/chunk/模块解析（同 URL `import()` 27ms 成功）、字体、未捕获异常（红态 `Runtime.exceptionThrown` 计数 0）、主线程死锁（`setTimeout(0)` 延迟 4.4ms）。

**消融（4× CPU 节流，`readiness-ablate.py`）**：`measuretext` / `fonts` / `resize`(ResizeObserver) / `observer`(MutationObserver) / 只降频应用入口 rAF 全**仍红**；只降频 `business-grid-*`/`ag-grid` 发起的 rAF **转绿 350ms**；全 rAF 降频转绿 550ms ⇒ 主因是 AG Grid 自身的 rAF 自旋。

**触发面**：`项目档案→付款通知书`（4× 下稳定红）。`项目档案→欠款台账` 139ms 绿；直接冷开 `/preview/notices` 绿 1856ms；`首页→付款通知书` 绿 2717ms。即「先进入含 business-grid 的留存页，再切到重网格页」才会被拖死。

**口径纠正**：1× 无节流下 `projects→notices` 复现不稳定（连跑 3 次均绿 458.8/539.6/684.3ms），4× CPU 节流是本轮唯一确定性红入口；不得声称 1× 必红。

## 2. 候选 WIP（仅两处，均在 candidate 工作树）

工作树 `var/worktrees/site-performance-check-20261103`，HEAD 仍 `78c79c8abfd94507e194a348a77cb212bbb2329c`，`git status` 仅：
- `M apps/frontend/src/page-surface.tsx`（7+/2-，sha256 `2a1ce79fc3af7a5c20882fff654ebbb768b5b7c17b8f2cd0bf009a2a1be26002`）
- `?? apps/frontend/tests/test_first_display_retained.py`（77 行，sha256 `cc567b115d174a396d9e7cea50b335b3cb4178c757c19ee63b22096da2161223`）

改动：新增 `retainedBox`（`display:block; position:absolute; inset:0; visibility:hidden; pointerEvents:none; zIndex:-1`）；渲染行 `style={active ? { visibility: ready ? undefined : 'hidden' } : retainedBox}` 并加 `aria-hidden={active ? undefined : true}`。**active 分支与 committed 完全一致**，首显字体/数据/布局保护零改动，无超时强显、无预热、无全局 TTL。
`aria-hidden` 是必需的：只给 `visibility:hidden` 时留存页的「恢复自动列宽」按钮仍进 role 查询（`readiness-aria-a1.json`：baseline 命中 2 个，加 `aria-hidden` 后 1 个）。

受管补丁与源码备份（证据组 `files/`）：`readiness-fix-page-surface.patch`（30 行）、`readiness-fix-regression-test.patch`、`wip-page-surface.tsx`、`wip-test_first_display_retained.py`。

## 3. 红/绿（单变量，同一脚本同一判据，EXIT 0=绿 / 1=红）

命令前缀（cwd = candidate 工作树）：
```
export MTRL_RUN_ID=site-performance-readiness-20261103 MTRL_EFFORT=site-performance-readiness \
  MTRL_LIFECYCLE_OUTPUT="<managed>/groups/site-performance-readiness-20261103/files" \
  TAIL465_WORKTREE="D:/dev/mtrl-workbench/var/worktrees/site-performance-check-20261103" \
  PLAYWRIGHT_BROWSERS_PATH="C:/ProgramData/ms-playwright"
PY="D:/dev/mtrl-workbench/backend/.venv/Scripts/python.exe"; G="<managed>/.../files"; R=.artifacts/active/site-performance-tail465-20261103/check-run
$PY -B -X utf8 "$G/readiness-notices.py" --preview-run $R --paths projects --label X   # 红环
$PY -B -X utf8 "$G/readiness-slow.py"    --preview-run $R --rates 4 --reps 2 --label X # 节流红环
```

| 检查 | committed 78（build-02/04，idx `0400d389…`） | 候选（build-03/05，无 aria）；候选（build-06/07，含 aria） |
|---|---|---|
| `readiness-notices --paths projects` | **红**，4 次 20023.9/20069.2/20072.8/**20103.6**ms，EXIT=1 | 绿 240–253ms，EXIT=0 |
| `readiness-slow --rates 1,4,8` | 1× 2/2 绿（401.8/442.9）；**4× 0/2**（20135.5/20021.9）；**8× 0/2**（20061.8/20212.6），EXIT=1 | 4× **2/2 绿**（1644.1/1995.0 → 含 aria 版 1480.8/1522.9），EXIT=0 |
| `test_first_display_retained.py` | **红**：`expect(.notices-page).to_have_count(1)` 实际 0，31.18s | **2 passed** 40.09s / 43.22s |
| `readiness-matrix15` 15 路×2 进入方式 | 未跑（15 路采集器原路径 exit 2） | 1× ok 29 行；4× ok 29 行（最慢 `/inventory` nav 5444ms） |
| `readiness-geom`（通知书 + 机械费 cold vs nav） | 未跑 | ok：通知书两路几何完全相同 `view 1792×1022 / page 1760×982 / grid 1758×758`，`docScrollW=winW=1920` |
| `test_grid_widths.py::test_notice_amount_click_keeps_automatic_and_manual_widths` | 3/3 通过（11.10s） | **无 aria：3/3 失败**（strict mode violation，命中留存页「恢复自动列宽」）；**含 aria：3/3 通过**（11.15s） |

证据：`files/reports/readiness-notices-red78-verify.json`、`readiness-slow-cpu1.json`、`readiness-notices-green-b06-both.json`、`readiness-slow-green-b06-4x.json`、`readiness-matrix15-b06-4x.json`、`readiness-geom-b06-4x.json`、`readiness-ablate-*.json`、`readiness-rafsrc-r1.json`、`readiness-redroot-rr2.json`、`readiness-lazywalk-lw1.json`、`readiness-aria-a1.json`、`readiness-hide-hid1.json`。

## 4. build 与实际源对应

| build | 源 | index_sha256 |
|---|---|---|
| build-02 | committed 78（git 干净） | `0400d3897731…bdc16` |
| build-03 | WIP **无** aria-hidden | `5431e50f7c6a…d06d1` |
| build-04 | committed 78 还原（`git show HEAD:` 写回 CRLF 再 build，用于同代码对照） | `0400d3897731…bdc16`（与 build-02 同） |
| build-05 | 与 build-03 同源重出 | `5431e50f7c6a…d06d1` |
| build-06 | WIP **含** aria-hidden（注释未定稿） | `d2dfc8d71d18…2e4af` |
| build-07 | WIP 含 aria-hidden + 定稿注释 | `d2dfc8d71d18…2e4af`（仅注释变化，产物散列相同） |

当前 `reports/version.json` = build-07；`frontend_sources['apps/frontend/src/page-surface.tsx']` = `2a1ce79f…` 与工作树一致。

## 5. 已验证 / 未验证

已验证（green 运行发生在 build-06，除注释外与最终 build-07 同源）：
- 新回归 2 passed；原红环与 4× 节流环转绿；15 路矩阵 29 行全 ready+data；几何 cold/nav 一致；`test_grid_widths` 目标测试 3/3 通过。
- 全量对照（**build-05，无 aria 版**）：WIP 15 failed / 120 passed；committed 对照 build-04 同一失败子集 14 failed / 56 passed，差集仅 `test_grid_widths` 那条（已由 aria 修复）。其余 14 条失败在 committed 上同样失败：`test_startup_styles` 2 条、`test_fee_items` 2 条、`test_grid_migration`、`test_inventory`、`test_mechanical_reports`、`test_preview_copy` 2 条、`test_process`、`test_project_history`、`test_settlement`、`test_table_selection` 2 条。已用单变量 A/B 证明 `test_startup_styles` 两条与 `test_inventory`/`test_table_selection[inventory]` 与本改动无关（`readiness-abetween-*.json`、`readiness-inv-*.json`）；`test_settlement` 是副本 `/api/m07/settlement` rows=0。

**未验证（须在集成后补）**：
- 最终 build-07（含 aria）上**未重跑**新回归、红环、15 路矩阵、几何与 `test_grid_widths`；上述 green 数字来自 build-06（同 `index_sha256`，仅多定稿注释）。
- **含 aria 版的全量 pytest 没有完成**：build-06 上那轮因我在构建产物与源之间改了注释触发 `RuntimeError: 构建的前端输入已变化，须离线重新构建`（125 errors，无效运行）；build-07 上那轮被会话中止，止于 53%，无结论。
- 1× 无节流下 red→green 的稳定性未做多次重复（4× 是判据环）。
- 未复核 `first-visible` 在其它 autoHeight 页（只测了机械费）。

## 6. 资源退出状态（停止失败，如实报告）

- 端口 8065 **无 LISTENING**；`curl http://127.0.0.1:8065/visual-version` → 无服务；pid **43812 已不存在**（`tasklist /FI "PID eq 43812"` 空）。
- 官方 `frontend_preview.py --run … --stop` **失败**：`RuntimeError: 预览身份、真实副本来源或进程不符`（`frontend_preview_runtime.py:162`，`active_preview()` 因 `live_process(owner)` 为假而拒停——服务进程在后台 job 被杀时已退出，`finally` 里的 `finish_preview` 未执行，登记未回收）。
- 因此登记仍为陈旧状态：`check-run/reports/real_owner.json` 的 `status="ready"`、`pid=43812`；`var/state/react-writable-preview/current.json` 仍指向它。**我没有手改登记，也没有强杀任何进程**。
- 遗留 disposable schema（只读查询列出，未删）：`frontend_rewrite_397_cb7e14126a2d4d1589b506910ca864c6`（最后实例，`disposable=true` / `preserve_schema_on_stop=false`），以及更早遗留 `frontend_rewrite_397_48c7dd9964684fa3b31d24c95ce4596e`、`frontend_rewrite_397_68b8838c875e4985a8656faeaca9b205`（owner `mtrl`）。
- 接手方需要：先按预览指南清理陈旧登记（或按官方流程重跑一次 start/stop 让它自行 `finish_preview` + DROP SCHEMA），再重建 build 并复跑第 5 节的未验证项。

未做：任何 git add/commit/push/switch/reset/clean/stash；未改主根产品源码；未碰 8000；未登录 i8、无外部/业务写。
