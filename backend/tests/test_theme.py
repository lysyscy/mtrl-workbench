"""Theme roles, stylesheet ownership, and contrast."""

from __future__ import annotations

import re
from pathlib import Path

from app.mod03_notice import page, theme_react

APP_DIR = Path(__file__).resolve().parent.parent / "app"
THEME_SOURCE = APP_DIR / "mod03_notice" / "page.py"
# ⛔ 打印件（印在纸上的样子）—— 它的颜色**不属于**站点主题，必须排除
PRINT_DIR = APP_DIR / "mod03_notice" / "print"
# ⛔ **成品件**（导出给 Excel 的工作簿样式，如 `report_export/setl_export.py` 里的表头底色
#    `#ED7D31`）—— 与打印件**同一条理由**（§十一：「⛔ 打印件颜色不属于站点主题」）：
#    那是**交付出去的成品文件**的样式，不是页面的样式。把它拉进主题真源
#    = 让站点主题去管一个离线 Excel 文件 —— 方向就错了。
EXPORT_DIR = APP_DIR / "report_export"

# ⚠️ 2026-09-18（`§19` **批 1**）：**m01 / m02 两个静态页已删**（授权 `D18`）⇒ 这里只余 `m03`
#    （它归**批 4**：前置「打印 / 导出接进新壳」已于 2026-09-18 补齐 —— `TAIL-46`）。
# ⚠️ 2026-09-19（`TAIL-27` · `§19` **批 4**）：`STATIC_PAGES` 已随**最后一个静态页 `m03.html`**
#    一起消失（`m01`/`m02` 在批 1 删 ✓）—— 旧静态页托管（`main.py` 的 `_PAGES`）同批删掉。
#    ⛔ 判据没丢：主题真源与「同源」这条**绑定判据**在下面（`ACC-UI-THEME-001/001-05`）。

_HEX_RE = re.compile(r"(?<!&)#[0-9a-fA-F]{6}\b")   # ⚠️ 前面不是 `&` —— 排除 `&#8597;` 这类 HTML 实体
_VAR_DEF_RE = re.compile(r"(--[a-z0-9-]+):")
_VAR_USE_RE = re.compile(r"var\((--[a-z0-9-]+)\)")



def _variables(css: str) -> dict[str, str]:
    return dict(re.findall(r"(--[a-z0-9-]+):\s*([^;\n]+);", css))


def _theme_vars() -> dict[str, str]:
    return _variables(page.THEME_CSS)


def _iter_app_py():
    for f in sorted(APP_DIR.rglob("*.py")):
        if PRINT_DIR in f.parents or EXPORT_DIR in f.parents:
            continue
        yield f


# ---------------------------------------------------------------- 定义完整


def test_主题变量表可列举且覆盖全中性与状态色():
    defined = set(_theme_vars())
    # 中性
    assert {"--bg", "--sf", "--sf2", "--sf3", "--bd", "--bd2", "--bd3"} <= defined
    assert {"--tx", "--tx2", "--mut", "--mut2"} <= defined
    # 主色 + 强调底之上的文字（深色主题下会变，故必须变量化）
    assert {"--pri", "--pri-l", "--on"} <= defined
    # 特殊行 / 可编辑格 / 阴影
    assert {"--hl", "--draft", "--edit-l", "--shadow"} <= defined


def test_状态色一律四档成组():
    defined = set(_theme_vars())
    for name in ("ok", "wn", "dg", "bl", "in", "vi"):
        group = {f"--{name}", f"--{name}-d", f"--{name}-l", f"--{name}-bd"}
        assert group <= defined, f"状态色 {name} 缺档：{group - defined}"


def test_全工程引用的变量都有定义_引用了没定义会静默失效():
    """共享 Python CSS 与 React 主题引用的变量必须有定义。"""
    defined = set(_theme_vars()) | set(_VAR_DEF_RE.findall(theme_react.render_react_theme(page.DEFAULT_THEME)))
    used: set[str] = set()
    for f in _iter_app_py():
        used |= set(_VAR_USE_RE.findall(f.read_text(encoding="utf-8")))
    assert used, "全工程居然一个主题变量都没用？"
    assert not (used - defined), f"引用了但未定义（会静默失效）：{sorted(used - defined)}"


# ---------------------------------------------------------------- 只经变量出口


def test_除主题表本身外_全工程CSS不再出现色值字面量():
    seen: list[str] = []
    for f in _iter_app_py():
        text = f.read_text(encoding="utf-8")
        if f == THEME_SOURCE:
            before, begin, body = text.partition("THEME-DEF BEGIN")
            _, end, after = body.partition("THEME-DEF END")
            assert begin and end
            text = before + after
        seen.extend(f"{f.relative_to(APP_DIR.parent)}: {hit}" for hit in _HEX_RE.findall(text))
    assert not seen, "主题定义区外有硬编码色值：\n  " + "\n  ".join(seen)


def test_基础样式自带主题变量_引用BASE_CSS的页面自动获得定义():
    """全工程 8 处 `<style>{BASE_CSS}` ⇒ 变量定义**不可能漏**（这是防漏的关键设计）。"""
    assert page.BASE_CSS.startswith(page.THEME_CSS)
    assert ":root{" in page.BASE_CSS
    # 主题表在基础样式之前（CSS 变量必须先定义后使用；同名后定义者胜，顺序不能反）
    assert page.BASE_CSS.index(":root{") < page.BASE_CSS.index("table.dt{")


# ---------------------------------------------------------------- 修历史 bug


def test_合计行与分段竖线用到的变量都已定义():
    """⚠️ 2026-09-16 修的历史问题：这两条规则是**照原型抄的**，却漏抄了 `:root`
    ⇒ 变量无定义 ⇒ 整条声明静默失效（合计行吸附底色 / 内阴影 / 分段竖线都不显示）。"""
    defined = set(_theme_vars())
    for css in (page.STICKY_BOTTOM_CSS, page.VSEP_CSS):
        for name in _VAR_USE_RE.findall(css):
            assert name in defined, f"{name} 未定义（这条规则会整条失效）"
    # sticky 必须写在 <tr> 上（写在 td 上永不生效，见 docs/reference/sticky-total-row.md）
    flat = page.STICKY_BOTTOM_CSS.replace(" ", "")
    assert "tr.sumrow{position:sticky" in flat
    assert ">td{position:sticky" not in flat
    # 分段竖线照原型用 --bd（原工程曾误抄成 --bd2）
    assert "border-left:2px solid var(--bd)" in page.VSEP_CSS


# ---------------------------------------------------------------- 打印件隔离


def test_打印件不受站点主题影响():
    """⛔ 印在纸上的颜色是「版式的样子」，与屏幕主题无关 ⇒ 打印件里不得出现主题变量。"""
    print_sources = list(PRINT_DIR.rglob("*.py"))
    assert print_sources, "打印件目录不见了？"
    for f in print_sources:
        text = f.read_text(encoding="utf-8")
        assert not _VAR_USE_RE.search(text), f"打印件里引用了站点主题变量：{f.name}"
        assert "THEME_CSS" not in text, f"打印件里引用了主题表：{f.name}"


def test_主题只在一处定义_不得出现第二份副本():
    """换主题 = 改这一份。多一份副本 = 迟早漂移。"""
    owners = []
    for f in _iter_app_py():
        if f.name != 'theme_react.py' and ":root{" in f.read_text(encoding="utf-8"):
            owners.append(f.name)
    assert owners == ["page.py"], f"主题调色板只能由page.py持有，实际：{owners}"
    assert theme_react.REACT_THEME_SPEC is page.REACT_THEME_SPEC


def test_一套主题的值互不重复_成对色的底与字必须不同():
    """守卫「取值表本身」的健全性：状态色的浅底与深字不能是同一个值（那样等于没有对比度）。"""
    vals = _theme_vars()
    for name in ("ok", "wn", "dg", "bl", "in", "vi"):
        fg = vals[f"--{name}"].strip().lower()
        bg = vals[f"--{name}-l"].strip().lower()
        deep = vals[f"--{name}-d"].strip().lower()
        assert fg != bg, f"{name}：浅底与主色相同 —— 没有对比度"
        assert fg != deep, f"{name}：深字与主色相同 —— 成组就白做了"


# ---------------------------------------------------------------- 类级基础样式（TAIL-24 · 2026-09-17）


def _bare_rule_owners(selector: str) -> list[str]:
    """**裸选择器**（行首就是它，如 `.mut{`）出现在哪些文件里；带祖先的（`.dt th .mut{`）不算。"""
    pat = re.compile(rf"^\s*{re.escape(selector)}\s*\{{", re.M)
    return [f.name for f in _iter_app_py() if pat.search(f.read_text(encoding="utf-8"))]


def test_基础控件类级样式完备_不靠元素选择器与内联style兜():
    """⭐ `TAIL-24`：`button{}` 只管 `<button>` 元素 —— 本仓大量用 `<a class="btn">` 当按钮。

    漏掉类级规则的症状：锚点按钮**显示成纯链接文字**（重置 / 返回 / 取消 / 清除列筛选），
    `.inp` 只能靠调用点内联 style 兜（各页输入框长相不一）、`.sm` 完全无效。
    ⚠️ 断言只能钉**"规则在不在、且走变量出口"**；好不好看只能人眼。
    """
    css = page.BASE_CSS
    # ⚠️ `BASE_CSS = THEME_CSS + 基础样式` ⇒ 变量定义段（`:root{…}`）**本来就该有色值**，
    #    只查**基础样式那一段**（与 `test_除主题表本身外…` 同一刀口）。
    base_only = css[len(page.THEME_CSS):]
    for sel in (".btn{", ".btn.sm{", ".btn.pri{", ".inp{", ".mut{", ".sm{"):
        assert sel in base_only, f"基础样式段缺类级规则 {sel}（不许再靠调用点兜）"
    # 锚点当按钮的关键一条：不能带下划线（否则一眼看出是链接）
    btn_rule = next(line for line in base_only.splitlines() if line.startswith(".btn{"))
    assert "text-decoration:none" in btn_rule, "`<a class='btn'>` 会带下划线 ⇒ 看着仍是链接"
    assert not _HEX_RE.search(base_only), "基础样式段里出现了色值字面量（应走 var(--…)）"


def test_mut与sm是唯一真源_不许页级再抄一份():
    """⭐ `TAIL-24` 的连带整改：`.mut` 原先**各页 `EXTRA_CSS` 各抄一份**，取值还不一致
    （`notice_page` = `--mut`、`mod05_flow` = `--mut2`）⇒ 既漂移、又有页面根本没有它。

    守的规则与 `:root` 同款：**裸选择器只许出现在唯一真源里**；
    带祖先的作用域微调（`.dt th .mut{…}` / `.bulk .mut{…}`）仍然允许。
    """
    assert _bare_rule_owners(".mut") == ["page.py"], "`.mut` 又出现页级副本了（应只留 BASE_CSS）"
    assert _bare_rule_owners(".sm") == ["page.py"], "`.sm` 应只留 BASE_CSS"


# ---------------------------------------------------------------- 静态页 / 服务端页同源


# ⚠️ 2026-09-19（`§19` 批 4）：原先这里有一条「**静态页**引用同一份真源、不自带 `:root`」的守卫；
#    最后一个静态页 `m03.html` 删除（授权 `D18`）后它**没有观测对象了** ⇒ 随之移除
#    （它是 `@acc()` **未绑定**的守卫，不是判据点 ✓）。下面的 `001-05` 是**绑定**判据，一字未动。


def test_主题端点使用共享变量与React主题():
    from fastapi.testclient import TestClient
    from app.main import create_app

    with TestClient(create_app()) as client:
        served = client.get('/static/theme.css')
        assert served.status_code == 200
        assert served.headers['content-type'].startswith('text/css')
        assert served.text == page.THEME_CSS
        react = client.get('/static/theme.css?surface=react')
        assert react.status_code == 200
        assert react.text == theme_react.render_react_theme(page.DEFAULT_THEME)
    paths = set(create_app().openapi()['paths'])
    for gone in ('/m05/import', '/m06/import', '/m08/import', '/m14/settings'):
        assert gone not in paths


def test_主题清单和样式共同使用新版松绿():
    assert page.theme_names() == ["松绿"]
    assert set(page.THEME_SEEDS) == set(page.THEME_SPEC) == set(theme_react.REACT_THEME_SPEC) == {"松绿"}
    assert all(page.THEME_SPEC["松绿"].values())

    pine = _theme_vars()
    react = _variables(theme_react.render_react_theme("松绿"))
    assert {key: react[key] for key in pine} == pine
    for key, value in {
        "--bg": "#edf3f0", "--sb": "#0b221d", "--pri": "#0c6b61", "--bd3": "#6b8177",
        "--r": "6px", "--r2": "8px",
    }.items():
        assert pine[key] == value
    for css in (page.THEME_CSS, theme_react.render_react_theme("松绿")):
        assert css.startswith(page.FONT_CSS + ":root{")
        assert css.rstrip().endswith("}")


def test_退役或未知的主题回落松绿():
    react = theme_react.render_react_theme("松绿")
    for name in (None, "", "  ", "默认", "靛青", "深色", "玫瑰柔粉", "不存在的主题"):
        assert page.theme_name(name) == theme_react.theme_name(name) == "松绿"
        assert page.render_theme(name) == page.THEME_CSS
        assert theme_react.render_react_theme(name) == react


def _srgb_lin(channel: float) -> float:
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def _rel_lum(hex_color: str) -> float:
    r, g, b = (_srgb_lin(int(hex_color[i:i + 2], 16) / 255) for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a: str, b: str) -> float:
    la, lb = sorted((_rel_lum(a), _rel_lum(b)))
    return (lb + 0.05) / (la + 0.05)


def test_松绿正文侧栏与状态色达到WCAG_AA():
    values = _theme_vars()
    text_pairs = [
        ("--tx", "--bg"), ("--pri", "--bg"), ("--on", "--pri"),
        ("--sb-hd", "--sb"), ("--sb-tx", "--sb"), ("--sb-mut", "--sb"),
        ("--sb-dis", "--sb"), ("--sb-hd", "--sb-hover"),
        ("--on", "--sb-on"), ("--sb-on-hl", "--sb-on"), ("--on", "--toast-bg"),
        ("--pri-d", "--pri-l"),
    ]
    text_pairs.extend(
        (text, surface)
        for surface in ("--sf", "--sf2")
        for text in ("--tx", "--tx2", "--mut", "--mut2")
    )
    text_pairs.extend(
        (f"--{role}{suffix}", f"--{role}-l")
        for role in ("ok", "wn", "dg", "bl", "in", "vi")
        for suffix in ("", "-d")
    )
    for fg, bg in text_pairs:
        ratio = _contrast(values[fg], values[bg])
        assert ratio >= 4.5, f"{fg} / {bg} = {ratio:.2f}:1"
    for bg in ("--sf", "--sf2", "--bg"):
        ratio = _contrast(values["--bd3"], values[bg])
        assert ratio >= 3, f"--bd3 / {bg} = {ratio:.2f}:1"
