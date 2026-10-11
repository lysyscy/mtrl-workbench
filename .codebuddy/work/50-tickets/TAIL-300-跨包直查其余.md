# TAIL-300: 清空分层门禁 C2 的待清名单：其余 11 处跨包直查逐处改走对方服务台出口（含 mod11 那处双主人 join；mod09 只许走原单出口，不得叠加调整单）

**What to build:** 清空分层门禁 C2 的待清名单：其余 11 处跨包直查逐处改走对方服务台出口（含 mod11 那处双主人 join；mod09 只许走原单出口，不得叠加调整单）

**Blocked by:** TAIL-299（门禁 C2 与其待清名单先落地）

**Status:** ready-for-agent

- [ ] **待清名单清零**：`_ALLOW_C2_PENDING` 空（`_C2_PENDING_START` 留作历史起点），`test_layering.py` 全绿。
- [ ] **逐处走主人包出口**（11 行清单见 Comments）：每处**改前先核**该出口是否已存在（`mod03_notice.service` / `mod05_flow.service` / `mod08_inv.service` / `mod11_jc.service` / `mod02_i8`）；不存在则按施工图 §3.2 的取舍表判「值得开 / 该登记例外」，⛔ 不为单调用者单开转手层。
- [ ] ⭐ **双主人 join**（`mod11_jc/repository.py:138`：mod03 的 `stat_paid` ＋ mod05 的最近生效流水日期）：两个主人各出**批量出口**（一次给一批通知书的值，⛔ 不准 N+1；返回形状要能直接喂回现在那段装配）。
- [ ] ⛔ **mod09 那处的陷阱**：只能走 `mod08_inv.service.load_original_details`（原单 · **不叠加**人工调整）＋ 本侧取那 5 个键；**换 `load_rows` = 把人工调整并进自动项 = 第二套口径** ⇒ 判据必须钉住「自动项不含调整单」这条。
- [ ] **锁那 1 处**（`mod05_flow/router.py:265`，付款临界区）：登记为 `_ALLOW_C2_BY_DESIGN`（理由 = 撤销付款临界区必须在**同一事务**内锁通知书行），**不进 pending**；并在该处补一句「为何在本侧锁」的注释（现在附近没有）。
- [ ] **反向灵敏度**：每改一处，对应隔离自证能造红（或复跑 B1 那支的对应靶）；`mut_cover` 台账同步。
- [ ] **收尾**：`_impactscope` 实选集 ＋ `chain_audit`（改的是取数出口，全站链路对账要过）；若某处的 API 返回形状变了 ⇒ **那一处补真机**；票 Comments 记证据与未验边界。

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
