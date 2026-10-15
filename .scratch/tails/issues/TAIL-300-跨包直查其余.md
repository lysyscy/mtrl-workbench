# TAIL-300: 清空分层门禁 C2 的待清名单：其余 16 处跨包直查逐处改走对方服务台出口（含 mod11 那处双主人 join；mod09 只许走原单出口，不得叠加调整单）

**What to build:** 清空分层门禁 C2 的待清名单：其余 16 处跨包直查逐处改走对方服务台出口（含 mod11 那处双主人 join；mod09 只许走原单出口，不得叠加调整单）

**Blocked by:** TAIL-299（门禁 C2 与其待清名单先落地）

**Status:** done

- [x] **待清名单清零**：`_ALLOW_C2_PENDING` 空（`_C2_PENDING_START` 留作历史起点），`test_layering.py` 全绿。
- [x] **逐处走主人包出口**（实际16条清单见Comments最新订正）：每处**改前先核**该出口是否已存在（`mod03_notice.service` / `mod05_flow.service` / `mod08_inv.service` / `mod11_jc.service` / `mod02_i8`）；不存在则按施工图 §3.2 的取舍表判「值得开 / 该登记例外」，⛔ 不为单调用者单开转手层。
- [x] ⭐ **双主人 join**（`mod11_jc/repository.py:138`：mod03 的 `stat_paid` ＋ mod05 的最近生效流水日期）：两个主人各出**批量出口**（一次给一批通知书的值，⛔ 不准 N+1；返回形状要能直接喂回现在那段装配）。
- [x] ⛔ **mod09 那处的陷阱**：只能走 `mod08_inv.service.load_original_details`（原单 · **不叠加**人工调整）＋ 本侧取那 5 个键；**换 `load_rows` = 把人工调整并进自动项 = 第二套口径** ⇒ 判据必须钉住「自动项不含调整单」这条。
- [x] **锁那 1 处**（`mod05_flow/router.py:265`，付款临界区）：登记为 `_ALLOW_C2_BY_DESIGN`（理由 = 撤销付款临界区必须在**同一事务**内锁通知书行），**不进 pending**；并在该处补一句「为何在本侧锁」的注释（现在附近没有）。
- [x] **反向灵敏度**：每改一处，对应隔离自证能造红（或复跑 B1 那支的对应靶）；`mut_cover` 台账同步。
- [x] **收尾**：`_impactscope` 实选集 ＋ `chain_audit`（改的是取数出口，全站链路对账要过）；若某处的 API 返回形状变了 ⇒ **那一处补真机**；票 Comments 记证据与未验边界。

---

## Comments

**2026-10-11 · 建票（agent）。** 来源：2026-10-11 架构体检 B 案；TAIL-299 落地门禁后剩下的 11 处｜不做会怎样：不做：门禁的待清名单永远清不完（本仓口径：待清只许变短），21 处里永远有一半在名单外裸奔｜落点：落点：mod03_notice service 与 list_view · mod04_plan service · mod05_flow repository 与 router（付款临界区锁一处登记为按设计的例外，理由写清）· mod09_fee repository · mod11_jc repository 与 service · tests/test_layering.py 的待清名单（逐处删行、只许变短）｜阶段 / 时机：随时（排 TAIL-299 之后）｜**排期四问**（`§14.3` 同源）：四问：一 会真发生（清单实测）；二 真发生静默错数（双主人 join 那处最典型）；三 不做也能活但名单会长期挂着；四 有更省的：按能搬就搬逐处走主人包出口，搬不动的写理由登记例外

**2026-10-11 · 建票时随票的施工清单（只读核实）。**

待清的 11 处（`_ALLOW_C2_PENDING` 起步就是这 11 条减掉「锁那 1 处」= 10 条）：

| 文件:行 | 谁查谁的表 | 要什么 | 改法 |
|---|---|---|---|
| `mod03_notice/sup_match.py:98` | mod03 ← mod11 合同 | 合同供应商（匹配池） | mod11 出口（开工时先核现有出口够不够） |
| `mod03_notice/list_view.py:278` | mod03 ← mod11 付款子表 | notice_id → contract_ids | mod11 **批量**新出口 |
| `mod04_plan/service.py:61` | mod04 ← mod03 通知书 | 单据号 → 审批金额 | 查询＋视图搬回 mod03（口径归主人） |
| `mod04_plan/service.py:63` | mod04 ← mod05 流水 | 单据号 → 已付（生效汇总） | mod05 出口（先核 `payment_stat_views` / `notice_debt_views` 能否直接用） |
| `mod05_flow/repository.py:411` | mod05 ← mod03 通知书 | 待开工时核清用途 | mod03 出口 |
| `mod05_flow/router.py:265` | mod05 ← mod03 通知书 | 付款临界区**行锁** | ⭐ **登记按设计例外**（票面那条），不进名单 |
| `mod09_fee/repository.py:21` | mod09 ← mod08 库存明细 | 该月窄投影（**不叠加**调整） | `mod08_inv.service.load_original_details` ＋ 本侧取 5 键（⛔ 不得用 `load_rows`） |
| `mod11_jc/repository.py:132` | mod11 ← mod05 流水 | 最近生效流水日期（批量 by notice） | mod05 **批量**新出口 |
| `mod11_jc/repository.py:138` | mod11 ← mod03 通知书 | `stat_paid`（批量 by notice） | mod03 **批量**新出口 |
| `mod11_jc/service.py:277` | mod11 ← mod03 通知书 | 校验通知书存在 | mod03 出口（判存在） |
| `mod11_jc/repository.py:590` | mod11 ← mod02 i8 执行记录 | 最近一次抓取记录 | mod02 出口（先核它有没有 service；没有则按取舍表判） |

两处用途待逐处核（子代理只给了一句）：`mod05_flow/repository.py:411` · `mod11_jc/repository.py:590` —— 开工时先读上下文，⛔ 别按猜改。

预判核验面：`_impactscope` 实选集 ＋ `chain_audit`（改的是取数出口）；某处 API 返回形状变了 ⇒ 那一处补真机。

**2026-10-12 · TAIL-299实扫订正，未实施300。** 用户同意按实际清单；29处＝本轮收12处Project＋以下16待清＋1按设计例外。以下取代建票预估11行；查询处身份由`backend/tests/test_layering.py::_ALLOW_C2_PENDING`持有，行号会随改动漂移，接手按文件/函数定位。待清当前16，`_C2_PENDING_START=16`保留起点，只许变短；撤销付款`mod05_flow/router.py::api_revoke`的锁独立在BY_DESIGN，不在待清。

| 文件／函数 | 查询主人模型 | 接续要点 |
|---|---|---|
| mod03_notice/sup_match.py · row_pool_rows | mod11 JcContract | 匹配池；项目索引已走mod01出口，合同仍待清 |
| mod03_notice/list_view.py · _links_by_notice | mod11 JcPayment | notice→contract_ids批量读取 |
| mod04_plan/service.py · notice_amounts | mod03 PaymentNotice | 审批金额 |
| mod04_plan/service.py · notice_amounts | mod05 PaymentFlow | 生效已付汇总 |
| mod05_flow/repository.py · notice_rows | mod03 PaymentNotice | 欠款/台账/统计共用输入 |
| mod05_flow/repository.py · revoke | mod03 PaymentNotice | 撤销人工统计模式判断；新补 |
| mod05_flow/repository.py · revoke_info | mod03 PaymentNotice | 确认窗口事实快照；新补 |
| mod05_flow/repository.py · sync_stat_paid | mod03 PaymentNotice | key_share锁定重读并同步统计；新补，出口须保持当前session和锁参数 |
| mod09_fee/repository.py · inv_rows | mod08 InvDetail | 只走load_original_details，不叠加调整 |
| mod11_jc/repository.py · payments_of_many | mod05 PaymentFlow | 批量最近生效日期 |
| mod11_jc/repository.py · payments_of_many | mod03 PaymentNotice | 批量stat_paid，保留双主人装配 |
| mod11_jc/service.py · act_link_notice | mod03 PaymentNotice | 存在校验 |
| mod11_jc/repository.py · latest_unsettled | mod02 RunRecord | 最近集采抓取未匹配数据；别只按函数名猜用途 |
| mod01_projects/pending.py · latest_pending | mod02 RunRecord | 最近未建档项目抓取记录；数字包名实扫补入 |
| mod01_projects/archive_pending.py · latest_pending | mod02 RunRecord | 归档待建档记录；数字包名实扫补入 |
| mod03_notice/repository.py · latest_unresolved | mod02 RunRecord | 未归属通知书抓取记录；数字包名实扫补入 |

新活件`tools/mut/_mut_layering.py`已提供五形态、正当引用、名单逐条命中/增长及防空扫的隔离验证入口。处理300前先查各主人service能否复用，保持锁事务、批量读取和原单口径，不为单调用者加转手层。

**2026-10-12 · 领票。** 已核299为done、最新交接及实际16条清单；工作区开工无dirty，快照tmp-20261012-tail300-start.json。按既定规格实施，不提交推送，不扩展C–F。


**2026-10-12 · 落账。** 最新16条全部走主人出口，C2实扫pending=0、BY_DESIGN=1、found=1、extra空；历史起点16保留。付款欠款/台账/统计改取完整id升序通知书事实，含剔除/撤单、无列表上限；撤销模式、事实快照及统计同步均用同session出口，key_share/populate_existing原样转交。原api_revoke临界区直锁及其事务理由注释已由299落地，本轮保持，不另增例外。

集采子表本包查询＋通知书stat_paid窄投影＋流水最近生效日期，固定3查询（1/4张合同均3，空输入0），保留手工付款日期/金额及零统计值，不回退审批金额、旧关联金额或撤销日期；通知书关联一次读全，供应商池复用合同出口。mod09复用load_original_details并保留原5键/月筛选，调整100→900时自动项仍100；手工费用查询保持。mod02新增recent_records供材料待建档、常用项目同步待人工、通知书未归属、集采未归属四件共用，原类型/倒序/LOOKBACK/标记解释与不回溯旧清单语义保持。出口取舍依据实际共用及原薄查询函数，不另开无用途窗口。API返回结构保持。

**2026-10-12 · 唯一一次code-review双轴。** 基点HEAD `befb2a90fcbe3b54a7614206e88ffb403d85cab8`＋开工无dirty快照。Standards：0条；Spec：发现1处ORM缓存与原标量读值差异，已同批补修，最终未解决0条。测试库复现缓存10、SQL事实75时错误回10；改为主人stat_paid_of_many批量窄投影后回75，改回ORM读取的隔离靶必红。不重开第二轮。候选集合/匹配判定保持，原无ORDER BY不承诺供应商候选顺序。

**2026-10-12 · 核验与失败修正。** 按AGENTS读取现状、最新交接、299/300，按动作取issue-tracker§四、IDE§十一/十五/十六、分层施工图§3.2、architecture§一、说明书§4/5.5/6.6/9.3及工具主人。基点为 `tmp-20261012-tail300-start.json`。首批107项相关回归通过；补修后18项金额/撤销/集采链路通过。`_run_rulers.py --since .codebuddy/work/00-scratch/tmp-20261012-tail300-start.json` 首轮116件pytest rc=0/85.07s，总113.58s，仅mut_cover台账未生成失败；重生成后第二轮116件rc=0/81.26s，总110.48s、BAD空。补修后的最终影响入口日志为scratch `tmp-tail300-rulers-final.log`，终轮结果以实际回执为准，不复用未覆盖新输入的旧绿。

`_run_muts.py --cases _mut_layering.py _mut_tail300.py`：分层靶rc=0/37.2s，含300全部16处改回直查必红及既有五形态/正常引用/名单/防空扫；行为入口首版误认pytest断言输出格式，修正后基线绿、6/6真实断言红；ORM补修后7/7最终rc=0/20.3s（原单、撤销日期、N+1、出口锁参数、同步锁参数、完整输入上限、缓存旧统计值），正式app/tests逐字节摘要未变。KEY/SLOW_KEY登记及mut_cover生成台账同步。没有运行无关全部变异或刷新权威四态。

`chain_audit.py` rc=0：全站11条、102/102已接、红0；原C6未认领分支提示保持。两次重启均成功、/app=200；补修后最终完整 `_shell_smoke.py` 39段rc=0、console/page错误无（日志 `tmp-tail300-smoke-final.log`），壳源字节未改，基线20261012-0813。页面、导出与金额实际消费者由影响选集、真实API/测试库回归及真机共同核验。

**未验边界。** C2仍为静态import可解析模型的五形态；动态getattr/运行期ORM别名/原始SQL及app顶层/home/report_export不在该门禁扫面。隔离金额/锁回归不代表现场双用户并发压力测试；本轮未验证真实i8抓取、打印机投递、部署迁移或备份恢复，原C6覆盖提示及这些既有边界保持。无新页面/API形状变化；仅清300、不扩架构报告C–F，不提交、不推送。证据集中于本票，工作区开工无旧dirty。

**2026-10-12 · 终轮与销号回执。** _tail_close.py --id 300干跑核对后--apply，票done、活动行移出、排期迁历史，真源活跃2/已销号302。全部文书写回后的最终_run_rulers按开工基点rc=0、BAD空：116件pytest选集99.19s，总133.03s；语法/字节/链路/文书/mut_cover及_run_muts/_gatescope自测均通过。补修后最终真机39段约88s、rc=0；服务重启/200，壳字节未改。终轮实际回执补记后仅复核文书，不重复未变业务选集。HEAD仍befb2a90fcbe3b54a7614206e88ffb403d85cab8，无提交推送；全部未验边界如上。

**2026-10-12 · 提交推送授权。** 用户明确要求提交并推送，取代此前不提交/不推送边界；仅提交本轮300的23件修改，不含凭据或scratch。此前最终影响检查rc=0/BAD空、116件选测与最终39段真机证据输入未变，不重复业务检查；运行真实提交钩子，推送后核对远端master与本地HEAD。提交SHA与推送成功以Git记录和实际命令回执为准。
