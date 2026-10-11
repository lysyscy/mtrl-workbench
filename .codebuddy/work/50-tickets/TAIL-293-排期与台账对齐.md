# TAIL-293: 排期与台账对齐：销号时把 §14.3 的行迁入已办留痕，T6 改判活动、已办与幽灵编号

**What to build:** 排期与台账对齐：销号时把 §14.3 的行迁入已办留痕，T6 改判活动、已办与幽灵编号

**Blocked by:** 无前置；与业务提交分开审，防状态裁决混进代码提交

**Status:** done

- [x] 销号一张票 ⇒ 它在 §14.3 的行自动迁进「已办排期」区，活动区只剩活动票；顶部计数与真源一致
- [x] T6 反例一：活动票在 §14.3 缺行 ⇒ 判红
- [x] T6 反例二：已办票留在活动区（冒充活动）⇒ 判红
- [x] 幽灵编号（虚构票）仍判红；栏位不全 / 状态非受控词照旧判红
- [x] `_tail_open.py` / `_tail_close.py` 先干跑、再在副本上真跑一趟；`doc_audit` 必须修 0
- [x] §14.3 里既有已办行一次迁清，活动票（`TAIL-284` `TAIL-287` `TAIL-290`～`TAIL-293`）不受影响

---

## Comments

**2026-10-11 · 建票（agent）。** 来源：用户 2026-10-11 会话拍定（D 批治理，见 D32）｜不做会怎样：§14.3 继续堆积已办行，接手指南把已办票当成待开工｜落点：tools/oneoff/_tail_close.py 与 _tail_open.py · tools/audit/audit_meta.py 的 check_tail_ledger · .codebuddy/plans/开发计划-主文档.md｜阶段 / 时机：随时（与业务改动分开审）｜**排期四问**（`§14.3` 同源）：①规模：只改销号同步与 T6 的三条判定，不推翻既有七查 ②要改：现十余行已办仍写随时，脚本故意只提醒不改 ③改哪层：销号脚本搬行、T6 判活动区与已办区分离 ④做完＝两条反例见红，活动票排期缺一行必红

**2026-10-11 · 落账（agent）。** 用户确认 A：同份计划建「已办排期（历史）」区（§14.4）；295移出的旧批次只链到当日日志及归档索引，不搬回正文。核实现有§14.3的7行均为活动票，既有已办行已由295迁清，本轮无需再迁旧行。完成销号自动搬原行、开票活动区插行及同源计数；副本开票改为检查副本T6，正式开票仍过doc_audit。T6原七查及票检查保留，区分活动与历史：缺活动行红、已办冒充活动红、两区幽灵编号红；活动误入历史也红。

命令统一前缀：backend\.venv\Scripts\python.exe -X utf8。逐条验收证据：

- `tools/mut/_mut_docaudit.py --tail293`，rc=0（约1.16秒）；隔离副本在 D:/dev/mtrl-workbench/.codebuddy/work/00-scratch/tmp-20261011-tail293-ovfjqq3p，运行后自动清理；完整输出见 `.codebuddy/work/00-scratch/tmp-20261011-tail293-mut.log`。两条指定反例各T6红1：TAIL-284活动缺排期、TAIL-289已办冒充活动；逐例复原主文档MD5均为8f92352d182fc34aa8e4ebb8cb73e860，复原后T6绿。
- 幽灵活动编号与幽灵历史编号各红1；活动误入历史红2；票缺What to build红1、台账只剩2格红2；状态bogus红1。每条在副本上调用真实check_tail_ledger，改回MD5一致且T6绿；票复原MD5为218886e02b291b54eeb4253e87e3d3a3。正常已办历史行不误伤（T6绿）。
- 同一副本上 `_tail_open.py` / `_tail_close.py` 各先干跑rc=0（副本相关件MD5不变），再加--apply真跑rc=0；参数--plan/--closed-index/--tickets均指副本。隔离TAIL-298开票计数8/293，销号7/294，排期原行只出现一次且逐字节移进历史；票done、T6绿。正式仓库没有建立TAIL-298。
- `tools/audit/doc_audit.py`，rc=0，必须修0·疑似49；T6/T4无红。`-m py_compile`四个改动Python件rc=0。按影响入口 `tools/oneoff/_run_rulers.py --paths`（本票7件）明确要求选择audit_meta的隔离自证、未执行检查；已选上述--tail293分支，未跑整支正式件变异。
- 按入口所选检查逐项执行：doc_audit/audit_drift/audit_meta/audit_work/syntax_audit/bytes_guard/claim_audit均rc=0；refs_query --selftest为8/8、_doc_downgrade --selftest为12/12，均rc=0。mut_cover --check初次不一致，按其提示重新生成后rc=0（115件、1条未覆盖登记）；输出与源码无新增未覆盖登记。六个选中测试文件共50项，pytest rc=0（10.33秒），局部结果隔离，未刷新权威四态。各检查日志在同目录tmp-20261011-tail293-*.log。
- 临时核验脚本首次漏继承系统环境，pytest加载时报WinError10106；已修正并只重跑失败项，最终BAD=[]。不是业务失败，未修改后端解决环境问题。

未验边界：本票纯治理，不动delivery/与backend/app/；未跑全套业务pytest、真机壳自检或完整变异套件，不刷新完整权威四态。已有backend/.codebuddy下截图与本票无关，未改未验。旧批次保留原日志/归档落点，未重导回计划；历史疑似及已有未覆盖登记保持真实。未提交；正式销号及最终doc_audit、字节/行尾复核结果在下条追加。

**2026-10-11 · 正式销号及最终核对（agent）。** `_tail_close.py --id 293`干跑rc=0，再加--apply真跑rc=0；§15移除293、票done，两处计数同源为活跃6/已销号294，293排期原行在§14.4恰好一次，其他6张活动票排期与HEAD逐字节一致。销号后doc_audit rc=0，必须修0·疑似49，T6/T4全绿。最终修正副本开票用例号读取，保持与正式T6真源一致；py_compile rc=0，`tools/mut/_mut_docaudit.py --tail293`再次rc=0，完整证据见 `.codebuddy/work/00-scratch/tmp-20261011-tail293-final-mut.log`（收尾后副本主文档复原MD5=d4630ffe623fe84d5f16a3983dd5f3b7）。八个改动件逐件数CRLF与LF，均为CRLF、裸LF=0；git diff --check rc=0，git status无行尾警告。按影响入口待选分支已明确选隔离--tail293；其他检查输入未变的有效结果复用，仅对收尾文档/新增引用及行尾补验。未提交。
