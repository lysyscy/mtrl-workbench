"""`ACC-X-DEL-001` 跨域能力 · **删除的分档与二次确认**（`MOD-13` · §9.4）。

## ⚠️ 这一片的性质：**不是"写新功能"，是"给已有的删除出口补判据"**

取证（2026-09-20）发现：这条用例 8 个点原本 **0/8 全未绑定**，但**落点早就都在了** ——
`mod03_notice.notice_manual_actions.apply_manual_delete` ·
`mod03_notice.rules_repository.delete_row` · `mod08_inv.domain.boundary_violations` …
⇒ 缺的只是**断言**（`§9.4` 那套分档从没被机器钉过）。

## 本文件钉什么（本轮 4 条）

| 点 | 钉的事实 | 落点 |
|---|---|---|
| `001-01` | 删除前**列影响范围**，且是**真实计数**（逐行对得上，⛔ 不是"共 N 条"这种占位） | `plan_ui.delete_impact` |
| `001-04` | **i8 源数据行一律无删除入口**（对照：可删行必须有） | `mod08_inv.domain.boundary_violations` |
| `001-06` | 逐行 / 多选删除**都只删选中行**；**未确认就拒** | `plan_ui.delete_rows` |
| `001-07` | **撤销调整单只删该条**：i8 源数据一行不动、该行退出差异表 | `mod08_inv.domain` |

⏳ **尚未钉（落点已找到，留给下一轮）**：`001-02` 配置类硬删（`rules_repository.delete_row`）·
`001-08` §9.4 分档清单本身。

✅ `001-05`（手动行删除同步清归属与勾选）**已钉** —— 落点 `notice_manual_actions.apply_manual_delete`
（⚠️ 2026-09-21 · `T5` 拆分：自 `notice_actions` 整块搬来，判定与文案一字未变）。

⭐ **`001-03`（账号软删 = 行保留 / 可识别 / 可恢复）** —— 它一直卡在「等 `m15` 开工」（本仓那时
  全仓**0 处软删字段**）⇒ **`m15` 片 1 一落地它就解锁了**，本文件已补上。
  ⚠️ 与 `ACC-USR-MGMT-001/001-09`（同一件事）的分工：那边钉**函数行为**（同会话内存对象），
  本文件钉**分档归属 ＋ 真库往返**（换一个 session 再查）—— **两边都钉，⛔ 不复述对方**。
"""

from __future__ import annotations

import pathlib
import re
from decimal import Decimal

import pytest

import app

from app.core.errors import MustReportError
from app.core.errors import MustReportError as _MRE       # noqa: F401  （显式见于断言）
from app.mod03_notice import notice_manual_actions as NA
from app.mod03_notice import rules_repository as RR
from app.mod08_inv import domain as I
from tests.acc_plugin import acc

from tests.shell_src import SHELL, act_entry  # noqa: F401  ← `P4`① 读取点收敛

# ⭐ 2026-10-03（`TAIL-219` 批 2b）：本件原先自带剪刀 `_fn`（"标记 A → 标记 B"）——
#    已**整把删掉**，取段改走壳的语义口径（这里要的是 `ACT` 的一条 ⇒ `act_entry`）。⛔ 别写回来。


def _rows() -> list[dict]:
    """三行计划行（形状按 `delete_impact` 读的键给：`id` / `year_month`）。"""
    return [{"id": 11, "year_month": "2026-08", "doc_no": "P001"},
            {"id": 12, "year_month": "2026-08", "doc_no": "P002"},
            {"id": 13, "year_month": "2026-09", "doc_no": "P003"}]


def _results() -> dict:
    return {11: "完全匹配", 12: "金额不符", 13: "完全匹配"}


# ---------------------------------------------------------- `001-01` 影响范围


@acc("ACC-X-DEL-001", "001-01")
def test_删除前列出真实影响范围而不是占位():
    from tests.m03_action_helpers import _client, _notice
    client, fake = _client([_notice(11, is_manual=True, ph_id="MANUAL-11", bill_no="M11",
                                  project_name="项目甲", stat_paid=Decimal("70")), _notice(12)])
    impact = NA.manual_delete_impact(fake, 11)
    assert impact['notice_id'] == 11 and impact['label'] == 'M11'
    assert impact['project_name'] == '项目甲' and impact['stat_paid'] == '70.00'
    assert '70.00' in impact['message'] and not fake.deleted
    assert 'API.manualDeleteImpact(' in act_entry('ntDel')



# ---------------------------------------------------------- `001-04` 无删除入口


@acc("ACC-X-DEL-001", "001-04")
def test_i8源数据行一律无删除入口():
    """§4.2.7 / `NG-03`：**i8 抓取回来的行永不删**（源数据只读）⇒ 本页**连删除入口都不建**。

    ⚠️ 判据要求**两面都看**：「i8 源数据行一律无删除入口」＋「**对照：可删行必须仍有删除入口**」
       —— 只钉"没有"是不够的*（把整页的删除都删掉也能让前半句成立）*。
    """
    # ① i8 源数据那一页（库存单据）：不得出现删除动作
    bad = I.boundary_violations(action_ids=("delete", "del", "DELETE"))
    assert len(bad) == 3, f"删除动作没被拦住：{bad}"
    assert all("NG-03" in b for b in bad), "拦了但没说清依据（`NG-03`）"

    # ② 合规面：正常列 / 正常动作 ⇒ **一条都不报**（⛔ 不能"什么都报"来假装严格）
    assert I.boundary_violations(column_keys=("amount", "warehouse", "adj_amount")) == [], \
        "正常列被误判成违规 ⇒ 这个守卫会变成噪音、人就不看了"
    assert I.FORBIDDEN_ACTIONS == ("delete", "del"), "禁用的动作清单变了（要同批改本件与文档）"


# ---------------------------------------------------------- `001-02` 配置类硬删


@acc("ACC-X-DEL-001", "001-02")
def test_配置类数据硬删且被引用数据不随删():
    """§9.4 原文：「**配置类数据**（项目配置、规则配置等）→ **硬删除**」。

    ⚠️ 这条判据有两半，**两半都要钉**：
    - 「行数 −1」= 真的是硬删（⛔ 不是打标记 —— 打标记是**核心业务数据**那一档的做法）；
    - 「**被引用数据不随删**」= 删规则**不许顺手去改历史剔除标记** —— §4.2.2 明文
      「**改规则不重算历史**：已产生的剔除标记（`exclude_source=rule`）不受影响、也不重算」。
      ⚠️ 这一半最容易被"顺手补一个重算"给破坏（看着像做好事），所以用**真库计数**钉。
    """
    from app.core.db import session_scope
    from app.mod03_notice.models import PaymentNotice
    from sqlalchemy import func, select                                            # noqa: PLC0415

    # ① 硬删 = `s.delete(row)`（⛔ 不是"打一个 deleted 标记"）
    src = pathlib.Path(RR.__file__).read_text(encoding="utf-8")
    assert "s.delete(row)" in src, "配置类删除不是硬删（§9.4）"
    assert "deleted_at" not in src and "is_deleted" not in src, \
        "配置类出现软删字段 —— §9.4 的两档被搞混了"

    # ② 真删：加一条 → 删它 → 库里查不到
    with session_scope() as s:
        RR.ensure_seeded(s)                     # 库空则落出厂默认（幂等）
        n0 = len(RR.all_rows(s))
        row = RR.add_row(s, kind="biz_type", values="付款测试值", meaning="__自检__")
        rid = int(row.id)
        assert len(RR.all_rows(s)) == n0 + 1
        RR.delete_row(s, RR.get_row(s, rid))
        assert RR.get_row(s, rid) is None, "删完还查得到 ⇒ 不是硬删"
        assert len(RR.all_rows(s)) == n0, "行数没回到原值"

        # ③ 「被引用数据不随删」：删规则**不动**已有的剔除标记
        before = s.scalar(select(func.count()).select_from(PaymentNotice)
                          .where(PaymentNotice.excluded.is_(True)))
        RR.delete_row(s, RR.add_row(s, kind="biz_type", values="付款又一条", meaning="__自检__"))
        after = s.scalar(select(func.count()).select_from(PaymentNotice)
                         .where(PaymentNotice.excluded.is_(True)))
        assert after == before, (
            f"删规则把历史剔除标记改了（{before} → {after}）—— §4.2.2 明写「**改规则不重算历史**」"
            "；剔除行是**另一批数据**（`payment_notice.excluded`），删配置不该碰它")
        s.rollback()


# ---------------------------------------------------------- `001-05` 手动行删除


@acc("ACC-X-DEL-001", "001-05")
def test_手动行删除只删该行且清归属与勾选():
    """§4.2.6：「编辑 / 删除**只对手动新增行**开放；i8 抓取回来的行不受影响」。

    ⚠️ 三件一起看（缺一件就有一条路漏）：
    ① **唯一出口**：PRG 与 JSON API **共用** `apply_manual_delete`（⛔ 不许两份校验、不许两份文案）；
    ② **只删该行**：i8 行**连门都摸不到**（`assert_manual_editable` 当场拒）；
    ③ **壳侧同步**：删掉的 id 必须从这个会话的**勾选集**里退出来
       —— 否则汇总条会继续把它算进去（勾选一个**已经不存在的行**）。
    """
    # ① 唯一出口（两处都调它）
    assert "def apply_manual_delete(session, notice_id: int)" in \
        pathlib.Path(NA.__file__).read_text(encoding="utf-8"), "删除手动行没有唯一出口"
    api = pathlib.Path(NA.__file__).resolve().parents[0] / "notice_api_router.py"
    assert "apply_manual_delete" in api.read_text(encoding="utf-8"), \
        "JSON API 没走同一个出口（那就有了第二份校验/文案）"

    # ② i8 行**连门都摸不到**：`assert_manual_editable` 当场拒（不是"删了再报错"）
    with pytest.raises(MustReportError):
        NA.assert_manual_editable({"ph_id": "PH20260801001", "bill_no": "FKTZS001"})
    NA.assert_manual_editable({"ph_id": "MANUAL-abc123", "bill_no": ""})   # 手动行放行

    # ③ 壳侧：删完把 id 从勾选集里退出来；⛔ 且不许本地 splice 冒充删除
    ok = act_entry("ntDelOk")
    assert "pickSet.delete(id)" in ok, "删完没退出勾选集（汇总条会继续算一个不存在的行）"
    assert "splice" not in ok, "⛔ 壳里还在本地 splice 冒充落库"
    assert "API.manualDelete(" in ok, "删除没走后端端点"


# ---------------------------------------------------------- `001-06` 只删选中行


@acc("ACC-X-DEL-001", "001-06")
def test_只删选中行且未确认就拒():
    from tests.m03_action_helpers import _client, _notice
    from app.mod03_notice.models import PaymentNotice
    a, b = _notice(11, is_manual=True, ph_id="MANUAL-11"), _notice(12)
    client, fake = _client([a, b])
    assert 'API.manualDelete(' not in act_entry('ntDel')
    assert 'API.manualDelete(' in act_entry('ntDelOk')
    row, message = NA.apply_manual_delete(fake, 11)
    assert row is a and fake.deleted == [a]
    assert fake.by_model[PaymentNotice] == [b] and b.bill_no == 'B12'



# ---------------------------------------------------------- `001-03` 账号软删（等 m15 的那条）


@acc("ACC-X-DEL-001", "001-03")
def test_软删档的账号_行保留可识别可恢复且走真库往返():
    """claim：「**软删类（账号）= 行保留 / 可识别 / 可恢复**」（§9.4 的**软删那一档**）。

    ⚠️ 本条与 `ACC-USR-MGMT-001/001-09` 是**同一件事**，但**测法刻意不同**（⛔ 不复述对方）：
    - `001-09` 钉**函数行为**：调 `R.soft_delete(row)` 后看**同一个会话里的那个对象**；
    - 本文件钉**分档归属 ＋ 真库往返**：从「删除分档」那一侧确认
      **账号确实归在"软删"档**，而且**换一个会话再查**（⇒ 落的是库、不是内存）。

    ⭐ 为什么"换会话再查"是**必要**的、不是重复：`001-09` 那种同会话断言，
      在实现改成"只改内存、没 flush"时**照样绿**（对象上的字段当然变了）
      —— 而那种实现在真机上等于**没删也没留痕**。真库往返才能排除它。
    """
    from app.core.db import session_scope
    from app.mod15_user import domain as D
    from app.mod15_user import repository as R
    from app.mod15_user.models import UserAccount
    from sqlalchemy import func, select

    with session_scope() as s:
        R.ensure_seeded(s)
        actor = D.active_admins(R.all_users(s))[0]
        u = R.create(s, account="__自检_分档软删__", name="分档自检人", password="p")
        uid, name, acc = u.id, u.name, u.account
        n0 = len(R.all_users(s))
        R.soft_delete(s, uid, actor=actor)
        s.commit()                                   # ⚠️ 交给**真库**（下面要换会话查）

    # ⭐ 真库往返：**新会话**里逐条验三性
    with session_scope() as s:
        row = s.get(UserAccount, uid)
        # ① 行保留（⛔ 不是 `s.delete`）
        assert row is not None, "软删之后行没了 —— 那是硬删，不是 §9.4 的软删档"
        assert len(R.all_users(s)) == n0, "软删改了行数"
        # ② 可识别（账号名与人名都还在 —— 历史留痕里的人名要认得出来）
        assert row.account == acc and row.name == name, "软删改了账号名/姓名 —— 留痕里的人名会认不出来"
        assert R.by_account(s, acc) is not None, "按账号名找不到这一行了"
        # ③ 留痕（§9.4「软删除 **+ 留痕**」）
        assert row.deleted_at is not None and (row.deleted_by or "").strip(), "有删无痕"
        # ④ 可恢复（**在另一个会话里**恢复，再换会话确认）
        R.restore(s, uid)
        s.commit()
    with session_scope() as s:
        assert s.get(UserAccount, uid).deleted_at is None, "跨会话恢复不回来"
        # ⑤ 清理：本条**故意落库**（要跨会话）⇒ 必须自己收拾干净，⛔ 不能留给下一个用例
        R.soft_delete(s, uid, actor=actor)
        s.delete(s.get(UserAccount, uid))
        s.commit()
        assert s.scalar(select(func.count()).select_from(UserAccount)
                        .where(UserAccount.account == acc)) == 0, "自检行没清干净"


# ---------------------------------------------------------- `001-07` 撤销调整单


@acc("ACC-X-DEL-001", "001-07")
def test_撤销调整单只删该条且源数据不动():
    """2026-09-20 改写（原 claim 指着一个已撤的页）：**撤销调整单 = 只删这一条调整单**。

    ⚠️ 「删除」在这个域里的形态很特别：**删的是"人的判断"，不是"数据"** ——
       调整单撤掉之后，i8 原始行**还在**、原始金额**一字未动**，只是它**退出了差异表**。
       这正是 §9.4「源数据永不删」在差异这个场景下的落点。
    """
    raw = {"id": "IV-9", "doc_no": "CK009", "seq": 1, "material": "钢板",
           "warehouse": "甲仓", "amount": Decimal("500.00")}
    before = dict(raw)

    adj = I.make_adjustment(raw, Decimal("450.00"), "价差", operator="张伟")
    assert I.is_adjusted(I.with_adjustment(raw, adj)) is True

    cleared = I.with_adjustment(raw, {})                  # 撤销 = 去掉调整单这一层
    assert I.is_adjusted(cleared) is False, "撤销后仍算「调过」⇒ 差异表会留一条幽灵"
    assert cleared["amount"] == before["amount"] == Decimal("500.00"), \
        "撤销调整单**绝不能**碰到 i8 原始金额（源数据永不删、永不改）"
    assert raw == before, "连传入的源行都不该被就地改"


# ---------------------------------------------------------- `001-08` 分档本身

#: **软删 + 留痕**那一档的**物证**（§9.4 原文：「软删除 + 留痕」⇒ 得有"痕"这个字段）
SOFT_MARKS = ("deleted_at", "is_deleted", "voided_at", "archived_at", "defered_at", "removed_at")
#: **硬删**那一档的物证（真把行从表里拿掉）
HARD_MARKS = (".delete(", "sa_delete(")
#: 落库动作（用来区分"真在改库"与"只是算一算 / 变换内存数据"）
WRITE_MARKS = (".add(", ".flush(", ".delete(", ".execute(", "sa_delete(", ".merge(", ".commit(")


def _funcs(text: str) -> dict[str, str]:
    """顶层 `def` → 函数体（到下一个顶层 `def` / `class` 为止）。

    ⚠️ 必须**连 `class` 一起切** —— 只按 `def` 切的话，`class` 后面那些**方法**会被算进
       上一个顶层函数体内（方法那层有缩进、`^def` 不匹配）⇒ 顺手把别人的删除语句算到自己头上。
    """
    out: dict[str, str] = {}
    for part in re.split(r"(?m)^(?=def \w+\s*\(|class \w+)", text):
        m = re.match(r"def (\w+)\s*\(", part)
        if m:
            out[m.group(1)] = part
    return out


@acc("ACC-X-DEL-001", "001-08")
def test_删除分档穷尽且不交叉():
    """§9.4 的**分档清单本身**（claim 原文：「哪些软删 / 哪些硬删 / 哪些不能删」）。

    ⚠️ 判据钉的**不是**某一档的行为（那是 `001-02` / `001-04` 的活），而是**这张表本身**：

    ① **穷尽** —— 全仓每个"名字像删除"的函数都必须能归到某一档。
       ⛔ 最该防的是**第四种语义**：既不是真删库、也不是标记字段，而是"把 `status` 写成 `'deleted'`"
       之类 —— 那种删除**界面上看不出、统计也不重算**，是这条线上**最难查**的错。
    ② **不交叉** —— 声明"禁删"的模块**必须真的没有**删除出口
       （⛔ 防"`NG-03` 声明还在、实现里偷偷加一个 `delete_row`"）。
    ③ ⭐ **软删档双向开** —— 「有标记字段 ⇔ 有软删出口」。
       现在全仓标记字段 **0 处**（删的都是真删），这条现在**绿**；而 `m15` 用户管理落地
       （账号软删，§7.9 L480）时它**自动仍然成立**，⛔ 不用回来改断言 ——
       这才是"判据不绑死当前实现"的写法（⚠️ 反例：写死「软删出口必须 ≥ 1」⇒ 今天红、且今天**没有**可得的东西）。
    ④ **实档都得有人** —— ⛔ 防"清单里写了、实现里一个都没有"式假绿。
    """
    root = pathlib.Path(app.__file__).resolve().parent
    hard, soft, pure, unclear = [], [], [], []
    for p in sorted(root.rglob("*.py")):
        rel = str(p.relative_to(root))
        for name, body in _funcs(p.read_text(encoding="utf-8")).items():
            if "delete" not in name.lower() and "remove" not in name.lower():
                continue
            where = f"{rel}::{name}"
            rest = body.replace(f"def {name}", "", 1)          # ⚠️ 先去掉自身签名，免得数到函数名自己
            if any(k in body for k in HARD_MARKS):
                hard.append(where)                             # 真删（把行从表里拿掉）
            elif re.search(r"\b\w*delete\w+\s*\(", rest):
                pass                                           # 委派给别的删除出口（如 `apply_manual_delete`）
            elif any(k in body for k in SOFT_MARKS):
                soft.append(where)                             # 软删 + 留痕
            elif not any(k in body for k in WRITE_MARKS):
                pure.append(where)                             # 只读 / 纯内存变换 ⇒ **压根不是删除出口**
            else:
                unclear.append(where)

    # ① 穷尽：⛔ 不许有"落了库、但说不清算哪一档"的删除
    assert not unclear, (
        "这些函数名里有 delete/remove、又**真的在动库**，却既不是真删、也没有留痕字段"
        " ⇒ 归属不明（第四种删除语义）：\n  " + "\n  ".join(unclear)
        + "\n  ⇒ 要么改成 `s.delete`（硬删档），要么加留痕字段（软删档），要么它其实只该是只读。")

    # ② 不交叉：`NG-03` 说库存单据页不新增删除入口 ⇒ 那个模块里就不许有删除出口
    inv_bad = [f"{p.relative_to(root)}::{n}"
               for p in sorted((root / "mod08_inv").rglob("*.py"))
               for n in _funcs(p.read_text(encoding="utf-8"))
               if "delete" in n.lower() or "remove" in n.lower()]
    assert not inv_bad, (
        "`mod08_inv` 声明了 `NG-03`（本页不新增删除入口）却出现了删除出口：\n  "
        + "\n  ".join(inv_bad) + "\n  ⇒ 分档**交叉**了：声明禁删，实现却在删。")

    # ③ 软删档双向开（今天 0 处标记字段 ⇔ 今天没有软删出口；`m15` 落地后 ⇔ 自动反过来）
    with_marks = [f"{p.relative_to(root)}" for p in sorted(root.rglob("*.py"))
                  if any(k in p.read_text(encoding="utf-8") for k in SOFT_MARKS)]
    assert bool(soft) == bool(with_marks), (
        f"软删档**两半对不上**：留痕字段 {len(with_marks)} 处、软删出口 {len(soft)} 个"
        f" —— 要么有字段没用（那 `§9.4` 的\"软删 + 留痕\"白写）、要么有软删没留痕（那就不是软删）"
        f"\n  有字段的文件：{with_marks}\n  软删出口：{soft}")

    # ④ 实档都得有人（⛔ 防空清单假绿）
    assert len(hard) >= 6, f"硬删档只有 {len(hard)} 个出口 —— 太少，解析可能失效了：{hard}"
    assert len(pure) >= 3, (
        f"「名字像删除、其实不是删除出口」只认了 {len(pure)} 个 —— 太少。"
        "⚠️ 这一类**必须存在**（`delete_impact` 只算影响、`delete_rows` 是视图层纯变换、"
        "`remove_from_batch` 是移出付款批次），它们被误当成删除出口正是分档最容易错的地方。")
