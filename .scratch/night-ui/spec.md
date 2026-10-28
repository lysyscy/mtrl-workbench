# 夜间前端优化：执行与验收记录

本文件是本轮工作唯一任务记录。检查点 `NUI-20261029-02`，2026-10-28 22:43 UTC。任务继续中，尚未完成早上验收。

## 目标、基线与授权

用户要求使用已安装 Impeccable 全面优化密集业务工作台，截止北京时间 2026-10-29 09:00（UTC01:00）。保持今日功能和审美、金额/保存/撤销/选择/搜索/打印语义，以有证据的收益分批推进。

- 主库最新交接基线：`54b8a21bab43cfd8fc7dc75ea2525c5c3846b320`，`D:/dev/mtrl-workbench`，master。用户原有 `.tmp-fees-width.py`、`debug.log` 不处理。
- 本轮原生 Git worktree：`D:/UserData/Documents/Codex/2026-10-29/task/mtrl-workbench`，分支 `codex/night-ui-20261029`。托管创建接口不支持 durable，使用获批原生 worktree，未重复 clone。
- 父任务 `01a172cb-a3c9-7230-8b62-ffe44fed30cc`；本执行任务 `01a1834f-00fc-73c1-ab3c-5fb593266025`。
- 只在隔离预览及测试副本验证，允许本地提交。禁止正式8000切换、真实业务写入、i8登录/抓取、物理打印、正式迁移、推送/合并/部署。不得覆盖其他任务未提交成果或改锁/伪造owner。
- 采用项目 `docs/guides/frontend-design.md`、预览和验证指南；已读 Impeccable4.8.0、frontend-design，按真实 audit/operate/adapt/harden/clarify/optimize 等参考工作流使用。context仅跑一次；最后一次人工 detector 尚待最终 UI 修改完成后执行。

## 8065交接和当前可查看版本

原任务 **梳理机械费工作台改进方案**，ID `01a182d3-54ae-75a1-b2f6-a44a32838fa2`，确认主库54b8、无后续源码/索引改动。通过官方线程接口发送协调要求、读取其实际回执，交接已发生。

用户21:21 UTC明确“允许使用8065”后，先只读查看原版。原任务以自身正常CLI停止PID8224，exit0；本任务独立核旧进程退出、端口释放及旧测试schema删除，再按正常唯一预览流程启动本轮。未强杀、未篡改锁、未另开端口。证据 `reports/preview-handoff.json`。

- 地址：`http://127.0.0.1:8065/preview`，账号 `preview-admin`，空密码；`preview-user` 为大字号深色预设。
- 当前 **work/build-09**，PID **31092**，schema `frontend_rewrite_397_d1c544124cfa4e46aadca75004dbe4a9`，数据库 `mtrl_workbench_test`，revision `mechauto261028`，disposable=true，synthetic=false，i8=false。
- owner：本run `reports/real_owner.json`。`registered_preview()` 核对进程、HTTP版本、源码/静态资源散列与HTML。构建时Git为052c371加本批未提交源码，owner如实保留该元数据；提交后用产品散列核对当前HEAD，不手工改owner。
- 正常生命周期：`backend/.venv/Scripts/python.exe -B -X utf8 tools/dev/frontend_preview.py --stop`；重新启动使用 `--source-env D:/dev/mtrl-workbench/.env --run .artifacts/active/night-ui/20261029-01 --copy-source --disposable --port 8065`，隐藏后台进程。后续保留当前预览供接续和验收，失去用途时才正常停止。
- 历史8065未获交接拒绝已被新授权解决。历史file协议拒绝未绕过；本轮不再依赖它。原文与执行边界保存在 `reports/access-blockers.json`。当前无审批/访问阻塞。

## 已实现

前两批本地提交 `977de0fe`、`0a38c8b3`，文档检查点 `052c3715`：共享弹窗容器允许子浮层、正文自己滚动；统一弃稿确认实际选择器；日期单字段浮层随字号缩放及视口限高；项目编辑取消不合理最小宽；通知抓取/关联长结果限高和局部sticky；大表来源/历史提示至少12px；规则/用户/项目弹窗内边距和工具栏换行；列宽恢复图标统一SVG；预览标签限preview路径；未知路由友好返回；首页容器约束。无接口/保存业务改写。

本批 build-09，随本检查点本地提交：

1. 修复月度会大表序号过窄和金额最小宽漏算共享内边距/边框，避免完整金额尾数被裁切。
2. 共享行高规划在发布行数据后复核实际显示列宽；滚动条使flex列变窄时废弃旧stamp并重排。实测库存长说明需97.22px而旧行高74px，已修复。单列宽查找改用已有Map，跨列仍保留原语义。独立代码复核建议清空旧prepared，已纳入。
3. 项目页沿既有模块级React.lazy/Suspense模式加载，首页不再提前加载AG Grid及业务表格。
4. 库存金额列先去重原始值再格式化/测宽；纯文本采用AG原生单元格，删除无用React壳组件。明确保留标识列原自动列宽策略，防止原生文本迁移引入22px横向滚动；原长文换行、虚拟化和手动列宽仍保留。
5. 扩展既有库存滚动回归，检查实际原生文本的横纵向溢出。无新增框架或依赖。

外观弹窗原生dialog/Tab方案和新增键盘测试已完整撤回，未计成果。机械三文件至本检查点尚未编辑；已有最小修复建议，后续在已完成交接基线上实施，不改今日自动保存、零值、未知回执和清空最后金额语义。

## 覆盖地图与真实验证

| 页面/区域 | 常规1920×1080、1.12字号 | 已执行交互/待深化 |
|---|---|---|
| 首页 | build09 ready | 真实摘要/失败重试；首载三轮性能 |
| 项目档案 | ready | 行内写入回读、未知结果回执 |
| i8接入层 | ready | 状态只读；未登录/抓取 |
| 付款通知书 | ready | 长结果样式已改，复杂长结果仍待代表性实测 |
| 欠款台账 | ready | 主表；展开及大字号组合待验 |
| 付款流水 | ready | 主表；详情组合待验 |
| 集采台账 | ready | 弃稿保护/关闭继续编辑既有目标回归 |
| 过程资料 | ready | 主表；弹层组合待验 |
| 收发结存与提取 | ready | 主表；弹层组合待验 |
| 月度会大表 | ready | 金额/序号修复，保存不改 |
| 库存单据与调整单 | ready | 3项回归：本地筛选、调整写读/撤销、滚动/锚点/列宽；18287行性能 |
| 特殊费用 | ready | 主表；细节组合待验 |
| 机械费 | ready | 实际复现车牌规则取消即丢稿；尚待修复 |
| 规则配置 | ready | CRUD回归；新版弹窗截图及取消关闭 |
| 用户管理 | ready | 用户与外观持久化回归 |
| 共享外观/历史/弃稿/列宽 | 部分交互通过 | 小窗口、1.4字号、深浅色、reduced-motion代表性组合待验 |

- build00为未修改前基线；04初次15页为13ready、2overflow，不能当当前失败。05大表修复后ready；07及**09最新15/15 ready**，报告 `reports/layout-build09-1920.json`。
- 首批15个浏览器节点真实执行全部通过：14pass，1项因系统pytest临时目录ACL在测试体前报错，改用本run新basetemp单独重跑export后1pass。证据 `reports/browser-targets-01.json`、`logs/browser-targets-01.log`、`browser-export-02.log`。
- **build09最新10项目标浏览器回归全部通过（107.86s，exit0）**：库存3、列宽4、preview真实读取/行内写入未知结果/读取失败重试及过期3；`logs/browser-regression-03.log`。其中列宽4与前批重复，不声称25个唯一测试。
- Node既有单测11/11pass。build09 typecheck/build退出0；AG Grid大块警告仍存在。源码双轴审查仅覆盖54b8..0a38，均0明确发现；本批另作目标复核，未冒称全批双轴完成。
- 8主题184组静态配色对比均>=4.5:1，只是token证据，不是DOM主题矩阵。
- 新版截图：`screenshots/build09-rule-dialog.jpg`，实际1920×1080/1.12，弹窗537.59×416.64、带内边距、取消正常。基线 `baseline-rule-dialog.jpg`，前批 `build04-rule-dialog.jpg`。
- 未把测试收集当执行、其他版本当本分支、抽样当穷举。未增加键盘专项。

## Hindsight口径核实

正常recall只读，未改记忆。项目bank `project-3379fef93fbada35`；doc `mtrl-workbench-mouse-first-interaction-20261027`；来源线程 `01a17c2a-1c9e-72f0-b414-4eef7a72dbaf`，正式规则在 `docs/guides/frontend-design.md#操作方式（用户2026-10-27确认）`。

- fact `e63fd1f7-fe2d-4598-8cb7-c799657e0dba`：鼠标操作＋普通文本输入。
- fact `ea2f35b1-2769-4048-b412-46317b49c04c`：退役自写全局undo/redo快捷键、Tab跨格/跨行、方向键选择和专用键盘焦点模式及其专项验收。
- fact `818945eb-286c-4ddf-a7e0-da802e556c88`：保留IME、基本输入确认/取消、普通选取/复制/粘贴、组件/浏览器默认行为、离格保存及草稿/异步回执/输入位置/撤销重做按钮业务保护。

用户本次21:50 UTC再次明确性能优先、取消Tab专项。证据 `reports/memory-scope-check.json`，不把例外继续列入待验。

## 性能：同条件测量和成熟来源

报告 `reports/performance-comparison.json` 统一原始数据、口径和限制。正常Chrome156，无CPU/网络限速，预览真实副本，仅读取交互。不是现场INP、Lighthouse TBT、React渲染次数或冻结数据库基准。

- 首页3个全新context，1920×1080/字号1：build06→07，JS传输 **533236→232653字节，减少56.37%**，三次一致。ready中位890.89→734.8ms，但after首轮1096.5ms更慢；首次进入项目1024→1388ms承担延迟网格成本。37字体文件约967892字节未改，不能声称全站均加速。
- 库存18287行，同数据副本散列完全匹配，代码/字体热缓存，字号1.12，3轮筛选和60帧大步滚动：build07→09，恢复全部结果中位1935.83→1943.82ms；输入到帧中位68.8→75.25ms、最差168.8→203.5ms；脚本滚动帧中位50.8→44.5ms、最差85.6→120.1ms。**运行指标有升有降，不宣称输入或整体运行性能改善**。筛选结果数量全验、筛选期间额外HTTP读取0。全时段场景原版和新版都有16px内部横向滚动，不计为无溢出通过。
- CPU原样采样见 `reports/cpu-cpu-before.json`，规划/DOM几何/文本测宽主要；未有after CPU对比，不补造结论。没有采用自制调度器、deferred filter、缓存层或新依赖。
- Context7查询官方文档：React模块级lazy/Suspense https://react.dev/reference/react/lazy （GitHub reactjs/react.dev/src/content/reference/react/lazy.md）；AG公共稳定引用 https://www.ag-grid.com/react-data-grid/react-hooks/ ；纯文本免自定义renderer https://www.ag-grid.com/react-data-grid/scrolling-performance/ 。只读参考，不执行外部脚本。

## 接续：按实际收益优先

1. 机械草稿问题已有旧/新源码溯源和真实复现，原任务正常交接完成。最小接入现有MechanicalDialog dirty/requestClose/paused协议，优先车牌规则及项目显示选择；核对工作台编辑再按独立风险处理。不得改金额自动保存与异步结果链。
2. 本分支代表性小窗口、最大1.4字号、深浅主题、reduced-motion实际验收，尤其日期浮层和长结果/弹窗底部操作；遇真实问题再改，避免猜测式宽泛CSS。
3. 性能继续先量后改；库存当前输入收益不足，不能靠中位选择性宣称完成。字体仍近1MB，但500字重用于当前导航，不能直接删预载而破坏字体就绪。
4. 留足最终源码检查、目标测试、正常CLI构建、本地提交和最新预览核对。最终UI修改后执行一次Impeccable detector。当前是阶段成果，非整夜任务结束。

接续先只读核分支/HEAD、owner实际PID及registered_preview、上轮日志/本文件；不重做原交接、记忆检索或已通过且无变更的测试。保留当前8065预览和测试schema。全部日志/截图/临时脚本归本run，artifact不入Git，不清理前人材料。

## 第四批：机械设置草稿与回执保护

原任务最新主库1255a7cd仅更新其交接文档，产品仍54b8，未覆盖其成果。机械规则与显示项目复用已有dirty/requestClose/paused：取消、关闭和往返切页保草稿；比较有效项目顺序和规范化关键词，未选项目位置/空行/重复词不误报。未知、旧版或内容不匹配的设置回执保留输入、禁重复写，弹窗内可显式重读；只有重读内容与当前输入一致才认可已保存，显示选择也同步。后台读取不重置草稿基线。机械工作台仅新增route inactive暂停接线，未改其事项/抓取流程。明细保存队列、金额计算、零值和最后金额清空链保持。

独立只读审查发现的两项设置边界与一项跨页重载保护均已落实。build11目标执行8pass，2项lazy测试只因测试状态选择器指向包装层失败；改为实际“项目列表”region后2pass，产品未因该测试修正再改。10个唯一节点功能断言通过，失败原始日志保留，不声称一次全绿。日志browser-mechanical-02.log、browser-loading-03.log。

补充：未知设置回执后重读仍失败时保持“待核实”，不沿用普通成功写入后的“修改已保存”文案。build13对应lost/stale/mismatch三个目标全部通过（33.45s），包含重读失败、输入保留、禁重复写及再次重读恢复。日志browser-settings-05.log。
