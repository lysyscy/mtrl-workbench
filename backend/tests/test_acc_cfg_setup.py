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

from app.core import app_settings
from app.core.app_settings import (
    SETTING_I8_BASE_URL,
    SETTING_PRINT_ID_MATERIAL,
    SETTING_PRINTER_IPP_URL,
    SETTING_KEYS,
    SPECS,
    effective,
    validate,
)
from app.core.config import (
    I8_PATH_COMMON_PROJECT,
    I8_PATH_PAYMENT_NOTICE,
    I8_PATH_PRINT_DESIGN,
    I8_PATH_WAREHOUSE_LIST,
    i8_endpoint_of,
)
from app.mod14_config.models import AppSetting
from app.mod14_config.repository import save
from app.mod14_config.view import render_settings_page
from tests.acc_plugin import acc

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


def _page(**kw) -> str:
    env = {s.key: f"http://env-default/{s.key}" for s in SPECS}
    return render_settings_page(env_values=env, logs=[], **kw)


# ------------------------------------------------------------ 001-01 页面范围


@acc("ACC-CFG-SETUP-001", "001-01")
def test_设置页只列连接参数不含账号密码与端点路径():
    html = _page()
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


# ------------------------------------------------------------ 001-02 取值优先级


@acc("ACC-CFG-SETUP-001", "001-02")
def test_取值优先级库优先_清空即回落(monkeypatch):
    monkeypatch.setattr(app_settings, "_load_from_db", lambda: {SETTING_I8_BASE_URL: "http://from-db"})
    app_settings.invalidate()
    try:
        assert effective(SETTING_I8_BASE_URL, "http://from-env") == "http://from-db"
        # 库里为空 ⇒ 回落 .env
        assert effective(SETTING_PRINTER_IPP_URL, "ipp://env:631/ipp/print") == "ipp://env:631/ipp/print"
        # 库与 .env 都空 ⇒ 空串（不臆造）
        assert effective(SETTING_PRINT_ID_MATERIAL, "") == ""
    finally:
        app_settings.invalidate()


# ------------------------------------------------------------ 001-03 改动留痕


@acc("ACC-CFG-SETUP-001", "001-03")
def test_改动留痕含改前改后与改动人():
    s = _Sess()
    changes = save(s, values={SETTING_PRINTER_IPP_URL: "ipp://new:631/ipp/print"}, operator="张三")

    assert changes == [{"key": SETTING_PRINTER_IPP_URL, "old": "", "new": "ipp://new:631/ipp/print"}]
    logs = s.logs()
    assert len(logs) == 1, "每次变更必须留痕一条"
    lg = logs[0]
    assert lg.key == SETTING_PRINTER_IPP_URL
    assert lg.old_value == ""                       # 改前（原来是空 = 未设置）
    assert lg.new_value == "ipp://new:631/ipp/print"
    assert lg.operator == "张三"                     # 改动人
    assert lg.at is not None                        # 时间
    assert isinstance(s.added[0], AppSetting)       # 当前值也落了库


@acc("ACC-CFG-SETUP-001", "001-03")
def test_值没变则不记留痕():
    s = _Sess({SETTING_PRINTER_IPP_URL: AppSetting(key=SETTING_PRINTER_IPP_URL, value="ipp://same")})
    changes = save(s, values={SETTING_PRINTER_IPP_URL: "ipp://same"}, operator="张三")
    assert changes == [] and s.logs() == []


# ------------------------------------------------------------ 001-04 反直觉提示


@acc("ACC-CFG-SETUP-001", "001-04")
def test_版式ID带反直觉提示():
    html = _page()
    assert "其他支出" in html, "必须写明：材料类走「其他支出」版式"
    assert "付款通知书" in html, "必须写明：外租机械类走「付款通知书」版式"
    assert "与直觉相反" in html
    assert "配反了" in html or "印错版式" in html


# ------------------------------------------------------------ 001-05 只影响传入项


@acc("ACC-CFG-SETUP-001", "001-05")
def test_保存只影响传入的key不得顺带改别的():
    rows = {
        SETTING_I8_BASE_URL: AppSetting(key=SETTING_I8_BASE_URL, value="http://keep-me"),
        SETTING_PRINT_ID_MATERIAL: AppSetting(key=SETTING_PRINT_ID_MATERIAL, value="PID-KEEP"),
    }
    s = _Sess(rows)
    changes = save(s, values={SETTING_PRINTER_IPP_URL: "ipp://x:631/ipp/print"}, operator="张三")

    assert [c["key"] for c in changes] == [SETTING_PRINTER_IPP_URL]
    assert rows[SETTING_I8_BASE_URL].value == "http://keep-me"      # 一行不动
    assert rows[SETTING_PRINT_ID_MATERIAL].value == "PID-KEEP"
    assert len(s.logs()) == 1


# ------------------------------------------------------------ 001-06 端点随之推导


@acc("ACC-CFG-SETUP-001", "001-06")
def test_改服务地址后四个端点随之推导(monkeypatch):
    class _S:
        i8_base_url = "http://old-host:1"

    monkeypatch.setattr(app_settings, "_load_from_db", lambda: {SETTING_I8_BASE_URL: "http://new-host:2"})
    app_settings.invalidate()
    try:
        for path in I8_PATHS:
            got = i8_endpoint_of(_S(), path)
            assert got == "http://new-host:2" + path, f"端点未跟随服务地址：{got}"
            assert "old-host" not in got
        # 库为空 ⇒ 回落 .env（桩的 i8_base_url）
        monkeypatch.setattr(app_settings, "_load_from_db", lambda: {})
        app_settings.invalidate()
        assert i8_endpoint_of(_S(), I8_PATH_PRINT_DESIGN) == "http://old-host:1" + I8_PATH_PRINT_DESIGN
    finally:
        app_settings.invalidate()


# ------------------------------------------------------------ 001-07 非法拒绝


@acc("ACC-CFG-SETUP-001", "001-07")
def test_地址格式非法须拒绝不静默写入():
    assert validate(SETTING_I8_BASE_URL, "106.46.169.212:30785") is not None   # 缺协议
    assert validate(SETTING_PRINTER_IPP_URL, "192.168.5.248:631") is not None
    assert validate(SETTING_I8_BASE_URL, "") is None                            # 空 = 清除，合法
    assert validate(SETTING_I8_BASE_URL, "http://a:1") is None
    assert validate(SETTING_PRINTER_IPP_URL, "ipp://a:631/ipp/print") is None
    # 版式 ID 是文本（不强求 URL 形态），空亦合法
    assert validate(SETTING_PRINT_ID_MATERIAL, "3700000000000215") is None
    # 未知 key 必须报错（防拼错键名静默写库）
    assert validate("i8_typo_key", "x") is not None
