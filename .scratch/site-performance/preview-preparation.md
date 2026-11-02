# 预览批次准备（465–469 两版冻结构建与验证节点）

状态：**仅准备**。本批未启动/停止预览、未复制数据库、未跑 HTTP 或浏览器；C470 独占 DB/backend_verify。
准备时间 2026-11-03；执行者 dsh-tail465；证据组 `site-performance-tail465-20261103`（owner `dsh-tail465`）。
解释器统一 `D:/dev/mtrl-workbench/backend/.venv/Scripts/python.exe`；`--source-env` 后续用主根 `D:/dev/mtrl-workbench/.env`（只由工具内存读取，未打印）。

## 1. 两个独立受管 run 与构建（均 `--prepare-build` 官方入口，未注入 fingerprint 绕过）

| | baseline | candidate |
|---|---|---|
| 工作树（detached，源码/索引未改，`git status` 干净） | `D:/dev/mtrl-workbench/var/worktrees/site-performance-base-20261103` | `D:/dev/mtrl-workbench/var/worktrees/site-performance-check-20261103` |
| run（在各自 `ROOT/.artifacts/active` 内） | `.artifacts/active/site-performance-tail465-20261103/base-run` | `.../check-run` |
| build（run 下新建目录） | `base-run/work/build-01` | `check-run/work/build-01` |
| `reports/version.json` | `base-run/reports/version.json` | `check-run/reports/version.json` |
| source_commit | `3c5712ed79d7790e818f5b2476e44fef971c6b73` | `8673a52cb0f4cc73deac894a4ace041872ee6559` |
| index_sha256 | `b161ce3e63e077ca36fe132054f5812d683e623abbaaad4e2c0d80bfaef8f1e4` | `d63411319ccb305ebe41709ecd64ba6db49801ce1cb1db24ca0f1c6c7cb7edc2` |
| files / assets | 39 / 37 | 39 / 37 |
| frontend_sources | 115 | 115 |
| 源码输入摘要 sha256（sorted json） | `f745e7b495e7e4fa60e8a7d4aefcf9e110a5c329e42a64598663bf0d16a59d0d` | `07d0e904a050a0fd765acd6d2e157d53c531f33a9490fa6b8ba61d4010b0f00f` |
| `apps/frontend/src/process.tsx` | `fbfd7d4b23c363c33960ab384346a8c1d305991801b087bb26c9b73983e8fda4` | `c5c15fa350d25ff9c09903e291db2518e621b4ebb7aa5a106cb8b0911a92ff97` |
| packageManager 声明/实际 | `pnpm@12.15.0` / `12.15.0`（`C:\Program Files\nodejs\corepack.cmd`） | 同左 |
| diagnostic_instrumentation | False | False |

原命令（cwd = 对应工作树，逐字）：
```
D:/dev/mtrl-workbench/backend/.venv/Scripts/python.exe -B -X utf8 tools/dev/frontend_preview.py \
  --run .artifacts/active/site-performance-tail465-20261103/base-run \
  --prepare-build .artifacts/active/site-performance-tail465-20261103/base-run/work/build-01
```
→ `BASELINE_EXIT=0`；candidate 只把 `base-run` 换成 `check-run` → `CANDIDATE_EXIT=0`。
日志：`{run}/logs/{package-manager,typecheck,build}.log`。package-manager=`12.15.0`；typecheck 尾行 `$ tsc --noEmit`（无报错）；build `vite v8.3.5`、`✓ 1718 modules transformed`、`✓ built in 1.94s`(base)/`1.80s`(check)。
`verify_build` 复核（`check_sources=True`，两版均含源码散列与全资产散列）：base 与 check 都返回构建路径、`EXIT=0`。

**两版前端输入差异只有 3 个文件**：`apps/frontend/src/process.tsx`(465)、`contracts.tsx`(468)、`settlement-api.ts`(469)；其余差异在后端与文档。即两版采集的 UI 差异可归因到这 3 个模块。

## 2. 资源与占用

- 每个 run 约 3 MB，目录被各自工作树 `.gitignore:45:/.artifacts/` 忽略（`git check-ignore -v` 已核），不进索引。
- 两工作树 `apps/frontend/node_modules` 是指向主根依赖的 Junction，本批未安装/修改依赖、未复制 `.env`。
- 当前**无活动预览**：`var/state/react-writable-preview/` 无 `current.json`；8065/8000 无监听（`netstat` 已核）。两 run 未登记 owner，真实库存副本未创建。
- 主根当前 `HEAD=8673a52c` 且有未提交 `backend/app/mod07_setl/big_service.py`（属 470 在飞改动）。`product_sources()` 含 `backend/app`，故**采集必须用上述冻结工作树**，不要用主根起预览。

## 3. 拟用节点（只选实际改动影响路径；全部只附着已登记真实副本）

运行方式（前端测试无 `apps/frontend/pytest.ini`，须显式 `PYTHONPATH` + `-o addopts=`，从**对应版本根**发起）：
```
cd /d <worktree>  &&  PYTHONPATH="<worktree>;<worktree>/apps/frontend/tests" \
  D:/dev/mtrl-workbench/backend/.venv/Scripts/python.exe -B -X utf8 -m pytest \
  -p no:cacheprovider -o addopts= -q apps/frontend/tests/test_process.py::test_real_process_raw_adjusted_rows_and_totals
```
已实跑 `--collect-only` 核入口（未跑用例，零浏览器）：base 工作树 `test_process.py` = 11 条；check 工作树 `test_process.py + test_contracts.py + test_inventory.py` = 17 条；均 `EXIT=0`。

- **465 过程资料**（`apps/frontend/src/process.tsx`）：`test_process.py::test_real_process_raw_adjusted_rows_and_totals`、`::test_real_process_enter_saves_without_clicking_elsewhere`、`::test_rapid_process_saves_never_revert_or_move_view`、`::test_history_failure_keeps_draft_other_cell_saves_and_blank_differs_from_zero`、`::test_process_unknown_receipt_keeps_submission_context_and_never_retries_itself`、`::test_unknown_receipt_does_not_rebase_a_later_draft_over_another_write`、`::test_difference_first_visible_frame_has_final_geometry`。性能侧用 `tail465-preview-ab.py`（首次进入/切项目/`layoutTiming.measured`），非 pytest。
- **464 机械屏幕读模型**（`process-api.ts` 走 `/api/m06/mech-screen`、`mod06_proc`）：`test_mechanical_details.py::test_real_detail_enter_autosave_keeps_later_field_draft`、`::test_internal_blur_and_enter_save_only_their_field_and_keep_later_draft`、`::test_lost_detail_receipt_can_reread_and_resume_without_another_write`、`::test_unknown_settings_receipt_keeps_input_and_rereads_without_repeat_write`；后端代表 `backend/tests/test_page_m06.py::test_屏幕读模型与完整机械接口逐值同签名_只少来源明细`（C470 窗口）。
- **466 库存**（`inventory-api.ts` readInventory Set）：`test_inventory.py::test_real_inventory_filter_is_local_and_keeps_amounts`（零 HTTP 本地筛选/合计/单据定位）、`::test_known_inventory_rows_keep_scroll_extent`、`::test_actual_inventory_adjustment_save_readback_and_revoke`（写，须 disposable）。
- **467 欠款事实复用**（`mod05_flow`）：`test_ledger.py::test_actual_ledger_edit_keeps_next_draft_and_reads_back`、`::test_actual_ledger_lost_write_receipt_cannot_resubmit`、`test_ledger_layout.py::test_actual_ledger_layout_tracks_rows_and_totals`、`test_startup_styles.py::test_debt_tables_publish_without_waiting_for_the_other_side`；后端 `backend/tests/test_tail467_debt_facts.py`。
- **468 集采勾选/列宽**（`contracts.tsx` context + memo）：`test_contracts.py::test_real_unified_search_and_no_supplier_or_amount_control`、`::test_real_contract_inline_typing_and_readback_keep_next_input_stable`；`test_grid_widths.py::test_save_preserves_narrow_manual_columns_on_full_list[contracts-…]`、`::test_native_resize_survives_reload_and_window_change[contracts-…]`、`::test_account_isolation_and_width_reset_preserve_filter_sort_and_selection`；`test_table_selection.py::test_contract_mouse_click_has_no_grid_ring`。
- **469 收发结存读模型**（`settlement-api.ts` `/api/m07/extract-screen`）：`test_settlement.py::test_real_settlement_row_amounts_and_natural_height`、`::test_real_extract_annual_rows_follow_status`、`::test_annual_first_visible_geometry_is_final_readonly`；导出代表 `test_mechanical_reports.py::test_actual_four_sheet_download_and_independent_project_preferences`；后端 `backend/tests/test_tail469_screen_reads.py`。
- 采集条件固定：视口 1920×1080、字号 1.12 = `UI_SCALES` 的 `large`（`backend/app/mod15_user/domain.py:150-158`）。**只有临时账号 `preview-user` 自带 `ui_scale='large'`、`theme='深色'`（`tools/dev/frontend_preview.py:99-102` 播种）；owner 的 `preview_account` 是 `preview-admin`（1.0）**。pytest 侧改字号的既有做法是 `POST /api/m15/ui-scale` + `finally` 还原（`test_grid_widths.py:40-42,64`）。
- 已把 `tail465-preview-ab.py` 登录账号改为参数 `--account`（默认 `preview-user`，见 §4-5），`--scale` 仍是"核实际值、不修改账号设置"。

## 4. 已知缺口与建议（需主控裁决，本批未绕过）

1. **`frontend_measure.py` 只读门与当前 server 不兼容**：`preview_identity()`（`tools/dev/frontend_measure.py:210-217`）要求 `owner['read_only'] is True` 且 `preview_account=='preview-user'`，而 `frontend_preview_server.py:222-223` 新建实例写死 `read_only=False`、`preview_account='preview-admin'`（历史 `reports/real_owner.json` 全是 `read_only:false`）。⇒ `--stage screen` 会直接 `ValueError('Not a supported isolated read-only preview')`。建议 **A（不改共享工具）**：465 用已备的 `tail465-preview-ab.py` 直采 `data-layout-timing` + 墙钟，它只要 run 与登记 owner 一致，不看 `read_only`；其余票用 pytest 布局/业务断言 + `frontend_layout.py`（同样不要求 `read_only`）。**B**：由主控另派明确授权的共享工具修正（加 `--read-only` 登记），不属本票写域。
2. **`appearance` 门**：`frontend_measure.py:267-269` 要求 `theme==default && ui_scale=='standard'`，而 `preview-user` 播种就是 `theme='深色'`+`ui_scale='large'`（`frontend_preview.py:99-102`）——即使只读门修好，这条也会直接 `ValueError('Use default theme/standard scale')`。⇒ 屏幕采集与 1920×1080/1.12 同条件不可兼得，进一步支持建议 A。
3. **跨实例基线比对**：`measure()` 要求 baseline 与当前 `database/schema/revision` 全等（`frontend_measure.py:235-237`）；baseline/candidate 是两个不同 disposable schema，天然不等。⇒ 两版各自独立成对采集，用**同一固定输入 + 同一脚本**比较绝对指标，不复用跨实例 baseline 链。
4. **字号 1.12 与登录账号不符**：`frontend_layout.py:163,168` 用 `owner['preview_account']`（=`preview-admin`，standard 1.0）登录，随后 `--scale 1.12` 必报 `实际字号与目标不符`（`frontend_measure.py:264` 则直接写死登录 `preview-user`）。可行做法（不改共享工具）：`--scale 1` 采 standard 档；或对 disposable 副本用 `POST /api/m15/ui-scale` 把**该副本临时账号**切 `large` 采后 `finally` 还原（pytest 既有做法，`test_grid_widths.py:40-42,64`）。切 1.12 前须主控确认允许改临时副本账号偏好（不是用户账号）。
5. 本轮已把 `tail465-preview-ab.py` 的登录账号从 `owner['preview_account']` 改为 `--account`（默认 `preview-user`），因为它读的是布局标记而非 `preview_identity` 的只读门；这是本票证据脚本的局部参数化，不改共享工具。
6. 写入代表（466/467/468 的 `disposable` 用例）必须等主控给候选实例且确认 `disposable=True && preserve_schema_on_stop=False`；baseline/candidate 性能采集阶段一律不写业务数据。

## 5. 未做与下一步

未做：起预览、复制 DB、跑浏览器/HTTP、跑 `backend_verify`、任何 git 写操作；未改原票/plan/status/主根产品代码/冻结源码。当前 `var/state/react-writable-preview/` 无 `current.json`，两个 run 只有 `reports/version.json`、未登记 `real_owner.json`，8065/8000 无监听。

下一步（等主控给独占窗口；每次只起一个实例，采完 `--stop` 再起下一个）：
1. baseline：在 base 工作树执行 `backend/.venv/Scripts/python.exe -B -X utf8 tools/dev/frontend_preview.py --source-env D:/dev/mtrl-workbench/.env --run .artifacts/active/site-performance-tail465-20261103/base-run --copy-source --disposable --port 8065`。
2. 465 指标：`tail465-preview-ab.py --preview-run <base-run>/reports/real_owner.json --account preview-user --width 1920 --height 1080 --scale 1.12`（首次进入/切项目/`layoutTiming` 回读 + 截图）。
3. 466/468/469 代表：§3 具名 pytest 节点（写用例须 disposable），布局类用 `frontend_layout.py --preview-run <run> --width 1920 --height 1080 --scale 1`（见 §4-4）。
4. `--stop` 后核对 `reports/real_owner.json` 变为 `stopped-disposable`；candidate 换 check 工作树/check-run 重复 1–3，两版用同一脚本同条件对照绝对指标，不做跨实例 baseline 链。
