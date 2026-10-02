"""`ops/pip.ini` = **依赖镜像的唯一主人**（2026-10-02 立 · 出处 = `TAIL-188` 只读清点）。

⭐ **为什么要有本件**：镜像 URL 原先**只**活在 `backend/.venv/pip.ini` 里，而 **`.venv` 是 `.gitignore` 挡掉的**
（实测 `.gitignore:14`）⇒ **不进 bundle** ⇒ 目标机**重建 venv** 之后那份加固**当场失效**
（悄悄走默认 PyPI 官方源 —— 国内可能极慢／超时），而 `deploy_restore.ps1` **一个字都不报**。
⇒ 修法（用户 2026-10-02 选「乙」）= **真源搬进仓**（`ops/pip.ini`，随包走）＋ `deploy_restore.ps1` 第 3b 步
  把它**复制成 venv 级**。

⇒ 本件守的就是**「一处定义」**：venv 那份是**副本**、必须与真源**逐字节相同**（⛔ 它不是第二个主人）。
⚠️ **能证伪**：改任一份 / 删掉真源 ⇒ 本件必红（自证 = `tools/mut/_mut_pipini.py`）。
⚠️ **不判**"哪家镜像更好" —— 那是 `D10` 的裁定（🟡 · 用户采纳），本件只判"**只有一处**"。
"""

from __future__ import annotations

import pathlib

from tests.acc_plugin import acc

BACKEND = pathlib.Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
SRC = REPO / "ops" / "pip.ini"                  # ⭐ 唯一主人（随 bundle ⇒ 目标机 clone 就有）
DST = BACKEND / ".venv" / "pip.ini"             # 副本（`.venv` 不进包 ⇒ 由 deploy_restore.ps1 落）


@acc()
def test_依赖镜像的真源在仓里_且不是官方源():
    """⭐ `ops/pip.ini` 必须存在、**真的**设了镜像 —— 否则"加固"只剩个空壳。

    ⚠️ 判"不是官方源"而不是"必须是阿里云"：**选哪家镜像属 `D10` 的裁定**（⛔ 别把本件变成换镜像的拦路石）；
    本件只挡**退化成官方源**这一种（那等于加固失效）。
    """
    assert SRC.exists(), (
        f"⛔ 依赖镜像的**真源**不见了：{SRC}\n"
        "  ⇒ 它是 D10 加固① 的唯一主人（`deploy_restore.ps1` 第 3b 步从它复制到 venv 级）。\n"
        "  ⇒ 丢了的话：目标机重建 venv 后会**悄悄**走默认 PyPI 官方源（国内可能极慢/超时）。")
    text = SRC.read_text(encoding="utf-8")
    assert "[global]" in text, f"{SRC} 里没有 `[global]` 段 —— pip 不认这份配置"
    idx = [ln for ln in text.splitlines() if ln.strip().startswith("index-url")]
    assert idx, f"{SRC} 里没有 `index-url` ⇒ 没钉镜像（D10 加固① 落空）"
    url = idx[0].split("=", 1)[1].strip()
    assert url.startswith("http"), f"`index-url` 看着不像 URL：{url!r}"
    assert "pypi.org" not in url, (
        f"⛔ 真源指回了**官方源**（{url}）⇒ D10 加固① 等于没做（走官方源在国内会很慢）。")


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
