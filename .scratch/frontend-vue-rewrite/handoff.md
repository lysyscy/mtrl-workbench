# 付款通知书最小视觉收敛接续

<!-- MTRL-HANDOFF-BEGIN PH-20261026-notice-visual-01 -->

## 身份、目标与执行归属

- 编号：`PH-20261026-notice-visual-01`；源对话：`01a1763e-bf61-7882-b934-f4ea8948fd41`；接手对话：本次人工恢复会话（宿主编号未查询）。状态：已接手、已实施并加载原8065，等待用户视觉确认。
- 工作目录：`D:/UserData/Documents/Codex/2026-10-22/task/mtrl-workbench`，分支`codex/react-frontend-rewrite`。主检出`D:/dev/mtrl-workbench`只提供独立demo产物，不在master上改React。
- 用户已明确授权先修改前端设计文档，再对原8065付款通知书页做最小视觉调整并保留快速回退。两步现已实施；技术验看完成，未代用户确认，不推进全站或449。
- 用户要求“不想大改”，吸收独立demo优点。接手只读核实后直接按以下顺序实施，无需重新询问是否可以改源码；此次新授权替代此前“只做独立demo、不改源码”的范围限制，仅扩大到指定文档与付款通知书页。

## 已确认的吸收范围

1. 颜色：整理背景、表面、边框、正文/辅助文字、主操作和状态的层级，吸收Radix色阶角色及对比原则。先在付款通知书页验证，兼容既有账号主题/字号；保成功、危险、类别含义。复用现有颜色主人，不把静态demo的Slate/Teal直接硬编码到全站或重写八套主题。
2. 控件：普通按钮、输入框减少胶囊圆角，统一同组高度、内边距与对齐；采用轻量0.5px边界，减少阴影，类别保紧凑标签。嵌套圆角协调，保完整点击区和键盘焦点。
3. 文字：用正文、辅助、标题三个主要层级和400/500/600字重表达关系，保MiSans与现有字号档位；最小有效字号12px为用户试验要求。先查现有11.5/13.5/18基准及缩放，不机械套demo全局绝对尺寸或顺带改全站密度。
4. 文案：精简重复前缀/解释及过长操作名称，不用中点作界面文案分隔；保必要范围、风险、状态、可访问性名称和业务原始名称。

保原导航/侧栏主题、路由、信息区位置、表格列序/字段、操作入口、业务流程及数据逻辑。当前供应商统一按钮完整保留供应商名、合同关联状态及关联入口，两步弹窗、撤单/剔除后的查看/解除入口及通用弃稿确认保持。可编辑本次付款金额须明显可辨，不能像demo一样弱成普通文字；主操作按真实业务保留，不擅自把付款按钮搬到demo位置。

样板是虚构短数据，不能据它固定64px行高、截断真实长名称、合并或删列。行高仍随完整内容/控件需要，金额与操作可达。此次不新增动画；加载/字体/测宽测高问题归暂停的449，不借视觉改造实施加载链。

## 当前版本与两个不同入口

- 恢复时源码基线：`18842da8e5bd64162cf103d437cf49c6b39b6546`，工作树干净，比原材料的e2de8da5仅多交接文档提交。文档提交`193b8b97`；页面提交`17340172`及金额强调修正`e9e47fe4`。8065当前产品源码为`e9e47fe4388c6b827934f374e2764cff5141d514`；后续纯文档HEAD不冒充在用产品SHA。
- 真实可写试用：`http://127.0.0.1:8065/preview`，付款通知书`/preview/notices`。同一owner、schema、修订`bmonth261026`；试用数据、私有i8绑定/会话保留。本次换装后已调用`registered_preview()`核进程/HTTP/产品输入与完整构建。37张非账号表摘要一致；账号表含本地登录/外观验证变化，原中性浅色、标准字号已在界面恢复并回读。
- 唯一owner：`.artifacts/active/react-writable-preview/20261025-admin-i8/reports/real_owner.json`。在用构建：同run下`work/notice-visual-20261026-final`；原`work/project-picker-shell-fix`完整保留作回退。主指针：`D:/dev/mtrl-workbench/var/state/react-writable-preview/current.json`。不把当前Git文档HEAD误称8065已加载的产品SHA。
- 静态视觉参考：`http://127.0.0.1:30959/`，12条虚构数据，无脚本、API、业务逻辑。目录`D:/dev/mtrl-workbench/.artifacts/active/notice-visual-trial/20261026/`；`site/index.html`、`work/make_static_demo.py`、`work/radix-palette.json`、`reports/{owner,static-demo,detector,http-checks}.json`，以及`reports/before.png`/`after.png`。before为真实长数据、1761×1191，after为虚构短数据、1280×720，不能作同条件密度/性能对比。
- 30959由源对话创建的静态服务器维持，归属查该目录`reports/owner.json`和`work/serve_static.py`；统一exec session 82190只属源会话，不作为跨会话控制入口。接手核PID/命令/根目录后管理；保留作对照到用户验看结束，再正常退出，仅清本次资源。不要另开第三个预览。
- 原先误写的React试验已全部撤回，产品逐字节匹配8065输入；误写草稿和应用脚本已删除，不得恢复为本次实现。本次仅在此后新增获批的局部样式/文案，不恢复旧误写草稿。

## 当前验看与快速回退

- 先看原入口`http://127.0.0.1:8065/preview/notices`；下一步只等待用户判断局部视觉是否接受，再按其反馈继续。导航、列序、所有入口、关联两步状态机和业务数据逻辑未改；不执行真实付款/关联保存/i8外呼。
- 细节、实际覆盖、首轮旧工具链警告、最终指定工具链通过及目录检查非零项，均回[当前证据](evidence.md#通知书页最小视觉试点)。不把技术检查当人工验收。
- 原run的`recovery/notice-visual-20261026/`保存`baseline.json`、原`version.json`、三份拥有文件、38表修改前摘要与`rollback-notice-visual.py`。退出条件：用户接受且明确关闭回退窗口，或已回退并确认不再需要。
- **快速回退：** 双击该目录`rollback.cmd`；或用本项目Python运行同目录`rollback-notice-visual.py --apply`。脚本先核原完整构建、同一owner/schema/revision及本次拥有文件，发现后续产品改动即拒绝覆盖；通过后正常停止8065，只恢复设计文档与notices.css/tsx，恢复原构建清单，沿统一CLI以`--existing`启动原8065并核实，保留数据库和私有状态。Git HEAD不reset；源码恢复会成为明确的工作区差异。成功回执为原run `reports/notice-visual-rollback.json`。
- `--check`已在最终实例通过；本次未执行`--apply`完整回退往返，不宣称恢复路径已现场切换验证。原构建和当前完整构建均保留，两份本轮无消费者中间构建已移除。

## 权威资料、暂停项与保护

- 设计主人：`docs/guides/frontend-design.md`；运行及更新：`docs/guides/frontend-preview.md`；检查：`docs/guides/development-and-verification.md`；需求：`docs/requirements/payments.md`和`central-procurement.md`；讨论：`.scratch/frontend-vue-rewrite/questions.md`；当前成果/未验：同目录`evidence.md`；共同范围及合流门：`spec.md`。
- `.scratch/frontend-vue-rewrite/notice-visual-trial.md`记录独立demo范围/来源。Radix官方一手来源及MIT、MiSans许可在该文档和独立site内。demo源码detector空结果、字体12/14/18三档和HTTP隔离已查，不替代产品界面或449性能通过。
- `.scratch/tails/issues/TAIL-449-全站加载与表格尺寸稳定统一.md`已补首帧主题/CSS、尺寸覆盖主人及密集表宽度事项，仍暂停，ready-for-agent不是恢复授权。
- 前序MOD05拆页、关联弹窗/弃稿确认、多选隐藏小微壳已实现并加载8065，不重做Q1/Q2或既有grilling。445–448仍按原票待用户验看；之后原真实试用、双方版本合流、最终候选及423/424流程沿spec/evidence，未在本次完成。
- 合并master、正式切换/部署、正式迁移、真实i8新外呼/物理打印等仍守原授权边界。本次不推送公共远端；先前涉及非公开业务资料的公开推送未获确认，不能将普通仓库推送授权当成新增披露批准。
- 主检出`D:/dev/mtrl-workbench`已有无关脏`docs/agents/issue-tracker.md`、`docs/status.md`和未知`--full-page`，保持；其他项目/My-Skills不并入本任务。凭据不写交接，不打印owner私有账号字段。
- 旧交接`PH-20261026-react-trial-01`已由本编号接续；旧正文可从`e2de8da5`的本路径恢复，历史完成/未验的详细证据仍在原主人。

<!-- MTRL-HANDOFF-END PH-20261026-notice-visual-01 -->
