"""`MOD-14` **系统设置页**（服务端渲染 ＋ PRG）—— 口径主人 =《说明书》§7.8。

页面三段：**① 口径说明（可折叠）→ ② 设置表单 → ③ 变更留痕**。
⚠️ 本页**一律全局**；i8 账号密码**不在这**（绑定到本系统账号、每人一份 ⇒ 归 `MOD-15`）。
"""

from __future__ import annotations

from app.core.app_settings import SPECS, stored_value
from app.mod03_notice.page import BASE_CSS, esc

PAGE_ID = "m14"

from app.core.nav import NAV  # noqa: F401 —— 全站导航的**唯一主人**（改动见 core/nav.py）

TIPS = (
    "本页只放**会变、且变的时候不该改文件重启**的连接参数。",
    "取值优先级：**本页所设 → `.env`**（清空即回落到 `.env`）。",
    "⚠️ **i8 的账号与密码不在这里** —— 它绑定到**本系统的账号**、**每人一份**（登录体系落地后可在自己的账号里填）。",
    "⚠️ 本页每项改动**都会留痕**（与「规则配置」的硬删不留痕有意不同 —— 配错会印错版式 / 抓错数据）。",
)

EXTRA_CSS = """
.row{border:1px solid var(--bd);border-radius:8px;padding:12px 14px;margin:10px 0;background:var(--sf)}
.row .lb{font-weight:600;margin-bottom:4px}
.row .hn{color:var(--tx2);font-size:12px;line-height:1.7;margin:4px 0 8px}
.row .mt{font-size:12px;color:var(--tx2);margin-top:6px}
.row .mt b{color:var(--tx)}
.src{display:inline-block;font-size:11px;padding:1px 7px;border-radius:9px;margin-left:6px;
     background:var(--pri-l);color:var(--pri);vertical-align:middle}
.src.env{background:var(--sf2);color:var(--tx2)}
.err{border:1px solid var(--dg);background:var(--dg-l);color:var(--dg);padding:8px 12px;border-radius:6px;margin:10px 0}
.ok{border:1px solid var(--ok);background:var(--ok-l);color:var(--ok);padding:8px 12px;border-radius:6px;margin:10px 0}
.logs{font-size:12px}
.logs td{padding:4px 8px;border-bottom:1px solid var(--bd)}
"""


def _nav_html() -> str:
    return "".join(f'<a href="{esc(h)}">{esc(t)}</a>' for h, t in NAV)


def _row_html(spec, env_value: str) -> str:
    stored = stored_value(spec.key)
    if stored:
        src = '<span class="src">本页所设</span>'
        meta = ("当前生效：<b>%s</b>（本页所设；清空输入框并保存即回落到 <code>.env</code>）"
                % esc(stored))
    else:
        src = '<span class="src env">.env</span>'
        meta = ("未在本页设置 ⇒ 当前用 <code>.env</code> 的值：<b>%s</b>"
                % (esc(env_value) if env_value else "<i>（.env 也为空）</i>"))
    return (
        '<div class="row">'
        f'<div class="lb">{esc(spec.label)}{src}</div>'
        f'<div class="hn">{spec.hint}</div>'
        f'<input class="inp" style="width:100%" name="{esc(spec.key)}" value="{esc(stored)}" '
        f'placeholder="{esc(env_value)}" autocomplete="off">'
        f'<div class="mt">{meta}</div>'
        "</div>"
    )


def render_settings_page(*, env_values: dict[str, str], logs: list, flash: str = "",
                         errors: list[str] | None = None) -> str:
    body: list[str] = [
        '<div class="wrap">',
        '<div class="hdr"><h1>设置</h1><div class="nav">%s</div></div>' % _nav_html(),
    ]
    if errors:
        body.append('<div class="err">%s</div>' % "<br>".join(esc(e) for e in errors))
    if flash:
        body.append('<div class="ok">%s</div>' % esc(flash))

    body.append("<details open><summary>口径说明</summary><ul>%s</ul></details>"
                % "".join(f"<li>{t}</li>" for t in TIPS))

    body.append('<form method="post" action="/m14/settings/save">')
    for spec in SPECS:
        body.append(_row_html(spec, env_values.get(spec.key, "")))
    body.append('<div style="margin-top:12px"><button class="btn" type="submit">保存</button></div>')
    body.append("</form>")

    body.append('<h2 style="margin-top:22px">变更留痕</h2>')
    if logs:
        rows = "".join(
            '<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>'
            % (esc(str(getattr(l, "at", ""))[:19]),
               esc(getattr(l, "key", "")),
               esc(getattr(l, "old_value", "") or "（空）"),
               esc(getattr(l, "new_value", "") or "（空）"),
               esc(getattr(l, "operator", "")))
            for l in logs
        )
        body.append('<table class="logs tb"><thead><tr><th>时间</th><th>设置项</th>'
                    '<th>改前</th><th>改后</th><th>改动人</th></tr></thead>'
                    f"<tbody>{rows}</tbody></table>")
    else:
        body.append('<div class="mt">（还没有改动记录）</div>')

    body.append("</div>")
    return (
        "<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
        "<title>设置 · 材料报表自动化工作台</title>"
        f"<style>{BASE_CSS}{EXTRA_CSS}</style></head><body>"
        + "".join(body)
        + "</body></html>"
    )


__all__ = ["PAGE_ID", "NAV", "TIPS", "EXTRA_CSS", "render_settings_page"]
