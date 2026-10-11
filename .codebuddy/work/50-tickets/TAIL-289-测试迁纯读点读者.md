# TAIL-289: 把测试迁到纯读点读者（只用 const_src / func_body / page_slice 等出口、不再 import 整壳 SHELL），并让壳选集按读点收窄

**What to build:** 把测试迁到纯读点读者（只用 const_src / func_body / page_slice 等出口、不再 import 整壳 SHELL），并让壳选集按读点收窄

**Blocked by:** 无前置；⚠️ 收窄分支必须自带保守兜底：交集为空才不选，判不出来一律选

**Status:** ready-for-agent

- [ ] 先做**样板 3–5 件**：把"只读某一段壳"的测试从 `from tests.shell_src import SHELL` 改成**只用读点出口**（`const_src` / `func_body` / `page_slice` / `act_entry`），**断言语义不变**（同文件同断言，只换读取来源）。
- [ ] `_pytestscope.shell_plan` 增**按读点收窄**分支：改动落在**具名段**且测试读点**与之不交集**才不选；⛔ 判不出来（整壳读者 / 未登记读点 / 解析失败）⇒ **一律选**。
- [ ] 自证：造"改 `FL_THEAD` ⇒ 只选读它的件、⛔ 不选只读 `NT_THEAD` 的件"的隔离反例；反向（读点不交集却漏选）必须报红。
- [ ] **分批给数**：每批把"整壳读者 N 件"写进 Comments（基线 **61**，量测见 `tools/oneoff/_pytestscope.shell_plan` 上方那段）。
- [ ] 收窄生效后实测：改一段壳的**选集件数与墙钟**（基线：85–140 件 / ~100–160 s）。
- [ ] ⛔ 全程不放松现有门：整壳读者继续按老办法全选。

---

## Comments

**2026-10-11 · 建票（agent）。** 来源：2026-10-11 /retro 量测：188 件测试里整壳读者 61 件、纯读点读者 0 件 ⇒ 按读点收窄当时收益为 0（结论记在 tools/oneoff/_pytestscope.shell_plan 上方）｜不做会怎样：壳任意一处改动都会选中 ~85–140 件测试（~100–160 s/次）；不迁移就永远收不窄，而放松那扇门就是漏跑｜落点：backend/tests/*.py（61 件整壳读者分批迁）· backend/tests/shell_src.py（读点出口）· tools/oneoff/_pytestscope.shell_plan（按读点收窄的分支）｜阶段 / 时机：随时（大件，可分轮）｜**排期四问**（`§14.3` 同源）：①规模：先做 3–5 件样板 ＋ 收窄分支，再按批推 ②要改：现在'漏跑风险'与'慢跑成本'绑在一起 ③改哪层：测试的读取面 ＋ 选集判定层 ④做完＝整壳读者 61 → ≤N 分批给数，且收窄分支有'读点不交集 ⇒ 不选'的自证
