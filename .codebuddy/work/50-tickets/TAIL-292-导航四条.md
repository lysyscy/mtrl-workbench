# TAIL-292: 导航补齐：已关联到集采合同、流水与计划单据号到通知书、过程资料差异到库存原始行，精确落位可返回

**What to build:** 导航补齐：已关联到集采合同、流水与计划单据号到通知书、过程资料差异到库存原始行，精确落位可返回

**Blocked by:** 建议 A 之后；候选与详情显示项目内序号，依赖 A 的派生

**Status:** done

- [x] 「已关联」标签文案仍是四个字；「查看关联」详情显示项目内序号 ＋ 合同编号
- [x] 「查看集采合同」直达集采台账并按合同 id 高亮，冲突的项目 / 标记 / 金额筛选被临时纠正；目标失联时不乱跳、有提示
- [x] 付款流水「单据编码」→ 通知书精确行（含虚拟列表）；孤儿流水保持文本并提示找不到
- [x] 付款计划「单据号」：命中唯一通知书才可点；未匹配 / 编码歧义不跳
- [x] 过程资料差异行 → 库存页按原始行 id 定位高亮（⛔ 不是整仓被调整列表）；年份 / 月等筛选不藏目标
- [x] 既有路径回归：集采付款子表 → 通知书 550 行虚拟定位不退化
- [x] 目标行可见可返回；新增按钮不引发整行双触发

---

## Comments

**2026-10-11 · 建票（agent）。** 来源：用户 2026-10-11 会话拍定（D2.A 与 NAV 清单，见 D32）｜不做会怎样：引用只能看不能到；或落在整仓调整列表上，等于没定位｜落点：backend/app/web/shell 的 actions.js proj.js core.js pages-a.js · backend/app/web/index.html 的 V.m04 V.m05｜阶段 / 时机：随时（在 A 之后）｜**排期四问**（`§14.3` 同源）：①规模：只给有唯一业务身份的引用加跳转，不做全站导航框架 ②要改：差异行现在只按仓库筛、计划单据号与流水编码是纯文本 ③改哪层：复用现有加载-清筛选-定位-高亮形态，动作仍传数据库 id ④做完＝C 批四条验收过，含虚拟表定位与未命中不乱跳

**2026-10-11 · 完成实施与核验（agent，未提交；上一轮改完后中断，记录由接手窗口补齐）。** 四条跳转复用一套「加载-清筛选-定位-高亮-返回」形态（`refNavigate`/`refLocate`/`refBack`），动作一律传数据库 id；定位走虚拟实例内按行属性找行，重画后靠行上的 `nt-focus` ＋ `data-jc-id`/`data-inv-id`/`data-notice-id` 复原高亮；冲突筛选只在跳转视图内临时纠正，返回时逐字复原。

- 验收①：`proj.js:386` 标签仍是四个字「已关联」；`test_tail292_nav.py::test_contract_id_conflicting_filters_and_return` 断言「查看关联」详情含「项目内序号」与合同编号 `00HT`。
- 验收②：同上用例：从 m03 带五个冲突筛选点「查看集采合同」⇒ 落 m11、`jcVisible()` 只剩 id=11、`tr.nt-focus[data-jc-id="11"]` 在位、重画后仍 1 处；点「返回原页」回 m03 且 `fJc` 逐字复原；合同 id 不存在时只提示、留在原页。
- 验收③：`test_notice_exact_id_in_550_virtual_rows[flow]`（550 行真虚拟表内点流水「单据编码」）⇒ `tr.nt-focus[data-notice-id="1540"]` 可见（`bounding_box` 在视口内）；孤儿流水保持文本 ＋ `span[title="找不到对应通知书"]`。
- 验收④：`test_plan_unique_ambiguous_and_orphan_flow`：唯一命中才出 `data-act="plNotice"`（计数=1）；歧义 ⇒ `span[title="单据号有多条通知书，无法唯一定位"]`；未匹配 ⇒ 「找不到对应通知书」；两种都不跳（VIEW 仍 m04）。
- 验收⑤：`test_inventory_original_id_virtual_and_return`：m06 差异行按原始行 id 2540 落 m08 虚拟表内可见；跳转时临时清掉年份/仓库/方向/调整列筛选（`fIvYm='全部'`、`invOnlyAdj=false`）；返回后四元组逐字复原；行不存在只提示、不跳。
- 验收⑥：550 行虚拟定位两条入口都不退化 —— `[jc]` 路径 `navCalls==1`（不双触发）；完整真机壳自检 `tools/probe/_shell_smoke.py` 39 段 rc=0、无 console/page 错误。
- 验收⑦：目标行可见（在视口内）＋「返回原页」恢复筛选与滚动；「查看关联」纯只读由 `test_wired_m03_action.py::test_壳里查看关联是纯只读且流水含已撤销` 看管（隔离变异把入口换成写按钮即变红）。
- 反向灵敏度：`tools/mut/_mut_tail292.py` rc=0，5 条隔离变异（筛选未纠正 / 按仓库而非 id / 歧义取首条 / 虚拟不滚 / 只读换写动作）各 AssertionError，正式件未写靶。
- 相关回归：`test_tail292_nav` ＋ `test_tail290_jc` ＋ `test_tail291_revoke` ＋ `test_acc_jc_list` ＋ `test_naive_export_parity` ＋ `test_ux_pages::集采台账行身份区` 共 26 项 rc=0；`test_wired_m03_action` ＋ `test_wired_m03_list` ＋ `test_shell_ui_workflow` 共 47 项 rc=0。
- 真机浏览器：`tmp-20261011-292-notice-focus.png` / `tmp-20261011-292-inventory-focus.png`（隔离夹具下真浏览器截图，落 00-scratch）。
- 壳章：`tools/audit/shell_verify.py --snapshot` rc=0，基线 `20261011-2002`（含本轮收尾的注释订正；盖章前 39 段真机 rc=0）。
- 最终影响入口：`tools/oneoff/_run_rulers.py --paths`（本轮实际差异件）rc=0 · `BAD: []` · 总墙钟 334.03s，doc_audit 必须修 0、pytest 隔离 rc=0/182.09s、`tools/oneoff/_run_muts.py` rc=0，完整输出 `.codebuddy/work/00-scratch/tmp-20261011-292-rulers-final.log`。⚠️ 显式范围外两处：① `delivery/PRD/验收/验收基线.json` —— 选择器按设计判「需要调查实际依赖」rc=2，按工程主人查清消费者后单验（`tools/audit/acc_report.py` rc=0 无红；`@acc`-挂 `001-61` 的用例随上面 26 项跑过），⛔ 未为求绿改选择器；② `backend/.codebuddy/` 下 5 张误落的截图（非本票产物，待清）。
- 两轴 `/code-review`（基点 `7dfebc1`）：Standards 硬违规 2 条 ⇒ 同批修：`tools/oneoff/_run_muts.py` 登记 4 支新变异件（修前 `--cover-only` rc=1 = 整道变异闸门瘫痪；修后 `✅ 选集一致：KEY 31 支 ∪ KEEP_OUT 89 支 ＝ 盘上 120 支`）、计数副本同批改（说明书 §6.4.1 → 20 字段、验收基线 001-61 → 21 列，并清 `domain.py:38`、`pages-b.js:287`、`test_ux_pages.py:463` 三处失修注释）；判断项 4 条（失修注释 1 条已同批清；余 3 条记录未处置：mod11 序号派生两处各读一遍全量表、mod05 撤销前置判定三处重写 ＋ 别名不一致、导航属性名单散三件）。
- Spec 轴：缺失 0 · 越界 1 · 实现可疑 1（硬违规 0）。处置：① 实现可疑（D32「表头｜悬浮说明改成…」）**已定案为符合** —— 原句 `title="序号 = 当前筛选下的行号"` 本就在**数据格**上，现文「项目内动态序号，筛选不变」挂同一格，口径未走样；② 越界 = `plHit` 由「取首条」改「必须唯一」**连带**把「已付款金额 / 剩余付款金额」在单据号歧义时由显示首条数改成 `—`（`pages-a.js:47` ＋ `index.html:710-711`）：方向与票面「编码歧义不跳」一致，但票面只要求入口不可点 ⇒ **用户 2026-10-11 追认「保留」**（显首条数＝拿不确定的数冒充确定；若要回退只动这两列，入口唯一性保留）。

**未验边界：** 四条跳转未在正式库真数据上人工走一遍；浏览器证据来自隔离夹具（真虚拟表 550 行 × fixture 数据）。未试 i8 真抓后合同编号为空的行、真实孤儿流水的现场样本。未提交/推送，原有本地提交未动。

**2026-10-11 · 销号后按最终状态复跑（agent）。** 票面记录补两轴 review 行、README §〇 追加、§13.6 交接行更新、旧交接入当日日志之后，`tools/oneoff/_run_rulers.py --paths` 再跑一次：rc=0 · `BAD: []` · 总墙钟 208.57s —— 重跑只重放受影响的文档面（pytest 隔离 167.21s），真机壳自检按签名**复用**（`tmp-20261011-201042-shell-smoke.log`，rc=0）；`doc_audit.py` 必须修 0（T1/T6 无红）、`audit_meta.py` rc=0（仅既有 T5 长件黄）、`git diff --check` rc=0。
