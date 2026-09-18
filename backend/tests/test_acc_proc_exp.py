"""`MOD-06` 过程资料**导出**的验收断言（离线 · 不连库）—— **纯函数那一半**。

对应判据 `ACC-RPT-EXP-001`（口径主人 =《说明书》§7.1）：
- `001-01` 导出 = **每项目一份**文件；**≥2 个项目打成 zip**（清单与文件名由同一出口给）
- `001-02` 展开区**默认选中本页当前项目**（且不改动页面的**单选**项目）；**动过但清空了 ⇒ 保持空**
- `001-04` **取数跟随当前所显示的那张表**（三张表同形态、只有数据与文件名不同）

⚠️ 2026-09-18（`TAIL-27` · `§19` **批 2**）：旧**服务端页**的导出展开区整件已删（授权 `D18`）——
   原先钉在页面 html 上的那些（checkbox 面板 / 全选清空 / `data-exp-tab` / 落在 `.tw` 之外 …）
   已按 `§19` 铁律**搬到壳**（⛔ 判据不删）：`tests/test_wired_m06.py` 的
   「导出展开区是多选_每项目一份_多项目打zip」·「一个项目都没选时导出按钮禁用」·
   「导出展开区默认选中本页当前项目」·「导出取数跟随当前所显示的表」✓。
   本文件此后只守**纯函数出口**（`domain.export_manifest` / `export_selection` / `tab_name` …）。
"""

from __future__ import annotations

from app.mod06_proc import domain as D
from app.mod06_proc.service import build_page_data, parse_state
from tests.acc_plugin import acc
from tests.m06_helpers import FakeSession, dataset

CASE = "ACC-RPT-EXP-001"
YM = "2026-09"                          # 纯函数用（不受"今天"影响）


def _data(**params) -> dict:
    return build_page_data(FakeSession(dataset()), parse_state(params))


def _cands() -> list[str]:
    """候选项目（**≥2 个**——否则下面几条断言失去区分力）。"""
    cands = _data()["export"]["projects"]
    assert len(cands) >= 2, f"候选不足 2 个（实得 {cands}）⇒ 本件多条断言失去区分力"
    return cands


# ------------------------------------------------------------ 001-01 每项目一份 · ≥2 打 zip


@acc(CASE, "001-01")
def test_每项目一份文件_多项目打成zip():
    cands = _cands()
    one = D.export_manifest([cands[0]], tab=D.TAB_ADJUSTED, ym=YM)
    assert one["count"] == 1 and one["zip"] is False and one["zip_name"] == ""
    assert len(one["files"]) == 1 and one["files"][0]["project"] == cands[0]

    two = D.export_manifest(cands[:2], tab=D.TAB_ADJUSTED, ym=YM)
    assert two["count"] == 2 and two["zip"] is True
    assert two["zip_name"] == f"{D.EXPORT_DOMAIN}_{YM}.zip"
    assert [f["project"] for f in two["files"]] == cands[:2]
    assert len({f["name"] for f in two["files"]}) == 2, "两份文件名撞了 ⇒ 不是「每项目一份」"


# ------------------------------------------------------------ 001-02 默认选中 · 动过则保持


@acc(CASE, "001-02")
def test_展开区默认取当前项目_动过则保持():
    cands = _cands()
    # 没动过 ⇒ 默认 = 当前项目（空当前项目 ⇒ 空）
    assert D.export_selection(cands[0], [], touched=False) == [cands[0]]
    assert D.export_selection("", [], touched=False) == []
    # ⚠️ 边界：**动过但清空了**必须保持空 —— 否则「清空」会被静默撤销
    assert D.export_selection(cands[0], [], touched=True) == []
    assert D.export_selection(cands[0], [cands[1], cands[1], " "], touched=True) == [cands[1]]


# ------------------------------------------------------------ 001-04 取数跟随当前所显示的表


@acc(CASE, "001-04")
def test_导出取数跟随当前所显示的那张表():
    """三张表**同形态**、只有数据与文件名不同 ⇒ 文件名里必须带**当前那张表**的名字
    （⛔ 不许固定成表② —— 那样用户看着表①导出，拿到的是别的表）。"""
    cands = _cands()
    for tab in (D.TAB_RAW, D.TAB_ADJUSTED, D.TAB_DIFF):
        man = D.export_manifest([cands[0]], tab=tab, ym=YM)
        assert D.tab_name(tab) in man["files"][0]["name"], \
            f"表签 {tab} 的名字没进文件名 ⇒ 取数没跟当前表"
