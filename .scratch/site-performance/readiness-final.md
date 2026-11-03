# 首显缺陷终验（build-08）

窄验证：沿用主控定稿的三文件，只跑指定入口。未做新诊断、未全量 pytest、未重跑 15 页矩阵；b06/07 同产物绿证按主控要求复用。

## 1. 同步（主根 → candidate），未改主根

主根三文件 sha256（candidate 已逐字节相同）：

| 文件 | sha256 |
|---|---|
| `apps/frontend/src/page-surface.tsx` | `ef86ad2f885975e3a2e54cc99e5bff8f11a661c04040ed666f81247c3d3d68fe` |
| `apps/frontend/src/style.css` | `e6628b2afe90394891c0cefc4217976101b823a4c661ef9a82b286e285889e01` |
| `apps/frontend/tests/test_first_display_retained.py` | `a6ca49e2baf0e87a15d2d80c727070806229ae3baf1ffbc2ed6d75cdc12f204b` |

主根 git 状态下这三项为 `M`/`M`/`??`（主控自己的定稿改动），我未再改动。candidate 工作树 HEAD 仍 `78c79c8abfd94507e194a348a77cb212bbb2329c`，源码改动仅这 3 个路径。

定稿内容要点：`style.css` 新增 `.main>main{position:relative}`（让绝对定位的隐藏盒相对内容区而非视口）；`page-surface.tsx` 注释精简为 2 行、渲染行保留 `hidden` + `inert` + `aria-hidden` + `retainedBox`；回归合并为单条，视口 1280×480、4× CPU 节流、断言留存页 `clientWidth/clientHeight/scrollTop` 往返完全一致。

## 2. 清理陈旧登记（未伪造成正常 stopped）

- 复核：pid **43812 已死**（`tasklist` 空）、8065 **无 LISTENING**、`current.json` 指向该已死登记。
- 用官方 `exclusive_preview()` 锁 + `TestDatabaseGuard` 确认库为 **`mtrl_workbench_test`**，owner 记录为 `disposable=true` / `preserve_schema_on_stop=false` / `read_only=false` / `synthetic=false`，且 `live_process(owner)` 为假、端口空闲、同库其他会话数 **0**。
- 只 DROP 当前 owner 的精确 schema `frontend_rewrite_397_cb7e14126a2d4d1589b506910ca864c6`（owner `mtrl`），再用 `finish_preview()` 退登记并清指针，记录状态 **`abandoned-disposable-cleaned`**（非 `stopped-*`）。
- 报告：`files/reports/readiness-reclaim-cb7e1412.json`；脚本 `files/readiness-reclaim.py`。

**另两个 schema 保留未删（如实）**：`frontend_rewrite_397_48c7dd9964684fa3b31d24c95ce4596e`、`frontend_rewrite_397_68b8838c875e4985a8656faeaca9b205`。我在受管证据组、旧组、worktree `.artifacts`、`var/state` 中**都找不到本会话创建它们的记录**；唯一命中是 `.artifacts/archive/frontend-retirement/20261028-01/reports/frozen-trees-result.json`（2026-10-28，早于本会话，命中的是 `i8-human-preview-20261022` 的日志目录名 `…48c7dd99…`，属他人历史运行）。既然不能证明本会话创建，按指令保留。

## 3. 构建与启动（官方流程）

```
$PY tools/dev/frontend_preview.py --source-env D:/dev/mtrl-workbench/.env \
  --run .artifacts/active/site-performance-tail465-20261103/check-run \
  --prepare-build .artifacts/active/site-performance-tail465-20261103/check-run/work/build-08
# EXIT=0 → build-08, index_sha256 93bca6e8f1669b358dd6d4b00234dc79f06adfb59a89f7e0c341a0b67934df99,
#           source_commit 78c79c8a…, diagnostic_instrumentation false, 39 files
$PY tools/dev/frontend_preview.py --source-env D:/dev/mtrl-workbench/.env \
  --run .artifacts/active/site-performance-tail465-20261103/check-run --copy-source --disposable --port 8065
# /visual-version → schema frontend_rewrite_397_8a1bf06ae27c434b832df4c1a5e2cc8e,
#   cookie mw_real_preview_550c72e523bccec0, index_sha256 93bca6e8…, synthetic false
```
`.env` 只由官方工具在内存读取；未改源用户，用副本既有账号 `preview-admin`。

## 4. 指定入口结果

| 命令 | 退出码 | 结果 |
|---|---|---|
| `pytest tests/test_first_display_retained.py tests/test_grid_widths.py::test_notice_amount_click_keeps_automatic_and_manual_widths -q` | **0** | **2 passed in 32.37s** |
| `corepack pnpm test:unit`（apps/frontend） | **0** | **tests 34 / pass 34 / fail 0**，2336ms |

- 新回归的「外层 scroll」数据前提**成立**：脚本内 `assert before['scroll'] > 0, 'The real project page must exercise outer scrolling'` 未触发，故未做任何内容模拟；1280×480 下项目页可滚到底，留存期间 `clientWidth/clientHeight/scrollTop` 与切换前完全相同，返回后 `scrollTop` 不变。
- 我未改动这两个测试文件内容，也未新增测试。

## 5. 正常停止与现场退出

```
$PY tools/dev/frontend_preview.py --run …/check-run --stop   # EXIT=0
```
- `reports/real_owner.json` → `status="stopped-disposable"`，`disposable=true`、`preserve_schema_on_stop=false`，pid 43636（已不存在）。
- 8065 **无 LISTENING**、`/visual-version` 无服务、`var/state/react-writable-preview/current.json` **已不存在**（指针清除）。
- 本实例 schema `frontend_rewrite_397_8a1bf06ae27c434b832df4c1a5e2cc8e` 已由官方 `finally` DROP；现存 disposable schema 仅第 2 节报告的两个非本会话项。`public` 未触碰。

## 6. 未验证 / 不在本轮范围

- 未重跑 b06/07 已覆盖的红环、4× 节流环、15 路矩阵、几何对照（主控要求复用既有绿证）。
- 未跑全量 `pytest tests`（主控明确不做）。
- 既有失败清单未复核（先前 b17/b18 已记录：`test_startup_styles` 2 条、`test_fee_items` 2 条、`test_grid_migration`、`test_inventory`、`test_mechanical_reports`、`test_preview_copy` 2 条、`test_process`、`test_project_history`、`test_settlement`（副本 rows=0）、`test_table_selection` 2 条；以上在 committed build-04 上同样失败，非本次改动引入）。
- `.main>main{position:relative}` 的可见影响只由本轮单条几何/scroll 回归与 b06/07 几何绿证覆盖，未做跨断点/多滚动容器的额外矩阵。

未做：git 任何操作、改主根源码、碰 8000/public/生产、登录 i8、外部调用、真实打印、正式业务写入。
