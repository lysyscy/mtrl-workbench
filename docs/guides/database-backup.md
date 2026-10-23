# 数据库备份与恢复边界

本机 Windows 计划任务 MtrlWorkbench-DailyBackup 调用 ops/backup_databases.py。当前任务时间、账号和结果用 Get-ScheduledTask/Get-ScheduledTaskInfo 核实；已注册不能证明后续每次成功。该任务独立于业务服务，备份不要求重启服务。

脚本从项目配置读取两个不同本机库，不把口令放参数或回执。每轮在 var/backups/databases/.partial-* 生成两份 custom 归档，校验 SHA256、字节数及 pg_restore 目录后才发布日期目录，last-run.json 保存结果；失败非零且半成品保留调查。完成备份不覆盖，也不自动按日期删除，目录权限限制 SYSTEM/Administrators。

只读核一份备份，使用 backend/.venv/Scripts/python.exe -B -X utf8 ops/backup_databases.py --pg-bin <匹配版本bin> --verify <备份目录>。pg-bin 来自目标主机真实安装，不能照抄旧机器版本。

恢复先创建隔离空库，用匹配 pg_restore；核各表行数、内容摘要、序列和相关业务读取后才考虑替换目标。目录/SHA 核对只证明归档可读及字节一致，不能代替完整恢复。pg_dump 不含集群角色、NSSM、机器环境、.env、会话及应用私有恢复材料；换机必须分别准备它们，单份 dump 不能代表整机恢复包。

调整任务/恢复/真实库替换须当前相应授权。停止新增备份任务时先禁用计划任务，再按实际范围处理 ACL/注册，历史备份与数据库不随任务退出。操作前核路径与所有权，保留已有业务恢复点。
