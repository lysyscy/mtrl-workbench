# TAIL-223: 落地流程顺序坑

**What to build:** 把 `ops/init_db.sql` 改成**可重跑**：现在建角色的 `<PASSWORD>` 与建库落在同一次 `deploy_restore` 里，第一次跑必然用字面 `<PASSWORD>` 建出角色，而 `CREATE ROLE` 不可重跑 ⇒ 库口令永远改不过来。

**Blocked by:** None (can start immediately) · ⚠️ 修它要动**交付关键件** ⇒ ⛔ 别赶在产包前动

**Status:** ready-for-agent

- [ ] `init_db.sql` 跑两次不报「角色已存在」（口令能改过来）
- [ ] 文档里的顺序与脚本实际顺序一致
- [ ] 过 `tools/oneoff/_ps_bom.py` ＋ `_ps_parse_check.ps1`

---

## Comments

**2026-10-04 · 建票（agent）。** 来源：用户 2026-10-04「甲」（检查产包流程时量出 · 出处 = `memory/journal/2026-10-04.md` §4）｜**不做会怎样：** 照 `ops/deployment.md` 手工落地的人必踩：`selfcheck` 第③项红，**原因不明显**｜**落点：** `ops/init_db.sql`（可重跑）＋ `ops/deployment.md` §一/§二 ＋ `ops/deploy_restore.ps1` 第 5 步措辞｜**阶段 / 时机：** `随时`｜索引 = 计划 §15（**一行一票**）
