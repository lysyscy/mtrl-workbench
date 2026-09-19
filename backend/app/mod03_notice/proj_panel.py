"""项目选择器（可多选 / 单选）—— **全站唯一出口**（原型 `projPanel(...)` 的服务端等价物）。

**为什么必须唯一**（2026-09-17 实测后抽件）：
- 设计规则 **§8.2 复用点** 明写「**项目选择器**」应当**只有一个出口**；
- 原型里它是共用渲染函数 `projPanel({list, selected, allAct, noneAct, pickAct, meta})`，
  外层统一 `<div class="fi pjwrap">` ＋ 按钮（`已选 N 个` / `全部项目` ＋ `▼`）＋ 展开面板；
- ⚠️ **实测（`tools/ui_parity.py`）：本工程 7 页各写一份** —— `m03` 用 `<select multiple>`、
  `m06`/`m07` 自造 `.pjsel`（且两份 CSS 取值不一致）、`m09` 又是一份 radios …
  ⇒ ① 与原型结构对不上（`pjwrap` 恒为 0）；② 改一处样式要改 7 处。

**形态说明（有意与原型不同 · 属"怎么展开"而非"结构长什么样"）**：
原型靠 JS 展开浮层；本工程是**服务端渲染** ⇒ 用 **`<details>`** 承载「按钮 ＋ 面板」（**零 JS**）。
**结构与类名照原型**（`.fi.pjwrap` / `.pjsel` / `.btn`），样式只在 `BASE_CSS`（真源）定义一次。

⭐ **S4④ 查证结论（2026-09-19 · `§19` 批 4）**：本件**只被服务端渲染页用** ——
   全仓唯一生产调用方 = `notice_page._filter_controls`（本模块的测试在 `test_notice_page.py`）；
   **没有任何 API 端点复用它**（新壳自己的项目面板是 `app/web/index.html` 的 `projPanel()`）。
   ⇒ 它属**页面件**，随批 4 的删页一起消失 ✗（不是"按裁定保留"）。
"""

from __future__ import annotations

from app.mod03_notice.page import esc

DEFAULT_EMPTY_HINT = "（项目档案为空 —— 先跑一次「同步常用项目列表」）"


def proj_panel_html(
    options,
    *,
    selected=(),
    multiple: bool = True,
    name: str = "project",
    form: str = "",
    label: str = "项目",
    empty_hint: str = DEFAULT_EMPTY_HINT,
) -> str:
    """→ **一整段** `.fi.pjwrap`（含 `<label>`）—— 直接当 `filters[i]["html"]` 用，
    并给该项加 `"raw": True`（否则 `_render_filter_bar` 会再包一层 `.fi`／`<label>`）。

    - `options` —— `[{"key", "label"}, …]`；**`key` = 仓库名**（§2.7.4），显示名走档案的展示名：
      候选出口唯一 = `MOD-01` 的档案列表，⛔ 各页别自己拼。
    - `selected` —— 已选 `key` 集合；**空 = 全部项目**（与原型的"全部项目"同义）。
    - `multiple=False` ⇒ 单选（`radio`；原型里台账那类"单选"页用它）。
    - `form` —— 控件在 `<form>` 之外时用 `form="<id>"` 关联（`m03` 就是这种）。
    """
    keys = {str(k) for k in (selected or ())}
    label_text = f"{label}（可多选）" if multiple else label
    shown = f"已选 {len(keys)} 个" if keys else "全部项目"
    fq = f' form="{esc(form)}"' if form else ""
    opts = list(options or ())
    if not opts:
        inner = f'<div class="pjsel mut sm">{esc(empty_hint)}</div>'
    else:
        kind = "checkbox" if multiple else "radio"
        items = "".join(
            f'<label><input type="{kind}" name="{esc(name)}" value="{esc(o["key"])}"'
            f'{" checked" if str(o["key"]) in keys else ""}{fq}> '
            f'{esc(o.get("label") or o["key"])}</label>'
            for o in opts
        )
        inner = f'<div class="pjsel">{items}</div>'
    return (
        f'<div class="fi pjwrap"><label>{esc(label_text)}</label>'
        f'<details><summary class="btn"><span>{esc(shown)}</span>'
        f'<span class="mut">&#9660;</span></summary>{inner}</details></div>'
    )


__all__ = ["DEFAULT_EMPTY_HINT", "proj_panel_html"]
