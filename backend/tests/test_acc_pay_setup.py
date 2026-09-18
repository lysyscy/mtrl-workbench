"""`ACC-PAY-SETUP-001`（打印机地址设置）5 个判据点的验收断言。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import Settings, get_settings
from app.core.errors import MustReportError
from app.mod03_notice.settings_store import apply_printer_setting, validate_printer_uri
from tests.acc_plugin import acc

_MOD03_HTML = Path(__file__).resolve().parents[1] / "app" / "mod03_notice" / "static" / "m03.html"


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """避免测试写入的值经 `lru_cache` 泄漏到其它测试。"""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ------------------------------------------------------------------ 001-01


@acc("ACC-PAY-SETUP-001", "001-01")
def test_系统内提供可发现的修改入口():
    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.mod03_notice.router import router as mod03_router

    routes = {(r.path, tuple(sorted(r.methods))) for r in mod03_router.routes}
    assert ("/api/m03/settings/printer", ("GET",)) in routes
    assert ("/api/m03/settings/printer", ("PUT",)) in routes

    # 页面上有可发现的入口（设置按钮）
    # ⭐ `TAIL-46`（2026-09-18）：**断言搬到新壳** —— 旧页 `mod03_notice/static/m03.html` 在
    #    「删旧渲染层」（§19）的删除范围内 ⇒ 判据**不动**（claim 还是"系统内提供可发现的修改入口"），
    #    但它钉的**形态**换成新壳：入口由 `BIND.m03` 渲染后注入，读写走上面那两个端点。
    _shell = (Path(__file__).resolve().parents[1] / "app" / "web" / "index.html").read_text(
        encoding="utf-8"
    )
    assert "m03PrinterOpen" in _shell and "打印机设置" in _shell, \
        "新壳里必须有**可发现**的打印机设置入口（旧页一删，这里就是唯一入口）"
    assert "API.printerGet()" in _shell and "API.printerSet(" in _shell, \
        "设置要真的读写后端（⛔ 不是只弹个提示）"

    # 端到端：入口可读到当前值
    res = TestClient(create_app()).get("/api/m03/settings/printer")
    assert res.status_code == 200 and "printer_ipp_url" in res.json()


# ------------------------------------------------------------------ 001-02


@acc("ACC-PAY-SETUP-001", "001-02")
def test_保存后即时生效无需重启(monkeypatch):
    from app.mod03_notice.print import ipp

    monkeypatch.setenv("PRINTER_IPP_URL", "ipp://10.0.0.9")
    get_settings.cache_clear()
    assert get_settings().printer_ipp_url == "ipp://10.0.0.9"

    # 下一次取配置即新值（无需重启）——打印时按新地址投递
    captured: dict[str, str] = {}

    def _fake_post(url, **kw):
        captured["url"] = url

        class _Resp:
            status_code = 200
            content = b"\x01\x01\x00\x00" + b"\x00" * 8  # IPP successful-ok

        return _Resp()

    monkeypatch.setattr(ipp.httpx, "post", _fake_post)
    ipp.send_pdf(b"%PDF-1.4")
    assert captured["url"].startswith("http://10.0.0.9")

    # 再改一次，同样即时生效
    monkeypatch.setenv("PRINTER_IPP_URL", "ipp://10.0.0.10")
    get_settings.cache_clear()
    assert get_settings().printer_ipp_url == "ipp://10.0.0.10"


# ------------------------------------------------------------------ 001-03


@acc("ACC-PAY-SETUP-001", "001-03")
def test_配置持久化重启后仍生效(tmp_path, monkeypatch):
    monkeypatch.delenv("PRINTER_IPP_URL", raising=False)
    env = tmp_path / ".env"
    env.write_text("APP_ENV=dev\nPRINTER_IPP_URL=\n", encoding="utf-8")

    apply_printer_setting("ipp://192.168.5.248", env_path=env)

    # 已落盘
    assert "PRINTER_IPP_URL=ipp://192.168.5.248" in env.read_text(encoding="utf-8")
    # "重启"= 重新读配置文件，仍生效
    assert Settings(_env_file=str(env)).printer_ipp_url == "ipp://192.168.5.248"


# ------------------------------------------------------------------ 001-04


@acc("ACC-PAY-SETUP-001", "001-04")
def test_地址为空或非法须显式报错(tmp_path):
    for bad in ("", "   ", "192.168.5.248", "ftp://x", "ipp:/bad", "not a url"):
        with pytest.raises(MustReportError):
            validate_printer_uri(bad)

    env = tmp_path / ".env"
    original = "APP_ENV=dev\nPRINTER_IPP_URL=ipp://192.168.5.1\n"
    env.write_text(original, encoding="utf-8")

    with pytest.raises(MustReportError):
        apply_printer_setting("", env_path=env)
    # 非法输入 ⇒ 不落盘、不静默沿用（文件一字未动）
    assert env.read_text(encoding="utf-8") == original


# ------------------------------------------------------------------ 001-05


@acc("ACC-PAY-SETUP-001", "001-05")
def test_只改打印机不动其他配置(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "APP_ENV=dev\n"
        "I8_USER=SCY980803\n"
        "DATABASE_URL=postgresql+psycopg://mtrl:pw@127.0.0.1:5432/mtrl_workbench\n"
        "PRINTER_IPP_URL=ipp://192.168.5.248\n"
        "LOGS_DIR=logs\n",
        encoding="utf-8",
    )
    original_lines = env.read_text(encoding="utf-8").splitlines()

    apply_printer_setting("ipp://192.168.5.250", env_path=env)

    lines = env.read_text(encoding="utf-8").splitlines()
    changed = [
        (a, b) for a, b in zip(original_lines, lines) if a != b
    ]
    # 只有打印机那一行变化，其余（i8 账号 / 数据库 / 日志）一字不动
    assert changed == [("PRINTER_IPP_URL=ipp://192.168.5.248", "PRINTER_IPP_URL=ipp://192.168.5.250")]
    assert len(lines) == len(original_lines)
