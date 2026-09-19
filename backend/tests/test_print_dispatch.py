"""出纸**通道分流**（`TAIL-46`-②）—— 三条通道怎么选、怎么降级，以及**两条硬规矩**。

口径照用户调好的 `i8一键打印_新版`：`auto` = **IPP → 系统驱动 → RAW 9100**。

⚠️ **一个字节都不真发**：三条通道全部用**桩**注入 ⇒ 自检**不碰打印机**（本仓规矩：自检不碰真实设备）。
⚠️ **判据点**：这是**扩范围**（`ACC-PAY-SETUP-001` 的 5 点讲的是"打印机设置"这一件事）⇒ 一律 `@acc()` 显式不绑定。
"""

from __future__ import annotations

import types
from pathlib import Path

import pytest

from app.core.errors import MustReportError
from app.mod03_notice.print import dispatch as D
from tests.acc_plugin import acc

PDF = b"%PDF-1.4 fake"
from tests.shell_src import SHELL  # noqa: F401  ← `P4`① 读取点收敛
# ⚠️ 2026-09-19（`T5` 拆件）：批量执行器的**实体**已搬到 `notice_executors.py`（`router.py` 只再导出它）
#    ⇒ 读源码的断言**改指新件**（⛔ 判据一字未改：「投递必须走分流器、不许退回裸 send_pdf」）。
EXEC = (Path(__file__).resolve().parents[1] / "app" / "mod03_notice" / "notice_executors.py").read_text(
    encoding="utf-8"
)


def _spy(name: str, note: str = "", boom: str = "") -> tuple[list[tuple], object]:
    """造一个**桩通道**：记下每次调用 + 按需返回说明或抛错。"""
    calls: list[tuple] = []

    def _fn(pdf: bytes, arg) -> str:  # noqa: ANN001
        calls.append((pdf, arg))
        if boom:
            raise MustReportError(boom)
        return note

    return calls, _fn


def _settings(**kw) -> types.SimpleNamespace:
    base = {"print_mode": "auto", "printer_name": "", "printer_ipp_url": "ipp://192.168.5.248"}
    base.update(kw)
    return types.SimpleNamespace(**base)


@pytest.fixture()
def wired(monkeypatch):
    """把"当前设置"换成桩（避免读真实 `.env`），并让 `effective_of` 直接用传入值。"""
    monkeypatch.setattr(D, "get_settings", lambda: _settings())
    monkeypatch.setattr(D, "effective_of", lambda key, val: val)


# ------------------------------------------------------------------ 单通道：只走它


@acc()
def test_ipp_通道只走_ipp():
    ci, ipp = _spy("ipp", note="已投递（未核实）—— 打印机收下了")
    cd, drv = _spy("driver")
    cr, raw = _spy("raw")
    note = D.dispatch_pdf(PDF, mode="ipp", printer_uri="ipp://h", ipp=ipp, driver=drv, raw=raw)
    assert len(ci) == 1 and not cd and not cr, "选定的通道只许走它一个"
    assert note == "已投递（未核实）—— 打印机收下了", "单通道的说明要**原样**带出来（⛔ 别改写）"


@acc()
def test_单通道失败只报那一档():
    calls, drv = _spy("driver", boom="本机没有打印驱动接口")
    with pytest.raises(MustReportError) as e:
        D.dispatch_pdf(PDF, mode="driver", printer_name="RICOH IM 3000 PCL 6",
                       printer_uri="ipp://h", driver=drv)
    msg = str(e.value)
    assert "系统驱动" in msg and "本机没有打印驱动接口" in msg, f"要把那一档的原因讲清：{msg}"
    assert "三种" not in msg, "单通道失败别说成「三种」（会让人以为还有别的通道可试）"
    assert calls and calls[0][1] == "RICOH IM 3000 PCL 6", "打印机名要**原样**交到通道（驱动靠它出纸）"


@acc()
def test_系统驱动不给打印机名_当场拒():
    """⭐ 这不是"多一道校验"，而是 `003` 的口径本身：`driver` 靠**本机驱动**出纸、不用 IP ⇒
    不给名字就只能落到"系统默认打印机"，那不是用户选的意思（⛔ 不猜）。在**发请求之前**就要拦住。"""
    calls, drv = _spy("driver")
    with pytest.raises(MustReportError) as e:
        D.dispatch_pdf(PDF, mode="driver", printer_name="  ", printer_uri="ipp://h", driver=drv)
    assert "打印机名" in str(e.value)
    assert not calls, "⛔ 拦在投递之前（一次也不许调通道）"


# ------------------------------------------------------------------ auto：顺序 与 两条硬规矩


@acc()
def test_auto_试法顺序是_ipp_驱动_raw():
    assert D.AUTO_ORDER == ("ipp", "driver", "raw"), (
        "口径照 `i8一键打印_新版`：先标准、再系统驱动、最后 RAW（⛔ 别改顺序）"
    )


@acc()
def test_auto_前一档报错就试下一档():
    """⭐ 降级**只允许**发生在"明确报错"时（IPP 被拒收 ⇒ 正是"没 PDF 解释器"那种情形）。"""
    _ci, ipp = _spy("ipp", boom="IPP 报 0x0400：document-format 被拒")
    cd, drv = _spy("driver", note="已投递（未核实）—— 已交系统打印驱动出纸")
    cr, raw = _spy("raw")
    note = D.dispatch_pdf(PDF, mode="auto", printer_uri="ipp://h", ipp=ipp, driver=drv, raw=raw)
    assert len(cd) == 1 and not cr, "IPP 报错 ⇒ 试系统驱动；成功即停（⛔ 不再试 RAW）"
    assert "自动选「系统驱动」" in note, f"要告诉用户最终走的是哪一档：{note}"


@acc()
def test_auto_前一档说已投递就停住_绝不重复出纸():
    """⭐⭐ **最要紧的一条**：「已投递（未核实）」= "**可能已经打了**" ⇒ 必须停住。

    否则同一张纸会**打两遍**（用户最能感知的浪费）—— 这是「假失败」的孪生兄弟。
    """
    _ci, ipp = _spy("ipp", note="已投递（未核实）—— 打印机收下了，但没能核实")
    cd, drv = _spy("driver")
    cr, raw = _spy("raw")
    note = D.dispatch_pdf(PDF, mode="auto", printer_uri="ipp://h", ipp=ipp, driver=drv, raw=raw)
    assert not cd and not cr, "⛔ 前档说\"已投递\"后**绝不许**再试下一档（会重复出纸）"
    assert "自动选「IPP」" in note and "已投递（未核实）" in note


@acc()
def test_auto_全失败要把三档理由都带上():
    """⭐ `001-08`「显式报出原因」：只给一句"打印失败" ⇒ 现场无从下手（实测教训）。"""
    _a, ipp = _spy("ipp", boom="连不上 192.168.5.248")
    _b, drv = _spy("driver", boom="没装 pywin32")
    _c, raw = _spy("raw", boom="9100 口没人听")
    with pytest.raises(MustReportError) as e:
        D.dispatch_pdf(PDF, mode="auto", printer_uri="ipp://h", ipp=ipp, driver=drv, raw=raw)
    msg = str(e.value)
    for kw in ("连不上 192.168.5.248", "没装 pywin32", "9100 口没人听"):
        assert kw in msg, f"三档各自的原因都要带上，缺了「{kw}」：{msg}"
    assert "只导出 PDF" in msg, "要给出下一步（先确认制单本身没问题）"


# ------------------------------------------------------------------ RAW 目标与设置读取


@acc()
def test_raw_端口固定9100_地址里的端口不照抄():
    """⚠️ 地址里的端口（`ipp://host:631/…`）是 **IPP** 用的 —— 照抄到 RAW 等于投错门。"""
    assert D.raw_target("ipp://192.168.5.248") == ("192.168.5.248", 9100)
    assert D.raw_target("ipp://192.168.5.248:631/printers/x") == ("192.168.5.248", 9100)
    assert D.raw_target("  ipp://10.0.0.9  ") == ("10.0.0.9", 9100)
    with pytest.raises(MustReportError) as e:
        D.raw_target("192.168.5.248")
    assert "看不懂" in str(e.value), f"地址取不出 IP 要显式报错：{e.value}"


@acc()
def test_通道按当前设置走_不用重启(monkeypatch):
    """设置弹窗改完即生效（`001-02`）⇒ 分流器每次都**现读**设置，⛔ 不许把通道缓存在别处。"""
    monkeypatch.setattr(D, "get_settings",
                        lambda: _settings(print_mode="raw", printer_name=""))
    monkeypatch.setattr(D, "effective_of", lambda key, val: "ipp://h")
    calls, raw = _spy("raw", note="已投递（未核实）—— RAW 发完")
    _c, ipp = _spy("ipp")
    note = D.dispatch_pdf(PDF, ipp=ipp, raw=raw)
    assert len(calls) == 1 and not _c, "设置里选的是 RAW ⇒ 只走 RAW"
    assert note.startswith("已投递（未核实）"), "单通道的说明原样带回"


# ------------------------------------------------------------------ 接线与壳侧


@acc()
def test_接线点用的是分流器_不是裸_send_pdf():
    assert "print_dispatch if mode == MODE_PRINT" in EXEC, "排版那条路投递必须走分流器（②）"
    assert "dispatch_pdf=(send_pdf" not in EXEC, "⛔ 别退回裸 `send_pdf`（那样通道就白设了）"


@acc()
def test_壳侧有本机打印机名可选():
    assert "printerList: () => API.get('/api/m03/settings/printers')" in SHELL
    dlg = SHELL[SHELL.index("async function m03PrinterOpen()"):]
    dlg = dlg[:dlg.index("async function openOwnDialog()")]
    assert 'list="m03PrinterNames"' in dlg and "m03PrinterNames" in dlg, "名字要给下拉（要一字不差）"
    assert "手填" in dlg, "取不到名字时要如实说清"
