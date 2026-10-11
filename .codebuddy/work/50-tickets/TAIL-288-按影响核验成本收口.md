# TAIL-288: 按影响核验的两处成本收口：pytest 回执签名排除产物目录、六支变异脚本加 --no-full-suite

**What to build:** 按影响核验的两处成本收口：pytest 回执签名排除产物目录、六支变异脚本加 --no-full-suite

**Blocked by:** 无前置；⚠️ 改签名属放宽闸门，必须同时给自测三向并与 6 支开关同批自证

**Status:** done

- [x] ① `_gatescope.input_signature` 的 pytest 分支把**产物目录**排除出签名（`.codebuddy/work/00-scratch/` 与 `backend/.codebuddy/`）—— 理由同 `artifacts/`：**产物不该触发自己**。判据 = 自测三向：产物变 ⇒ **可复用**；`backend/app/**` / `backend/tests/**` / `tools/**` 变 ⇒ **必重跑**；环境变 ⇒ 必重跑。
- [x] ① 实测：同一轮内**第二次**跑按影响入口时，`pytest（隔离结果）` 打「复用 …」且总墙钟显著下降（本轮基线：**98 s/次**）。
- [x] ③ 另 6 支带"重跑全套"的变异脚本加 `--no-full-suite`（`_mut_tail04_pages` 已有）：**默认行为不变**（不带开关照旧跑全套；权威四态是否写入取决于显式结果出口）。
- [x] ③ 每支用 `--no-full-suite` 跑通一次：打印"跳过全套 … 本轮不刷新权威四态"，且 rc 仍由命中数 / MD5 复原决定。
- [x] ⛔ 边界写清：跳过即"本轮**不刷新权威四态**"，票面与 Comments 不得宣称刷新过。
- [x] 收尾：`_run_rulers.py --paths <改动件>` rc=0 / `BAD: []`；`tools/oneoff/_gatescope.py --selftest` rc=0。

---

## Comments

**2026-10-11 · 建票（agent）。** 来源：2026-10-11 /retro 落地时的实测与遗留（同回合 pytest 复用不了；另 6 支带全套的变异脚本未同批加开关）｜不做会怎样：① 每轮白跑一次 ~98 s 的相同 pytest；② 同回合想省那趟全套时没有开关，只能改脚本或重复跑｜落点：tools/oneoff/_gatescope.py（input_signature 的 pytest 分支 ＋ 自测）· tools/mut/_mut_{tail04_pages,tail04,tail35,rules,m7w,m14,m09}.py（开关）｜阶段 / 时机：随时｜**排期四问**（`§14.3` 同源）：①规模：只动签名范围与一个开关，不新增检查 ②要改：实测同回合重复跑（98 s×2）＋ 6 支脚本没有跳过手段 ③改哪层：签名在 _gatescope.input_signature、开关在脚本自身 ④做完＝自测三向（产物变可复用 · 代码变必重跑）＋ 实测同一轮第二次打「复用」＋ 6 支各跑一次带开关


**2026-10-11 · 实施与用户追加范围（agent，未提交）。** 开工 HEAD `7c630b768e9e2c8c2c07176ff8eb2a49f9c8f903`；八个目标文件与附审查报告基线无差异，已有 `backend/.codebuddy/` 保留。pytest 签名仅新增排除该产物目录；scratch 已由 inventory 排除，未重复改。既有 selftest 验证产物可复用、代码/测试/工具/环境/参数变化必重跑，并加一条移除新排除就必红的隔离反例。六支新增显式开关，默认完整复原态 pytest 参数保持；权威四态是否写入取决于显式结果出口，已订正票面。

首次六支全部因旧锚点 SKIP 返回 1；另发现 MOD-07 一个目标名已不存在（pytest rc=5 被旧脚本误计命中），特殊费用一个旧变异破坏括号配平。用户本会话明确追加“扩大当前票范围，修复旧锚点并验证相关业务判据”。同票修正旧落点、唯一锚点、退役入口与目标名；特殊费用变异改成合法表达式。收发结存失败回执原断言被其他端点满足，配置表原断言看不到 TBL 派生标记：两个隔离错误输入修前均绿、修后均 AssertionError；只修这两个现有判据，不新增检测工具/判据点，不改业务实现/页面/数据库，不混做 TAIL-289。

**2026-10-11 · 核验落账。** 命令与结果：

- `backend/.venv/Scripts/python.exe -X utf8 tools/oneoff/_gatescope.py --selftest` rc=0；按影响 A 轮再次选中自测 rc=0（23.03s），机制隔离反向自证 rc=0（197.53s）。
- `backend/.venv/Scripts/python.exe -X utf8 tools/oneoff/_run_rulers.py --since .codebuddy/work/00-scratch/tmp-20261011-tail288-entry.json` 同输入 A/B 均 rc=0、BAD 空：270.45s → 27.09s，B 明确复用 pytest（A 的 6 件测试 11.13s）及机制反向自证。省时包括复用长反向自证，不能宣称只省了 pytest 243s。
- 两个调整后的测试文件直接 pytest：17 条通过；追加修复的按影响选集 35 件测试 rc=0（34.68s）。初次 repair 入口因覆盖台账未同步 rc=1；原生成器重生成后 `mut_cover.py --check` rc=0，repair-fixed 入口 rc=0、BAD 空（5.92s），复用输入未变的 pytest。
- 六支在专用副本串行调用自身 `main()`，传 `--no-full-suite`、真实 pytest 子进程、测试库；移除外部 ACC_RESULTS_PATH。每支正常目标选集先绿；最终全部目标退出码为 1（已检查断言/预期拒绝失败，非未收集或环境失败），命中数见表。逐支全部 app 文件 MD5 一致，正式权威四态逐字节未变。详证 `.codebuddy/work/00-scratch/tmp-20261011-tail288-fixed-verification.json` 与 `.codebuddy/work/00-scratch/tmp-20261011-tail288-fixed-six.log`。

| 脚本 | 命中 | SKIP | 变异运行耗时 |
|---|---|---|---|
| `_mut_tail04.py` | 11/11 | 0 | 75.30s |
| `_mut_tail35.py` | 8/8 | 0 | 51.09s |
| `_mut_rules.py` | 8/8 | 0 | 41.99s |
| `_mut_m7w.py` | 15/15 | 0 | 72.25s |
| `_mut_m14.py` | 14/14 | 0 | 70.31s |
| `_mut_m09.py` | 18/18 | 0 | 88.76s |

六支均打印“跳过全套 pytest（--no-full-suite）：本轮不刷新权威四态”，rc=0。六支复验变异部分合计 399.70s；从开工快照到落账约 1139s（含调查、首轮旧红、修补及重验，串行副本与按影响检查有交叠）。语法编译与字节检查通过；收尾文档核验另留同前缀 close-gates 日志。

**2026-10-11 · 唯一一轮两轴 code-review（基点 HEAD）。** Standards 0 项、Spec 0 项；评审覆盖初始签名/开关/自测改动。用户后来授权的旧锚点及两处判据修补由上述正常/反向实测与差异自查验证，没有追加 review。

**未验边界。** 未跑整套业务 pytest、真机壳自检或默认完整测试分支；本轮不刷新权威四态。六支历史脚本普遍 `returncode != 0` 的旧判定保留，本次实测逐项核对失败性质，未扩建通用执行框架。未改/提交凭据，未提交，生产数据与既有 dirty 原样。

**2026-10-11 · 收尾核验。** 文档按影响入口 rc=0、BAD 空、8.05s；git diff --check 通过。销号工具已同步票状态 done、计划短索引及计数；原行尾保留。

**2026-10-11 · retro 落实（用户授权后提交推送）。** 个人 implement 技能改为按仓库影响核验、复用有效证据，唯一一轮 review 放在范围稳定和相关核验后；批量脚本先在内存确认全部替换再写盘，依赖命令逐项确认退出码；提交/推送遵循用户授权。该技能位于仓库外，只在本机生效。销号工具改为从原字节解码，保留计划和票文件的换行，票写入失败时按原字节回滚计划。临时隔离自证覆盖 CRLF/LF 的干跑、写入、回滚；旧版在 CRLF 写入字节断言失败（rc=1），修后两种换行全部通过（rc=0，约0.7s）。既有 TAIL-288 的业务/变异输入未再改变，复用上述有效结果；无新增永久检测或第二轮 review。

**2026-10-11 · retro 核验。** 按影响入口显式选择销号工具、票与计划，rc=0、BAD 空、23.52s；相关隔离 pytest 50 项通过（10.21s），检查明细见 `00-scratch/tmp-20261011-tail288-retro-gates.log`。用户已明确授权本轮全部工作提交推送，提交钩子仍按正常流程执行。
