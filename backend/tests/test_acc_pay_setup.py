"""`ACC-PAY-SETUP-001`（打印机地址设置）5 个判据点的验收断言。"""

from __future__ import annotations

import pytest

from app.core.config import Settings, get_settings
from app.core.errors import MustReportError
from app.mod03_notice.settings_store import apply_printer_setting, validate_printer_uri

# ⚠️ 2026-09-19（`§19` 批 4）：`_MOD03_HTML` 已随旧静态页 `m03.html` 一起消失（本处已无引用）——
#    本文件的断言自 `TAIL-46`（2026-09-18）起就**只打新壳**（`app/web/index.html`）。


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """避免测试写入的值经 `lru_cache` 泄漏到其它测试。"""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ------------------------------------------------------------------ 001-01


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

    # 端到端：入口可读到当前值
    res = TestClient(create_app()).get("/api/m03/settings/printer")
    assert res.status_code == 200 and "printer_ipp_url" in res.json()


def test_打印机地址只有这一处入口与一处存储():
    from app.core.app_settings import SPECS

    assert not any(setting.key == "printer_ipp_url" for setting in SPECS)


def test_保存后即时生效无需重启(tmp_path, monkeypatch):
    import httpx

    from app.mod03_notice.print import dispatch, ipp

    env = tmp_path / ".env"
    env.write_text("PRINTER_IPP_URL=ipp://first.test\nPRINT_MODE=ipp\n", encoding="utf-8")
    monkeypatch.setitem(Settings.model_config, "env_file", str(env))
    monkeypatch.delenv("PRINTER_IPP_URL", raising=False)
    monkeypatch.delenv("PRINT_MODE", raising=False)
    observed = []

    def reply(url, *, content, **kwargs):
        observed.append((url.host, int.from_bytes(content[2:4], "big")))
        return httpx.Response(200, content=bytes.fromhex("0101 0000 00000001 03"))

    monkeypatch.setattr(ipp.httpx, "post", reply)
    assert dispatch.lock_a4_channel().send(b"%PDF-first").last.status == "accepted"
    apply_printer_setting("ipp://second.test", env_path=env)
    assert dispatch.lock_a4_channel().send(b"%PDF-next").last.status == "accepted"
    assert observed == [("first.test", 4), ("first.test", 2), ("second.test", 4), ("second.test", 2)]


# ------------------------------------------------------------------ 001-03


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
    assert lines[len(original_lines):] == ["PRINT_MODE=ipp"]
    for a, b in zip(original_lines, lines):
        if a.startswith("PRINTER_IPP_URL="):
            continue
        assert a == b, f"不该动的配置被改了：{a!r} → {b!r}"
