"""看板页渲染（**不占模块号** · 交互规格主人 = 原型 `V.home`）。

⭐ 把手与原型一致：`data-todo="<键>" data-n="<数>" data-act="go" data-k="<键>"` ——
   `demo/_smoke.js` 的 `§10f` 就是按这套把手取值的（**改把手 = 改契约**）。
"""

from __future__ import annotations

from app.mod03_notice.page import BASE_CSS, esc, nav_html

PAGE_ID = "home"
TITLE = "看板 · 待办"

TIPS = (
    "**这是默认落地页**：把各域「待人处理」的事集中列出，数字**实时算**（不是昨天的快照）。",
    "⚠️ **看板只做汇总**：每项数字都取自**对应数据域自己的出口** —— 要改口径请去那一页，别在本页改。",
    "⚠️ 「集采待确认」「差异待核对」所属域**尚未实现** ⇒ 记 0 并标注（⛔ 不臆造、也不把该项藏起来）。",
)

EXTRA_CSS = """
.hgrid{display:flex;flex-wrap:wrap;gap:12px;margin-top:10px}
.todo{flex:0 0 210px;display:block;text-decoration:none;color:inherit;
  background:var(--sf);border:1px solid var(--bd);border-radius:10px;padding:12px 14px}
.todo:hover{border-color:var(--pri)}
.todo .v{font-size:26px;font-weight:700;line-height:1.1}
.todo.zero .v{color:var(--mut)}
.todo .k{margin-top:4px;font-weight:600}
.todo .d{margin-top:3px;font-size:12px;color:var(--mut)}
.todo .tag{margin-left:4px}
"""


def _card_html(row: dict) -> str:
    count = int(row["count"])
    cls = "todo zero" if count == 0 else "todo"
    mark = " <span class=\"tag wn\">该域未实现</span>" if row["unsupported"] else ""
    return (
        f'<a class="{cls}" href="{esc(row["target"])}"'
        f' data-todo="{esc(row["key"])}" data-n="{count}"'
        f' data-act="go" data-k="{esc(row["key"])}">'
        f'<div class="v">{count}</div>'
        f'<div class="k">{esc(row["label"])}</div>'
        f'<div class="d">{esc(row["domain"])} · {esc(row["cover"])}{mark}</div>'
        f'</a>'
    )


def render_home(rows: list[dict], *, errors: dict | None = None) -> str:
    """→ 看板页 HTML。`rows` = `domain.dashboard()` 的输出（**9 项恒在**）。"""
    body = "".join(_card_html(r) for r in rows)
    warn = ""
    if errors:
        detail = "；".join(f"{k}（{v[:60]}）" for k, v in errors.items())
        warn = f'<div class="notice wn">⚠️ 有 {len(errors)} 项取数失败、已记 0：{esc(detail)}</div>'
    tips = "".join(f"<li>{t}</li>" for t in TIPS)
    return (
        "<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
        f"<title>{esc(TITLE)}</title><style>{BASE_CSS}{EXTRA_CSS}</style></head><body>"
        # ⭐ 全站导航（唯一出口）—— **本页是默认落地页，没有它用户进来就不知道有哪些页面**
        f"{nav_html('/')}"
        f'<section class="view" data-view="{PAGE_ID}">'
        f"<h3>{esc(TITLE)}</h3>"
        f'<ul class="mini">{tips}</ul>'
        f"{warn}"
        f'<div class="hgrid" data-seg="todos">{body}</div>'
        "</section></body></html>"
    )


__all__ = ["PAGE_ID", "TITLE", "TIPS", "EXTRA_CSS", "render_home"]
