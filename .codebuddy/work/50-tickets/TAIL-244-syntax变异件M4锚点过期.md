# TAIL-244: _mut_syntax.py 的 M4 锚点过期（脚本钉「三条规则都能区分」· 尺子自检结论已改成「四条」）⇒ 该靶恒判未命中（实测 4/5）⇒ 要修锚点并定它归快集还是慢集

**What to build:** _mut_syntax.py 的 M4 锚点过期（脚本钉「三条规则都能区分」· 尺子自检结论已改成「四条」）⇒ 该靶恒判未命中（实测 4/5）⇒ 要修锚点并定它归快集还是慢集

**Blocked by:** 无前置（⚠️ 归类前先量秒数 —— `_run_muts.py` 那两道预算提醒会自己喊；⛔ 不许为消掉提醒去改预算）

**Status:** ready-for-agent

- [ ] （领票时补：怎么算做完 · 要能证伪）

---

## Comments

**2026-10-06 · 建票（agent）。** 来源：TAIL-239 第 2 步实测（2026-10-06）｜不做会怎样：syntax_audit 的内建自检继续休眠（本件 docstring 原话「没有任何地方跑它」）⇒ 它腐化了没人知道 ⇒ 而 syntax_audit 本身就在收工闸门 CMDS 里｜落点：tools/mut/_mut_syntax.py 的 M4 那条 needle · 快/慢归类看 _run_muts.py 的 KEY / SLOW_KEY（它是单一出口）｜阶段 / 时机：随时｜**排期四问**（`§14.3` 同源）：①它是「有一次证明过 ≠ 有守卫」的实例：内建 --selftest 写了、当时能过、此后没人碰 ②成本极小（改一个词 ＋ 量秒数定分层）③同域＝syntax_audit 的反向灵敏度 ④⭐ 它要 node --check ＋ 会动壳件（print-export.js / index.html）⇒ 进闸门比别的重，得想清 shell_verify 盖章那一步
