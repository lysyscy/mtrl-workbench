"""反向灵敏度 · **M5 集采域域内核**（`ACC-JC-*` 那 11 条断言的区分力自检）。用完即删。

做法：逐条把 `app/mod11_jc/domain.py` **故意改坏** ⇒ 对应断言必须**变红** ⇒ 改回后**逐字节复原**（MD5 校验）。

⚠️ **本脚本比老的 `_mut_*.py` 多做了一件事（新纪律，建议后续脚本照做）**：
   跑 `pytest -k` **子集**时把 `ACC_RESULTS_PATH` 指到**临时文件** ——
   否则 acc 插件会把"只跑了这几个测试"的结果写回工程基线 `artifacts/acc_results.json`，
   于是 `doc_audit` 的 `T4`（四态数字核对）**当场报错**（2026-09-19 实测踩到：基线被写成
   "绿 15 · 未绑定 495"）。⛔ 子集运行**永远**把结果指到外面。

跑法：`python tools/_mut_jc.py`（期望：命中 N/N · SKIP 0 · MD5 逐字节复原 ✅）
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BE = ROOT / "backend"

PY = BE / ".venv" / "Scripts" / "python.exe"
SRC = BE / "app" / "mod11_jc" / "domain.py"
TEST = "tests/test_acc_jc_domain.py"
TEST_LIST = "tests/test_acc_jc_list.py"
TEST_WRITE = "tests/test_acc_jc_write.py"          # ⭐ M5-4 写路径（2026-09-19 追加）
TEST_FETCH = "tests/test_acc_jc_fetch.py"          # ⭐ M5-6 抓取落库（2026-09-19 追加）
TEST_ORCH = "tests/test_acc_jc_fetch_orch.py"      # ⭐ M5-6 抓取编排（2026-09-19 追加）
TEST_PAYLINK = "tests/test_acc_jc_pay_link.py"     # ⭐ M5-5 双向引用（2026-09-19 追加）
TEST_SUP = "tests/test_acc_sup_match.py"           # ⭐ M5-5 供应商自动匹配（2026-09-19 追加）
TEST_IMPORT = "tests/test_acc_jc_import.py"        # ⭐ M5-8 Excel 解析层（2026-09-19 追加）
TEST_API04 = "tests/test_i8_contract_api04.py"     # ⭐ API-04 取数层（2026-09-19 追加）

#: 允许被变异的目标文件（判据散在域内核 / 仓储 / 装配 / 模型四件里）
TARGETS: list[Path] = [
    SRC,
    BE / "app" / "mod11_jc" / "repository.py",
    BE / "app" / "mod11_jc" / "fetch_service.py",      # ⭐ M5-6 抓取编排（2026-09-19 追加）
    BE / "app" / "mod03_notice" / "list_view.py",      # ⭐ M5-5 关联态的**唯一接入点**（2026-09-19 追加）
    BE / "app" / "mod03_notice" / "sup_match.py",      # ⭐ M5-5 供应商自动匹配（2026-09-19 追加）
    BE / "app" / "mod11_jc" / "excel_parse.py",        # ⭐ M5-8 Excel 解析层（2026-09-19 追加）
    BE / "app" / "mod11_jc" / "import_service.py",     # ⭐ M5-8 导入服务（2026-09-19 追加）
    BE / "app" / "mod02_i8" / "contract_source.py",    # ⭐ API-04 取数层（2026-09-19 追加）
    BE / "app" / "mod11_jc" / "service.py",
    BE / "app" / "mod11_jc" / "models.py",
]


def locate(anchor: str, srcs: dict[Path, bytes]) -> Path:
    """锚点**在哪一件**里 ⇒ 就改那一件（⚠️ 锚点必须唯一命中，否则停手）。

    ⚠️ 2026-09-19：判据不只在 `domain.py`（读路径在 `repository.py` / `service.py`）⇒
       **别把目标文件写死**，否则新加的变异会"永远命中 0 次"（很像锚点写错，实为找错了文件）。
    """
    hits = [p for p, b in srcs.items()
            if anchor.encode("utf-8") in b or anchor.encode("utf-8").replace(b"\n", b"\r\n") in b]
    if len(hits) != 1:
        raise LookupError(f"锚点在 {len(hits)} 件里命中（期望 1）：{anchor[:60]!r}")
    return hits[0]

#: (说明, 老片段, 新片段, 该变红的测试名)
MUTS: list[tuple[str, str, str, str]] = [
    # ---- 结算两条路径（001-10）
    ("结算改口径：有贸易公司也去取供应商发票（两条路串用）",
     "    if str(trade_co or \"\").strip():\n        return trade_invoice_sum(invoices)\n    return supplier_invoice_sum(invoices)",
     "    if str(trade_co or \"\").strip():\n        return supplier_invoice_sum(invoices)\n    return supplier_invoice_sum(invoices)",
     "test_结算两条路径各取各自子表合计_互不串用"),
    ("结算让两侧相加（instead of 二选一）",
     "    if str(trade_co or \"\").strip():\n        return trade_invoice_sum(invoices)\n    return supplier_invoice_sum(invoices)",
     "    return trade_invoice_sum(invoices) + supplier_invoice_sum(invoices)",
     "test_结算两条路径各取各自子表合计_互不串用"),
    # ---- 欠款（001-09）
    ("欠款改成「结算 ＋ 付款」（方向反了）",
     "    return (Decimal(str(settle or 0)) - Decimal(str(pay or 0))).quantize(Decimal(\"0.01\"))",
     "    return (Decimal(str(settle or 0)) + Decimal(str(pay or 0))).quantize(Decimal(\"0.01\"))",
     "test_主表金额列只读汇总_改子表即改欠款"),
    ("主表金额列改成「落库式」：只认第一笔付款（后续子表变化不再影响）",
     "    inv = supplier_invoice_sum(invoices)\n    tinv = trade_invoice_sum(invoices)\n    pay = pay_sum(payments)",
     "    inv = supplier_invoice_sum(invoices)\n    tinv = trade_invoice_sum(invoices)\n    pay = pay_sum(payments[:1])                                   # （变异）只认第一笔 ⇒ 子表再变也不动",
     "test_主表金额列只读汇总_改子表即改欠款"),
    # ---- 子表校验（001-05 / 001-06）
    ("发票日期不再必填（只填金额也放行）",
     "    if not _date_text(date):\n        return MSG_NEED_DATE",
     "    if False:\n        return MSG_NEED_DATE",
     "test_子表日期必填_只填金额不填日期不得落库"),
    ("付款校验放宽（与发票不再同款）",
     "    return invoice_problem(date, amount)",
     "    return None",
     "test_子表日期必填_只填金额不填日期不得落库"),
    ("金额只拦非数字、不再拦 0 与负数（与 MOD-09 串了）",
     "    if value <= 0:\n        raise ValueError(MSG_BAD_AMOUNT)",
     "    if False:\n        raise ValueError(MSG_BAD_AMOUNT)",
     "test_发票金额只走大于零这一个出口_不设上限"),
    ("金额加了上限（口径说不设上限）",
     "    if value <= 0:\n        raise ValueError(MSG_BAD_AMOUNT)",
     "    if value <= 0 or value > Decimal(\"1000000\"):\n        raise ValueError(MSG_BAD_AMOUNT)",
     "test_发票金额只走大于零这一个出口_不设上限"),
    # ---- 自由文本（001-15）
    ("域内核偷偷引入付款方式枚举校验（DEV-J-03 明令不许）",
     "def parse_amount(raw) -> Decimal:",
     "def method_problem(raw) -> str | None:\n    \"\"\"（变异）引入枚举校验 —— 违反 DEV-J-03。\"\"\"\n    return None if str(raw or \"\").strip() in (\"现汇\", \"承兑\", \"供应链\") else MSG_BAD_AMOUNT\n\n\ndef parse_amount(raw) -> Decimal:",
     "test_付款方式自由文本_不得引入枚举校验"),
    # ---- 三态（ACC-JC-FETCH-001/001-10）
    ("抓取把人工标记冲掉（一律回「待确认」）",
     "    v = str(current if current is not None else \"\").strip()\n    if v in (TAG_IN, TAG_OUT):\n        return v\n    return TAG_PENDING",
     "    return TAG_PENDING",
     "test_抓取不覆盖已人工标记的行"),
    ("归一函数把认不出的值猜成「纳入台账」",
     "    return v if v in TAGS else TAG_PENDING",
     "    return v if v in TAGS else TAG_IN",
     "test_抓取不覆盖已人工标记的行"),
    # ---- 去重 / 候选 / 金额提示（ACC-JC-PAY-001）
    ("去重形同虚设（永不拦）",
     "    return notice_id is not None and int(notice_id) in {int(x) for x in (existing_notice_ids or ())}",
     "    return False",
     "test_全库去重_同一通知书只能被引用一次"),
    ("去重只在本合同内（口径是「不分合同」）",
     "    return notice_id is not None and int(notice_id) in {int(x) for x in (existing_notice_ids or ())}",
     "    return False  # 变异：只在同合同内查 ⇒ 跨合同重复引用漏过",
     "test_全库去重_同一通知书只能被引用一次"),
    ("关联金额不一致 ⇒ 直接拦截（口径是只提示不拦）",
     "    if a == d:\n        return None",
     "    if a != d:\n        raise ValueError(\"金额不一致\")\n    if a == d:\n        return None",
     "test_关联不做金额校验_不一致只提示不拦截"),
    ("候选丢了「当前那张无条件保留」",
     "        if current_id is not None and int(c.get(\"id\") or 0) == int(current_id):\n            out.append(c)",
     "        if False:\n            out.append(c)",
     "test_候选范围收窄到本项目与已匹配供应商_且当前那张无条件保留"),
    ("候选不收窄供应商（候选范围过宽）",
     "        if sup and str(c.get(\"supplier\") or \"\").strip() != sup:\n            continue",
     "        if False:\n            continue",
     "test_候选范围收窄到本项目与已匹配供应商_且当前那张无条件保留"),
    ("候选不看项目键（跨项目串）",
     "        if str(c.get(\"project_key\") or \"\").strip() != key:\n            continue",
     "        if False:\n            continue",
     "test_候选为空时给提示且不允许提交"),
    # ---- 读路径（仓储 / 装配）：M5-3
    ("列表的「项目」筛选被忽略（筛了等于没筛）",
     "    if str(project_key or \"\").strip():\n        stmt = stmt.where(Project.warehouse_name == str(project_key).strip())",
     "    if False:\n        stmt = stmt.where(Project.warehouse_name == str(project_key).strip())",
     "test_项目筛选键是仓库名_且筛选后行数独立复算_复位回全量"),
    ("列表的合计行漏掉「欠款」列（合计与逐行相加不一致）",
     "        for k in D.SUM_KEYS:\n            totals[k] = totals[k] + Decimal(str(row.get(k) or 0))",
     "        for k in D.SUM_KEYS:\n            totals[k] = totals[k] + Decimal(str(row.get(k) or 0))\n        totals[\"debt\"] = D.ZERO  # （变异）欠款列不参与合计",
     "test_合计行各金额列独立复算"),
    ("明细里两张发票子表混在一起给（不再按 kind 分）",
     "        \"supplier_invoices\": [r for r in invoices if r[\"kind\"] != \"trade\"],\n        \"trade_invoices\": [r for r in invoices if r[\"kind\"] == \"trade\"],",
     "        \"supplier_invoices\": list(invoices),\n        \"trade_invoices\": list(invoices),",
     "test_派生金额由子表现算_改子表即改欠款"),
]


#: ⭐ **M5-4 写路径**（2026-09-19 追加）—— 4 条，逐条钉住那条判据的**唯一**实现点。
#: ⚠️ 前三条都在"**默认值 / 范围 / 白名单**"上：它们正是**最容易被人顺手改坏、而测试若只测 happy path 就发现不了**的地方。
MUTS += [
    ("手工新增的三态默认被改成「待确认」（与抓取默认同源了）",
     "DEFAULT_TAG_ON_CREATE = TAG_IN",
     'DEFAULT_TAG_ON_CREATE = "待确认"',
     "test_手工新增的三态默认是纳入台账"),                      # 001-07
    ("批量标记丢掉 id 过滤（一次改全表 —— 越过了只作用勾选行）",
     "select(JcContract).where(JcContract.id.in_(ids))",
     "select(JcContract)",
     "test_批量标记只作用勾选行"),                              # 001-05
    ("白名单里混进 `tag`（三态被主表编辑口子绕过）",
     '    "arch", "arch_no", "ret_date",\n)',
     '    "arch", "arch_no", "ret_date", "tag",\n)',
     "test_收发登记三列与备注可手改并落值"),                     # 001-12
    ("发票校验被短路（缺日期也落库）",
     "    bad = D.invoice_problem(date, amount)",
     "    bad = None  # 故意短路",
     "test_发票子表字段是日期加金额"),                            # 001-04
    # ---- M5-6 抓取落库（2026-09-19 追加）
    ("重抓时把三态一律刷成「待确认」（人工标记被冲掉）",
     "cur.tag = D.tag_after_fetch(cur.tag)",
     "cur.tag = TAG_PENDING",
     "test_再次导入不覆盖旁路字段"),                             # 001-09 / 001-10
    ("无编号的行被静默丢掉（不计数）",
     "        if not no:\n            skipped += 1\n            continue",
     "        if not no:\n            continue",
     "test_落库幂等_按合同编号"),                                # 实现层自检（禁静默）
    # ---- M5-6 抓取编排（2026-09-19 追加）
    ("「先同步常用项目」被跳过（拿旧档案直接判 ⇒ 该纳管的会被判成不需要）",
     "                do_sync = sync or sync_and_archive",
     "                do_sync = lambda *a, **k: {}  # 故意不同步",
     "test_先同步常用项目再匹配"),                               # ⭐ 顺序断言
    ("同步的兜错只兜窄异常（同步一失败就把整个抓取打掉）",
     "                except Exception as exc:                        # noqa: BLE001 —— 降级，不抛",
     "                except ValueError as exc:                       # 故意只兜窄的",
     "test_同步失败不拖垮抓取"),                                 # ⭐ 安全绳断言
    # ---- M5-5 付款域双向引用（2026-09-19 追加）
    ("换合同时**不摘旧的**（一条通知书挂上两张合同 = 破掉一对一）",
     "        moved_from = int(old.contract_id)\n        R.delete_payment(s, old.id)",
     "        moved_from = int(old.contract_id)\n        pass  # 故意不摘旧的",
     "test_一对一_换合同先解绑再写新"),                            # 001-03
    ("关联态的接入点退回「恒为无关联」（双向可见那一侧就断了）",
     "        if nid is not None:\n            grouped.setdefault(int(nid), []).append(int(cid))\n"
     "    return lambda notice_id: grouped.get(int(notice_id), [])",
     "        if nid is not None:\n            grouped.setdefault(int(nid), []).append(int(cid))\n"
     "    return lambda notice_id: False  # 故意退回恒 False",
     "test_两个方向写同一份记录"),                                # 001-01
    # ---- M5-5 供应商自动匹配（2026-09-19 追加）
    ("片段长度写成 `level + 2`（**复刻壳里真出现过的那个 bug**：等级越高片段越长，却不报错）",
     "    n = FRAG_LEN_OFFSET - level",
     "    n = level + 2",
     "test_片段长度必须等于6减等级"),
    ("探测顺序**反了**（先短后长 ⇒ 2 字片段把一堆无关供应商扯进来）",
     "    for level in range(1, MAX_LEVEL + 1):",
     "    for level in range(MAX_LEVEL, 0, -1):",
     "test_先长后短"),                                            # 一个文件里的多个用例按 -k 一起跑
    # ---- M5-8 Excel 解析层（2026-09-19 追加）
    ("合并格**不铺满**（`供应商合同总价` 那一支整支丢掉，却不报错）",
     "    out = [[str(v or \"\").strip() for v in row] for row in grid]\n"
     "    for r1, r2, c1, c2 in merges:",
     "    out = [[str(v or \"\").strip() for v in row] for row in grid]\n"
     "    for r1, r2, c1, c2 in []:",
     "test_合并格要按真实合并区铺满"),
    ("表头探测改回「数**单元格**个数」（被重复列名骗 ⇒ 认成第 3 行）",
     "        return len({h for v in row for h in HEADER_HINTS if h in str(v)})",
     "        return sum(1 for v in row for h in HEADER_HINTS if h in str(v))",
     "test_表头探测按不同词计数"),
    ("幂等键**恒不相等**（重传同一个文件 ⇒ 合同翻倍）",
     "    return (\n        str(row.get(\"contract_date\") or \"\").strip(),",
     "    return (\n        str(id(row)),  # 故意的：每次都不一样",
     "test_落库幂等"),
    # ---- API-04 取数层（2026-09-19 追加）
    # ⚠️ 原先这条是「材料名回归无脑取第 2 段」—— **已随函数一起删掉**：
    #    2026-09-19 定案材料名不再拆单据名（改**逐条问详情** → `ItemName`），
    #    `_material_from_bill_name` 整个函数没了 ⇒ 那条变异的锚点必然失效。
    #    ⛔ **不能让失效的变异留在清单里**（会永远 SKIP，把"没验过"伪装成"验过了"）。
    # ⚠️ 也别把它改成指向新测试 —— 那是**两回事**：新测试钉的是"日期过滤要包一层"。
    ("日期过滤**少包一层**（`queryfilter` 直接放内层 ⇒ i8 照样返回全量、**也不报错**）",
     "    query = json.dumps({\"queryFilter\": inner}, ensure_ascii=False) if since else \"\"",
     "    query = inner if since else \"\"",
     "test_日期过滤必须包一层queryFilter"),
]


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def _fit(fragment: str, sample: bytes) -> bytes:
    """把锚点 / 新片段**按目标文件的真实行尾**归一。

    ⚠️ 2026-09-19 实测踩到：本仓 `.py` 的**行尾不统一**（有的 LF、有的 CRLF）——
       多行锚点不归一 ⇒ **永远"命中 0 次"**（单行锚点看不出来，于是"一半能中、一半全 SKIP"，很像锚点写错）。
    """
    b = fragment.encode("utf-8")
    if b"\r\n" in sample:
        return b.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    return b.replace(b"\r\n", b"\n")


def run_one(case: str) -> bool:
    """跑**一个**断点；⚠️ 结果写到**临时文件**（⛔ 别碰工程基线，见文件头）。"""
    with tempfile.TemporaryDirectory() as td:
        env = dict(os.environ)
        env["ACC_RESULTS_PATH"] = str(Path(td) / "acc_tmp.json")
        r = subprocess.run(
            [str(PY), "-m", "pytest", "-q", "-k", case, TEST, TEST_LIST, TEST_WRITE, TEST_FETCH, TEST_ORCH,
             TEST_PAYLINK, TEST_SUP, TEST_IMPORT, TEST_API04],
            cwd=str(BE), capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
        )
    return r.returncode == 0


def main() -> int:
    srcs = {p: p.read_bytes() for p in TARGETS}
    digests = {p: hashlib.md5(b).hexdigest() for p, b in srcs.items()}
    hit = miss = 0
    for desc, old, new, case in MUTS:
        try:
            tgt = locate(old, srcs)
        except LookupError as exc:
            print(f"  ⛔ {desc} —— {exc} ⇒ **未验证**")
            miss += 1
            continue
        base = srcs[tgt]
        oldb, newb = _fit(old, base), _fit(new, base)
        cnt = base.count(oldb)
        if cnt != 1:
            print(f"  ⛔ {desc} —— 锚点命中 {cnt} 次（期望 1）⇒ **未验证**")
            miss += 1
            continue
        tgt.write_bytes(base.replace(oldb, newb, 1))
        green = run_one(case)
        tgt.write_bytes(base)
        red = not green
        print(("  ✅ " if red else "  ⛔ 未命中 ") + desc + f"  → `{case}` " + ("变红" if red else "**仍是绿的**"))
        hit += red

    ok = all(p.read_bytes() == srcs[p] and hashlib.md5(srcs[p]).hexdigest() == digests[p] for p in TARGETS)
    print(f"\n  命中 {hit}/{len(MUTS) - miss}  · SKIP {miss}  · 逐字节复原：{'✅' if ok else '❌ 没复原'}")
    return 0 if (hit == len(MUTS) and ok) else 1


if __name__ == "__main__":
    sys.exit(main())
