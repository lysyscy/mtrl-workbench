# tools/ · 索引（`TAIL-58` · 2026-09-21 分目录）

> ⛔ **本件是地图，不是口径** —— 各尺子的口径与阈值在 `ops/阈值表.md`，收工闸门在 `MEMORY.md §〇之二`。
> ⭐ **该跑哪把尺子**：平时只跑 5 条常用（见 `执行情况` §⑥），**收尾跑完整十二条**（`MEMORY.md §〇之二`）。

| 目录 | 放什么 | 怎么跑 |
|---|---|---|
| **`audit/`** | **13 把尺子**（`doc_audit` / `audit_drift` / `audit_meta` / `syntax_audit` / `ui_parity` / `wiring_audit` / `chain_audit` / `asset_audit` / `claim_audit` / `cover_gap` / `prg_form_audit` / `shell_verify` / `sticky_probe`）＋ 基础设施（`shell_source` ＝ 壳读取唯一出口）＋ `acc_report`（四态报表）＋ `mut_cover`（变异覆盖台账生成器） | `backend\.venv\Scripts\python.exe tools\audit\<件>.py` |
| **`mut/`** | **反向灵敏度**（`_mut_*.py` · 65 件）：把实现**故意改坏** ⇒ 对应判据必须红 ⇒ **逐字节复原**。台账 = `artifacts/变异覆盖台账.md`（生成物，⛔ 不手改） | 逐个跑；台账：`tools/audit/mut_cover.py [--check]` |
| **`probe/`** | **真机 / 端到端**（`_shell_smoke` ＋ `_shell_*` 分段 · `_e2e_*` 真库往返 · `i8_*` · render/print smoke · `_audit_face`） | 单独跑（需服务在跑 ＋ Playwright） |
| **`oneoff/`** | **一次性 / 留痕**（`_apply_*` 机械改写 · `_doc_*` 文档回写 · `_acc_add_*` 判据登记 · `_fix_*`）—— ⛔ 不回读、不进收尾闸门 | 按需 |

## 纪律（⛔ 别破坏）

1. **新增尺子 ⇒ 放 `audit/`**，并在 `doc_audit` 的 T 表、`ops/阈值表.md` 登记；
2. **新增变异 ⇒ 放 `mut/`**，docstring **第一段写「守什么」**（`mut_cover` 台账抓它），并在重跑 `mut_cover` 后把表 B 里对应条目删掉；
3. **⛔ 全站只许一处 `wb.save(`**（`report_export/save.py`，`tests/test_export_save.py` 静态扫描守着）；
4. 搬动任何件 ⇒ **同批改锚点路径**（`_mut_*.py` 按路径定位，搬了不改 = **静默失效**，`TAIL-57` 台账的"⚠️找不到"列会亮）。
