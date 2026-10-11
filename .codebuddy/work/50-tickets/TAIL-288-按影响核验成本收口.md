# TAIL-288: 按影响核验的两处成本收口：pytest 回执签名排除产物目录、六支变异脚本加 --no-full-suite

**What to build:** 按影响核验的两处成本收口：pytest 回执签名排除产物目录、六支变异脚本加 --no-full-suite

**Blocked by:** 无前置；⚠️ 改签名属放宽闸门，必须同时给自测三向并与 6 支开关同批自证

**Status:** ready-for-agent

- [ ] ① `_gatescope.input_signature` 的 pytest 分支把**产物目录**排除出签名（`.codebuddy/work/00-scratch/` 与 `backend/.codebuddy/`）—— 理由同 `artifacts/`：**产物不该触发自己**。判据 = 自测三向：产物变 ⇒ **可复用**；`backend/app/**` / `backend/tests/**` / `tools/**` 变 ⇒ **必重跑**；环境变 ⇒ 必重跑。
- [ ] ① 实测：同一轮内**第二次**跑按影响入口时，`pytest（隔离结果）` 打「复用 …」且总墙钟显著下降（本轮基线：**98 s/次**）。
- [ ] ③ 另 6 支带"重跑全套"的变异脚本加 `--no-full-suite`（`_mut_tail04_pages` 已有）：**默认行为不变**（不带开关照旧跑全套、写权威四态）。
- [ ] ③ 每支用 `--no-full-suite` 跑通一次：打印"跳过全套 … 本轮不刷新权威四态"，且 rc 仍由命中数 / MD5 复原决定。
- [ ] ⛔ 边界写清：跳过即"本轮**不刷新权威四态**"，票面与 Comments 不得宣称刷新过。
- [ ] 收尾：`_run_rulers.py --paths <改动件>` rc=0 / `BAD: []`；`tools/oneoff/_gatescope.py --selftest` rc=0。

---

## Comments

**2026-10-11 · 建票（agent）。** 来源：2026-10-11 /retro 落地时的实测与遗留（同回合 pytest 复用不了；另 6 支带全套的变异脚本未同批加开关）｜不做会怎样：① 每轮白跑一次 ~98 s 的相同 pytest；② 同回合想省那趟全套时没有开关，只能改脚本或重复跑｜落点：tools/oneoff/_gatescope.py（input_signature 的 pytest 分支 ＋ 自测）· tools/mut/_mut_{tail04_pages,tail04,tail35,rules,m7w,m14,m09}.py（开关）｜阶段 / 时机：随时｜**排期四问**（`§14.3` 同源）：①规模：只动签名范围与一个开关，不新增检查 ②要改：实测同回合重复跑（98 s×2）＋ 6 支脚本没有跳过手段 ③改哪层：签名在 _gatescope.input_signature、开关在脚本自身 ④做完＝自测三向（产物变可复用 · 代码变必重跑）＋ 实测同一轮第二次打「复用」＋ 6 支各跑一次带开关
