"""打印机**出纸通道**的设置（`TAIL-46`-③）—— 口径照用户调好的 `i8一键打印_新版`（2026-09-18）。

**四条通道**：`auto`（依次试 IPP → 系统驱动 → RAW 9100，推荐）· `ipp`（只用标准方式）·
`driver`（走 Windows 打印驱动，**须给打印机名**）· `raw`（只走 RAW 9100）。
⚠️ **为什么要有它**：现网有的打印机**没有 PDF 解释器**（只认位图格式）⇒ 走 IPP 会被**直接拒收**、
走 RAW 会收下但**打成乱码** ⇒ 只有"系统驱动"那条路能出纸。

⚠️ 本文件**不写真实 `.env`**（`monkeypatch` 把落点换到 `tmp_path`）、**不连打印机**。
⚠️ **判据点**：这是**扩范围**（`ACC-PAY-SETUP-001` 的 5 点讲的是"地址"那一件事）⇒ 一律 `@acc()` 显式不绑定。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.errors import MustReportError
from app.mod03_notice import settings_store as SS
from tests.acc_plugin import acc

from tests.shell_src import SHELL  # noqa: F401  ← `P4`① 读取点收敛


def _env(tmp_path: Path) -> Path:
    p = tmp_path / ".env"
    p.write_text("APP_ENV=dev\nPRINTER_IPP_URL=ipp://192.168.5.248\nLOGS_DIR=logs\n",
                 encoding="utf-8")
    return p


# ------------------------------------------------------------------ 校验（唯一出口）


@acc()
def test_四条通道都认_别的都不认():
    for m in ("auto", "ipp", "driver", "raw"):
        assert SS.validate_print_mode(m, "任意打印机名" if m == "driver" else "") == m
    assert SS.validate_print_mode("", "") == "auto", "留空 = 自动（默认）"
    assert SS.validate_print_mode("  DRIVER ", "X") == "driver", "大小写 / 空白要规整"
    with pytest.raises(MustReportError) as e:
        SS.validate_print_mode("raw9100", "")
    assert "只能是" in str(e.value), f"拒绝理由要把合法值列出来：{e.value}"


@acc()
def test_选系统驱动必须给打印机名():
    """`driver` 靠**本机驱动**出纸、不用 IP ⇒ 不给名字就只能落到"系统默认打印机"，
    ⛔ 那不是用户选的意思（不猜）。"""
    with pytest.raises(MustReportError) as e:
        SS.validate_print_mode("driver", "   ")
    assert "打印机名" in str(e.value)
    assert SS.validate_print_mode("driver", "Ricoh IM 3000") == "driver"


# ------------------------------------------------------------------ 落盘（三项一起写 · 先校验后写）


@acc()
def test_三项一起写且其余配置一字不动(tmp_path):
    env = _env(tmp_path)
    out = SS.apply_printer_setting("ipp://192.168.5.250", mode="driver",
                                   printer_name="Ricoh IM 3000", env_path=env)
    assert out == {"printer_ipp_url": "ipp://192.168.5.250", "print_mode": "driver",
                   "printer_name": "Ricoh IM 3000"}
    text = env.read_text(encoding="utf-8")
    assert "PRINT_MODE=driver" in text and "PRINTER_NAME=Ricoh IM 3000" in text
    assert "APP_ENV=dev" in text and "LOGS_DIR=logs" in text, "别的配置一字不动（001-05 的口径）"


@acc()
def test_任一项非法就一个字都不写(tmp_path):
    """⭐ 反向：**不许出现半套**（地址改了、通道没改）。校验在写之前 ⇒ 文件内容**逐字节不变**。"""
    env = _env(tmp_path)
    before = env.read_bytes()
    with pytest.raises(MustReportError):
        SS.apply_printer_setting("ipp://192.168.5.250", mode="不存在的通道", env_path=env)
    with pytest.raises(MustReportError):
        SS.apply_printer_setting("ipp://192.168.5.250", mode="driver", printer_name="", env_path=env)
    with pytest.raises(MustReportError):
        SS.apply_printer_setting("不是地址", mode="auto", env_path=env)
    assert env.read_bytes() == before, "非法任何一种 ⇒ 一个字都不许写"


@acc()
def test_端点三项进三项出(tmp_path, monkeypatch):
    """弹窗回填要三项、保存要三项（⛔ 别只回地址——那样用户改了通道也看不出来）。"""
    monkeypatch.setattr(SS, "ENV_FILE", _env(tmp_path))
    from app.mod03_notice import router as m03r
    from app.mod03_notice.schemas import PrinterSettingRequest

    got = m03r.get_printer_setting()
    assert {"printer_ipp_url", "print_mode", "printer_name"} <= set(got.model_dump())
    out = m03r.set_printer_setting(PrinterSettingRequest(
        printer_ipp_url="ipp://192.168.5.251", print_mode="raw", printer_name=""))
    assert out.print_mode == "raw" and out.printer_ipp_url == "ipp://192.168.5.251"


# ------------------------------------------------------------------ 壳侧


@acc()
def test_壳弹窗三项齐且判定全在后端():
    open_fn = SHELL[SHELL.index("async function m03PrinterOpen()"):]
    open_fn = open_fn[:open_fn.index("async function openOwnDialog()")]
    for f in ('id="m03PrinterUrl"', 'id="m03PrintMode"', 'id="m03PrinterName"'):
        assert f in open_fn, f"弹窗少了 {f}"
    for m in ("自动（推荐）", "系统驱动", "RAW 9100"):
        assert m in open_fn, f"通道说明里要有「{m}」"
    assert "乱码" in open_fn, "要讲清「打不出纸 / 乱码」时怎么办（这是这条设置存在的理由）"
    save = SHELL[SHELL.index(" m03PrinterSave:async"):]
    save = save[:save.index("/* —— MOD-06")]
    assert "API.printerSet(url, mode, nm)" in save, "三项一起提交"
    assert "validate" not in save, "⛔ 壳里不许自己校验（那是后端唯一出口的活）"
