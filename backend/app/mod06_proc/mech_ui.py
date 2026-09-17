"""`MOD-06` **机械手录**（§5.2.5 ③）—— 区块渲染 ＋ 表单校验（**不连库**）。

口径：
- ⭐ **机械 6 列全段手录**（含历史段）—— 与材料列**相反**：材料列**恒只读**（引用 / 快照，§5.2.3），
  机械列**两段都能录**（出口 = `domain.column_editable`）。
- ⭐ 值落**旁路载体** `proc_mech_manual` ⇒ **不被重抓 i8 / 重导历史覆盖**（§5.2.5 ③ 与 §9.3 同源思路）。
- ⚠️ **0 是合法录入值**（表单空框与「录了 0」在金额上不可区分 ⇒ 空按 0 记）；
  **负数 / 非数字 ⇒ 报错且一个字都不写库**（`core.money.require_non_negative` 是值的唯一出口）。

⚠️ 本文件**只渲染与校验**：落库唯一出口 = `repository.save_mech`；路由只做「校验 → 调它 → PRG 回跳」。
"""

from __future__ import annotations

from decimal import Decimal

from app.core.money import MoneyError, to_money
from app.mod06_proc import domain as D
from app.mod03_notice.page import esc

PLACEHOLDER_YM = "YYYY-MM"


def parse_mech_values(raw) -> dict[str, Decimal]:
    """表单 6 个框 → `{mech_i: Decimal}`。**空 ⇒ 0**；**非数字 / 负数 ⇒ `ValueError`**（带列名）。"""
    out: dict[str, Decimal] = {}
    for i, label in enumerate(D.MECH_COLUMNS):
        key = f"mech_{i}"
        text = str((raw or {}).get(key) or "").strip().replace(",", "")
        if not text:
            out[key] = Decimal("0.00")
            continue
        try:
            value = to_money(text)
        except (MoneyError, ArithmeticError, ValueError) as exc:
            raise ValueError(f"「{label}」不是数字：{text!r}") from exc
        if value < 0:
            raise ValueError(f"「{label}」不得为负数（当前 {value}）")
        out[key] = value
    return out


def _value_of(data: dict, ym: str, key: str) -> str:
    """该核算月的**现值**（用于回填表单）；没有这一行 ⇒ 空串。"""
    for row in data.get("rows") or ():
        if str(row.get(D.YM_KEY)) == ym:
            value = row.get(key)
            return "" if value in (None, "") else f"{to_money(value):.2f}"
    return ""


def block_html(data: dict, *, ym: str = "", message: str = "", kind: str = "ok") -> str:
    """「机械手录」区块（表体下方）——**两段都可录** ＋ **0 合法 / 负数拒绝**的显式说明。

    ⚠️ 输入框只给**机械 6 列**（`mech_*`）：材料列**不得出现输入框**（§5.2.3 · 判据 `ACC-RPT-PROC-001/001-08`）。
    """
    state = data["state"]
    months = list(data.get("mech_months") or ())
    fields = "".join(
        f'<div class="fi"><label>{esc(name)}</label>'
        f'<input class="inp num" name="mech_{i}" value="{esc(_value_of(data, ym, f"mech_{i}"))}" '
        f'inputmode="decimal" placeholder="0.00"></div>'
        for i, name in enumerate(D.MECH_COLUMNS)
    )
    tip = (f"已手录 <b>{len(months)}</b> 个月：{esc('、'.join(months) or '（还没有）')}。"
           if months else "该项目还没有手录过机械费 —— 填一个核算月再保存即可。")
    return (
        '<details class="mech" data-seg="mech-manual" open>'
        "<summary>机械手录（机械 6 列 · 两段都可录）…</summary>"
        f'<form method="post" action="/m06/mech" class="mechf">'
        f'<input type="hidden" name="pj" value="{esc(state.get("warehouse") or "")}">'
        f'<input type="hidden" name="tab" value="{esc(state.get("tab"))}">'
        '<div class="fbar">'
        '<div class="fi"><label>核算月</label>'
        f'<input class="inp" name="ym" value="{esc(ym)}" placeholder="{esc(PLACEHOLDER_YM)}"></div>'
        f"{fields}"
        '<div class="fi"><label>&nbsp;</label><span>'
        '<button class="btn sm pri" type="submit">保存本月手录</button></span></div>'
        "</div>"
        f'<div class="mut sm" data-seg="mech-tip">{tip}'
        "机械费报表（`MOD-10`）做好后**只换数据源、页面不动**（§5.2.5 ③）。"
        "**0 是合法值**；**负数会被拒绝且不写库**。</div>"
        "</form></details>"
    )


def notice_html(message: str, kind: str = "ok") -> str:
    """回执条（PRG 回跳后显示）——**一律 `esc`**（消息走查询串 ⇒ 属反射型注入面）。"""
    if not str(message or ""):
        return ""
    k = str(kind or "ok")
    k = k if k in ("ok", "wn", "err") else "ok"
    return f'<div class="notice {k}" data-seg="mech-msg">{esc(message)}</div>'


__all__ = ["PLACEHOLDER_YM", "parse_mech_values", "block_html", "notice_html"]
