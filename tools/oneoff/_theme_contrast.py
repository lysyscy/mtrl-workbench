"""主题**对比度体检**（诊断用 · 也可当交付前的复核）：逐套算关键配对的 WCAG 对比度。

⭐ 为什么要这一件：用户 2026-09-21 报「**左侧页面选择栏在各类主题下视觉不平衡**」——
   "不平衡"这种话没法直接断言，但它**可测**：把"文字色 / 底色"的对比度算出来，
   低于 AA（正文 4.5 / 大字号 3.0）的**就是看不清**。⛔ 不靠肉眼争论。

⚠️ 用的是**真正的 WCAG 相对亮度**（sRGB → 线性 → 0.2126R+0.7152G+0.0722B），
   ⛔ 不是 `page._lum()` 那个**粗略加权**（它是给 `_on()` 选黑白用的，两者别混）。

用法：`backend/.venv/Scripts/python.exe tools/_theme_contrast.py`
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.mod03_notice import page as P  # noqa: E402


def _srgb_to_lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _rel_lum(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    if len(h) not in (6, 8):
        raise ValueError(f"不是色值：{hex_color!r}")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * _srgb_to_lin(r) + 0.7152 * _srgb_to_lin(g) + 0.0722 * _srgb_to_lin(b)


def contrast(a: str, b: str) -> float:
    la, lb = _rel_lum(a), _rel_lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def vars_of(name: str) -> dict[str, str]:
    css = P.render_theme(name)
    out = {}
    for m in re.finditer(r"--([a-z0-9-]+):\s*([^;\n]+);", css):
        out["--" + m.group(1)] = m.group(2).strip()
    return out


#: (说明, 前景, 背景, 阈值) —— ⚠️ **配对必须照 CSS 的真实用法填**（不是"哪个色配哪个色"）
#  本表逐行对着 `backend/app/web/index.html` 的 `<style>` 抄：
#    `.sb-i{color:var(--sb-tx)}` on `.sb{background:var(--sb)}` 等。
#  ⚠️⚠️ 阈值就一条线：**凡是"给人读的文字"一律 4.5**（WCAG AA 的 3.0 只放行 ≥24px 或 ≥18.66px 粗体，
#     本仓没有那个字号）⇒ ⛔ 别拿"它是次要文字"当降标准的理由（用户已经两次报"看不清/看着不平衡"）。
#     只有**纯装饰**（分隔线）才按可辨性 1.15。
PAIRS = [
    ("正文", "--tx", "--bg", 4.5),
    ("正文/卡片", "--tx", "--sf", 4.5),
    ("次正文", "--tx2", "--sf", 4.5),
    ("弱化文字（空态/提示）", "--mut", "--sf", 4.5),
    ("主色作链接字", "--pri", "--bg", 4.5),
    ("按钮字", "--on", "--pri", 4.5),
    ("⭐侧栏-普通项", "--sb-tx", "--sb", 4.5),
    ("⭐侧栏-品牌/悬停", "--sb-hd", "--sb", 4.5),
    ("⭐侧栏-编号·分组·页脚", "--sb-mut", "--sb", 4.5),
    ("⭐侧栏-悬停底上的字", "--sb-hd", "--sb-hover", 4.5),
    ("⭐侧栏-选中项", "--on", "--sb-on", 4.5),
    ("⭐侧栏-选中项里的编号", "--sb-on-hl", "--sb-on", 3.0),
    ("侧栏分隔线可辨", "--sb-bd", "--sb", 1.15),
    ("标签-主色", "--pri-d", "--pri-l", 4.5),
    ("标签-成功", "--ok-d", "--ok-l", 4.5),
    ("标签-提醒", "--wn-d", "--wn-l", 4.5),
    ("标签-危险", "--dg-d", "--dg-l", 4.5),
    ("标签-中性", "--in-d", "--in-l", 4.5),
    ("标签-特殊", "--vi-d", "--vi-l", 4.5),
    ("成功字/卡片", "--ok-d", "--sf", 4.5),
    ("提醒字/卡片", "--wn-d", "--sf", 4.5),
    ("危险字/卡片", "--dg-d", "--sf", 4.5),
    ("中性字/卡片", "--in-d", "--sf", 4.5),
    ("特殊字/卡片", "--vi-d", "--sf", 4.5),
]


def main() -> int:
    names = P.theme_names()
    print(f"主题 {len(names)} 套：{names}\n")
    fails: list[str] = []
    for name in names:
        v = vars_of(name)
        bad = []
        print(f"── {name} ──")
        for label, fg, bg, need in PAIRS:
            if fg not in v or bg not in v:
                bad.append(f"{label}：变量缺失（{fg}/{bg}）")
                continue
            r = contrast(v[fg], v[bg])
            ok = r >= need
            if not ok:
                bad.append(f"{label} {v[fg]} on {v[bg]} = {r:.2f} < {need}")
            print(f"   {'✅' if ok else '⛔'} {label:22s} {v[fg]:>9s} on {v[bg]:>9s} = {r:5.2f}  (需 {need})")
        if bad:
            fails.append(f"{name}：\n    " + "\n    ".join(bad))
        print()
    print("=" * 60)
    if fails:
        print(f"⛔ 不达标的主题 {len(fails)}/{len(names)}：\n" + "\n".join(fails))
        return 1
    print(f"✅ 全部 {len(names)} 套的主题都过 AA")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
