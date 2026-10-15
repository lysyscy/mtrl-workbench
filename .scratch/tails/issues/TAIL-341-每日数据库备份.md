# TAIL-341: 建立本机每日数据库备份并核查失败与恢复依据

**What to build:** 建立本机每日数据库备份并核查失败与恢复依据

**Blocked by:** None (can start immediately)

**Status:** done

- [x] 两库每日备份任务实际运行成功；只发布经字节、SHA与归档目录核验的完整组。
- [x] 失败、坏档和错误目标有回归；不覆盖或自动删除旧备份，口令不进入参数或证据。
- [x] 运行身份、任务时间、位置、恢复方法及未验边界写入运维指南。

---

## Comments

**2026-10-15 · 建票（agent）。** 来源：用户2026-10-15要求其余问题逐项立票并标状态｜不做会怎样：事项被旧状态或销号掩盖，后续接手无法判断真实边界｜落点：原职责对应代码或现场配置；证据在本票Comments｜阶段 / 时机：随时｜**排期四问**（`§14.3` 同源）：①保持原范围②仍有实际缺口③按独立事项留票④具体验收与触发见本票

**2026-10-15 · 当前分诊。** Agent本轮实施；不自动删除旧备份。票状态为claimed；技术可自行处理的继续实施，其余等待明确条件，不因建票自动执行真实业务写入。


**2026-10-15 · 核实与范围（agent）。** 新增ops/backup_databases.py，3项回归通过（backup-tests.log）。手动及SYSTEM实际运行均成功，MtrlWorkbench-DailyBackup LastTaskResult=0，每日09:30、错过补跑、重复实例忽略；实际组20261015-082345-32685e96及last-run.json在.artifacts/recovery/databases。新目录ACL限SYSTEM/Administrators。校验为SHA+pg_restore --list，不是本次完整恢复演练；既有两库完整隔离恢复证据仍在TAIL-337。C/D同物理盘，独立介质另票347；不因本票完成抹掉该限制。
