"""`MOD-11` 抓取**编排**（`M5-6`）的实现层自检 —— 离线 · 不连 i8（取数件全部注入）。

守的是三条**顺序/边界**事实（它们错了都不会报错，只会**静默出错**）：
1. ⭐ **先同步常用项目 ⇒ 再匹配** —— 用户 2026-09-19 明确「集采抓取也要纳入全自动建档的一环」；
   反过来的后果 = 把**该纳管的项目误判成"不需要"**（静默漏掉，最坏的一类错）；
2. **匹配不上 ⇒ 不落库**（= i8 常用列表里也没有 = 不需要 · 用户口径）；
3. **同步失败不拖垮抓取**（照 `mod08` / `recovery` 的安全绳：降级并进回执，合同照常落）。

⚠️ 库级断言**一律非破坏**：末尾 `s.rollback()`（⛔ 一行不留）。
⚠️ 本文件用 `@acc()` 显式声明**不绑判据点**：`M5-6` 剩下的判据点（`001-01` 触发方式 · `001-02` 按月弹窗）
   都还在**待修订**（用户已定"只人工点击"、接口无月份参数）⇒ 现在绑会把口径钉错。
"""

from __future__ import annotations

from app.core.db import session_scope
from app.mod01_projects import repository as pj_repo
from app.mod01_projects.models import TYPE_NORMAL
from app.mod01_projects.sync_service import sync_and_archive
from app.mod11_jc import fetch_service as FS
from app.mod11_jc import repository as R
from tests.acc_plugin import acc

WH_NEW = "__自检仓_抓取新项目__"
FULL_NEW = f"{WH_NEW}项目(TBLX9999000001)"


def _fetch_rows() -> list[dict]:
    """两条取数结果：一条的项目名**归一化后**与"档案里的新项目"相等，一条谁都不认。"""
    return [
        {"contract_no": "__自检_F_1__", "project_name": FULL_NEW, "sign_date": "2026-09-15",
         "material_name": "主材钢材", "supplier_name": "业祥", "contract_amt": "100",
         "remark": ""},
        {"contract_no": "__自检_F_2__", "project_name": "档案里没有的项目", "sign_date": "2026-09-15",
         "material_name": "管件", "supplier_name": "尚坤", "contract_amt": "200", "remark": ""},
    ]


def _sync_new_project(s, *, load_common=None, load_warehouses=None) -> dict:
    """注入的"同步"：把**新项目**推进档案（模拟"用户在 i8 里把它加进常用列表"）。"""
    return sync_and_archive(
        s,
        load_common=lambda: [{"name_full": FULL_NEW, "phid": "9", "code": "TBLX9999000001", "ab": ""}],
        load_warehouses=lambda: [{"warehouse_name": WH_NEW, "owner_full_name": FULL_NEW}],
    )


def _sync_fail(s, *, load_common=None, load_warehouses=None) -> dict:
    raise RuntimeError("模拟：i8 名单取不到")


@acc()
def test_先同步常用项目再匹配_否则会把该纳管的判成不需要():
    """⭐ 顺序断言：**同步之后**那条原本"档案里没有"的项目才能匹配上。

    ⚠️ 这条要能红：把 `run_fetch` 里"先同步"那一步删掉 / 挪到匹配之后 ⇒ `matched` 会变成 0。
    """
    with session_scope() as s:
        # 先造一条**已被别的流程用过**的普通项目（⛔ 与本用例要匹配的那个无关）
        pj_repo.create_project(s, project_type=TYPE_NORMAL, name_full="__自检_别的项目__",
                               warehouse_name="__自检仓_别的__", phid="")
        s.flush()
        assert R.one_by_no(s, "__自检_F_1__") is None, "前置：库里本没有这张合同"

        out = FS.run_fetch(s, confirmed=True, fetch=lambda c: _fetch_rows(), sync=_sync_new_project)

        assert out["ok"] is True and out["degraded"] is False
        assert out["fetched"] == 2
        assert out["matched"] == 1, "⭐ 同步把新项目建了档 ⇒ 它那条必须匹配上（顺序对了才有这个数）"
        assert out["unmatched"] == 1, "档案里没有的那条 ⇒ 匹配不上"
        assert [p["name"] for p in out["unmatched_projects"]] == ["档案里没有的项目"], \
            "回执要**报出**匹配不上的项目名（禁静默）"

        # ② 匹配上的落了库、匹配的**没落**
        assert R.one_by_no(s, "__自检_F_1__") is not None, "匹配上 ⇒ 必须落库"
        assert R.one_by_no(s, "__自检_F_2__") is None, "匹配不上 ⇒ **不落库**（= 不需要）"
        assert R.one_by_no(s, "__自检_F_1__").tag == "纳入台账", "抓取落的默认「纳入台账」（`TAIL-97`）"
        s.rollback()


@acc()
def test_同步失败不拖垮抓取_降级进回执且仍按现有档案匹配():
    """⭐ 安全绳断言：同步那一步炸了 ⇒ **抓取照常完成**（数据与档案是两件事）+ 回执里说清。

    ⚠️ 这条要能红：把 `run_fetch` 里那个 `try/except` 去掉 ⇒ 整个抓取会抛出去。
    """
    with session_scope() as s:
        out = FS.run_fetch(s, confirmed=True, fetch=lambda c: _fetch_rows(), sync=_sync_fail)
        assert out["ok"] is True, "同步失败 ⛔ 不许把抓取一起打掉"
        assert isinstance(out.get("sync"), dict) and out["sync"].get("degraded") is True, \
            "降级必须**显式**进回执（禁静默）"
        assert "同步失败" in str(out["sync"].get("message")), "回执里要有那句说明"
        assert out["matched"] == 0 and out["unmatched"] == 2, "按**现有**档案匹配 ⇒ 两条都不认"
        assert "⚠️" in out["message"], "降级那句要出现在给人看的那行 message 里"
        s.rollback()


@acc()
def test_未二次确认不写执行记录也不动数据():
    """用法错误（没二次确认）⇒ 抛 `MustReportError`，⛔ 不写执行记录、不碰档案。"""
    from app.core.errors import MustReportError

    with session_scope() as s:
        before = R.count_contracts(s)
        try:
            FS.run_fetch(s, confirmed=False, fetch=lambda c: _fetch_rows())
        except MustReportError as exc:
            assert FS.KICK_WARNING in str(exc), "报错里要带上「会顶号」的提醒"
        else:
            raise AssertionError("没二次确认必须抛 MustReportError")
        assert R.count_contracts(s) == before, "一行都不许动"
        s.rollback()
