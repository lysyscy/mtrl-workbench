# TAIL-304: 报告E渲染后加工显式追加并保持重画行为

**What to build:** 报告E渲染后加工显式追加并保持重画行为

**Blocked by:** None (can start immediately)

**Status:** done

- [x] 登记步骤按原顺序各执行一次，局部返回不漏后续步骤。
- [x] 普通/虚拟重画、状态页、引用返回与全选/工具入口保持，相关回归、隔离反向及最终完整壳自检通过并盖章。

---

## Comments

**2026-10-12 · 建票（agent）。** 来源：用户报告E｜不做会怎样：旧值包裹分散并可能漏调用原加工｜落点：backend/app/web/index.html与shell｜阶段 / 时机：随时｜**排期四问**（`§14.3` 同源）：①已有三页多步骤②漏步骤会静默失去交互③列表追加替代旧值包裹④不依赖加载机制改造

**2026-10-12 · 实施与证据（agent）。** 使用ask-matt、improve-codebase-architecture和codebase-design；按AGENTS读取README§〇、主计划§13.6/§15、MEMORY、issue-tracker§四、前端守则§0→§9、IDE§十/十一/十五/十六及工具细则§廿三。加载只读证据由架构skill要求的子agent独立复核；业务取舍无需重新裁定。

- 小interface：index.html:500/501的addBind(view, step)/runBind(view)。登记只追加数组，运行按登记顺序；局部return只结束该步骤，异常仍终止本轮加工，保持旧行为。没有优先级、重复登记守卫、插件生命周期或其他共享机制改造。
- 次数与顺序：m03=基础全选→打印入口→引用返回（3）；m11=基础全选→隐列/钉列/导出→引用返回（3）；m08=摘除朴素导出→引用返回（2）；m04/m15/m06/m09/m02/m01各1，总14步。view.js:130/292两条路径各调用一次；状态页不调用；虚拟滚动只换tbody，不重跑页加工。登记只在脚本求值时发生，不在render中追加。
- 新增5项真实浏览器隔离判据：各页次数与真实函数内容顺序、局部return、状态页、连续重画后按钮不重复、一次全选点击只响应一次、虚拟首画/滚动/重画、m11全选/半选及hide→pin、引用工具撤除。集采隐列动作沿用原行为：render内hide/pin一次，动作之后再各一次重量；本轮未顺带删除这两次调用。
- 原型切片留在index.html，上屏文字不改，11具名函数体及三页共用返回函数体与开工HEAD逐字一致（只排除登记外壳与旧值调用）：`python -X utf8 .codebuddy/work/00-scratch/tmp-E-compare.py` rc=0，证据tmp-E-compare.log。共享读取tools/audit/shell_api.py仅将bind_blocks改取完整addBind语句；其余窗口未改。调用者已查明为测试转发、m02/m03打印判据、工具自身与本轮测试；`python -X utf8 tools/audit/shell_api.py` rc=0，证据tmp-E-api.log。
- 新判据与迁移判据的反向灵敏度：`python -X utf8 tools/mut/_mut_shell_bind.py`，正常放行→18/18指定判据红→复原全绿，证据tmp-E-mut-final.log；只改复制的backend/web与读取工具，不复制凭据，独立结果出口。旧_mut_m7w仅同步m06锚；对应靶已由新隔离入口实跑，未运行其写正式靶的旧入口。mut_cover重新生成（表B既有1条保留，非本轮新缺口）。
- 相关选测：影响入口选择91件，首次810项（807绿、3红），144.91s；3红是漏迁移的旧BIND写法（双路径、库存摘除、m09入口），已保留含义迁移。补修47项rc=0（tmp-E-fixes.log/json），同批补3隔离靶；其余已绿输入未变，逐项追认。最终合并追认证据tmp-E-reused-results.json，共810项有效绿；不是重跑整套pytest，不刷新权威四态。其余相关工程检查rc=0/必须修0，完整初跑输出tmp-E-impact.log保留真实失败，不改写成全绿。
- 最终完整壳自检：`python -X utf8 tools/probe/_shell_smoke.py` rc=0，39/39段、未认领console/page错误0；完整输出tmp-E-final-shell-smoke.log。所有变异已完成且只在隔离副本造靶，随后`python -X utf8 tools/audit/shell_verify.py --snapshot` rc=0，章20261012-1021（tmp-E-stamp.log）。
- 失败补修说明：新虚拟测试的变量名/标记写错已修；m11测试最初漏算旧动作的第二次hide/pin，已按真实旧行为订正；这几项是测试错误，没有借机改滚动或隐列实现。最终相关失败全部修复。
- 未验边界：浏览器交互用隔离数据/API写出口；完整真机沿用既有39段覆盖，不代表所有业务组合、真实打印机、部署/恢复全部验过。缺件/错序只读VM不证明现场用户诊断；静态加载取舍见303。不迁移模块、不扩D/F，无后端运行代码变化、无需重启；开工无已有dirty，不提交、不推送。

**2026-10-12 · 交付。** 两项独立取舍，BIND已实施，加载机制保留；按协议销号。

**2026-10-12 · 收尾核验。** 销号索引追加时多了一空行，T6据此报四条幽灵/缺索引；空行已修，计数使用audit_meta.ledger_counts/audit_common.write_counts重算为活跃2/已销号305。最终文档影响入口rc=0、19项相关回归通过、15.83s、BAD: []（tmp-E-close-check.log）；最终代码字节核验必须修0（tmp-E-bytes-final.log）。完整壳自检日志起止约91s，首次较广回归144.91s；反向入口未单独计时，不据此虚报总耗时。所有结果出口保持隔离，权威四态未刷新。

**2026-10-12 · 双轴code-review与P3补修（基点b89a597，含E未提交差异及新增文件）。** Standards为1条P3、Spec为0条：core.js:988与test_shell_render.py:7沿用旧BIND调用说明，违反issue-tracker§四「改机制同批回扫注释」。已同步为addBind登记、runBind在完整DOM重建后按顺序执行；未改函数体、判据、页面文字或加载机制。定点复核该发现已消除，其余双轴结论保持：14步原顺序/次数、普通与虚拟首画、状态页跳过、虚拟滚动不重跑及集采动作原有第二次hide/pin正确；静态加载取舍有依据，见303。

- 修复证据：一次性编辑脚本tmp-E-P3-fix.py rc=0，core.js剥注释后正文逐字一致，test_shell_render.py除模块说明外AST一致，原行尾保持；py_compile rc=0。首次测试命令因工作目录下解释器相对路径写错未启动用例，改用绝对venv路径后真实运行，未冒充测试通过。
- 实际影响：自动选择的壳源码使用者为90件；本轮仅注释/模块说明变化，运行正文与判据未变，复用上一轮有效相关结果及18隔离靶证据，不重复全部选集或变异。新增定点运行tests/test_shell_render.py与tests/test_shell_bind.py，11项全部通过、rc=0，证据tmp-E-P3-pytest.log及独立tmp-E-P3-pytest-results.json；权威四态未刷新。前轮Spec agent独立复跑新增5项也通过。
- 壳字节变化后重新完成最终完整tools/probe/_shell_smoke.py，rc=0，39/39段、未认领console/page错误0，证据tmp-E-P3-smoke.log；随后shell_verify.py --snapshot rc=0，新章20261012-1043，证据tmp-E-P3-stamp.log。没有后端运行代码变化，无需重启。
- 票保持done，未新开票或重复销号。现状页与E交接段仅同步评审补修；本轮回写最终按影响输出见tmp-E-P3-final-impact.log，提交时运行真实pre-commit钩子。未验边界延续上文：VM不证明现场诊断，39段不代表全部业务组合/真实打印机/部署恢复。本轮用户已授权提交推送，覆盖此前不提交/不推送边界；只提交E，保留并行D，不扩D/F。
