# 自有业务技能的手动调用与本机部署

2026-10-19用户批准：允许Skills Manager云同步；建立自有业务preset，本机开启，其他电脑不默认部署；日常不进入模型的技能自动发现上下文；全部自有技能有按需维护说明。后续明确机械费归集技能迁入材料工作台。

已创建preset“材料业务·手动调用”（c9204668-ced5-4188-a3fd-7b81808d4f0a），包含7项：付款计划核对、机械费归集、i8审批材料辅助，以及询价清单整理、实时价格、供应商回价核对、技术资料解读。未把业务技能加入Default/CODEX等通用preset，未切换旧active preset。

## 维护与分发

- 材料工作台持有skills/payment-plan-audit及skills/machinery-fee-consolidation的唯一源码；后者由业务流程/机械费报表以本机Move-Item迁入。原历史outputs、validation未动，原项目README/AGENTS/测试已接续新源。
- 审批辅助及询价技能继续在各自项目维护。所有7个SKILL.md均只用一行引用references/maintenance.md，不向Agent记忆文件添加业务说明。
- 更新入口是D:/dev/业务流程/tools/sync_business_skills.py，生成派生包后调用Skills Manager安装/更新；中央库及Agent目录不是维护源。询价4项各携带同源共享参考，依赖中的SKILL改名为GUIDE避免重复发现；包内仅一个SKILL入口。排除.venv、缓存、业务产物及验证目录。
- 支持的本机Agent已通过preset显式部署：Codex、CodeBuddy、WorkBuddy、OpenCode、AutoClaw，共35对；付款计划原ID保留。未启用既有关闭的Claude Code/Copilot。

## 调用策略与依据

| 宿主 | 已配置 / 核验依据 | 当前边界 |
|---|---|---|
| Codex | agents/openai.yaml的allow_implicit_invocation=false；安装技能规范明确默认不注入模型清单，显式调用仍可用 | 本轮未启动新模型会话验证；当前会话已有上下文无法撤回 |
| CodeBuddy | SKILL.md的disable-model-invocation=true、user-invocable=true；[官方文档](https://www.codebuddy.ai/docs/cli/skills) | 未改其他用户设置或插件 |
| WorkBuddy | 同上；本机resources/app.asar.unpacked/cli/dist/codebuddy-lite-wb.mjs明确读取该字段，并在模型命令/技能清单及上下文计量处过滤disableModelInvocation | 不使用其跨端同步的总开关冒充“本机专用”策略；新会话实际运行待验 |
| OpenCode | metadata下opencode/autoinvoke="false"、opencode/slash="true"；[官方说明](https://opencode.ai/docs/skills)明确排除自动清单并保留按名读取 | 本机CLI版本2.0.32，未实际发起模型任务 |
| AutoClaw | 本机D:/software/AutoClaw2/resources/app/dist/main.cjs读取frontmatter的disable-model-invocation，并在visibleSkills清单过滤；按名读技能仍保留 | 本轮验证安装实现与部署文件，未运行真实Agent业务任务 |
| ZCode | [当前官方说明](https://zcode.z.ai/cn/docs/skill)未说明该限制；本机resources/glm/zcode.cjs未找到上述控制字段 | 不部署业务技能，避免无依据地声称不会常驻上下文；仍可手工指定中央库文件 |
| 豆包 | 未从官方资料或当前可读运行实现确认自动清单隐藏策略 | 不部署业务技能，仍可手工指定中央库文件 |

[Codex官方调用策略](https://learn.chatgpt.com/docs/build-skills#optional-metadata)确认禁用隐式调用。不同Agent的“记忆”与技能上下文是两套机制：本轮未写任何Agent记忆文件，也没有清理用户既有记忆；不承诺宿主在未来手动使用技能后绝不会自行保存会话记忆。

## 验证与另一台电脑

验证证据保存在D:/dev/业务流程/validation/2026-10-19/business-skill-deployment：7项入口、相对链接、调用策略及唯一SKILL入口通过；干净分发包、中央库和5个Agent的所有非缓存文件SHA逐项一致。机械费迁移后的6项合成测试通过，审批技能2项隔离携带测试通过，文档审计必须修0；迁移前源目录没有Git基线，不虚构Git前后比对。初次误用无openpyxl的系统Python未能导入测试，换用项目既有.venv后通过，未安装新依赖。

复制已备份的完整库和同步元数据到隔离目录，使用Skills Manager的--skills-root恢复，7个业务技能均显示deployed_to空：新库恢复不会自动建立这35对本机部署。此为隔离模拟，不冒充实体第二台电脑验收。另一台电脑保留库及preset定义，不点击部署业务preset；若以前已单独安装同名技能，应在该电脑撤下其部署。不能远程替未连接电脑清除既有安装。

本轮没有执行技能业务流程、登录i8、修改真实表格、迁移数据库、重启服务或提交推送项目源码。Skills Manager后台备份由用户现有配置负责，本轮未手动强推云端；云备份完成状态与源代码保存分开报告。

## 中文命名与标签（2026-10-19）

用户要求给上述7项统一标签并使用中文名。现已通过Skills Manager添加“材料业务”标签，名称分别为：原表付款计划核对、机械费报表归集、i8审批材料辅助、询价清单整理、材料实时价格研究、供应商回价核对、技术资料解读。源SKILL.md的name和agents/openai.yaml的display_name已同步；英文目录标识及7个技能ID保持，更新工具按目录和ID定位，避免改显示名称后重复安装。机械费默认调用提示也已换成中文名称。

核验中发现Skills Manager的legacy更新会把技能重新部署到默认范围；已撤下误扩到ZCode/豆包的14对部署，并恢复AutoClaw。更新工具现逐技能快照实际目标集合，更新后通过Skills Manager撤下多余目标、补回原目标。用付款计划技能真实更新验证后，7项仍仅在原5个Agent部署。35对文件SHA、标签、ID与显式调用策略通过；Codex真实发现接口的中文名称隔离样例通过，未发起模型或业务任务。回执在业务流程validation/2026-10-19/business-skill-deployment/chinese-names。

用户后续更名：材料实时价格研究→网络询价，原表付款计划核对→付款计划核对。源、Skills Manager及当前已部署副本已更新核对，技能ID、标签和手动调用策略保持。本次观察两项均部署于Codex、CodeBuddy、WorkBuddy、OpenCode，未借更名扩大部署；此前部署数量属于当时快照。

## 入口正文与维护指针修正（2026-10-19）

用户指出询价分发入口近乎空白，维护说明没有明确要求使用manage-skills，接手Agent因副本滞后建议改junction。已确认生成器此前将正文移到guidance/GUIDE，这是不必要的包装。现4个询价分发SKILL.md直接保留完整业务正文，仅对随包共享参考的链接作路径适配；网络询价173行，清单56行，回价42行，技术资料40行。保留非空中文description及既有手动调用策略，不采用截图中清空description的做法。旧GUIDE只兼容原相对引用，同技能GUIDE转指正文，避免双份维护规则。

7份维护说明已明确调用manage-skills、核source/ID/部署、改项目源码、通过Skills Manager更新、比对包与实际副本，副本落后属于未完成更新而非必须改junction。正文只留一行按需维护引用。核对了其他Agent最近的7份询价参考修改，已存在当前源码，按源码保留，不覆盖回旧发布快照。安装副本和源码路径不要求字节相同：派生包可适配相对引用，业务正文完整，安装副本必须与相应发布包一致。

当前真实部署范围按本轮开始的Skills Manager状态保持，不重新套旧的5个或4个Agent快照；本轮不主动添加/删除Agent。源、分发包和部署验证回业务流程validation/2026-10-19/skill-layout-repair。未执行询价、审批或付款业务，也未改Agent记忆或部署链接模式。


### 2026-10-19 本轮维护说明与完整入口修复核验

- 七项维护源的 SKILL.md 保留完整业务正文、非空描述及手动调用配置；维护入口一行明确禁止直接修改中央库或 Agent 安装副本内任何文件，必须回维护源修改并通过 manage-skills 发布。
- references/maintenance.md 明确正文、参考、脚本、模板均适用同一维护流程。询价发布包保留完整入口，旧 GUIDE 仅兼容历史引用。
- 已经 Skills Manager 更新全部七项；中央库与 codebuddy、codex、doubao、opencode、workbuddy 共 35 项实际部署的完整文件哈希与发布包一致，ID、材料业务标签及手动调用 preset 保留。核验记录：D:/dev/业务流程/validation/2026-10-19/skill-layout-repair/verification.json。
- 网络询价曾返回拒绝访问；清理用户授权不保留的豆包冲突副本后，经 Manager 重新部署、更新已成功。本轮通过 Manager 撤销并恢复其原五个部署目标；未手工写入中央库或 Agent 技能正文。
- 用户已自行删除移出的豆包恢复副本，本轮未重建备份。更新工具补充 JSON 错误识别并通过模拟错误回归，避免退出码为 0 的更新失败被误判成功。
- 未运行真实业务流程、访问 i8 或修改业务数据；未提交、推送 Git。
