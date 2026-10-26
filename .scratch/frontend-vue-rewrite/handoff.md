# 付款通知书最小视觉收敛接续

<!-- MTRL-HANDOFF-BEGIN PH-20261026-notice-visual-01 -->

## 身份、目标与执行归属

- 编号：`PH-20261026-notice-visual-01`；源对话：`01a1763e-bf61-7882-b934-f4ea8948fd41`；接手对话：未创建。状态：材料已核对，等待人工接续核验。
- 工作目录：`D:/UserData/Documents/Codex/2026-10-22/task/mtrl-workbench`，分支`codex/react-frontend-rewrite`。主检出`D:/dev/mtrl-workbench`只提供独立demo产物，不在master上改React。
- 用户已明确授权下一对话：先修改前端设计文档，再对原8065付款通知书页做最小视觉调整供用户验看，并保留快速回退能力。当前对话只保存材料/交接词；未修改设计规范或产品UI，未新建接手对话。
- 用户要求“不想大改”，吸收独立demo优点。接手只读核实后直接按以下顺序实施，无需重新询问是否可以改源码；此次新授权替代此前“只做独立demo、不改源码”的范围限制，仅扩大到指定文档与付款通知书页。

## 已确认的吸收范围

1. 颜色：整理背景、表面、边框、正文/辅助文字、主操作和状态的层级，吸收Radix色阶角色及对比原则。先在付款通知书页验证，兼容既有账号主题/字号；保成功、危险、类别含义。复用现有颜色主人，不把静态demo的Slate/Teal直接硬编码到全站或重写八套主题。
2. 控件：普通按钮、输入框减少胶囊圆角，统一同组高度、内边距与对齐；采用轻量0.5px边界，减少阴影，类别保紧凑标签。嵌套圆角协调，保完整点击区和键盘焦点。
3. 文字：用正文、辅助、标题三个主要层级和400/500/600字重表达关系，保MiSans与现有字号档位；最小有效字号12px为用户试验要求。先查现有11.5/13.5/18基准及缩放，不机械套demo全局绝对尺寸或顺带改全站密度。
4. 文案：精简重复前缀/解释及过长操作名称，不用中点作界面文案分隔；保必要范围、风险、状态、可访问性名称和业务原始名称。

保原导航/侧栏主题、路由、信息区位置、表格列序/字段、操作入口、业务流程及数据逻辑。当前供应商统一按钮完整保留供应商名、合同关联状态及关联入口，两步弹窗、撤单/剔除后的查看/解除入口及通用弃稿确认保持。可编辑本次付款金额须明显可辨，不能像demo一样弱成普通文字；主操作按真实业务保留，不擅自把付款按钮搬到demo位置。

样板是虚构短数据，不能据它固定64px行高、截断真实长名称、合并或删列。行高仍随完整内容/控件需要，金额与操作可达。此次不新增动画；加载/字体/测宽测高问题归暂停的449，不借视觉改造实施加载链。

## 当前版本与两个不同入口

- 保存本材料前React HEAD：`e2de8da53c5cf69204772f01bd14c93b2830cbc0`，工作树干净。此提交仅补449、更新问题现状和独立试验说明；实际产品最后变更是`efc6f51eebc5eddb0cb24cacb3b1c27fcf8c693b`。
- 真实可写试用：`http://127.0.0.1:8065/preview`，付款通知书`/preview/notices`。同一owner、schema、修订`bmonth261026`；试用数据、私有i8绑定/会话保留。源对话在交接前调用`registered_preview()`核过进程/HTTP/产品输入和完整构建。
- 唯一owner：`.artifacts/active/react-writable-preview/20261025-admin-i8/reports/real_owner.json`。在用构建：同run下`work/project-picker-shell-fix`。主指针：`D:/dev/mtrl-workbench/var/state/react-writable-preview/current.json`。不把当前Git文档HEAD误称8065已加载的产品SHA。
- 静态视觉参考：`http://127.0.0.1:30959/`，12条虚构数据，无脚本、API、业务逻辑。目录`D:/dev/mtrl-workbench/.artifacts/active/notice-visual-trial/20261026/`；`site/index.html`、`work/make_static_demo.py`、`work/radix-palette.json`、`reports/{owner,static-demo,detector,http-checks}.json`，以及`reports/before.png`/`after.png`。before为真实长数据、1761×1191，after为虚构短数据、1280×720，不能作同条件密度/性能对比。
- 30959由本对话创建的静态服务器维持，归属查该目录`reports/owner.json`和`work/serve_static.py`；统一exec session 82190只属源会话，不作为跨会话控制入口。接手核PID/命令/根目录后管理；保留作对照到用户验看结束，再正常退出，仅清本次资源。不要另开第三个预览。
- 原先误写的React试验已全部撤回，产品逐字节匹配8065输入；误写草稿和应用脚本已删除，不得恢复为本次实现。当前前端代码无试验差异。

## 下一步顺序与快速回退

1. **只读核实。** 读本文件、现有AGENTS及`docs/status.md`，核目录/分支/脏改/实际owner和`registered_preview()`；读取必要设计、预览和验证指南及对应源码。保护新出现的并行修改。
2. **先改设计文档。** 修改`docs/guides/frontend-design.md`，明确“通知书页先试点”的最小视觉收敛及范围，解决原药丸圆角/阴影/悬停位移与新试点的冲突；区分可推广原则、当前局部试点与尚未验收，不提前宣布全站完成。保主题角色唯一主人与业务约束。此步完成后接着实施，不额外等一轮批准。
3. **实施前固定回退点。** 核并记录源码基线、拥有文件清单、当前owner/version及完整在用构建，保留`project-picker-shell-fix`原构建和可恢复的文档/源码版本。文档和页样式改动独立保存，给出可实际执行的快速回退入口。回退只撤本次拥有的视觉改动并恢复8065原构建/对应产品输入，按现有预览工具核支持方式；不能仅改owner伪造身份，也不能reset/覆盖无关改动或重拷数据库。必要时为本次小范围提供明确脚本/命令，先核现有CLI能力，不另造服务体系。
4. **只改付款通知书视觉。** 检查现有`apps/frontend/src/notices.tsx`、`notices.css`及实际依赖，尽量局部样式/文案；共用件如必须调整，控制影响范围并核直接调用者。复用AntD/AG Grid，保真实全部内容、金额输入和既有统一关联按钮。不复制静态demo的列合并/短数据布局。
5. **离线构建后更新原8065。** 按`docs/guides/frontend-preview.md`的统一工具及原run做新目录离线构建，必要正常停止/恢复同一试用实例。保留schema和私有状态，不复制/seed/迁移试用库，不新增预览，不碰正式8000/正式库。未涉及后端结构则不升级schema。换装后核实际产品及完整构建。
6. **够用的验看后交给用户。** 复用既有有效证据，运行受影响typecheck/build，浏览器由原根入口到通知书，查看真实长数据、勾选摘要、金额编辑外观和统一关联入口，检查主题/字号的受影响代表状态，不机械跑全矩阵。视觉检查不需要执行付款/抓取等真实外部写入。保存前后截图、可执行回退方式和版本位置，停在用户视觉验看；尚未获得全站推广或加载改造授权。

## 权威资料、暂停项与保护

- 设计主人：`docs/guides/frontend-design.md`；运行及更新：`docs/guides/frontend-preview.md`；检查：`docs/guides/development-and-verification.md`；需求：`docs/requirements/payments.md`和`central-procurement.md`；讨论：`.scratch/frontend-vue-rewrite/questions.md`；当前成果/未验：同目录`evidence.md`；共同范围及合流门：`spec.md`。
- `.scratch/frontend-vue-rewrite/notice-visual-trial.md`记录独立demo范围/来源。Radix官方一手来源及MIT、MiSans许可在该文档和独立site内。demo源码detector空结果、字体12/14/18三档和HTTP隔离已查，不替代产品界面或449性能通过。
- `.scratch/tails/issues/TAIL-449-全站加载与表格尺寸稳定统一.md`已补首帧主题/CSS、尺寸覆盖主人及密集表宽度事项，仍暂停，ready-for-agent不是恢复授权。
- 前序MOD05拆页、关联弹窗/弃稿确认、多选隐藏小微壳已实现并加载8065，不重做Q1/Q2或既有grilling。445–448仍按原票待用户验看；之后原真实试用、双方版本合流、最终候选及423/424流程沿spec/evidence，未在本次完成。
- 合并master、正式切换/部署、正式迁移、真实i8新外呼/物理打印等仍守原授权边界。本次不推送公共远端；先前涉及非公开业务资料的公开推送未获确认，不能将普通仓库推送授权当成新增披露批准。
- 主检出`D:/dev/mtrl-workbench`已有无关脏`docs/agents/issue-tracker.md`、`docs/status.md`和未知`--full-page`，保持；其他项目/My-Skills不并入本任务。凭据不写交接，不打印owner私有账号字段。
- 旧交接`PH-20261026-react-trial-01`已由本编号接续；旧正文可从`e2de8da5`的本路径恢复，历史完成/未验的详细证据仍在原主人。

<!-- MTRL-HANDOFF-END PH-20261026-notice-visual-01 -->
