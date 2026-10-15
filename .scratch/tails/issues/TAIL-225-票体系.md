# TAIL-225: 票体系

**What to build:** 票体系落地：建票仓 `.codebuddy/work/50-tickets/` ＋ `T6` 认票文件（票 = 一个文件 · 索引 = 一行）。

**Blocked by:** None (can start immediately)

**Status:** done

- [ ] 8 张在办票迁成文件
- [ ] `T6` 认票文件（在位 / 幽灵 / 栏齐 / 状态受控）
- [ ] `_tail_open` 建票、`_tail_close` 标 `done`
- [ ] 反向灵敏度同批
- [ ] 闸门全绿

---

## Comments

**2026-10-04 · 建票（agent）。** 来源：用户 2026-10-04「②按推荐」＋「走正式的 `ask-matt` 推荐技能」（方案 §十一 乙案）｜**不做会怎样：** 不做 ⇒ 尾巴继续挤在表里一格（现普遍 1000–2400 字，是字墙最大来源）｜**落点：** `audit_meta.check_tail_ledger`（`T6`）＋ `_tail_open`/`_tail_close` ＋ `T12`/`T15` ＋ `tools/mut/` 靶｜**阶段 / 时机：** `立刻`｜索引 = 计划 §15（**一行一票**）

## 销号实况（2026-10-04 · 完整版 —— ⚠️ 原先写在 §四 那一行里，**982 字** ⇒ 被 `T21` 判「字墙」）

⭐ 这是票体系的**第一个实战示范**：`§15 §四` 的那一行**只留结论 ＋ 指针**，过程细节落在**这里**。

**同批改的机器件（逐件）**：
- `tools/audit/audit_meta.py`：`WORK_DIR_ALLOW` ＋`50-tickets` · `WORK_NAME_PREFIX` ＋`("50-tickets", ("TAIL-",))` ·
  新增 `TICKET_DIR_REL` / `TICKET_FIELDS` / `TICKET_STATES` / `TICKET_NAME_RE` / `TICKET_STATE_RE` ·
  `check_tail_ledger`（`T6`）末尾加**四条票检查**（在办票必须有票文件 / 幽灵票 / 票栏齐全 / 状态受控词）。
- `tools/audit/audit_work.py`：`T15` 的扫描面加 `50-tickets`（票文件的**文头四行复用同一份词表** —— ⛔ 没在 `T6` 里另写一套）。
- `tools/audit/doc_audit.py`：`T15` 说明与注释里的「四区」改「五区」。
- `ops/agents/issue-tracker.md` §六：从「随批建」改成「**已建** ＋ 同批改哪几处」。
- 根 `README.md`：抬头补票仓一段 · §三 目录树 `work/` 四区 → **五区**（＋`50-tickets/` 行）· §四 命名表加「**尾巴票**」一行。
- `.codebuddy/work/README.md` §一：落点表里「待办、尾巴」那行改指**票仓**。
- `tools/oneoff/_tail_open.py`：**建票文件**（`--short` / `--state` / `--tickets`；不达标连票文件一起回滚）。
- `tools/oneoff/_tail_close.py`：**票文件标 `done`**（找不到票文件 ⇒ 不写盘；票文件写不动 ⇒ 主文档回滚）。
- `tools/mut/_mut_docaudit.py`：`M19`（挪开在办票的票文件 ⇒ 必红）＋ `M20`（造幽灵票 ⇒ 必红）⇒ **20/20**。
- `tools/audit/mut_cover.py`：`IGNORED_REFS` 登记两条票 md（它的索引只收 `.py/.js/.html` ⇒ 不登记会常挂假"找不到"）。

**排查记**：`_tail_open.py` 自测（副本 plan ＋ 副本票仓）当场崩 —— `tpath.relative_to(REPO)` 在传**相对路径**时抛
`ValueError` ⇒ 改成 `pathlib.Path(a.tickets).resolve()`。⭐ **口径 = 干跑优先 ＋ 收尾断言**（本仓老话：自测的价值就在这儿）。

**闸门**：`_run_rulers.py --all` **rc=0 · `BAD: []`** · pytest 全绿 · `doc_audit` 修 0 · 四态 **644 / 0** ·
`mut_cover` **104** 一致 · ⛔ 没碰壳 ⇒ 无需真机 / 无需盖章。

**遗留（另开票）**：`§15 §一` 的索引行仍写着"来源 / 不做会怎样"⇒ 与票文件**重复**；下一步应**收成薄索引**
（编号 / 一句话 / 阶段 / 状态 / 票文件），细节全留票文件。
