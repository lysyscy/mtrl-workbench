# 正式加载回执

2026-11-03 11:19（北京时间），用户要求“重启到正式服务”。标准发布器已加载`8e4512ce31b15c284dc8eebbb4d1f2b8404c8c18`，资源`var/frontend/releases/8e4512ce31b1`，上一版`fbb42d23b0e3`保留回退。未合并master。

正式构建重新运行typecheck/build，发布器核完整资源后停止旧服务、仅切换FRONTEND_APP_DIR、启动并核实际索引、37份公开资源、缺资源404及8000监听归属。回执status=loaded、health=200、listener.owned=true，新服务Running/LocalSystem。正式索引SHA256 `fd247dd6d8aac2629621319ae8b51cd7188755c0aa513891e54074c4a9d5d102`。

随后只读GET核`/app/notices`=200，`/api/m06/mech-screen`=200/93288B及完整屏幕键，`/api/m07/extract-screen?year=2026&status=在建`=200/4655B（annual/balances），`/api/m05/debt`=200/19495B。这些证明正式连通及结构，不重复声称现场交互已验收。

最初server_ctl publish在服务操作前因默认受管输出目录与构建器active目录约束不匹配退出；随后使用同一发布器支持的显式`--run .artifacts/active/frontend-release/20261103-site-performance`成功，未修改守卫。首次失败报告保留于主控受管组`111750-511062-41092`；成功原始报告/构建日志归`.artifacts/archive/frontend-release/20261103-site-performance`，临时work构建退出，实际发布包保持。

发布器按既有登记仅退役旧包`e822612e221b`，保当前及上一版。未执行数据库迁移、正式业务写入、i8登录/抓取或实际打印。原无关修改及油卡工作树保持。源码保存、正式加载和现场人工验收分别记录；早期凭据输出事故未借本轮发布改变口令或处置状态。
