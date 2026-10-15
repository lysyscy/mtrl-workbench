# TAIL-342: 核实当前服务日志保存与在线轮转是否生效

**What to build:** 核实当前服务日志保存与在线轮转是否生效

**Blocked by:** None (can start immediately)

**Status:** done

- [x] 核实真实服务stdout/stderr落点、在线轮转开关及阈值。
- [x] 区分配置在位与实际达到阈值的轮转，不为测试覆盖或截断现有日志。

---

## Comments

**2026-10-15 · 建票（agent）。** 来源：用户2026-10-15要求其余问题逐项立票并标状态｜不做会怎样：事项被旧状态或销号掩盖，后续接手无法判断真实边界｜落点：原职责对应代码或现场配置；证据在本票Comments｜阶段 / 时机：随时｜**排期四问**（`§14.3` 同源）：①保持原范围②仍有实际缺口③按独立事项留票④具体验收与触发见本票

**2026-10-15 · 当前分诊。** Agent本轮只读核验。票状态为claimed；技术可自行处理的继续实施，其余等待明确条件，不因建票自动执行真实业务写入。


**2026-10-15 · 核实与范围（agent）。** 只读核NSSM注册表：AppStdout/AppStderr均在本仓logs，AppRotateFiles=1、AppRotateOnline=1、AppRotateBytes=10485760；现日志存在且低于阈值。服务Running且/app200。已验证配置在位，未强制制造10MB输出触发轮转；不删除旧日志。原sandbox内nssm.exe重定位报错属受限运行环境，提升后注册表和服务可核，不作为主机故障。证据operations-readonly.json。
