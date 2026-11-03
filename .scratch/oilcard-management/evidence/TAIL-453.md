# TAIL-453 验证记录

2026-10-31，分支 `codex/oilcard-management-20261031`，实施起点 `e296e816ed13a05e7572bae6bc6e88fb5a3dda66`。范围为实体卡、用卡账户、当前关联及关联历史；充值、发票、报表仍由后续票实现。

## 自动检查

- 后端使用 `tools/dev/backend_verify.py --source-env .env --test tests/test_oilcard_archives.py --test tests/test_layering.py -- -q -o addopts=`，19 passed。覆盖完整文本卡号、多个未知卡号、同卡/同项目多账户、主副卡约束、独立归档、版本冲突、未登录写入拒绝、关联快照及撤销/重做。测试 schema 已清理。原始回执为本机 AgentArtifacts 组 `100114-314401-35320` 下 `files/reports/backend-verify.json`，返回码 0，数据库及临时文件清理均完成。
- 通过项目预览入口 `tools/dev/frontend_preview.py --run .artifacts/active/oilcard-implementation/20261031-453 --prepare-build .artifacts/active/oilcard-implementation/20261031-453/work/build-01` 完成正式类型检查和构建，退出码 0；Node v24.22.1，Corepack pnpm 12.15.0。
- `corepack pnpm exec node --import=tsx --test tests/unit/cell-save.test.mjs tests/unit/identity-gate.test.mjs`：2 passed。复用的保存队列及身份保护定向检查通过。
- 早期迁移父节点错误造成双 head，已改为真实父节点 `mechauto261028` 后通过上述后端检查；未以 stamp 或跳过迁移处理。

## 真实页面代表路径

通过 ego-browser 操作完整产品预览，地址 `http://127.0.0.1:8065/preview/oilcard`。预览为源数据只读复制到 `mtrl_workbench_test` 的一次性 schema `frontend_rewrite_397_421d8f1ba4f3408c8cd9965babb9e819`，迁移到 `oil453261031`，`synthetic=false`。启动后使用 `registered_preview()` 核实所属进程、构建与 schema。

- 使用预览专用账号登录；从侧栏进入油卡管理。
- 新增未知卡号档案，录入 `0001234567890123456789` 并回车离格保存，改为主卡并填写独立备注。
- 新增另一张未知副卡，通过下拉关联主卡；账户关联候选只出现副卡。
- 新增账户草稿，填写名称、选择已有项目后自动建档；选择未知副卡，输入账户备注并离格保存。
- 将账户归档后刷新，名称、项目、卡片、归档状态和账户备注均读回；重新启用成功。
- 关联历史显示最初未关联卡片及后续关联副卡的两条记录；返回实体卡页确认主卡完整号码、主副关系和独立备注未被账户编辑覆盖。
- 已查看账户及实体卡截图，必要字段和控件在当前桌面视口可见。截图及浏览器脚本归本轮 `.artifacts/active/oilcard-implementation/20261031-453`，不作为业务原件。

浏览器脚本中等待了错误的按钮名/标签及使用失效快照引用的回合不计通过；重新观察真实页面后完成上述路径，没有绕过业务界面写入。

## 资源和边界

页面核验完成后通过 `frontend_preview.py --stop` 正常退出 PID 10980，服务退出码 0，终端确认 `ISOLATION cleaned schema=frontend_rewrite_397_421d8f1ba4f3408c8cd9965babb9e819`。8801 合成原型与生产服务未由本任务启停。没有真实初始导入、外部 i8/中石化操作或生产迁移/部署。

本票完成技术验证；不代表用户已人工验收或生产已加载。最终累计 Standards / Spec 独立双轴审查仍按本 effort 的统一收尾执行。
