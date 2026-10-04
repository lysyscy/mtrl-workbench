# TAIL-188: 交付包与迁移

**What to build:** 交付包与迁移（本机 ⇒ 办公室电脑）：包 = 「**可继续开发的可运行系统**」（开发链全带）—— 在目标机上装得起来、起得来、跑得通 `selfcheck`，并且能接着往下调试。

**Blocked by:** None (can start immediately) · ⚠️ 硬约束 = 赶在**产包（去办公室的前一天）**之前

**Status:** ready-for-agent

- [ ] 包能在目标机装起来（`ops\selfcheck.ps1` **rc=0**）
- [ ] 恢复演练：**对空库还原成功**才算数
- [ ] `MANIFEST.txt` 的 `HEAD` 与本机 `git log -1` 对得上

---

## Comments

**2026-10-04 · 建票（agent）。** 来源：用户 2026-09-29 口述（出处 = `.codebuddy/memory/2026-09-29.md` §㉓/㉓之二）｜**不做会怎样：** 目标机上装不起来 / 落地无自检 ⇒ 系统交不出去｜**落点：** `work/10-designs/设计-交付包与迁移-20260929.md` ＋ `ops/{pack,deploy_restore,selfcheck}.ps1` ＋ `ops/deployment.md`｜**阶段 / 时机：** `M8`｜索引 = 计划 §15（**一行一票**）
