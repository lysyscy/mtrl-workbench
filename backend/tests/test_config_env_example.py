"""⭐ `.env.example` 必须**覆盖** `Settings` 的每一个字段（`TAIL-192`-① · 2026-09-29）。

**为什么值得一条**：`.env.example` 是**换机 / 目标机时唯一能照着填的东西**（真 `.env` 既不进 git、
也不进交付包）—— 缺一个键 ⇒ 那台机器上**没人知道还有这一项**，表现是"某个功能默默用了默认值"，
很难查。2026-09-29 结构审计实测缺 **5** 个：`I8_SM2_PRIVATE_KEY` / `PRINT_MODE` /
`PRINTER_NAME` / `OPERATOR_NAME` / `SESSION_SECRET`。

**判法是双向的**：
① `Settings` 的每个字段都要在样例里有键；
② 样例里的键**必须**真有对应字段（防"样例里写了、代码根本不读"= 给人一条假线索）。

⚠️ 本件**刻意不绑契约面**（`@acc()` 空参）：这两条守的是**工程侧的可操作性**（换机时能不能配起来），
不对应任何"用户看得见的行为" ⇒ 不硬绑涨绿数（口径见 `TAIL-167` 的裁定）。要登记时按 `TAIL-147` 的先例走。
"""

from __future__ import annotations

from pathlib import Path


from app.core.config import Settings

ROOT = Path(__file__).resolve().parents[2]
ENV_EXAMPLE = ROOT / ".env.example"


def _env_example_keys() -> set[str]:
    """样例里**未被注释掉**的键（`#` 打头的行不算；`.env` 的注释惯例就是 `#`）。"""
    keys: set[str] = set()
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        keys.add(s.split("=", 1)[0].strip().upper())
    return keys


def test_样例必须覆盖配置的每一个字段():
    """缺哪个键 ⇒ 换机时那台机器上没人知道要填它。"""
    expected = {f.upper() for f in Settings.model_fields}
    have = _env_example_keys()
    missing = sorted(expected - have)
    assert not missing, (
        f"`.env.example` 缺这些键 ⇒ 别人不知道还有它们：{missing}"
        "（补一行「键=」＋ 一句「填什么 / 不填会怎样」）"
    )
    extra = sorted(have - expected)
    assert not extra, (
        f"`.env.example` 里这些键**代码根本不读**：{extra}"
        "（要么是拼错了，要么是已废弃 ⇒ 别给人一条假线索）"
    )
