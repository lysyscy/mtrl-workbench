"""主题变量层（`page.THEME_CSS`）的工程自检 —— 离线 · 不连库。

⚠️ 这里守的是**机制**，不是观感：
  - 颜色**只能经变量出口**（CSS 里不得再出现色值字面量）—— 可断言；
  - 变量**定义完整**（引用了但没定义 = 静默失效，这类错最难发现）；
  - 状态色**成组**（主色 / 深字 / 浅底 / 浅边框 四档齐全）—— 多主题的前提；
  - **打印件不受站点主题影响**（印在纸上的颜色与屏幕主题是两件事）。

⚠️ 观感（哪个颜色好不好看、对比度够不够）**只能靠人眼**，断言测不了。
⚠️ 本文件用 `@acc()` **显式不绑定判据点** —— 要变成 `ACC-*` 判据属契约层动作。
"""

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

# ⭐ 2026-09-19（`§19` 性能 · **主题②**）：**前端壳也是主题真源的消费者**（第三路，经 `/static/theme.css`）
#    ⇒ 它同样受「颜色只经变量出口 / 引用的变量必须有定义」这两条管。
#    ⚠️ 壳用**更严**的正则：3~8 位（否则 `#fff9`、`#0f172a26` 这类短写法／带 alpha 的**溜过去**）。
from tests.shell_src import SHELL, parts_text  # noqa: F401  ← `P4`① 读取点收敛
SHELL_THEME_LINK = '<link rel="stylesheet" href="/static/theme.css">'
_HEX_RE_ANY = re.compile(r"(?<!&)#[0-9a-fA-F]{3,8}\b")


def _theme_vars() -> dict[str, str]:
    return dict(re.findall(r"(--[a-z0-9-]+):\s*([^;\n]+);", page.THEME_CSS))


def _iter_html():
    """壳的**每一件**，产出 `(相对路径, 文本)` —— `P4`① 之后壳是多件（`index.html` ＋ `web/shell/*.js`），
    ⚠️ 只扫 `index.html` 会**静默漏掉接线层**（那正是色值最容易溜进去的一段）。"""
    return parts_text()


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
    """⚠️ 多主题的硬前提：底 / 字 / 深字 / 边框必须同套，否则第 2 套会「新绿字配旧浅绿底」。"""
    defined = set(_theme_vars())
    for name in ("ok", "wn", "dg"):
        group = {f"--{name}", f"--{name}-d", f"--{name}-l", f"--{name}-bd"}
        assert group <= defined, f"状态色 {name} 缺档：{group - defined}"


def test_全工程引用的变量都有定义_引用了没定义会静默失效():
    """⭐ 2026-09-27（`TAIL-129` 界面大小）：**"定义处"有两个** ——
      ① **主题真源**（`page.THEME_CSS`，全是**颜色**）；② **壳自己的样式块**（**非颜色**的尺寸/倍率，
         如界面大小的 `--fscale`，它的默认值必须写在壳里 —— 那是"JS 没跑时也不散架"的兜底）。
    ⚠️ 本条守的是「**引用必有定义**（否则 `var()` 取不到值 ⇒ 整条声明静默失效）」，不是
       「只能在主题真源里定义」⇒ 放开这一处**不会**削弱颜色那半：
       颜色另有更严的守卫（壳不许自带 `:root` / 硬编码色清零 / `ACC-UI-THEME-001` 那几条）。
    """
    defined = set(_theme_vars()) | set(_VAR_DEF_RE.findall(theme_react.render_react_theme(page.DEFAULT_THEME)))
    for _name, text in _iter_html():
        defined |= set(_VAR_DEF_RE.findall(text))       # ⭐ 壳自己定义的（`html{--fscale:1}` 这种）
    used: set[str] = set()
    for f in _iter_app_py():
        used |= set(_VAR_USE_RE.findall(f.read_text(encoding="utf-8")))
    # ⭐ 2026-09-19（主题②）：壳（HTML）也在这条口径里 —— 它引用的变量同样必须由真源定义
    for _name, text in _iter_html():
        used |= set(_VAR_USE_RE.findall(text))
    assert used, "全工程居然一个主题变量都没用？"
    assert not (used - defined), f"引用了但未定义（会静默失效）：{sorted(used - defined)}"


# ---------------------------------------------------------------- 只经变量出口


def test_除主题表本身外_全工程CSS不再出现色值字面量():
    """这条是**防回归**用的：以后谁顺手写个 `#fff` 进来，这里就会红。

    - `page.py` 的 `THEME_CSS` 段 = 唯一的色值定义处（白名单）；
    - `print/` 目录 = 打印件，**故意排除**（它的颜色不属于站点主题）。
    - ⭐ 2026-09-19（主题②）：**前端壳**（`app/web/index.html`）也一并扫 —— 同一判据点、加宽观测面
      （它原先自带一份 `:root`，是**第二份真源**：同名变量取值都与真源不同）。
    """
    seen: list[str] = []
    for f in _iter_app_py():
        text = f.read_text(encoding="utf-8")
        if f == THEME_SOURCE:
            # 只放行 THEME_CSS 那一段，其余部分仍受约束
            head, _, tail = text.partition('THEME_CSS = """')
            theme_body, _, rest = tail.partition('"""')
            text = head + rest
            # ⭐ 2026-09-20（多主题）：**主题定义区**（`THEME-DEF BEGIN/END`）也放行 ——
            #    它装的是**种子色**（`THEME_SEEDS` 一行一套）与派生用的纯色常量。
            #    ⚠️ §7.7 说的「一份主题变量表统管」就是它 ⇒ 它**是那个出口**，不是违规。
            #    ⛔ 按标记断区（而不是"放行整个 page.py"）：区外的色值**仍然会红**。
            before, _, tail2 = text.partition("THEME-DEF BEGIN")
            _, _, after = tail2.partition("THEME-DEF END")
            text = before + after
        for hit in _HEX_RE.findall(text):
            seen.append(f"{f.relative_to(APP_DIR.parent)}: {hit}")
    for _name, text in _iter_html():
        for hit in _HEX_RE_ANY.findall(text):
            seen.append(f"{_name}: {hit}")
    assert not seen, "CSS 里又出现色值字面量了（应改走 var(--…)）：\n  " + "\n  ".join(seen)


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
    assert theme_react.THEME_SEEDS is page.THEME_SEEDS


def test_一套主题的值互不重复_成对色的底与字必须不同():
    """守卫「取值表本身」的健全性：状态色的浅底与深字不能是同一个值（那样等于没有对比度）。"""
    vals = _theme_vars()
    for name in ("ok", "wn", "dg"):
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


def test_服务端渲染页与静态页拿到的是同一份变量():
    """**三路同源**：`<link>` 的端点 = 服务端页内联的常量 = 前端壳 `<link>` 的那一份 = `page.THEME_CSS`。

    ⭐ 2026-09-19（`§19` 性能 · **主题②**）：加上**壳**这一路。壳先前自带一份同名 `:root`
    （16 个取值全与真源不同）⇒ 它是**第二份真源**；现改为只 `<link>` 真源、本地零定义。
    """
    from fastapi.testclient import TestClient

    from app.main import create_app

    client = TestClient(create_app())
    served = client.get("/static/theme.css")
    assert served.status_code == 200
    assert served.headers["content-type"].startswith("text/css")
    assert served.text == page.THEME_CSS          # 端点返回的就是那一份，不是副本
    # ⚠️ 2026-09-18（`§19` 批 2）：`/m04` 已随旧渲染层删除（授权 `D18`）⇒ 从这一组里去掉。
    # ⚠️ 2026-09-19（`§19` 批 3）：`/m05` **也已删** ⇒ 换成本模块**暂留的导入页** `/m05/import`；
    # ⚠️ 2026-09-19（`§19` 批 4 · S4⑤）：`/m03/notices` **也已删**（m03 的服务端渲染页全清）。
    # ⭐ 2026-09-21（`§19` 四个暂留件收口）：**最后三个服务端渲染页也搬进了新壳**
    #    （`/m05/import*` · `/m06/import*` · `/m08/import*` ＋ `/m14/settings`）⇒ **服务端渲染层清零**，
    #    原来那三条「页内联的就是那一份真源」**已无对象可指** ⇒ 换成**结构性断言**：
    #    那几个路由必须**真的不在了**（⛔ 别留幽灵页），主题真源的消费者只剩两个出口 ——
    #    **本端点**（上面已逐字比过全文相等）＋ **壳的 `<link>`**（下面）。
    paths = set(create_app().openapi()["paths"])
    for gone in ("/m05/import", "/m06/import", "/m08/import", "/m14/settings"):
        assert gone not in paths, f"{gone} 应已随「四个暂留件收口」删除（服务端渲染层应清零）"
    # ⭐ 第三路 = **前端壳**：它必须 `<link>` 到同一个端点，且**不得自带 `:root`**
    #    （同特异度下文档里靠后的那份胜 ⇒ 自带一份就等于第二份真源，换主题必然漂）。
    shell = SHELL
    assert SHELL_THEME_LINK in shell, "壳没接主题真源（缺 `<link href=/static/theme.css>`）"
    assert ":root{" not in shell, "壳又自带 `:root` 了（那是第二份真源 ⇒ 换主题会漂）"


# ---------------------------------------------------------------- 多主题（《说明书》§7.7 · 2026-09-20）


def test_主题清单可列举且每套覆盖同一组变量名():
    """claim：「**主题清单可列举**，且每套主题必须**覆盖同一组变量名**
    （**缺项即显式报错**，不得静默沿用旧值）」。

    ⚠️⚠️ 「缺项即显式报错」是这条的**命门**：CSS 里 `var(--x)` 引用了**没定义**的变量，
       **不报错、只静默失效** ⇒ 页面上少一块样式（合计行没底色、分段竖线不见、标签没色），
       而**没有任何错误信号** —— 这正是 `page.py` 里那段注释记着的历史 bug（`sumrow`/`vsep` 抄了
       原型却**没抄 `:root`**）。⇒ 判据**不能**只数"清单里有几个名字"，
       必须**真的逐套比对变量名集合**。

    ⚠️ 另加一条**防空**：基准集合本身必须**够大** —— 否则"每套都是空集合的子集"也恒成立，
       覆盖面校验就变成了摆设（这类"恒真断言"比红更难发现）。
    """
    names = page.theme_names()
    # §7.7：用户 2026-09-20 定「清单 ≥10 套，换着玩」
    assert len(names) >= 10, f"预置主题清单只有 {len(names)} 套 —— §7.7 用户裁定「至少 10 套」"
    assert page.DEFAULT_THEME in names, "回落默认套必须**自己也在清单里**（否则它是个影子）"

    base = page._var_names()
    assert len(base) >= 60, (
        f"变量名基准集只有 {len(base)} 个 —— ⚠️ 基准太小（甚至为空）会让"
        "「每套都覆盖同一组」**恒真**，覆盖面校验就成了摆设。")
    assert page.THEME_CSS.count("--") >= 60, "默认套自己的变量数不对 —— 基准取错了源"

    # ⚠️ 先看"构造期有没有报错"：`render_theme` 缺项是**显式抛错**的，模块级构造会接住并记下原因
    assert not page._THEME_BUILD_ERROR, (
        "主题清单构造时就报错了（缺项）—— 原因：\n  " + page._THEME_BUILD_ERROR)

    gaps = page.theme_coverage_gaps()
    assert not gaps, (
        "这些主题**缺变量** ⇒ 引用它们的声明会**静默失效**（页面少一块样式、且不报错）：\n  "
        + "\n  ".join(f"{k}: 缺 {v}" for k, v in gaps.items()))

    # ⭐ 每套都真的能产出（不是"清单里写了、渲染不出来"）
    #    ⚠️ `page.THEME_CSS` 那段字面量**开头带一个换行**（`"""` 后面直接换行）⇒ 用 `lstrip()` 比。
    for n in names:
        css = page.render_theme(n)
        assert css.lstrip().startswith(":root{") and css.rstrip().endswith("}"), \
            f"「{n}」产出的 CSS 形态不对"


def test_非法主题名显式处理_回落默认套():
    """claim：「未知 / 非法主题名必须**显式处理**（回落默认套或显式报错，**两者择一**；
    不得白屏或半套样式）」。

    ⚠️ 本实现选的是「**回落默认套**」这一支（§7.7 ④「未设置时回落默认套」）。
    ⚠️ 三类输入都要覆盖，缺一类就会漏：
       ① **未设置**（`None` / 空串）；② **不认识的名字**；③ **路径穿越式**的名字。
       ⛔ ③ 尤其要紧：主题名会进 URL（`/static/theme.css?theme=…`），
       若拿它去拼路径（`open(f"themes/{name}.css")`）就是**任意文件读取**。
       本实现是**字典查表**（⛔ 不拼路径）⇒ 天然安全 —— 这条断言就是**把"查表"钉住**，
       防哪天被改成拼路径（那时它会红）。
    """
    default = page.THEME_CSS
    for bad in (None, "", "  ", "不存在的主题", "../page", "../../etc/passwd",
                "默认 ", "默认\n", "'; drop table", "<script>"):
        got = page.render_theme(bad)                       # type: ignore[arg-type]
        assert got == default, (
            f"非法/未知主题名 {bad!r} **没有显式回落默认套** ⇒ 会白屏或半套样式"
            "（`render_theme` 必须查表回落，⛔ 不许拿主题名去拼路径或抛裸异常）")
    # ⭐ 反过来：合法名**不许**被回落掉（否则"回落"就成了"永远默认"—— 那清单白列了）
    for good in page.theme_names():
        assert page.render_theme(good) == page.THEMES[good], f"合法主题「{good}」被误回落了"
    assert page.render_theme("深色") != default, "「深色」与默认套产出相同 ⇒ 派生没起作用（清单是假的）"


# ---------------------------------------------------------------- 主题规范表（2026-09-21 · 用户裁定）
# ⭐⭐ 用户原话：「重新设计并交付 **10 个完整、独立、可切换**的主题方案，每个主题需明确其
#    **适用场景与设计风格**，并提供**统一的结构规范**以保证一致性与可维护性」。
#    ⇒ 落成两条可执行的东西：① 清单**恰好 10 套**且有场景/风格（`THEME_SPEC`）
#      ② **对比度下限**（下面那条 —— "视觉平衡"没法直接断言，但"看不清"可以量化）。


def test_主题清单恰好十套且每套都有适用场景与设计风格():
    """claim（`001-02`）：「主题清单**可列举**」—— ⭐ 2026-09-21 加严：可列举 ⇒ **每套都要说得清
    "它是干什么用的"**（场景）与"它长什么样"（风格）。⛔ 只有名字的清单 = 用户无从选择。

    ⚠️ 为什么钉"**恰好 10 套**"：用户 2026-09-21 裁定的口径是「**10 个完整、独立**的方案」——
       原来 13 套里有 3 套是「深色·X」**变体**（不独立）⇒ 已删。多一套少一套都要**改口径**，
       ⛔ 不是"顺手加一行"。
    """
    names = page.theme_names()
    assert len(names) == 10, (
        f"主题清单是 {len(names)} 套 —— 用户 2026-09-21 裁定「恰好 **10** 个完整、独立的方案」"
        f"（多/少都要改口径，⛔ 不是顺手加一行）：{names}")
    assert set(page.THEME_SPEC) == set(names), (
        "`THEME_SPEC`（场景/风格）与 `THEME_SEEDS`（种子）**键集不同** —— "
        f"只加了种子忘了写规范：{sorted(set(names) ^ set(page.THEME_SPEC))}")
    scenes: list[str] = []
    for n in names:
        spec = page.THEME_SPEC[n]
        assert spec.get("scene", "").strip(), f"「{n}」没写**适用场景** ⇒ 用户不知道该选哪套"
        assert spec.get("style", "").strip(), f"「{n}」没写**设计风格**"
    scenes = [page.THEME_SPEC[n]["scene"] for n in names]
    assert len(set(scenes)) == len(scenes), (
        f"有两套主题的**适用场景一模一样** ⇒ 它们其实是一套：{[s for s in scenes if scenes.count(s) > 1]}")


#: ⭐ **可读性下限**：配对照 `backend/app/web/index.html` 的 `<style>` **逐条抄**（⛔ 不是"哪个色配哪个色"）。
#: ⚠️ 阈值就一条线：**凡是"给人读的文字"一律 4.5**（WCAG AA 的 3.0 只放行 ≥24px 或 ≥18.66px 粗体，
#:    本仓没有那个字号）⇒ ⛔ 别拿"它是次要文字"当降标准的理由 —— 用户已经两次报"看不清 / 不平衡"。
#: 只有**纯装饰**（分隔线）按可辨性 1.15。
_CONTRAST_PAIRS: list[tuple[str, str, str, float]] = [
    ("正文", "--tx", "--bg", 4.5),
    ("正文/卡片", "--tx", "--sf", 4.5),
    ("次正文", "--tx2", "--sf", 4.5),
    ("弱化文字（空态/提示）", "--mut", "--sf", 4.5),
    ("主色作链接字", "--pri", "--bg", 4.5),
    ("按钮字", "--on", "--pri", 4.5),
    ("⭐侧栏-普通项", "--sb-tx", "--sb", 4.5),
    ("⭐侧栏-品牌/悬停项", "--sb-hd", "--sb", 4.5),
    ("⭐侧栏-编号·分组·页脚", "--sb-mut", "--sb", 4.5),
    ("⭐侧栏-悬停底上的字", "--sb-hd", "--sb-hover", 4.5),
    ("⭐侧栏-选中项", "--on", "--sb-on", 4.5),
    ("⭐侧栏-选中项里的编号", "--sb-on-hl", "--sb-on", 4.5),
    ("侧栏分隔线可辨", "--sb-bd", "--sb", 1.15),
    ("标签-主色", "--pri-d", "--pri-l", 4.5),
    ("标签-成功", "--ok-d", "--ok-l", 4.5),
    ("标签-提醒", "--wn-d", "--wn-l", 4.5),
    ("标签-危险", "--dg-d", "--dg-l", 4.5),
    ("标签-手动剔除", "--bl-d", "--bl-l", 4.5),
    ("标签-中性", "--in-d", "--in-l", 4.5),
    ("标签-特殊", "--vi-d", "--vi-l", 4.5),
]


def _srgb_lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _rel_lum(hex_color: str) -> float:
    """⚠️ 用**真正的 WCAG 相对亮度**（sRGB → 线性 → 0.2126R+0.7152G+0.0722B）。
    ⛔ 别用 `page._lum()`：那是给 `_on()` 选黑白用的**粗略加权**，两者混用会算出假达标。"""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * _srgb_lin(r) + 0.7152 * _srgb_lin(g) + 0.0722 * _srgb_lin(b)


def _contrast(a: str, b: str) -> float:
    la, lb = _rel_lum(a), _rel_lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _theme_vars_of(name: str) -> dict[str, str]:
    return {("--" + m.group(1)): m.group(2).strip()
            for m in re.finditer(r"--([a-z0-9-]+):\s*([^;\n]+);", page.render_theme(name))}


def test_每套主题的关键配对都过对比度AA():
    """⭐⭐ **把"视觉平衡/看不清"变成可测的数字**（2026-09-21 用户报「左侧页面选择栏在各类主题下
    视觉不平衡」⇒ 排查发现**硬故障**：4 个深色套的侧栏选中项是**黑字压近黑底**，实测对比度 **1.05**）。

    ⚠️ 为什么不靠肉眼：观感是主观的，但"**文字与底的对比度**"是客观量 —— 低于 AA 就是**看不清**，
       不需要争论。⚠️ 这条**测不了**"好不好看"（那要人眼），它测的是"**能不能看清**"这条底线。

    ⚠️ 本断言当前是 `@acc()` **未绑定**（属工程守卫）：把它升成判据点要先在交付面新建一条
       （口径由用户 2026-09-21 的话直接给出，但**新建判据点 = 契约层动作**）。
    """
    rows: list[str] = []
    bad: list[str] = []
    for name in page.theme_names():
        v = _theme_vars_of(name)
        for label, fg, bg, need in _CONTRAST_PAIRS:
            if fg not in v or bg not in v:
                bad.append(f"{name}｜{label}：变量缺失（{fg} / {bg}）")
                continue
            r = _contrast(v[fg], v[bg])
            if r < need:
                bad.append(f"{name}｜{label}：{v[fg]} on {v[bg]} = {r:.2f} < {need}")
            rows.append(f"{name:8s} {label:22s} {v[fg]:>9s} on {v[bg]:>9s} = {r:5.2f} (需 {need})")
    assert not bad, (
        "这些主题/配对**读不清**（阈值：文字 4.5 / 装饰 1.15）—— ⛔ 别调低阈值，去调 `_derive`／种子：\n  "
        + "\n  ".join(bad) + "\n\n全部实测：\n  " + "\n  ".join(rows))


def test_侧栏不借用与本角色无关的变量():
    """⛔ **侧栏文字不许借 `--on` / `--in`**（2026-09-21 修的正是这个）：
    `--on` 的语义是「**主色之上**的前景」（深色套里它是**黑**），`--in` 是**状态档的中性色** ——
    两者都与"深色面板上的文字"无关。借用的后果实测过：深色套的侧栏品牌名/悬停项变**黑字压深面板**。

    ⚠️ 唯一合法的 `--on` 用法 = **选中项**（那一项的背景就是主色 `--sb-on`）——
    所以断言按"**选择器行**"判，⛔ 不是全文件搜一遍（那样连注释都会算进去）。
    """
    css = SHELL
    i = css.find(".sb-brand{")
    j = css.find(".sb-foot{")
    assert i > 0 and j > i, "找不到侧栏那段 CSS —— 选择器改名了？本断言要跟着改"
    block = css[i:j]
    # 逐行看：带 `.sb` 选择器的行里，除了 `.sb-i.on`，不许出现 `--on` / `--in`
    for ln in block.splitlines():
        s = ln.strip()
        if not s.startswith(".sb"):
            continue
        if ".sb-i.on" in s:
            continue
        for role in ("var(--on)", "var(--in)"):
            assert role not in s, (
                f"侧栏样式借了与本角色无关的变量：{role}\n  行：{s}\n"
                "  ⛔ 侧栏三档文字用 `--sb-hd` / `--sb-tx` / `--sb-mut`；"
                "`--on` 只许出现在**选中项**（它的底就是主色）")
    for need in (".sb-brand b{display:block;color:var(--sb-hd)",
                 ".sb-i:hover{background:var(--sb-hover);color:var(--sb-hd)"):
        assert need in block, f"侧栏缺了这条（三档文字规范）：`{need}`"

