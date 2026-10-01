# tools/ · 索引（`TAIL-58` · 2026-09-21 分目录）

> ⛔ **本件是地图，不是口径** —— 各尺子的口径与阈值在 `ops/阈值表.md`，收工闸门在 `MEMORY.md §〇之二`。
> ⭐ **该跑哪把尺子**：平时只跑 5 条常用（见 `.codebuddy/memory/MEMORY.md` §〇之二），**收尾跑全套** —— ⭐ **清单与条数的唯一出口 = `tools/oneoff/_run_rulers.py`**
> （＝下表 `audit/` 各尺子 ＋ `probe/_audit_face` ＋ `acc_report` ＋ `mut_cover`；⚠️ 别在此处抄条数，会上涨）。

| 目录 | 放什么 | 怎么跑 |
|---|---|---|
| **`audit/`** | **13 把尺子**（`doc_audit` / `audit_drift` / `audit_meta` / `syntax_audit` / `ui_parity` / `wiring_audit` / `chain_audit` / `asset_audit` / `claim_audit` / `cover_gap` / `prg_form_audit` / `shell_verify` / `sticky_probe`）＋ 基础设施（`shell_source` ＝ 壳读取唯一出口）＋ `acc_report`（四态报表）＋ `mut_cover`（变异覆盖台账生成器） | `backend\.venv\Scripts\python.exe tools\audit\<件>.py` |
| **`mut/`** | **反向灵敏度**（`_mut_*.py` —— ⚠️ 件数**别写死**（会涨），跑 `audit/mut_cover.py` 看现值）：把实现**故意改坏** ⇒ 对应判据必须红 ⇒ **逐字节复原**。台账 = `artifacts/变异覆盖台账.md`（生成物，⛔ 不手改） | 逐个跑；台账：`tools/audit/mut_cover.py [--check]` |
| **`probe/`** | **真机 / 端到端**（`_shell_smoke` ＋ `_shell_*` 分段 · `_e2e_*` 真库往返 · `i8_*` · render/print smoke · `_audit_face`） | 单独跑（需服务在跑 ＋ Playwright） |
| **`oneoff/`** | **一次性 / 留痕**（`_apply_*` 机械改写 · `_doc_*` 文档回写 · `_acc_add_*` 判据登记 · `_fix_*`）＋ ⚠️ **常驻小工具**（`_run_rulers.py` 收工一把跑 · `_ps_bom.py` / `_ps_parse_check.ps1` · `_list_tails.py` · `_page_measure.py` · `_prepush_sensitive.py` · `_oneoff_measure.py`）—— ⛔ 不回读、不进收尾闸门；⭐ **保留与处置口径见文末那一段** | 按需（`_run_rulers.py` = 收工必跑） |

## 纪律（⛔ 别破坏）

1. **新增尺子 ⇒ 放 `audit/`**，并在 `doc_audit` 的 T 表、`ops/阈值表.md` 登记；
2. **新增变异 ⇒ 放 `mut/`**，docstring **第一段写「守什么」**（`mut_cover` 台账抓它），并在重跑 `mut_cover` 后把表 B 里对应条目删掉；
3. **⛔ 全站只许一处 `wb.save(`**（`report_export/save.py`，`tests/test_export_save.py` 静态扫描守着）；
4. 搬动任何件 ⇒ **同批改锚点路径**（`_mut_*.py` 按路径定位，搬了不改 = **静默失效**，`TAIL-57` 台账的"⚠️找不到"列会亮）。

## `oneoff/` 的保留与处置口径（`TAIL-194` · 2026-09-29 立 · ⭐ **本处是唯一主人**）

**为什么单立一段**：它此前是**全仓唯一"没有保留期、也没有机器眼"的目录** —— 对照 `.workbuddy/scratch`
明写着「保留期 14 天 ＋ 索引 README ＋ 机器眼 `T20`」⇒ 这边只会**一直堆**，而"哪些还能用 / 谁在用"**没人答得上来**。

**三类件，处置不同**（⚠️ 判"属于哪一类"的唯一办法 = **查引用**）：

| 类 | 怎么判 | 处置 |
|---|---|---|
| ① **常驻小工具** | 收工闸门 / 口径 / 别的件会**反复**引用它（`_run_rulers.py` · `_ps_*.ps1` · `_list_tails.py` · `_page_measure.py` · `_prepush_sensitive.py` · `_oneoff_measure.py`） | ⛔ **长期保留** —— 名字带 `oneoff` **不代表**它是"一次性" |
| ② **被引用的留痕件** | 台账 / 设计件 / 判据 / 记忆里**提到了它的文件名** | ⛔ **长期保留** —— 它们是"当初怎么做的"的唯一书面凭证；删了就**断链**（`T3` 幽灵路径 / 交付面 `_links` 会报） |
| ③ **零引用的** | **没有任何**仓内文书提到它 | ⭐ **候选清理**：**移进** `tools/oneoff/_归档-YYYYMMDD/`（可逆、⛔ 不删）；或写明留档理由 |

**两条纪律**：
1. ⛔ **不盲删** —— 先跑**只读**量测件 `tools/oneoff/_oneoff_measure.py`（报：件数 / 容量 / 被引用 / **零引用清单**）；
2. ⭐ **删或移都是破坏性动作 ⇒ 要用户点头**（先查牵连、先备份 —— 见 `MEMORY.md` §五）。

**机器眼**：`T20`（保留期与容量 · `tools/audit/audit_work.py`）—— 件数 / 容量超线 ⇒ **黄一行**；
阈值登记 = `ops/阈值表.md`（**改数先改表**）；自证 = `tools/mut/_mut_t20.py`。

**现况快照（2026-09-29 实测 · ⚠️ 会漂 ⇒ 以量测件输出为准）**：**175 件（跟踪）· 1231 KB** ·
**102 被引用 / 73 零引用** ⇒ 零引用那 73 件是**候选**（⚠️ 但"零引用"≠"没用"：有些是**归档留痕**、
有些只在**不入 git 的记忆**里出现过 —— 本件的语料**已包含** `.codebuddy/memory/`）。

