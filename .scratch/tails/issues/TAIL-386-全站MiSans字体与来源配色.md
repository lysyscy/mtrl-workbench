# TAIL-386: 全站接入官方MiSans与剔除来源配色

**What to build:** 全站接入官方MiSans与剔除来源配色

**Blocked by:** None (can start immediately)

**Status:** done

- [x] 全站网页及登录页使用官方原版 MiSans 4.009 的 400/500/600 字重；字体实际字形加载，许可与版权随产品保存。
- [x] 手动剔除蓝色、自动剔除红色，多主题可辨，原规则悬停说明保持。
- [x] 普通／虚拟长表、冻结列、横向滚动、大金额输入和125%字号通过相关回归及看图；金额内容、Excel与业务逻辑不改。
- [x] 真实钩子提交并推送本人私库master，远端完整SHA一致；重启原服务并核新PID、HTTP及字体资源。
- [x] 退出8011临时模型服务和一次性模型、下载及对比素材；保留必要授权与验证证据并通过工作区结束检查。

---

## Comments

**2026-10-21 · 建票（agent）。** 来源：用户2026-10-21确认模型并授权正式接入、推送及重启｜不做会怎样：正式系统字体与来源配色仍未跟随已确认模型｜落点：backend/app/web/fonts、共享主题与壳；证据回本票Comments｜阶段 / 时机：随时｜**排期四问**（`§14.3` 同源）：①独立前端交付②本轮完成覆盖与许可③不影响业务金额④验收后关闭

**2026-10-21 · 恢复与范围。** 原目录master串行接续，不建工作树、不派子代理。起点1ee5024d07066a5fae4e946576dc5614b8f9f251，工作区干净；用户确认MiSans主字库4.009而非Latin4.007，并明确授权验证后提交推送私库master及重启原服务。字体素材三项SHA256逐项一致，原版字节与许可正式归backend/app/web/fonts；正式接入覆盖共享主题、主壳、登录与BASE_CSS页面，机械费独立数字样式一并处理。Excel与打印实现未改。

**2026-10-21 · 初轮验证与修正。** 沙箱TestClient启动在Python socketpair自连接受阻，未到产品断言，已终止本任务受阻进程后在宿主运行。首轮57过／4失败：测试Canvas未应用等宽数字，已改为真实DOM等宽测量；同类列宽Canvas测量同步按最宽数字预算，并让金额输入填满已测列宽，字体加载后复用layoutTables重测。随后61项通过，扩大77项通过；看图发现125%侧栏编号固定46px换行，已将宽度随档位缩放并加不换行保护。输入框经CDP实际字形核对为MiSans-Regular（custom font），不只检查CSS。最终验收另记下文。

**2026-10-21 · 源码验收。** 最终选集为test_web_fonts、test_theme、test_page_shell、test_ui_scale、test_shell_part_routes、test_static_conditional、test_table_layout、test_notice_paste_selection、test_mechanical_workbench_ui、test_tail365_366_ui、test_shell_render、test_visual_financial、test_shell_ui_workflow，共123项。命令为项目Python `-X utf8 -m pytest` 上述文件 `-q -o addopts= --tb=short`，宿主原始结果121通过／2失败（rc=1），未把该整次运行称为通过。两项失败已按事件级反馈归因：集采在pointerdown之前由Playwright额外滚动，动作自身保持203/97；虚拟表先滚动后聚焦的准备与窗口重画竞争，3次带事件记录复跑均通过。测试改为先进入编辑态、在真实pointerdown记录起点，原两轴/勾选断言保留；两组全部10场景随后通过（rc=0，30.92秒）。隔离副本关闭saveTableScroll后同一检查按left 821→0失败，反例检出，正式源码未改。故123项覆盖由有效121项及10项定向复验合并，无全量回归声明。

CDP核对中文、英文、数字、按钮、原生输入框为custom MiSans，400/500/600对应Regular/Medium/Semibold；十套主题含蓝/红标签对比度通过。1440标准、1024/125%、普通30行和虚拟450行，冻结偏移、横滚、长金额111,111,111.11及输入值未截断，已实际看图。语法与字节审计、文档审计必须修0。源码差异未触达Excel、打印模板及业务金额计算；不执行真实付款、恢复剔除、i8抓取或实体打印。原始记录在本机.artifacts的amount-font-preview/production-20261021运行，收尾按下文实际归档位置定位。

**2026-10-21 · 提交推送与运行加载。** 源码提交e1a0056c7373567986ea2ff70fe8b277a43578c4，真实pre-commit的syntax_audit、bytes_guard及凭据文件检查通过；推送本人私库lysyscy/mtrl-workbench master，远端完整SHA一致。按授权经pwsh调用ops/server_ctl.ps1重启，服务Running/Automatic，实际应用PID14924→9604（启动器23352，13:41:14）。原生端口枚举未暴露宿主监听，未据此误报服务失败或再次重启；通过新进程树、/healthz与/app及正式HTTP资源交叉核对。9项页面/脚本/样式/字体/许可资源与源码逐字节一致，正式页面和登录页9处字形为custom MiSans，内置浏览器已刷新看图。正式验收为未登录只读页面与资源，不宣称真实业务操作验收。

**2026-10-21 · 临时现场收尾。** 停止前再次逐项核PID6808/25056的http.server 8011、127.0.0.1与模型work目录，已关闭，8011不可访问；正式健康仍通过。一次性模型、两份字体下载原包、废弃对比截图、诊断脚本/源码副本及活动effort已实际删除。必要授权、原包版本摘要、失败与复验、提交/部署原始回执和选留截图共24件归本机 `.artifacts/archive/amount-font-preview/` 的原run子目录；retention到2026-11-20，工作区检查不会承诺后台定时删除。两run的run-closed与effort closed均ok，原件字体和许可只留正式运行资源；未建新工作树或子代理。当前票沿既有tracker保留，后续只补本次文档收尾提交。
