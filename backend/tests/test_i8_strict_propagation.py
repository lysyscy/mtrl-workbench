"""严格通道的停止**必须穿透业务容错**，而普通单条业务失败仍按原样降级（`TAIL-476`）。

为什么单独一份：浏览器会话方式下，"连接不在 / 站点或身份不符 / 浏览器没回音"与
"某个接口这次没取到"是**两件不同的事** ——
- 前者意味着**整条链的身份或目标已经不可信**，吞掉它就会继续按失效身份取数、
  甚至落一批半残数据（最坏的一类错：看着成功、其实来源不清）；
- 后者是**业务性失败**，既有产品行为就是降级/留空/回落缓存，⛔ 不该被本票改掉。

所以这里逐个钉住那些原本"一律 `except Exception`"的落点：
严格类抬出去、普通异常照旧。⚠️ 全部离线（不连 i8、不连库、不写执行记录）。
"""

from __future__ import annotations

import pytest

from app.core import app_settings
from app.core.config import Settings, get_settings
from app.mod02_i8 import contract_source
from app.mod02_i8 import sources as i8_sources
from app.mod02_i8.browser_broker import BrowserRelayUnavailable
from app.mod02_i8.browser_relay import MODE_BROWSER, MODE_HTTP, current_scope, relay_scope
from app.mod02_i8.browser_session import (
    StrictSessionStopped,
    StrictSessionEnded,
    StrictSessionUnavailable,
    StrictTargetMismatch,
)
from app.mod03_notice import router as m03r
from app.mod03_notice.schemas import WarehouseCheckRequest

BASE = "https://i8.example.test"


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch):
    """不读本机 `.env`；只给一个可比较的 i8 站点（详情地址由它推导）。"""
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    monkeypatch.setattr(app_settings, "_VALUES_LOADER", lambda: {"i8_base_url": BASE})
    monkeypatch.setattr(app_settings, "_CACHE", {"i8_base_url": BASE})
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class _Boom:
    """一个"一碰就停"的 i8 客户端：所有取数口都抛同一种异常。"""

    def __init__(self, exc: BaseException) -> None:
        self._exc = exc
        self.calls: list[str] = []

    def post_json(self, url, params=None, **kwargs):  # noqa: ANN001, ARG002
        self.calls.append(str(url))
        raise self._exc

    def get_json(self, url, params=None, **kwargs):  # noqa: ANN001, ARG002
        self.calls.append(str(url))
        raise self._exc

    def close(self) -> None:
        pass


STRICT_CASES = [
    StrictSessionStopped("新的通道停止类别也必须穿透现有业务容错。"),
    StrictSessionUnavailable("没有可复用的浏览器会话，本次未发出任何 i8 请求。"),
    StrictTargetMismatch("浏览器的 i8 站点与工作台当前配置不一致，本次已停止。"),
    StrictSessionEnded("浏览器里的 i8 会话已经不认了，本次已停止。"),
]


# --------------------------------------------------------------- 1 · 补档案（load_warehouse_rows）


@pytest.mark.parametrize("exc", STRICT_CASES, ids=lambda exc: type(exc).__name__)
def test_仓库名单的严格停止不被吞成None(exc):
    """`load_warehouse_rows` 原样返回 `None` 表示"补档案失败" —— ⛔ 严格停止不能走这条路。"""
    with pytest.raises(type(exc)):
        i8_sources.load_warehouse_rows(_Boom(exc))


def test_仓库名单的普通失败仍然只是None():
    """普通业务失败（i8 报错/网络抖动）**保持原行为**：返回 `None`，不抛。"""
    assert i8_sources.load_warehouse_rows(_Boom(RuntimeError("i8 500"))) is None


# --------------------------------------------------------------- 2 · 补材料名（fetch_item_name）


@pytest.mark.parametrize("exc", STRICT_CASES, ids=lambda exc: type(exc).__name__)
def test_补材料名的严格停止不被吞成空串(exc):
    """单条材料名失败可以留空；但整条会话/目标失效 ⇒ 必须停（否则后面每条都按失效身份问）。"""
    with pytest.raises(type(exc)):
        contract_source.ContractFetcher(_Boom(exc)).fetch_item_name("3700000000700286")


def test_补材料名的普通失败仍然返回空串():
    fetcher = contract_source.ContractFetcher(_Boom(RuntimeError("i8 500")))
    assert fetcher.fetch_item_name("3700000000700286") == ""


# --------------------------------------------------------------- 3 · 仓库名单查询入口（mod03）


def _wh_request(**kwargs):  # noqa: ANN003
    return WarehouseCheckRequest(warehouse_name="沭阳仓库", **kwargs)


def test_仓库查询入口真的把取数方式带进作用域(monkeypatch, tmp_path):
    """⚠️ 这个入口过去**连作用域都没有** ⇒ 用户选了浏览器方式也照样按直连去登录。

    这里钉的是行为：`session_mode=browser` 时，取数那一步看到的当前作用域必须是 `browser`。
    """
    from app.mod02_i8 import wh_cache

    monkeypatch.setattr(wh_cache, "CACHE_DIR", tmp_path / "wh")
    seen: list[tuple[str, str]] = []

    def loader(allow_kick=False, client=None):  # noqa: ANN001, ARG001
        seen.append(current_scope())
        return [{"warehouse_name": "沭阳仓库", "owner_full_name": "第四工程公司2026年小微项目"}]

    out = m03r.warehouse_check(_wh_request(session_mode="browser", device_id="dev-1"), wh_loader=loader)
    assert seen == [(MODE_BROWSER, "dev-1")], seen
    assert out.found is True and out.degraded is False

    # 缺省（旧调用）仍是直连，逐字节一如此前
    seen.clear()
    m03r.warehouse_check(_wh_request(), wh_loader=loader)
    assert seen == [(MODE_HTTP, "")], seen


@pytest.mark.parametrize("exc", STRICT_CASES, ids=lambda exc: type(exc).__name__)
def test_仓库查询入口的严格停止不回落旧缓存(exc, monkeypatch, tmp_path):
    """缓存兜底是给"这次没取到"用的 —— ⛔ 不能把"浏览器方式已停"说成"上次抓的名单还有效"。"""
    from app.mod02_i8 import wh_cache

    monkeypatch.setattr(wh_cache, "CACHE_DIR", tmp_path / "wh")
    wh_cache.save([{"warehouse_name": "沭阳仓库", "owner_full_name": "旧快照"}], source="自检")

    def loader(allow_kick=False, client=None):  # noqa: ANN001, ARG001
        raise exc

    with pytest.raises(type(exc)):
        m03r.warehouse_check(_wh_request(session_mode="browser", device_id="dev-1"), wh_loader=loader)


def test_仓库查询入口的普通失败仍回落旧缓存(monkeypatch, tmp_path):
    """既有产品行为不变：普通取数失败 ⇒ 用上一次名单接着判，并说清是几点抓的。"""
    from app.mod02_i8 import wh_cache

    monkeypatch.setattr(wh_cache, "CACHE_DIR", tmp_path / "wh")
    wh_cache.save([{"warehouse_name": "沭阳仓库", "owner_full_name": "旧快照"}], source="自检")

    def loader(allow_kick=False, client=None):  # noqa: ANN001, ARG001
        raise RuntimeError("i8 登录失败")

    out = m03r.warehouse_check(_wh_request(), wh_loader=loader)
    assert out.from_cache is True and out.found is True
    assert out.cached_at and out.cached_at in out.message


def test_浏览器方式缺连接时入口当场停而不是回登录(monkeypatch, tmp_path):
    """`open_i8_client` 在 browser 且无连接时抛的就是 `BrowserRelayUnavailable`（`StrictSessionUnavailable` 子类）。"""
    from app.mod02_i8 import wh_cache

    monkeypatch.setattr(wh_cache, "CACHE_DIR", tmp_path / "wh")
    wh_cache.save([{"warehouse_name": "沭阳仓库", "owner_full_name": "旧快照"}], source="自检")

    def loader(allow_kick=False, client=None):  # noqa: ANN001, ARG001
        with relay_scope(MODE_BROWSER, "dev-1"):
            # 真实路径：工厂在没有连接时就是抛这个（这里显式构造同一类异常）
            raise BrowserRelayUnavailable(
                "已选择「用浏览器已有会话」，但工作台与浏览器的连接不在（可能未连接、已断开或页面已刷新）。"
                "本次已停止；没有改用登录方式，也没有顶掉任何在线会话。"
            )

    with pytest.raises(BrowserRelayUnavailable):
        m03r.warehouse_check(_wh_request(session_mode="browser", device_id="dev-1"), wh_loader=loader)


# --------------------------------------------------------------- 4 · 通知书抓取（mod02 路由）


def test_预览失败时普通异常仍降级为手动导入():
    from app.mod02_i8 import router as m02
    from app.mod02_i8.schemas import FetchPreviewRequest

    def loader(year_month, allow_kick=False):  # noqa: ANN001, ARG001
        raise RuntimeError("i8 500")

    out = m02.fetch_preview(FetchPreviewRequest(year_month="2026-08"), rows_loader=loader)
    assert out.degraded is True and "手动" in out.message


@pytest.mark.parametrize("exc", STRICT_CASES, ids=lambda exc: type(exc).__name__)
def test_预览时严格停止不降级为手动导入(exc):
    """⛔ "i8 抓不到数 ⇒ 请手动导 Excel"既不真、也会把用户支到错的动作上。"""
    from app.mod02_i8 import router as m02
    from app.mod02_i8.schemas import FetchPreviewRequest

    def loader(year_month, allow_kick=False):  # noqa: ANN001, ARG001
        raise exc

    with pytest.raises(type(exc)):
        m02.fetch_preview(FetchPreviewRequest(year_month="2026-08"), rows_loader=loader)


@pytest.mark.parametrize("exc", STRICT_CASES, ids=lambda exc: type(exc).__name__)
def test_抓取运行时严格停止仍留失败记录并原样抛出(exc, monkeypatch):
    """执行记录（001-07）要留，但说明必须是**真实原因**；异常本体也照旧抛给上层。"""
    from app.mod02_i8 import router as m02
    from app.mod02_i8.schemas import FetchRunRequest

    recorded: list[dict] = []
    monkeypatch.setattr(m02, "_persist_fetch", lambda **kwargs: recorded.append(kwargs["payload"]))

    def loader(year_month, allow_kick=False):  # noqa: ANN001, ARG001
        raise exc

    with pytest.raises(type(exc)):
        m02.fetch_run(FetchRunRequest(year_month="2026-08"), rows_loader=loader)

    assert len(recorded) == 1, recorded
    assert recorded[0]["status"] == "failed"
    assert recorded[0]["error_message"] == str(exc), "说明必须是真实原因"
    assert "Excel" not in recorded[0]["error_message"], "⛔ 不能改口成'已降级为手动导入'"


def test_抓取运行时普通异常仍降级并留失败记录(monkeypatch):
    from app.mod02_i8 import router as m02
    from app.mod02_i8.schemas import FetchRunRequest

    recorded: list[dict] = []
    monkeypatch.setattr(m02, "_persist_fetch", lambda **kwargs: recorded.append(kwargs["payload"]))

    def loader(year_month, allow_kick=False):  # noqa: ANN001, ARG001
        raise RuntimeError("i8 500")

    out = m02.fetch_run(FetchRunRequest(year_month="2026-08"), rows_loader=loader)
    assert out.status == "failed" and out.degraded is True
    assert recorded and recorded[0]["status"] == "failed"


# --------------------------------------------------------------- 5 · 三个日常抓取服务


def _project(pid: int, warehouse: str, phid: str):
    from app.mod01_projects.models import Project

    return Project(id=pid, warehouse_name=warehouse, name_full=f"{warehouse}项目",
                   disp=warehouse, phid=phid)


def _session():  # noqa: ANN202
    from app.mod01_projects.models import Project
    from tests.m08_helpers import FakeSession

    return FakeSession({Project: [_project(1, "甲仓", "P1")]})


@pytest.mark.parametrize("exc", STRICT_CASES, ids=lambda exc: type(exc).__name__)
def test_收发结存抓取的严格停止不降级(exc, monkeypatch):
    """本域"失败 ⇒ 显式报错待人处理、不重试"的前提是**原因说对了**；要说错原因，就失去可诊断性。"""
    from app.mod07_setl import fetch_service as FS7
    from contextlib import nullcontext
    monkeypatch.setattr(FS7, 'session_scope', lambda: nullcontext(_session()))

    def factory():
        raise exc

    with pytest.raises(type(exc)):
        FS7.run_fetch(year_month="2026-08", confirmed=True, operator="测试",
                      client_factory=factory, export=lambda *a, **k: b"")


@pytest.mark.parametrize("exc", STRICT_CASES, ids=lambda exc: type(exc).__name__)
def test_库存抓取的严格停止不降级(exc, monkeypatch, tmp_path):
    from app.mod02_i8 import source_cache
    from app.mod08_inv import fetch_service as FS8
    from contextlib import nullcontext
    monkeypatch.setattr(FS8, 'session_scope', lambda: nullcontext(_session()))

    monkeypatch.setattr(source_cache, "DIR", tmp_path / "i8_source")

    def factory():
        raise exc

    with pytest.raises(type(exc)):
        FS8.run_fetch(year_month="2026-08", confirmed=True, operator="测试",
                      client_factory=factory, export=lambda *a, **k: b"")


@pytest.mark.parametrize("exc", STRICT_CASES, ids=lambda exc: type(exc).__name__)
def test_集采抓取的严格停止不降级(exc, monkeypatch):
    from app.mod11_jc import fetch_service as FS11

    def factory():
        raise exc

    monkeypatch.setattr(FS11, "save_run_record", lambda *a, **k: None)
    with pytest.raises(type(exc)):
        FS11.run_fetch(confirmed=True, operator="测试",
                       client_factory=factory, fetch=lambda client: [])


def test_集采抓取普通失败仍按原样降级(monkeypatch):
    """钉子不能钉成"以后所有失败都往上抛"：普通业务失败照旧降级进回执。"""
    from types import SimpleNamespace

    from app.mod11_jc import fetch_service as FS11
    from contextlib import nullcontext
    monkeypatch.setattr(FS11, 'session_scope', lambda: nullcontext(None))

    monkeypatch.setattr(FS11.fetch_task, "degrade_to_excel", lambda _exc: {"message": "降级"})
    monkeypatch.setattr(FS11.fetch_task, "fetch_record_payload", lambda **kwargs: kwargs)
    monkeypatch.setattr(FS11, "record_detail", lambda: {})
    monkeypatch.setattr(FS11.R, "fetch_detail", lambda **kwargs: {})
    monkeypatch.setattr(FS11, "save_run_record", lambda *a, **k: SimpleNamespace(id=8))

    def boom(client):  # noqa: ANN001, ARG001
        raise RuntimeError("boom")

    out = FS11.run_fetch(confirmed=True, operator="测试",
                         client_factory=lambda: _Boom(RuntimeError("unused")), fetch=boom)
    assert out["ok"] is False and out["degraded"] is True and out["message"] == "降级"


@pytest.mark.parametrize('exc', STRICT_CASES, ids=lambda exc: type(exc).__name__)
@pytest.mark.parametrize('stage', ['common', 'warehouses'])
def test_project_sync_propagates_strict_loader_stop(exc, stage):
    from app.mod01_projects.sync_service import build_plan

    def stopped():
        raise exc

    with pytest.raises(type(exc)):
        build_plan(load_common=stopped if stage == 'common' else lambda: [],
                   load_warehouses=stopped if stage == 'warehouses' else lambda: [])
