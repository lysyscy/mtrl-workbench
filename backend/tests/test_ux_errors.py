"""`TAIL-117` 批次 1（2026-09-27 用户裁定"按推荐执行"）：**报错人话化**的离线判据。

**守则落点**：§3.2（报错堆栈 / 调试日志拦在界面之外）· §3.7（报错处理硬规则：先翻成人话 ＋ 给下一步）
· §5.3（执行形态）· §5.8（内部信息**换地方**，不是删掉）· §6 第 1/2 条。

⭐ **为什么只能钉源码形态**：这条规则的本体是「**异常 → 屏幕**」之间那道转换，而 `toast()` 的内容是
   **运行期拼**的 ⇒ 离线看不见"用户到底看到什么"。⇒ 离线钉**两端形态**：
     ① **出口唯一** —— 造错的口只有一个（`errHuman`），⛔ 不许到处 `new Error(...)`；
     ② **原始串换地方** —— 方法 / 全路径 / 状态码只许进 `err.tech`（只进 console）；
     ③ **上屏面干净** —— 任何 `toast(...)` 那一行都不许出现 `HTTP ${` 或 `/api/`。
   真机那一半在 `tools/probe/_shell_err.py`（㉔：**真造一个 500**，看屏幕上到底有没有 `HTTP 500`）。

⚠️ 本件**不判**文案措辞好不好（那是守则 §10 变更记录与用户的事），只判**结构**。
"""

from __future__ import annotations

from tests.shell_src import SHELL, parts_text, func_body

#: 造错的口（唯一）——名字变了就同批改本件（⛔ 别让判据静默失效）
ERR_HUMAN = "errHuman"


def _part(suffix: str) -> str:
    """按**相对仓根的路径后缀**取壳的某一件（`parts_text()` 的键形如 `backend/app/web/shell/api.js`）。"""
    for rel, text in parts_text():
        if rel.endswith(suffix):
            return text
    raise AssertionError(f"壳里没有这一件：{suffix}（现有 {[r for r, _ in parts_text()]}）")


def test_造错的口只有一个():
    """⭐ `new Error(` 全壳**只许出现在「人话出口」的函数体里**。

    ⚠️ 为什么盯这个：分散 `new Error(...)` 的下场是**迟早有一处**又把 `HTTP 500` 拼进 `message`，
       而那一处会被 60 余处 `catch` 原样上屏（本批次之前就是这个状态）。
    ⚠️ **能证伪**：在任一 `.js` 里写回 `throw new Error('...')` ⇒ 本件必红。
    """
    assert f"const {ERR_HUMAN}" in SHELL, (
        f"「人话出口」（`{ERR_HUMAN}`）不见了 —— 守则 §3.7 在这套壳里**没有落点**了")
    hits = [rel for rel, text in parts_text() if "new Error(" in text]
    assert hits == ["backend/app/web/shell/api.js"], (
        f"`new Error(` 只许出现在「人话出口」那一件里；现在出现在：{hits}"
        "（散布出去 ⇒ 迟早有一处把状态码 / 接口地址当消息抛给用户）")


def test_五个取数失败点都过人话出口_技术串只进技术明细():
    """`api.js` 的 5 个失败点（`get` / `post` / `send` / `postForm` / `postFile`）必须**都**经人话出口，
    且原始串（`方法 全路径 → HTTP 状态码`）是**第二个实参** ⇒ 落到 `err.tech`（只进 console）。

    ⚠️ **能证伪**：把某一处改回 `throw new Error(...)` ⇒ 上一件红；把 tech 拼进 `message` ⇒ 本件红
       （`err.tech` 与 `console.warn` 都在函数体里，是"技术串有地方去"的唯一证据）。
    """
    api = _part("shell/api.js")
    calls = api.count(f"throw {ERR_HUMAN}(")
    assert calls >= 5, (
        f"`api.js` 里只有 {calls} 处走人话出口（应 ≥ 5：get / post / send / postForm / postFile）")
    assert "e.tech = String(tech" in api, "人话出口没把技术串收进 `err.tech`（⇒ 排障线索无处可去）"
    assert "console.warn" in api, "人话出口没把技术串**留痕**到 console（守则 §5.8：换地方，不是删掉）"
    assert "→ HTTP ${r.status}" in api, "技术串（方法 → 全路径 → 状态码）消失了 ⇒ 排障没留痕"


def test_提示条那一行不许出现内部串():
    """⭐ 任何 `toast(...)` 的那一行都不许出现 `HTTP ${` 或 `/api/` ——
    提示条是**用户读的**（守则 §5.2：面向用户的文字要能用非技术语言读懂）。

    ⚠️ 这条是**上屏面**的守：它不关心你怎么实现，只关心那句话里有没有内部串。
    ⚠️ **能证伪**：把状态码拼回提示条那一行（本批次改掉的就是它）⇒ 本件必红。
    """
    bad = [l.strip() for l in SHELL.splitlines()
           if "toast(" in l and ("HTTP ${" in l or "/api/" in l)]
    assert not bad, "这些提示条把内部串直接给用户看了（守则 §3.1/§3.7）：\n" + "\n".join(bad)


def test_首屏取数失败的横幅_人话在外技术明细折叠():
    """⭐ 首屏取数失败的那条**常驻横幅**（`bootErrorBanner`）必须：
    ① 可见区只说人话（`esc(BOOT_ERROR)` —— 它由 `soft()` 收到的 `e.message` 拼成，已是人话）；
    ② 原始串折进 `<details>`「技术明细」（守则 §5.9 次要信息可折叠 ＋ §5.8 换地方）；
    ③ 给**下一步**（重试 / 找管理员）。

    ⚠️ **能证伪**：把 `<details>` 去掉、直接把 `failsTech` 拼进可见区 ⇒ 本件必红。
    """
    seg = func_body("bootErrorBanner")
    assert "<details" in seg and "技术明细" in seg, \
        "横幅没有把原始串折进「技术明细」—— 用户会看到 `GET /api/… → HTTP 500`"
    assert "failsTech" in seg, "横幅的技术明细不是取自 `failsTech`（人话与技术串没有分开收）"
    assert ("重试" in seg) and ("管理员" in seg), "横幅没说**下一步**（守则 §2.2）"
    assert "esc(BOOT_ERROR)" in seg and "failsTech.map(t => esc(t))" in seg, "两半均须安全转义"
    assert "<details open" not in seg, "技术明细默认折叠"
