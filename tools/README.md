# tools/ · 工具用途与触发入口

> 读者：选择工具或维护检查的人。回答：工具职责与何时运行。流程回 ops/agents/issue-tracker.md §四；命令回 .codebuddy/memory/IDE-细节.md §十一。

| 目录 | 用途与读取条件 |
|---|---|
| audit/ | 结果、语法、接线、文档及字节检查；按实际保护后果选择。固定检查登记为 tools/oneoff/_run_rulers.py 的CMDS；工具自测单列SELFTESTS，按 tools/oneoff/_impactscope.py 的实际依赖触发。 |
| mut/ | 判据反向灵敏度；只在相关判据/机制改变时执行对应隔离自证，不随普通修改跑全部KEY。核验机制入口 `tools/mut/_mut_gatescope.py --paths <实际机制路径...>` 选择相关反例；不传范围、未知范围或反例自身变动时保留全部，每个反例调用所属真实自测。旧直接写工作靶的脚本须先隔离，不按默认入口运行。 |
| probe/ | 真机与端到端实测；改到对应运行行为时使用，需要时说明服务和现场前提。 |
| oneoff/ | 操作与历史脚本，以及开销票、影响选择和回执常驻工具；保留规则见下节。历史操作脚本仅在复现时读。 |

## 纪律（⛔ 别破坏）

1. **新增尺子 ⇒ 放 `audit/`**，并在 `doc_audit` 的 T 表、`ops/阈值表.md` 登记；⭐ **新增一条判据（`T*`）⇒ 同批核它接进了 `doc_audit`**（`T23` 半边④ 是范例：**拆掉接线就报红** ⇒ 忘了接线的判据自己会喊）；
2. **新增变异 ⇒ 放 `mut/`**，docstring **第一段写「守什么」**（`mut_cover` 台账抓它），并在重跑 `mut_cover` 后把表 B 里对应条目删掉；
3. **⛔ 全站只许一处 `wb.save(`**（`report_export/save.py`，`tests/test_export_save.py` 静态扫描守着）；
4. 搬动任何件 ⇒ **同批改锚点路径**（`_mut_*.py` 按路径定位，搬了不改 = **静默失效**，`TAIL-57` 台账的"⚠️找不到"列会亮）。
5. ⛔ **提交不许加 `--no-verify`**，且**判据是可观察的**：**提交输出里必须出现 `pre-commit` 行** ——
   那一行没出现 ＝ 钩子没跑 ＝ 钩子里的「暂存区文件名黑名单」（`ops/init_db.sql` / `.env` 绝不提交）
   **那一刻没被守**。⚠️ 2026-10-06 实测踩过：agent 顺手加了 `--no-verify`（事后补跑 5 条尺子全绿，
   但那道黑名单护栏确实没跑）⇒ **钩子的内容也已被 `_run_rulers.CMDS` 覆盖，唯独"提交那一刻"没有第二道**。
6. ⭐ **模块 / 函数的 docstring 第一句就得是它**（`Q4` 只查得前者）：⛔ **别把注释放 docstring 前面** ——
   那段字符串就不再是 docstring（`__doc__` 变 `None`），而**没有任何尺子看得见**；⛔ docstring 里写
   Windows 路径**用正斜杠或 raw 字符串**（`D:\dev\...` 的 `\d` 是非法转义 ⇒ `syntax_audit` 判红）。
   ⚠️ 2026-10-06 两条都当场踩过：前者在 `audit_work.py`、后者在 `syntax_audit.py` 自己身上。

## 隔离机械存储反例

`tools/mut/_isolated.py::isolated_backend`供`tools/mut/_mut_proc_split.py`与`tools/mut/_mut_tail270.py`共用：复制后端到scratch，子进程传测试库与独立四态出口，结束清临时副本；不复制凭据。新增同类反例优先复用，测试库写入仍由用例事务回滚。
一次性编辑脚本与可重复核验脚本分开；改过的锚不会作为下一次核验的前置动作。开工快照摘要与真机证据读取命令回 .codebuddy/memory/IDE-细节.md §十一。

## `oneoff/` 的保留与处置口径（`TAIL-194` · 2026-09-29 立 · ⭐ **本处是唯一主人**）

**三类件，处置不同**（⚠️ 判"属于哪一类"的唯一办法 = **查引用**）：

| 类 | 怎么判 | 处置 |
|---|---|---|
| ① **常驻小工具** | 收工闸门 / 口径 / 别的件会**反复**引用它（`_run_rulers.py` · `_run_muts.py` · ⭐ **`_pytestscope.py`**（**pytest 该跑什么的单一出口** · 2026-10-06 `TAIL-241`：三张名单 ＋ import 闭包 ＋ 缺口自检 ＋ `--cover-only`；⛔ 秒数看每次运行自己的输出）· `_gatescope.py`（输入摘要、通过回执与保守兜底；执行清单仍归 `CMDS` / `KEY`）· `_ps_*.ps1` · `_list_tails.py` · `_page_measure.py` · `_prepush_sensitive.py` · `_oneoff_measure.py` · ⭐ **`_tail_open.py` / `_tail_close.py`**（立/销台账 · 2026-10-02 补）· ⭐ **`_doc_downgrade.py`**（降档动作 · 2026-10-06）） | ⛔ **长期保留** —— 名字带 `oneoff` **不代表**它是"一次性" |
| ② **被引用的留痕件** | 台账 / 设计件 / 判据 / 记忆里**提到了它的文件名** | ⛔ **长期保留** —— 它们是"当初怎么做的"的唯一书面凭证；删了就**断链**（`T3` 幽灵路径 / 交付面 `_links` 会报）。活引用须同批更新；历史引用不能单凭零命中判断无用。 |
| ③ **零引用的** | **没有任何**仓内文书提到它 | ⭐ **候选清理**：**移进** `tools/oneoff/_归档-YYYYMMDD/`（可逆、⛔ 不删）；或写明留档理由 |

**两条纪律**：
1. ⛔ **不盲删** —— 先跑**只读**量测件 `tools/oneoff/_oneoff_measure.py`（报：件数 / 容量 / 被引用 / **零引用清单**）；
2. 删移先查现行用途和引用，按用户已授权范围执行；未授权或仍有现行用途才需确认。

**机器眼**：`T20`（保留期与容量 · `tools/audit/audit_work.py`）—— 件数 / 容量超线 ⇒ **黄一行**；
阈值登记 = `ops/阈值表.md`（**改数先改表**）；自证 = `tools/mut/_mut_t20.py`。


## 按需自证与归档

TAIL-297 清点的历史一次性脚本原文移入 `tools/oneoff/_归档-20261011/`，逐件用途、引用与两问理由见 `.codebuddy/work/50-tickets/TAIL-297-尺子体检.md` Comments；归档源字节未改，旧地址是当时操作的证据。恢复重放须从 Git 取对应原树和环境，不能在归档目录直接运行。现役 `_list_tails.py` 读取主计划与已销号姊妹件；`_prepush_sensitive.py` 核现行治理目录且 git 失败不当空结果；`_tail59_measure.py` 使用现行资料面。

`tools/probe/_cn_path_probe.py` 默认只量 D 件中文相对引用，`--documents` 量既有文档扫描面；有缺失候选返回非零，候选须区分历史、简称及未持久化产物，不表示 T3 已扩面。绝对仓外路径仍由 T3 原分支核存在。自测登记回 `_run_rulers.SELFTESTS`，反向见证为 `tools/mut/_mut_tail297.py`；待查判据的可配变异由 `_impactscope.mutation_candidates` 从活件登记与源码反查，只列候选，不当隔离或通过证明。

三个工具的 `--selftest` 可独立运行，普通修改与显式完整检查均只在工具/相关依赖变化时选中；选择及回执失效后果由 `_gatescope` 隔离自证验证。归档动作还依赖现行钩子及其检查实现；引用查询依赖公共扫描/票规则。依赖触发的唯一登记回 tools/oneoff/_impactscope.py。

变异按受影响机制明确选件，`_run_muts.py --cases` 允许KEY与KEEP_OUT中的活件；只有提供隔离输入的入口可执行。归档件不参加活件登记/机器引用/覆盖扫描，恢复说明在 tools/mut/_归档-20261009/README.md。保留件不代表本轮全部可执行；旧直接写靶件仍须先隔离。`mut_cover --check`只验生成台账与源码登记一致，不执行变异、不证明断言会红。
