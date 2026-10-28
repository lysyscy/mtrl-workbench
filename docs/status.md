# 当前活动工作

## React正式入口已启用（待用户日常验收）

用户2026-10-28 00:55 UTC授权后，正式`D:/dev/mtrl-workbench` master已整合候选e57f0695（产品846b4913），`mtrl_workbench.public`已从c432261023升至invadj261027，8000 `/app`加载完整React发布包，可以恢复使用。新备份、原数据/费用/序列及入口/静态资源/只读链路已核，停服请求至技术核验完成约147秒。实际账号登录与日常使用待用户确认；用户免于上线前验证的真实i8、物理打印和正式服务身份PDF继续标未验。

正式master上的[TAIL-423](../.scratch/tails/issues/TAIL-423-正式入口切换与运行核验.md#2026-10-28-正式切换已执行待用户日常验收)和[TAIL-424](../.scratch/tails/issues/TAIL-424-旧前端退役与清理.md)是现行状态与后续动作的主人：423为ready-for-human，424为needs-info。原React工作树36702cfd与候选工作树e57f0695保留为冻结来源和验收依据，不在其旧票据中另行推进现行状态。正式服务配置与界面回退方法回[部署](guides/deployment.md)。

旧壳尚未退役，回退保升级后端和当前数据库，不能用旧库覆盖正常新写入。用户日常验收及独立退役授权齐备后再按424处理。8065全部为试用数据、不回灌；本次切换未恢复其预览进程，旧端口/PID记录不代表当前在跑。

## 待验收与后续范围

全站视觉、交互和业务流程的用户实看仍待确认，按实际反馈处理，不把技术检查或切换成功当作用户签收。TAIL-449已按原范围验收关闭，既有性能取舍及未验边界沿下述原证据保留。

未实施架构候选统一由[TAIL-450](../.scratch/tails/issues/TAIL-450-架构差额后续实证与深化.md)持有，状态needs-triage；本次启用不自动启动或要求全部完成。

迁移前的范围、决定与技术证据按需查[共同规格](../.scratch/frontend-vue-rewrite/spec.md)、[问题与确认](../.scratch/frontend-vue-rewrite/questions.md)、[前端证据](../.scratch/frontend-vue-rewrite/evidence.md)及[架构深化证据](../.scratch/frontend-architecture/evidence.md)。这些材料中的原8065版本、PID和当时阶段状态属于历史快照；当前正式运行与用户验收以本页顶部及正式master的423/424为准。

## Mini App 付款原表核对台

[本地规格与七票入口](../.scratch/miniapp-payment-plan-audit/spec.md)已随本次整合保存在正式master，规格已确认、尚未实施；身份、依赖、验收和授权沿原规格与原票。核对口径归`skills/payment-plan-audit`，源码整合不代表Mini App已实施、个人技能已分发或真实拟方式回写已获授权。

## 机械费现有具体跟进

Git基点94c0021的机械费history-contract/evidence保有国风8月核实4500、采用5000和约定下月少做500的分别依据；下月4000只是约定，未取得执行证明，不能按9月项目总额自动核销。该事实沿现有机械费跟进事项处理；本次切换未新增该个案的执行核实，不将个案金额设为普遍规则。
