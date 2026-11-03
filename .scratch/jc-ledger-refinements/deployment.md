# 集采调整正式上线回执

2026-11-03 16:07（北京时间），按用户“上线”授权完成。正式产品提交 `073aaedd1b16a2e2f7d98a1ab5927103d74c0fd2`，分支 `codex/site-performance-20261102`；真实提交钩子通过。用户明确授权公开仓库正常推送后，已推送原origin并核远端SHA一致，未强推、未合并master。[Frontend checks](https://github.com/lysyscy/mtrl-workbench/actions/runs/41600788415)成功。

## 备份与迁移

- PostgreSQL18.6，现用工具目录 `D:/pgsql/18.6/pgsql/bin`。
- 两库备份为 `var/backups/databases/20261103-160209-75e0ace5`，现有工具已核SHA、字节数及归档目录；未做整库恢复演练。
- 正式库 `mtrl_workbench/public` 从 `mechauto261028` 升到 `c7d4e2a9b1f3`，仅新增操作回执表及索引；测试库从 `c432261023` 沿既有链升级到同一head。
- 两库迁移前后 `jc_contract`、`jc_invoice`、`jc_payment` 计数和完整行内容摘要均一致。未重录业务、未执行付款或调用i8。
- 迁移报告：`.artifacts/active/frontend-release/20261103-jc-ledger/reports/migration.json`。

## 正式加载

- 标准入口 `ops/server_ctl.ps1 -Action publish` 返回loaded。当前资源 `var/frontend/releases/073aaedd1b16`，回退 `8e4512ce31b1`；回退保当前数据库及正常新业务。
- 实际索引、36份资源散列、健康200及8000监听连接进程归属通过。
- 正式 `/api/m11/subtable-operation` 返回200；无实际操作的检查标识返回not_found，未写回执或业务。集采列表200，共271条，日期/同日ID升序、空日期后置核验通过。
- 标准发布重新完成类型检查和正式构建；复用此前62项单测、6项真实副本浏览器及后端具名检查。未在正式库执行GUI增删业务验收。
- 原始发布回执：`.artifacts/active/frontend-release/20261103-jc-ledger-publish/reports/deployment.json`。

## 过程问题与资源

- 沙箱无法查看宿主服务；获准宿主检查确认为Running且200，没有据沙箱输出认定正式服务不存在。
- 推送先被自动审批拒绝两次，理由为公开目的地需明确传输授权；用户明确同意后相同动作成功，未换途径绕过拒绝。
- 默认受管输出被构建器的旧目录校验拒绝，预检未触正式服务。使用独立具名兼容运行 `MTRL_EFFORT=frontend-release`、`MTRL_RUN_ID=20261103-jc-ledger` 及 `20261103-jc-ledger-publish` 后预检和发布通过，未改工具或安全校验。
- 标准发布器按既有归属规则退出旧正式资源，只保当前及上一回退。8065可丢弃副本预览仍保留，未删除其schema或可能正在查看的状态。
- 他人未提交文件及共享文档无关段落保持。本回执和status导航为上线后补记，不改变上述正式加载版本。
