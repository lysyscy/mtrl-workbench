"""系统设置（§7.8）—— 离线自检（**不连库**）。

对应判据 `ACC-CFG-SETUP-001`（7 点）：
- `001-01` 只列**连接参数**；不含 i8 账号密码 / 四个接口路径 / 开发运维参数
- `001-02` 取值优先级 **库 → `.env`**（清空即回落）
- `001-03` 改动**留痕**（改前 / 改后 / 改动人 / 时间）
- `001-04` ⭐ 页面带**版式 ID 的反直觉提示**
- `001-05` 保存**只影响传入的 key**（不得顺带改别的）
- `001-06` ⭐ 改「i8 服务地址」⇒ **四个端点随之推导变化**
- `001-07` 格式非法 ⇒ **拒绝**（不静默写入）
"""

from __future__ import annotations

import pytest

from app.core import app_settings
from app.core.app_settings import (
    SETTING_I8_BASE_URL,
    SETTING_PRINT_ID_MATERIAL,
    SETTING_PRINT_ID_MECHANICAL,
    SETTING_KEYS,
    SPECS,
    effective,
    validate,
)
# ⚠️ 2026-09-21：原先这里还 import `SETTING_PRINTER_IPP_URL` —— 它**已不在 `SPECS` 里**
#   （用户裁定「打印设置从 `MOD-14` 合并进 `MOD-03`」⇒ 入口与存储都归 `MOD-03`，
#    见 `ACC-PAY-SETUP-001` 与本文件 `001-01` 的新断言）。
from app.core.config import (
    I8_PATH_COMMON_PROJECT,
    I8_PATH_PAYMENT_NOTICE,
    I8_PATH_PRINT_DESIGN,
    I8_PATH_WAREHOUSE_LIST,
    i8_endpoint_of,
)
from app.mod14_config import settings_api
from app.mod14_config.models import AppSetting
from app.mod14_config.repository import save

@pytest.fixture(autouse=True)
def _offline_address_state(monkeypatch):
    # These display-contract tests stay offline; HTTP tests cover the real versioned row.
    monkeypatch.setattr(settings_api, "address_state", lambda _session: {"stored": "", "version": "missing"})
    from contextlib import nullcontext
    monkeypatch.setattr(settings_api, "session_scope", lambda: nullcontext(None))


I8_PATHS = (I8_PATH_PAYMENT_NOTICE, I8_PATH_WAREHOUSE_LIST,
            I8_PATH_COMMON_PROJECT, I8_PATH_PRINT_DESIGN)


# --------------------------------------------------------------------- 桩


class _Sess:
    """最小会话桩：只需 `get` / `add` / `flush`（`repository.save` 的用面）。"""

    def __init__(self, rows: dict | None = None) -> None:
        self._rows = dict(rows or {})
        self.added: list = []

    def get(self, _model, key):
        return self._rows.get(key)

    def add(self, obj) -> None:
        self.added.append(obj)

    def flush(self) -> None:
        pass

    def logs(self) -> list:
        from app.mod14_config.models import AppSettingLog
        return [o for o in self.added if isinstance(o, AppSettingLog)]


def _shown() -> str:
    """设置页**界面上真正会出现的文本** —— 拼自它的**唯一数据源**。

    ⚠️ 2026-09-21（`§19` 四个暂留件收口）：设置页**搬进了新壳** ⇒ 页面不再由 Python 拼 HTML，
       而是 `settings_api` 出 JSON（`items` / `tips`）、壳 `V.set` **逐字**渲染。
       ⇒ 本件改指那份 JSON（页面文本的**真源**），并在下面**同时**用壳源码钉住
       「壳确实是照着它渲染 + 保存走 `/api/m14/settings`」（两半合起来 = 原来的"看页面 HTML"）。
       ⛔ 不是放宽：`render_settings_page` 与壳那一段渲染**不可能同时错**，且真机的观感另有真人验收。
    """
    parts = list(settings_api.TIPS)
    for it in settings_api.items():
        parts += [str(it[k]) for k in ("key", "label", "hint", "stored", "env", "effective")]
    return "\n".join(parts)




# ------------------------------------------------------------ 001-01 页面范围


def test_设置页只列连接参数不含账号密码与端点路径():
    html = _shown()
    for spec in SPECS:
        assert spec.label in html, f"缺设置项：{spec.label}"

    # ⛔ 不得出现 i8 账号 / 密码（绑定到本系统账号、每人一份 ⇒ 归 MOD-15）
    for bad in ("i8_user", "I8_USER", "i8_password", "I8_PASSWORD", "i8 账号密码"):
        assert bad not in html, f"设置页不该出现账号类配置：{bad}"

    # ⛔ 不得出现四个接口路径（由服务地址推导，不各存一份）
    for path in I8_PATHS:
        assert path not in html, f"设置页不该暴露端点路径：{path}"

    # ⛔ 不得出现开发 / 运维参数
    for bad in ("database_url", "DATABASE_URL", "APP_PORT", "PRD_ACCEPTANCE_BASELINE", "LOG_RETENTION"):
        assert bad not in html, f"设置页不该出现运维/开发参数：{bad}"

    # ⭐⭐ 2026-09-21（用户裁定「打印设置从 `MOD-14` **合并进** `MOD-03`」）—— 打印机地址**不在本页**：
    #    它的**唯一入口** = 付款通知书页的「打印机设置」弹窗 ＋ **唯一存储** = `.env`
    #    ⇒ 判据改为「设置页只列**三类**连接参数」（`criterion` / `001-01` 同批改）。
    #    ⚠️ 这一条**不是形式**：两处入口 ＋ 两套存储正是那个坑的成因（库里有值时，弹窗改的**不生效**，
    #       而回执还说"即时生效"）。
    assert not any(s.key == "printer_ipp_url" for s in SPECS), (
        "`SPECS` 里又出现了打印机项 —— 与「打印设置合并进 `MOD-03`」冲突")
    assert len(SPECS) == 3, (
        f"设置页的连接参数应为**三类**（i8 服务地址 ＋ 两个版式 ID），实际 {len(SPECS)} 项："
        f"{[s.key for s in SPECS]}")
    assert "printer_ipp_url" not in html, "设置页（JSON 真源）里又出现了打印机地址 —— 它属 MOD-03"

    # ⭐ 另一半：**壳确实是照着这份数据渲染的**（否则上面那些约束只约束了一份没人看的 JSON）


# ------------------------------------------------------------ 001-02 取值优先级


def test_取值优先级库优先_清空即回落(monkeypatch):
    monkeypatch.setattr(app_settings, "_load_from_db", lambda: {SETTING_I8_BASE_URL: "http://from-db"})
    app_settings.invalidate()
    try:
        assert effective(SETTING_I8_BASE_URL, 'http://from-env') == 'http://from-db'
        assert effective(SETTING_PRINT_ID_MECHANICAL, 'PID-FROM-ENV') == 'PID-FROM-ENV'
        assert effective(SETTING_PRINT_ID_MATERIAL, '') == ''
    finally:
        app_settings.invalidate()


# ------------------------------------------------------------ 001-03 改动留痕


def test_改动留痕含改前改后与改动人():
    s = _Sess()
    changes = save(s, values={SETTING_PRINT_ID_MECHANICAL: "PID-NEW"}, operator="张三")

    assert changes == [{"key": SETTING_PRINT_ID_MECHANICAL, "old": "", "new": "PID-NEW"}]
    logs = s.logs()
    assert len(logs) == 1, "每次变更必须留痕一条"
    lg = logs[0]
    assert lg.key == SETTING_PRINT_ID_MECHANICAL
    assert lg.old_value == ""                       # 改前（原来是空 = 未设置）
    assert lg.new_value == "PID-NEW"
    assert lg.operator == "张三"                     # 改动人
    assert lg.at is not None                        # 时间
    assert isinstance(s.added[0], AppSetting)       # 当前值也落了库


def test_值没变则不记留痕():
    s = _Sess({SETTING_PRINT_ID_MECHANICAL: AppSetting(key=SETTING_PRINT_ID_MECHANICAL, value="PID-SAME")})
    changes = save(s, values={SETTING_PRINT_ID_MECHANICAL: "PID-SAME"}, operator="张三")
    assert changes == [] and s.logs() == []


# ------------------------------------------------------------ 001-04 反直觉提示




# ------------------------------------------------------------ 001-05 只影响传入项


def test_保存只影响传入的key不得顺带改别的():
    rows = {
        SETTING_I8_BASE_URL: AppSetting(key=SETTING_I8_BASE_URL, value="http://keep-me"),
        SETTING_PRINT_ID_MATERIAL: AppSetting(key=SETTING_PRINT_ID_MATERIAL, value="PID-KEEP"),
    }
    s = _Sess(rows)
    changes = save(s, values={SETTING_PRINT_ID_MECHANICAL: "PID-X"}, operator="张三")

    assert [c["key"] for c in changes] == [SETTING_PRINT_ID_MECHANICAL]
    assert rows[SETTING_I8_BASE_URL].value == "http://keep-me"      # 一行不动
    assert rows[SETTING_PRINT_ID_MATERIAL].value == "PID-KEEP"
    assert len(s.logs()) == 1


# ------------------------------------------------------------ 001-06 端点随之推导


def test_改服务地址后四个端点随之推导(monkeypatch):
    class _S:
        i8_base_url = "http://old-host:1"

    monkeypatch.setattr(app_settings, "_load_from_db", lambda: {SETTING_I8_BASE_URL: "http://new-host:2"})
    app_settings.invalidate()
    try:
        for path in I8_PATHS:
            got = i8_endpoint_of(_S(), path)
            assert got == 'http://new-host:2' + path, f'端点未跟随服务地址：{got}'
            assert 'old-host' not in got
        monkeypatch.setattr(app_settings, '_load_from_db', lambda: {})
        app_settings.invalidate()
        assert i8_endpoint_of(_S(), I8_PATH_PRINT_DESIGN) == 'http://old-host:1' + I8_PATH_PRINT_DESIGN
    finally:
        app_settings.invalidate()


# ------------------------------------------------------------ 001-07 非法拒绝


def test_地址格式非法须拒绝不静默写入():
    assert validate(SETTING_I8_BASE_URL, "106.46.169.212:30785") is not None   # 缺协议
    assert validate(SETTING_I8_BASE_URL, "") is None                            # 空 = 清除，合法
    assert validate(SETTING_I8_BASE_URL, "http://a:1") is None
    # ⚠️ 2026-09-21：原先这里还拿「打印机地址」当**第二个 url 型**例子 —— 它已**不在本页**
    #   （用户裁定「打印设置从 MOD-14 合并进 MOD-03」）⇒ 那两条随之下线。
    #   本页此后**只有 `i8_base_url` 是 url 型**，其余两个是文本型。
    # 版式 ID 是文本（不强求 URL 形态），空亦合法
    assert validate(SETTING_PRINT_ID_MATERIAL, "3700000000000215") is None
    # 未知 key 必须报错（防拼错键名静默写库）
    assert validate("i8_typo_key", "x") is not None
