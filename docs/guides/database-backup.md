# 本机每日数据库备份

当前办公室主机使用Windows计划任务`MtrlWorkbench-DailyBackup`，每天09:30以SYSTEM运行，错过时间后补跑，重复实例忽略，最长15分钟。执行程序是本项目backend/.venv/Scripts/python.exe，工作目录为仓根，参数为：

```powershell
-B -X utf8 "D:\dev\mtrl-workbench\ops\backup_databases.py" --pg-bin "D:\pgsql\18.6\pgsql\bin"
```

脚本读取项目现有配置，不把口令放进参数、Git或回执。只接受两个不同的本机库。每次在`.artifacts/recovery/databases/.partial-*`创建两份custom格式归档，SHA256、字节数和pg_restore目录检查都通过后才发布为独立日期目录；`last-run.json`报告最近成功或失败。失败返回非零并保留半成品供调查，已完成备份不覆盖、不按日期自动删除。

备份目录仅SYSTEM和本机Administrators可访问。2026-10-15已实际手动及SYSTEM运行成功（TAIL-341）；定时器未来每次是否成功，查看LastTaskResult和last-run.json，不从“已注册”推断。只读核对某份备份：

```powershell
backend/.venv/Scripts/python.exe -B -X utf8 ops/backup_databases.py --pg-bin D:/pgsql/18.6/pgsql/bin --verify <该份备份目录>
Get-ScheduledTaskInfo -TaskName MtrlWorkbench-DailyBackup
```

当前备份与数据库仍在同一块物理磁盘上，只能防误写和部分数据损坏；独立介质由TAIL-347等待用户指定。没有配置自动清理，空间增长在确定异盘方案时一并定保留策略。

恢复先建隔离空库，再用匹配版本pg_restore，逐表核数量、内容摘要与序列，验证后才考虑替换。TAIL-337有此前真实两库的完整隔离恢复证据；本次新备份只核归档目录与SHA，没有重做完整恢复。pg_dump不包含集群角色、NSSM、.env和应用私有恢复材料，这些沿现有保管方式保存，不能从单份dump推断整机恢复完成。格式与恢复工具见[PostgreSQL 18 pg_dump](https://www.postgresql.org/docs/18/app-pgdump.html)及[pg_restore](https://www.postgresql.org/docs/18/app-pgrestore.html)。

停止本项目新增备份任务时先禁用任务，再按实际路径恢复ACL或保留已有备份；禁止连同历史备份一起删除。该任务与应用服务独立，不需要为了备份重启业务服务。
