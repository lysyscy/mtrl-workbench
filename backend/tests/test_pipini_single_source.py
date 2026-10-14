"""安装源由ops/pip.ini持有，venv副本须逐字节一致。

2026-10-14用户要求全部最新稳定包，镜像滞后后改用官方源。
保留显式单一HTTPS源和副本保障；缺失、HTTP、多源或副本漂移须失败。
"""

from __future__ import annotations

import pathlib

import pytest

from tests.acc_plugin import acc

BACKEND = pathlib.Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
SRC = REPO / "ops" / "pip.ini"                  # ⭐ 唯一主人（随 bundle ⇒ 目标机 clone 就有）
DST = BACKEND / ".venv" / "pip.ini"             # 副本（`.venv` 不进包 ⇒ 由 deploy_restore.ps1 落）


@acc()
def test_依赖安装源在仓里_且单一明确():
    """2026-10-14镜像滞后，最新版本改用官方源；保留显式单源与副本保障。"""
    assert SRC.exists(), (
        f"⛔ 依赖镜像的**真源**不见了：{SRC}\n"
        "  ⇒ 它是 D10 加固① 的唯一主人（`deploy_restore.ps1` 第 3b 步从它复制到 venv 级）。\n"
        "  ⇒ 丢了的话：目标机重建 venv 后会**悄悄**走默认 PyPI 官方源（国内可能极慢/超时）。")
    text = SRC.read_text(encoding="utf-8")
    assert "[global]" in text, f"{SRC} 里没有 `[global]` 段 —— pip 不认这份配置"
    idx = [ln for ln in text.splitlines() if ln.strip().startswith("index-url")]
    assert len(idx) == 1, f"{SRC} 必须明确指定一个 `index-url`"
    url = idx[0].split("=", 1)[1].strip()
    assert url.startswith("https://"), f"`index-url` 必须使用 HTTPS：{url!r}"
    assert not any(ln.strip().startswith("extra-index-url") for ln in text.splitlines()), "不允许多源回退"


@acc()
def test_安装源缺失或多源必须拒绝(tmp_path, monkeypatch):
    source = tmp_path / "pip.ini"
    monkeypatch.setattr(f"{__name__}.SRC", source)
    for text in ("[global]\n", "[global]\nindex-url=http://pypi.org/simple\n", "[global]\nindex-url=https://pypi.org/simple\nextra-index-url=https://mirrors.aliyun.com/pypi/simple/\n"):
        source.write_text(text, encoding="utf-8")
        with pytest.raises(AssertionError):
            test_依赖安装源在仓里_且单一明确()


@acc()
def test_venv_那份是真源的副本_逐字节相同():
    """⚠️ **本机没有 venv（别的机器 / 干净 clone）⇒ 跳过** —— 那是"目标机已知代价"，⛔ 不判红。

    ⚠️ 比的是**字节**（不是文本）：这条守的正是"**一处定义**" —— 副本被手改过 ⇒ 当场红。
    """
    if not DST.exists():
        import pytest

        pytest.skip(f"本机没有 {DST}（⛔ 不当缺陷：`.venv` 不进包，目标机由脚本落）")
    assert DST.read_bytes() == SRC.read_bytes(), (
        f"⛔ {DST} 与真源 {SRC} **不一致** ⇒ 多处定义（本仓最忌）。\n"
        "  ⇒ 要么把副本改回真源的样子，要么**改真源**（改完 `deploy_restore.ps1` 会照它落）。\n"
        f"  真源 = {SRC.read_text(encoding='utf-8')!r}\n"
        f"  副本 = {DST.read_text(encoding='utf-8')!r}")
