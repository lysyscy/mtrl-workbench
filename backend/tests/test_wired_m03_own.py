"""前端壳「归属」适配的离线断言（`m03` 付款通知书 ⇒ 各页「项目筛选」的候选源）。

⭐ 背景（实测报障「项目筛选点开没有任何项目」）——**两个原因叠加**：
1. **真 bug**：适配层把 `proj` 填成 `project_display`（**展示名**），而 `ownOf(n)` 拿它做
   `PJs.find(p => p.full === n.proj)`（**全名等值**）、`isShellFull(n.proj)`（判壳）、
   `matchKids(n.proj, n.doc)`（壳下匹配）⇒ 三条**全部静默失配** ⇒ 归属判不出 ⇒ 候选空。
2. **数据**：库里付款通知书 **0 条**（归属未走完 ⇒ 整批不入库）⇒ 候选源天然空 ——
   这条不是 bug，但**它让 bug 一直没被发现**（两边都空）。

⇒ 断言钉两件事：`proj` 必须是**全名**；`OWN` 必须由**后端的 `ownership_id`** 重建。
"""

from __future__ import annotations

from pathlib import Path

from tests.acc_plugin import acc

ROOT = Path(__file__).resolve().parents[2]
SHELL = (ROOT / "backend" / "app" / "web" / "index.html").read_text(encoding="utf-8")


@acc()
def test_适配层的proj必须是项目全名():
    """⛔ `project_display` 是**展示名** ⇒ 填它会让归属判定三条路径全部静默失配。"""
    i = SHELL.find("function adaptNotice(")
    body = SHELL[i:i + 2200]
    assert "proj: x.project_name" in body, "`adaptNotice` 的 `proj` 没取项目**全名**"
    assert "proj: x.project_display" not in body, "`proj` 仍在优先取**展示名**（归属会判不出）"


@acc()
def test_归属缓存由后端的ownership_id重建():
    """⭐ 后端给了 `ownership_id`（权威值）⇒ 每次重拉都要按它重建 `OWN`。"""
    i = SHELL.find("async function reloadNotices()")
    body = SHELL[i:i + 1400]
    assert "x.ownership_id" in body, "`reloadNotices()` 没读后端的 `ownership_id`"
    assert "OWN[String(x.notice_id)]" in body, "没把归属灌进 `OWN`（键要 String，与档案 id 对齐）"
    assert "Object.keys(OWN).forEach" in body, "没**原地清空** `OWN`（不能 `OWN={}` —— 会切断外部引用）"
    # boot 必须走同一个出口（否则启动路径不填 OWN）
    # ⚠️ 2026-09-19（`P3` 主体）：取数改成「进哪页拉哪页」⇒ 判据搬到**取数表**
    #    （⛔ 判据一字未改：两条路径必须走**同一个**出口 `reloadNotices()`，不许各写一套）。
    from tests.shell_load_helpers import loaders as _loaders   # noqa: PLC0415
    assert "付款通知书" in _loaders(), "取数表里没有「付款通知书」这一路（两条路径会各写一套）"
