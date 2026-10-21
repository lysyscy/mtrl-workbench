# TAIL-384: 右上角按当前账号撤销重做安全站内操作，恢复误剔除18条

**What to build:** 右上角按当前账号撤销重做安全站内操作，恢复误剔除18条

**Blocked by:** None

**Status:** claimed

- [x] 精确恢复刚剔除的18条通知书，不改金额、分类、原归属或其他剔除记录。
- [x] 用户名左侧提供撤销/重做与快捷键；输入文字保留原生撤销，批量一步、当前账号隔离、刷新保留。
- [x] 白名单操作完整恢复；不支持项提示并截断历史；后续写入冲突整批拒绝，新增操作清重做分支。
- [ ] 定向回归通过，两库迁移一致，备份后加载，提交推送并核远端SHA。

---

## Comments

**2026-10-21 · 建票（agent）。** 来源：用户2026-10-21明确授权并选择安全操作覆盖、不支持项提示｜不做会怎样：误剔除等批量编辑无法撤回，手工恢复易误伤其他记录｜落点：公共历史事务、壳右上角入口及数据库迁移和回归｜阶段 / 时机：随时｜**排期四问**（`§14.3` 同源）：恢复目标已精确锁定；全局入口已指定；采用明确安全白名单；冲突拒绝覆盖

**2026-10-21 · 数据恢复。** 最新人工剔除事务 xmin=12001 精确18条（id=1,2,3,4,5,6,7,9,10,11,1160,1161,1176,1177,1178,1179,1180,1181），均为龙源项目。锁定后调用既有恢复入口提交，复读18条已恢复；目标金额/分类/非空归属与全部非目标剔除状态保持。初次缺注册Project模型在写入前失败并回滚，补注册后成功。回执：`.artifacts/archive/checks-20261021/090453-688152-37472/recovery/restore-18-notices.json`。不追补撤销历史。

**2026-10-21 · 实现与反馈。** 以51e80e2为起点，新增按账号持久操作历史与白名单；与业务同事务保存，批量全有或全无，目标/父项目值及xmin守卫，预期历史头防重复点击。HTTP首轮暴露默认请求期依赖晚提交导致回执缺失，改为function scope；长账号暴露varchar上限，改存完整账号摘要。扩大选集首次213通过、1失败（跨页标脏重复LOADED.clear），删除重复标脏、沿既有API.send主人处理；未放宽原测试。最新期初用例曾误以为换截止年月会覆盖旧行，核实际三元唯一键后改为同年月覆盖，保留原业务口径。

**2026-10-21 · 最终源码核验。** `pytest tests/test_operation_history.py tests/test_operation_history_ui.py tests/test_notice_action_api.py tests/test_shell_bind.py tests/test_shell_render.py tests/test_wired_boot.py tests/test_modal_focus.py tests/test_shell_ui_workflow.py tests/test_ledger_opening_range.py tests/test_ledger_opening_ui.py tests/test_tail274_ledger.py tests/test_tail273_ledger.py tests/test_acc_flow_led.py tests/test_acc_init.py tests/test_page_m05.py tests/test_ledger_export.py tests/test_wired_m05.py tests/test_acc_flow_debt.py tests/test_layering.py -o addopts= -q --tb=short` 退出0：215 passed in112.79s；补充含schema drift的定向选集44 passed in12.52s。覆盖真实测试库独立提交/xmin、同账号并发、批量冲突、账号隔离、真实HTTP与表单303、10类原入口及浏览器快捷键/输入原生撤销/缩放布局。doc_audit退出0（必须修0，既有疑似32），bytes_guard必须修0，diff --check通过。未跑全仓pytest，未为测试修改真实付款/抓取/通知书。
