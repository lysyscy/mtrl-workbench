# 夜间前端优化：验收记录

本文件是本轮唯一任务记录。产品实现、目标回归、最终集成核对与资源收尾已完成，8065保持最终版本供验收；北京时间2026-10-29 09:00的人类验收尚未发生。历史检查点按Git追溯，原始证据保留失败与负面样本。

## 当前成果与入口

- 工作树：`D:/UserData/Documents/Codex/2026-10-29/task/mtrl-workbench`；分支 `codex/night-ui-20261029`。
- 产品提交：`bd0ff843ab2835621ed4485fc26fcca85e2982d8`；性能复核后恢复构建 `work/build-21-restored`，全部资源SHA与核准build19完全一致，产品未再修改。后续仅文档提交。
- 验收入口：http://127.0.0.1:8065/preview 。账号 `preview-admin`，空密码；最终恢复默认主题、1.12字号。
- 当前PID `13340`，schema及正常CLI进程事实归 `reports/real_owner.json`、固定快照 `owner-build-21-restored.json`；数据库 `mtrl_workbench_test`，可丢弃真实副本，i8关闭。
- 产品摘要 `20fb586438cd485cb3f770755b1cfd5c480789c57cb861495d7495d68c4a2335`。实际进程、版本、源与构建哈希经 `registered_preview()` 核对；运行事实归 `reports/real_owner.json`，固定快照 `owner-build19.json`、`version-build19.json`。
- 证据根 `.artifacts/active/night-ui/20261029-01/`；下文reports、logs、screenshots均相对此根。

## 目标、协调与授权

用户要求用已安装Impeccable全面优化密集业务工作台，增加性能重点，保持今日功能和金额/保存/撤销/选择/搜索/打印语义。使用Impeccable4.8.0及frontend-design，按真实audit、operate、adapt、harden、clarify、optimize参考推进；context仅跑一次，未重装或改启用项。

主库 `D:/dev/mtrl-workbench` 产品基线 `54b8a21bab43cfd8fc7dc75ea2525c5c3846b320`。原任务 **梳理机械费工作台改进方案**（`01a182d3-54ae-75a1-b2f6-a44a32838fa2`）通过支持接口完成交涉，原任务自己用CLI停止PID8224、释放8065及旧schema，本任务才接手。其最新主线1255a7cd对54b8仅有交接证据文档差异，无新增产品；机械修改在核最新成果后实施，未覆盖脏改动。证据 `reports/preview-handoff.json`。

用户21:21 UTC明确“允许使用8065”；此前缺授权拒绝已解决。曾拒绝的file:诊断未执行，未换端口/协议、改锁/owner绕过。拒绝原文在 `reports/access-blockers.json`，不是当前阻塞。父任务 `01a172cb-a3c9-7230-8b62-ffe44fed30cc`，执行任务 `01a1834f-00fc-73c1-ab3c-5fb593266025`。

只做隔离验收、本地提交；未推送/合并/部署或改8000。正式 `mtrl_workbench.public` 仅由既有复制流程必要读取，未写真实业务；未登录/抓取i8或物理打印。本次限制优先于一般自动推送规则。

## 已完成批次

| 提交 | 结果 |
|---|---|
| `977de0fe` | 共享弹窗外壳不截正文，正文独立滚动；期间面板按字号缩放；项目选择区可收缩。 |
| `0a38c8b3` | 通知书长结果与列表有界、操作区可达；标签/来源/历史字号；大表、规则、用户工具、首页密度；恢复列宽统一SVG；预览与未知路由反馈。 |
| `052c3715` | 当时离线检查点，当前状态由本文件取代。 |
| `1e6abaf5` | 项目页lazy减少首页提前加载；金额测宽计入内边距；表格发布后核实际列宽、处理滚动条导致的变化再规划；列跨度宽度索引查找；库存数值去重测宽、原生文本替代逐格React文本组件。保换行及手工列宽策略。 |
| `c1de491c` | 机械车牌规则/显示项目真实草稿保护；有效值比较避免误报；取消/关闭/切页保留；未知、过期、不匹配回执不清稿不重复写；明确重读仅认可匹配当前输入的结果。 |
| `4d78238f` | 按页React错误边界保导航/其他保活页，显式重载消费既有保护；期间Popover用AntD原生bottom移位；通知书名称按真实renderer测行高；过程合计标签可与完整金额分行。 |
| `c532c4b5` | 库存列筛选用React useDeferredValue优先反馈输入，明确筛选状态；旧结果暂禁调整；操作状态仅在已提交layout effect发布。无固定延时、新请求、缓存层、依赖或业务计算变化。 |
| `bd0ff843` | 修复最大字号缩回后自动列宽残留。等AG Grid加载新列定义后复用原生列状态恢复与测宽，再应用已存手工宽度；保排序、列序、显示/固定、筛选和勾选，不把API改宽记成拖拽。 |

机械明细自动保存、队列、金额、零值、未知和撤销链保持原任务成果，未重写工作事项抓取/录入。显示项目比较有效勾选顺序；未选项目移位、往返勾选、规则空白/重复词不误报弃稿。后台读取不重置草稿基线，暂停弹层仍参加全局刷新保护。独立只读审查发现的恢复入口、回执、暂停保护、并发render ref问题均已修正。

## 覆盖与实际验证

15页：首页、项目、i8、通知书、欠款、流水、合同、过程、结存、大表、库存、费用、机械、规则、用户。检查导航/保活、金额与长文、滚动、字号、加载/空态/错误和弹层；不声称穷举全部业务状态或35类弹层组合。

最终build19三组代表条件共45/45内容完整，页面水平溢出0、所测单元格裁切0。三组为1280×800/1.12默认、1024×768/1.4默认、800×650/1.4深色+reduced-motion。必要表格内部横滚保留，原探针对此仍标overflow，不能称45样本均strict ready。证据 `reports/responsive-build19.json`，全部稳定前快照亦保留。最终1920×1080/1.12桌面15/15 strict ready，`reports/layout-build19-1920.json`。

最终IAB实际重载build19，登录测试账号，付款流水页1.12→1.4→1.12后返回保活通知书；日期列112px、编码160.156px，内部横滚available=total=1722，手工新增按钮恢复可用。`reports/cua-final19.json`与稳定截图 `screenshots/build19-notices-cua.png`。浏览器已恢复默认1280×720视口、默认主题1.12、停在首页并标记交付；未留强制测试视口。

build17此前桌面15/15 strict ready；小窗口矩阵首次43/45，付款流水两项在字号变化后短暂再准备。真实UI确认busy解除；定向复核两项均通过，分别记录pending→overflow、无裁切，非产品修复。`reports/responsive-build17.json` 与 `flow-responsive-build17-followup.json`。最终采样器在有限次数内等稳定，完整45样本且无错误才判通过，不丢弃原始未通过记录。

build14在800×650/1.4/深色/reduced-motion额外12类弹层实际打开/鼠标取消通过：手工项目、通知抓取配置、自动关联合同配置、欠款汇总/月报导出、过程导出、结存导出、库存抓取及原生月份浮层、库存调整、机械i6历史、用户新增、规则新增。未触发外部抓取或业务写入。`reports/dialog-coverage-build-14.json` 和 `screenshots/build-14-800-dialog-*.jpg`。显示项目、关键词、期间、规则另随响应式矩阵核对；实际减弱动画为none/0s，正文与取消可达。

| 实际版本/目标 | 真实执行 |
|---|---|
| build04，初始15个不同浏览器目标 | 14pass；1个在测试体前因pytest临时目录ACL出错，使用本run basetemp仅重跑export后1pass。`browser-targets-01.log`、`browser-export-02.log`，目标清单 `reports/browser-targets-01.json`。 |
| build09，库存3/列宽4/preview3 | 10passed/107.86s，`browser-regression-03.log`。部分列宽与前批重复，不累加成25个独立节点。 |
| build11，机械/摘要/资源失败 | 机械摘要8pass；lazy2仅因探针选错busy包装层失败，改为实际“项目列表”region后仅重跑2pass/12.10s。失败日志保留，产品未为探针修改。`browser-mechanical-02.log`、`browser-loading-03.log`。 |
| build12，窄布局影响面 | 10passed/80.43s，过程原始/调整合计与表头、通知付款草稿和首次鼠标选值、列宽持久/重置/账号隔离、首次字号。`browser-final-targets-04.log`。 |
| build13，机械未知回执 | lost/stale/mismatch三项3passed/33.45s，含重读失败与恢复。`browser-settings-05.log`。 |
| build13，通知关联合同 | 两步选择、丢hint回执读回、关联/解除、长列表选择和页脚2passed/24.60s；本地匹配，无i8。`browser-association-06.log`。 |
| build16，最终库存产品源 | 3passed/63.77s：连续改词最终结果及零HTTP重读；调整保存读回撤销；长表范围、切页锚点、手工列宽。`browser-inventory-07.log`。build17产品源/构建文件等价，提交元数据变化有版本证据。 |
| build18，字号/列宽 | 4个原目标通过；新增字号目标起初因1px阈值失败，实测差160.156→159.031px，手工147→147px；修正为2px自动测宽容差并补保活切页，单独重跑1passed/15.92s。旧版真实残留198.797px的失败保留。`browser-widths-08.log`、`browser-scale-before.log`、`browser-scale-diagnostic.log`、`browser-scale-after.log`。 |

日志位于logs。早期现有Node单测11/11pass。最终构建/类型检查和正常产品提交钩子通过；build19日志 `build19-build.log`、`build19-typecheck.log`。Impeccable全src扫描exit0/[]，后续机械文案、库存、列宽分别目标扫描exit0/[]；这是源码检测，不是完整浏览器可访问性认证。8套主题184对静态文本token对比≥4.5:1，仅静态证据。独立重点源码复核与实际回归分开，未冒称最终全量双轴重审；最后原生列状态复核归 `reports/scale-width-review.json`。

build12的1280×800项目页曾一次首入行高裁切，随后3个新context、3次实际字号1→1.12切换及build14最终矩阵未复现。原因未确认，未添加猜测修复。保留 `reports/responsive-build12.json`、`project-geometry-build12.json`、`project-scale-transition-build12.json`。

资源失败实测：原项目JS失败导致root/nav清空；改后保加载等待、错误反馈、导航和其他机械草稿。显式重载先被既有草稿保护阻止，明确放弃后才重载成功。

## 性能与来源

统一派生汇总 `reports/performance-comparison.json`，逐样本原始JSON同留。本机Chromium156，无CPU/网络节流；真实副本只读交互，非冻结DB基准、现场INP、Lighthouse TBT或React渲染次数。复制的tables/omitted/sequences/ledger指纹一致，正负样本均保留。

- 首页JS：build06为533236压缩响应体字节，最终build19为233014，减少56.30%。各3个新context、1920×1080、字号1；ready原样本[890.89,854.15,898.84]ms，最终[845.09,1192.54,906.49]ms，中位890.89→906.49ms，不能称整体首屏变快。最终长任务[69,76,74]ms也未改善；37个字体文件967892字节未改。首次项目1332.91ms对旧1024ms有lazy延后成本，温热切页另在原始JSON记录。`reports/performance-final19-route-load.json`。build14/17中间样本均保留，没有挑最快的一组作为最终结论。
- 库存结构调整build07→09：18287行/1.12，恢复全部行中位1935.83→1943.82ms，输入到rAF中位68.8→75.25ms；滚动帧中位50.8→44.5ms，最大85.6→120.1ms。结构简化没有整体提速结论。
- 最后一批build14→16：同浏览器/1920×1080/1.12/18287行、三轮温热筛选。输入事件到下一rAF中位68.95→24.10ms，最大161.4→65.9ms；恢复全部行中位1782.06→1925.03ms；滚动帧中位37.10→39.55ms、最大111.3→85.8ms。保留输入优先，结果准备仍慢；逐词全量核行数、HTTP重读0。首次after误用字号1的原记录保留且排除，匹配1.12后复测。不当成端到端输入延迟或现场INP。
- 最终build19再按完全相同条件复测：输入到rAF中位24.45ms、最大34.8ms；恢复全部行中位2179.93ms；脚本滚动帧中位50.35ms、最大87.6ms。与前测68.95/161.4ms相比输入反馈改善，但全量准备1782.06→2179.93ms、滚动中位37.10→50.35ms更慢；不能称库存整体提速。逐词行数核对、HTTP重读0、复制指纹一致。原始 `inventory-input-final-build19.json`；较好与较差结果同列，三轮样本不能推导现场性能保证。
- DOM/表格准备和字体初载仍可后续调查；收尾未引新调度器、缓存系统或盲删字体。

### 08:44补充：有界A/B/A性能归因

父任务要求08:50前复核退步，执行当前版A1→仅关闭useDeferredValue的B→恢复同核准资源A2。每阶段3个新context，各预热1轮后测6轮：18次恢复全量、72个输入帧样本、9段各60帧滚动。原三轮与失败记录均保留，不挑最快结果。每context内循环/帧有相关性，不能当成完全独立大样本。

| 阶段 | 恢复全量中位[范围]ms，n18 | 输入到rAF中位[范围]ms，n72 | 9段滚动中位数的中位[范围]ms |
|---|---|---|---|
| A1核准版 | 1998.15 [1827.91,2082.32] | 20.20 [15.30,77.90] | 45.60 [43.25,52.55] |
| B仅关闭输入延后 | 1195.76 [1109.87,1295.55] | 39.40 [23.60,101.20] | 26.75 [25.50,29.85] |
| A2恢复核准版 | 1342.78 [1229.69,1660.09] | 16.15 [11.70,58.20] | 29.00 [26.80,31.60] |

9个context的18287行数据SHA一致，列宽、总滚动高度1000106px、客户区高度780px一致；1.12字号、61个字体文件/6612968响应体字节在各计时段前后均不变，字体loaded，额外库存HTTP读取0，计时中无截图。首轮与后续滚动分开记录，未呈现足以解释全部差异的一致预热趋势。全系统CPU区间A1为38.20–40.32%，B24.21–27.95%，A2 29.23–33.21%；它包含浏览器自身工作，不能据此确定后台进程原因，旧样本也未记录CPU。

**结论：保留核准版本，无产品回退。** 同一核准代码A1→A2有显著时段差异，原1.78→2.18s的三样本比较不足以证明稳定版本退步。B吞吐更好但输入反馈更慢；调度可能有代价，净收益尚未在受控负载下确认，不能硬称回归不存在或整体提速。14→19的库存原生文本与行高规划代码未变化，因此不能把这一晚期差异直接归因给它们；相对更早React文本组件的绝对成本未独立二分，不回退已修正确性。B只是调度消融，并非完整历史build14。

性能目标仍未全部达成。后续票项：用现有Profiler及表格layoutTiming拆解全量行高/列宽准备、重复提交和React/AG Grid调度；以多context分布验证恢复全量与滚动，同时保持完整文本/金额、18287行范围、手工列宽/锚点、零HTTP本地过滤和输入反馈。库存全量冷入字体6.6MB另行调查，不能删字体破坏行高。

原始与四分位数：`reports/performance-followup-summary.json`、`inventory-repeats-a1-final19.json`、`inventory-repeats-b-no-deferred.json`、`inventory-repeats-a2-restored.json`；协议 `performance-followup-protocol.json`。临时库存源码已逐字节恢复，build21的全部构建文件与build19相同，B已正常CLI退出；未给用户留下对照版。

成熟来源：[React lazy](https://react.dev/reference/react/lazy)、[useDeferredValue](https://react.dev/reference/react/useDeferredValue)、[错误边界](https://react.dev/reference/react/Component#catching-rendering-errors-with-an-error-boundary)、[AG Grid React引用](https://www.ag-grid.com/react-data-grid/react-hooks/)、[AG Grid原生单元格/滚动](https://www.ag-grid.com/react-data-grid/scrolling-performance/)、[AG Grid初始与有状态列定义](https://www.ag-grid.com/javascript-data-grid/column-updating-definitions/)、[部分列状态](https://www.ag-grid.com/javascript-data-grid/column-state/)、[AntD定位FAQ](https://ant.design/components/tooltip/#faq)。Context7及GitHub reactjs/react.dev原文作适配参考；本地AntD6.6.7源码核实shift能力，AG Grid36.2.0源码核实事件顺序。未执行外部脚本。

## 鼠标口径、边界与资源退出

Hindsight正常只读recall：bank `project-3379fef93fbada35`，doc `mtrl-workbench-mouse-first-interaction-20261027`，来源线程 `01a17c2a-1c9e-72f0-b414-4eef7a72dbaf`；主人 `docs/guides/frontend-design.md#操作方式（用户2026-10-27确认）`。事实ID `e63fd1f7-fe2d-4598-8cb7-c799657e0dba`、`ea2f35b1-2769-4048-b412-46317b49c04c`、`818945eb-286c-4ddf-a7e0-da802e556c88`：鼠标及普通输入优先；不做全局快捷键、Tab跨格/跨行、方向选择、独立键盘模式和专项验收；保IME、普通输入/复制粘贴、组件原生能力及保存/异步回执/撤销保护。用户21:50 UTC再次确认。未写改记忆；`reports/memory-scope-check.json`。

未穷举全部弹层状态、主题、浏览器及数据；工作事项/发现录入更多草稿边界只做源码审查，未改造；i8外部动作、真实打印、正式切换不在执行范围。当前无审批阻塞，人类审美和业务验收待09:00。

自有旧构建、完成的pytest临时目录和运行脚本按生命周期释放，性能复核后work仅留当前8065所需build21-restored，依赖与工作树保供用户验收。必要测量方法压缩保留 `reports/measurement-methods.zip`；失败、原始指标、照片有限保留在本次验收run。生命周期明细 `reports/resource-lifecycle.json`。原最终workspace_check在active阶段exit0，`reports/workspace-check-final.json`；补测收尾检查另归 `workspace-check-followup.json`。run仍active，不虚报closed。验收结束由持有任务用原CLI `frontend_preview.py --stop` 正常停服清schema，再将必要证据有限归档/退出active；不能因回复结束停预览。

原主库.tmp-fees-width.py、主库debug.log和本工作树既有debug.log均未主动编辑、暂存或删除。主库日志SHA保持不变，主库Git仍只有原有两项未跟踪文件。本工作树日志在工具运行期间追加了Chromium GPU shared_image_manager.cc格式诊断，原9900字节前缀SHA仍完全一致，完整文件保留；最初创建者和具体写入进程归属未核定，不冒称整个文件字节未变。初始来源 `reports/protected-debug-provenance.json`，最终快照 `reports/protected-files-final.json`。本分支提交后tracked工作树干净，保留这一已知未跟踪debug.log。

补测后IAB现有tab2续绑失败：browser.user is unavailable，未执行页面操作或续标记。服务本身已由正常HTTP/进程哈希和A2三context实际页面操作验证；可直接打开8065链接，不能冒称本turn已续标记。详情browser-handoff-followup.json。
