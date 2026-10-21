# TAIL-385: 粘贴单据号严格识别、剔除明细定位与来源规则提示

**What to build:** 粘贴单据号严格识别、剔除明细定位与来源规则提示

**Blocked by:** None (can start immediately)

**Status:** claimed

- [x] 标准单据号精确匹配；未识别文本与未找到单据号分列，旧勾选保护继续生效。
- [x] 已剔除单据展示名称、项目、收款单位、日期、审批金额及来源；去处理仅定位这些记录，支持清除定位。
- [x] 手动剔除、自动剔除标签区分；悬停显示现行命中规则，不伪称旧标记保存了历史依据。
- [ ] 相关回归、资料同步、提交推送与运行服务验收完成。

---

## Comments

**2026-10-21 · 建票（agent）。** 来源：用户2026-10-21四点要求｜不做会怎样：杂文本混为未找到、剔除单据无信息且不能直达处理｜落点：MOD-03粘贴勾选与剔除标签；说明书§4.2.2及§4.3.5｜阶段 / 时机：随时｜**排期四问**（`§14.3` 同源）：①用户明确要求②直接影响核对③复用原列表与规则判定④隔离浏览器和领域回归后交付

**2026-10-21 · 原缺口回归。** 新增两项浏览器用例先运行：2 failed（杂文本进入 missing；剔除结果缺通知书详情）。初次命令路径错误未选测试、第二次相对解释器路径错误均不计验证；修正后实际取得上述红灯。

**2026-10-21 · 实施与验证。** 只认 FKTZS/QTZC＋YYYYMM＋四位序号；区分原始未识别文本与有效格式但缺失的单据号。剔除／撤单明细保留名称、项目、日期、收款单位、审批金额和来源；重号中的剔除记录也展示。去处理按内部ID过滤、清空勾选并提供清除定位；搜索能搜到来源标签。领域共用现有 match_exclude_rule，接口输出当前规则解释，不变更业务标记、不做迁移、不重算历史。

**2026-10-21 · 核验。** 最终命令（backend）：`.venv/Scripts/python.exe -X utf8 -m pytest tests/test_notice_paste_selection.py tests/test_tail309_notice_selection.py tests/test_wired_m03_list.py tests/test_notice_list.py tests/test_notice_action_api.py tests/test_classify.py tests/test_shell_part_routes.py tests/test_notice_list_source.py -q`，退出0，88项通过，42.58秒。1440标准字号／1024宽125%字号的模拟页面实测无横向溢出、处理按钮可达；截图人工检查通过。证据收尾归 `.artifacts/archive/tail-385/notice-paste-20261021/`。首次扩大选集发现旧骨架字面断言未跟随既有 notice-table 类（HEAD已如此），更新为当前真实TBL调用；没有修改产品表结构。未用真实付款、恢复剔除或打印来验证。
