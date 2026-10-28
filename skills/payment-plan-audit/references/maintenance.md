# 维护说明

仅在修改、维护或更新本技能时读本件；正常业务直接按SKILL.md执行。中央库、Agent安装目录及其中的正文、参考、脚本、模板都属于分发副本，禁止直接编辑；一律回维护源修改，再调用manage-skills发布。

## 维护与更新

1. **调用 `manage-skills` 技能。** 先读取宿主实际安装的manage-skills/SKILL.md，按它定位与当前Skills Manager配套的CLI。不要凭记忆手抄安装目录；没有该技能时先说明缺失，不另造一套部署方式。
2. **定位源码。** 本机维护源为`D:/dev/mtrl-workbench/skills/payment-plan-audit`，技能ID为`877236e1-3546-485f-a2be-2114add22a3d`，目录标识为`payment-plan-audit`。先用manage-skills的skills show/status核实际来源、preset和部署；其他电脑可能没有这个本机路径，找不到源码就停止维护，不能把安装副本认作源码。
3. **修改源码并检查。** 业务步骤仍放SKILL.md，必要参考按需读取；维护文件只管维护。保留人工改动，不把业务样本、结果、凭据或会话放入包。只改描述或文档不重跑真实业务。
4. **通过Skills Manager更新。** 在本机运行下列发布入口。它只生成依赖齐全的分发包，再调用Skills Manager更新原ID并核部署范围；询价共享参考仍在项目shared中唯一维护，发布时随包冻结。

```text
python -X utf8 D:/dev/业务流程/tools/sync_business_skills.py payment-plan-audit
```

5. **核验结果。** 用manage-skills检查source、refreshed、preset、标签及实际部署文件；出现held_back_removals、冲突或来源不符时保留现场并按工具要求处理，不强制覆盖、不删除重装。另核完整SKILL正文与相对引用；包与安装副本逐项一致，派生包只允许已说明的引用路径适配，源码业务正文无删减；更新不扩张到原来未部署的Agent。

## 副本与调用策略

项目目录是维护源；中央库是发布版本；Agent目录是Skills Manager管理的运行副本。**副本不自动跟随源码，源文件更新后必须执行上述更新。** 副本是正常分发方式，不应手工同步文件，或改成junction来绕开Skills Manager；链接/复制模式的调整也交给manage-skills，保留来源、ID及部署记录。

SKILL.md保留完整业务正文和简短中文description，无需清空描述或把正文挪成空入口。disable-model-invocation保持true；Codex的allow_implicit_invocation保持false；OpenCode的opencode/autoinvoke保持false。只在支持对应策略的宿主采用其设置，不用一句通用承诺替代实际核验。

本技能归入“材料业务·手动调用”preset、标签“材料业务”。本机现有部署保持，另一电脑不因维护而默认部署。不要把技能正文写入Agent记忆；已加载的会话内容与历史记忆无法靠技能更新撤回，需新会话核验。

Git提交推送另依当次授权。维护本技能不授权运行真实业务、登录i8、审批或付款。

## 本技能补充

规则或枚举改变时先在材料工作台运行tools/oneoff/_build_plan_audit_runtime.py，更新resources/audit-runtime.zip及dist/payment-plan-audit.skill并运行技能测试。--repo仅为开发规则入口，不恢复本机数据库取数。


### 豆包实体副本恢复

用户2026-10-23确认：豆包会自行将技能软链接展开成实体文件；本次及以后对Skills Manager已登记的豆包部署目标，发布时可直接删除该实体副本后由Manager重建，不备份、不重复询问此类处理。

既有sync_business_skills.py已落实此规则：只接受deploy的TARGET_CONFLICT，冲突须唯一指向当前技能已登记的豆包目标，且位于豆包既定.user_skills目录；确认目录为实体、内部无链接后才删除，立即重试受管部署并记回执。未登记、其他Agent或目录、多个冲突、软链接/junction仍保留现场按原规则处理。此例外不授权删除维护源、用户Excel或其他业务资料。
