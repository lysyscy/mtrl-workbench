"""`TAIL-209` 余项 ②：把壳里**会原样上屏的 `**`** 收拾干净（一次性批量替换）。

## 为什么改（真缺陷，不是措辞）

`**X**` 是"加粗"标记，壳里**只有 `lgMd` 会渲染它**（`legacy.js:40`）。
壳自己拼的字符串走的是**直插**：`modal({body})`（`base.js` 直接 `innerHTML`）、`toast(msg)`（`innerHTML`）
⇒ 那些 `**` **原样上屏**（用户看到满脸星号）。守则 §3.1「技术标记不上屏」。

## 改法**分三种**（⛔ 不能一刀切换成 `<b>`）

| 这串去哪儿 | 改法 | 为什么 |
|---|---|---|
| HTML 串（`toast` / `tip` / 拼的 `div`） | `**X**` ⇒ `<b>X</b>` | 与 `lgMd` 同一形态 |
| **属性值**（`title=` / `placeholder=`） | **去掉星号** | `<b>` 在属性里也**原样显示** |
| 走 `esc()` 的（`KIND_TXT` / `errWhyByStatus`） | **去掉星号** | `<b>` 会被转义成字面量 |

## 安全网（三条）

① 每条**断言命中恰好 1 次**（含 CRLF 变体各试一次）⇒ 不命中**整批不写**；
② 全部改完在**内存里**再扫一遍：剥掉注释后**不许还剩 `**`** ⇒ 还剩下就退出 1（⛔ 不写盘）；
③ 只改壳件；**注释里的 `**` 不动**（它不是上屏文字）。

⚠️ 口径出处 = 计划 `§13.6`「修订 13」行 ＋ `work/40-decisions/D29-文案审计口径-以熟手为准.md`。
⚠️ 本件只**清显示标记**，⛔ **不改文案内容**（按 `D29` 删干扰文字是**批 5**，另一批）。
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.audit.shell_source import parts_text, strip_comments  # noqa: E402

W = ROOT / "backend" / "app" / "web"

# (件名, 旧串, 新串) —— ⛔ 顺序无关；每条都要求**全文件唯一**
EDITS: list[tuple[str, str, str]] = [
    # ---------------- index.html ----------------
    # 三处都在 `title="…"` 属性里 ⇒ **只能去星号**（属性里写 <b> 也是原样显示）
    ("index.html",
     "且**仍挂着付款流水 / 集采关联** —— 按 §4.2.7，有牵涉时**不许静默退出统计**",
     "且仍挂着付款流水 / 集采关联 —— 按 §4.2.7，有牵涉时不许静默退出统计"),
    ("index.html",
     "但**已退出全部统计**；单据号必变",
     "但已退出全部统计；单据号必变"),
    ("index.html",
     "（那三栏**按项目分列**，这里只算选中的那一个）",
     "（那三栏按项目分列，这里只算选中的那一个）"),
    ("index.html",
     "'改**别人**的密码要管理员（你自己的密码在**你自己那一行**点「改密」）'",
     "'改别人的密码要管理员（你自己的密码在你自己那一行点「改密」）'"),
    # ---------------- shell/pages-a.js ----------------
    ("shell/pages-a.js",
     "⛔ 但**不会**改本行这两个数",
     "⛔ 但<b>不会</b>改本行这两个数"),
    # ---------------- shell/actions.js ----------------
    ("shell/actions.js",
     "toast(`当前筛选下**一行都没有**",
     "toast(`当前筛选下<b>一行都没有</b>"),
    ("shell/actions.js",
     "return toast('打印机设置**已保存**，",
     "return toast('打印机设置<b>已保存</b>，"),
    ("shell/actions.js",
     "它落库后**与导入行同住一表、同样要被审查**，且**导入不会清理它**（§9.5）",
     "它落库后<b>与导入行同住一表、同样要被审查</b>，且<b>导入不会清理它</b>（§9.5）"),
    ("shell/actions.js",
     "派生列与合计**已算成数值**",
     "派生列与合计<b>已算成数值</b>"),
    ("shell/actions.js",
     "dfOk:()=>toast('<b>本页已停用</b>（2026-09-20 裁定）：差异登记**不独立成页** —— '",
     "dfOk:()=>toast('<b>本页已停用</b>（2026-09-20 裁定）：差异登记<b>不独立成页</b> —— '"),
    ("shell/actions.js",
     "dfSave:()=>toast('<b>本页已停用</b>（2026-09-20 裁定）：差异登记**不独立成页** —— '",
     "dfSave:()=>toast('<b>本页已停用</b>（2026-09-20 裁定）：差异登记<b>不独立成页</b> —— '"),
    ("shell/actions.js",
     "dfDel:()=>toast('<b>本页已停用</b>（2026-09-20 裁定）：差异登记**不独立成页** —— '",
     "dfDel:()=>toast('<b>本页已停用</b>（2026-09-20 裁定）：差异登记<b>不独立成页</b> —— '"),
    ("shell/actions.js",
     "if(!rows.length) return toast('当前筛选下**一行都没有**",
     "if(!rows.length) return toast('当前筛选下<b>一行都没有</b>"),
    ("shell/actions.js",
     '<span class="mut sm">列是**全列**（含贸易公司 3 列）',
     '<span class="mut sm">列是<b>全列</b>（含贸易公司 3 列）'),
    ("shell/actions.js",
     "（剩下的列会**自动变宽**）",
     "（剩下的列会<b>自动变宽</b>）"),
    # ⚠️ 这处**本来就在 `<b>` 里面** ⇒ 星号只需去掉（⛔ 别嵌套 `<b>`）
    ("shell/actions.js",
     "<b>⚠️ 改类型**不会**回头重算已有合同的金额</b>",
     "<b>⚠️ 改类型不会回头重算已有合同的金额</b>"),
    ("shell/actions.js",
     "⚠️ 已有的合同**不会**重算金额落位",
     "⚠️ 已有的合同<b>不会</b>重算金额落位"),
    ("shell/actions.js",
     "但**落库前会给你一眼看见**。",
     "但<b>落库前会给你一眼看见</b>。"),
    # ---------------- shell/legacy.js ----------------
    ("shell/legacy.js",
     "（全量已随本批暂存，④ 落库按**全量**处理）",
     "（全量已随本批暂存，④ 落库按<b>全量</b>处理）"),
    ("shell/legacy.js",
     "⚠️ 表里有两类标记，**看颜色一眼分开**（鼠标放到那一行上看原因）：",
     "⚠️ 表里有两类标记，<b>看颜色一眼分开</b>（鼠标放到那一行上看原因）："),
    ("shell/legacy.js",
     "（浅底 ＋ 左侧竖条）= **不会写进系统，要你处理**",
     "（浅底 ＋ 左侧竖条）= <b>不会写进系统，要你处理</b>"),
    ("shell/legacy.js",
     "（灰底、没有竖条）= **本来就跳过**",
     "（灰底、没有竖条）= <b>本来就跳过</b>"),
    ("shell/legacy.js",
     "· 空行 —— **不用你改**）。</div>",
     "· 空行 —— <b>不用你改</b>）。</div>"),
    ("shell/legacy.js",
     "有 <b>${nbad}</b> 行**不会写入**",
     "有 <b>${nbad}</b> 行<b>不会写入</b>"),
    ("shell/legacy.js",
     "已在上表**逐行标出**（浅底",
     "已在上表<b>逐行标出</b>（浅底"),
    ("shell/legacy.js",
     "另有 <b>${nplain}</b> 行**本来就跳过**",
     "另有 <b>${nplain}</b> 行<b>本来就跳过</b>"),
    ("shell/legacy.js",
     "已标成灰底，**不用你改**）",
     "已标成灰底，<b>不用你改</b>）"),
    ("shell/legacy.js",
     "再**整批回滚后重导**",
     "再<b>整批回滚后重导</b>"),
    ("shell/legacy.js",
     "这一批**不需要你改文件**。",
     "这一批<b>不需要你改文件</b>。"),
    ("shell/legacy.js",
     "这一步**一个字节都不写库**</span>",
     "这一步<b>一个字节都不写库</b></span>"),
    ("shell/legacy.js",
     "这些问题**不影响其余行落库**；",
     "这些问题<b>不影响其余行落库</b>；"),
    ("shell/legacy.js",
     "那类报错**同一个数**，用来对号",
     "那类报错<b>同一个数</b>，用来对号"),
    # ---------------- shell/api.js ----------------
    # ⚠️ 这两句进的是 `Error.message`，壳里一律 `toast(...esc(e.message)...)` ⇒ **只能去星号**
    ("shell/api.js",
     "'这个动作在服务端**没有找到**（最常见的原因：后端刚改过、但**没有重启**）'",
     "'这个动作在服务端没有找到（最常见的原因：后端刚改过、但没有重启）'"),
    ("shell/api.js",
     "'请让管理员在服务器上**重启后端服务**（本仓无热重载），然后刷新页面重试。'",
     "'请让管理员在服务器上重启后端服务（本仓无热重载），然后刷新页面重试。'"),
    # ---------------- shell/core.js ----------------
    ("shell/core.js",
     "（集采是**逐条落库**，已落的不受影响）",
     "（集采是<b>逐条落库</b>，已落的不受影响）"),
    # ⚠️ 下面三处是 `title`（悬停）⇒ 去星号
    ("shell/core.js",
     "（只影响屏幕；⭐ **导出永远是全列**）",
     "（只影响屏幕；⭐ 导出永远是全列）"),
    ("shell/core.js",
     "expOld.title = '导出**当前屏幕上这些行**（含筛选）为 Excel —— ⭐ 列是**全列**（隐藏列也会导出）'",
     "expOld.title = '导出当前屏幕上这些行（含筛选）为 Excel —— ⭐ 列是全列（隐藏列也会导出）'"),
    ("shell/core.js",
     "b.title = '导出**当前屏幕上这些行**（含筛选）为 Excel —— ⭐ 列是**全列**（隐藏列也会导出）'",
     "b.title = '导出当前屏幕上这些行（含筛选）为 Excel —— ⭐ 列是全列（隐藏列也会导出）'"),
    ("shell/core.js",
     "⚠️ 这是**系统写入**（不是人工改仓库名，§2.3.1）",
     "⚠️ 这是<b>系统写入</b>（不是人工改仓库名，§2.3.1）"),
    ("shell/core.js",
     "**不能靠扶正解决** —— 需要人工核对档案",
     "<b>不能靠扶正解决</b> —— 需要人工核对档案"),
    ("shell/core.js",
     "'仓库名单本身**不落库**（它是建档的输入）",
     "'仓库名单本身<b>不落库</b>（它是建档的输入）"),
    ("shell/core.js",
     "'会按 phid **幂等建档**，并把",
     "'会按 phid <b>幂等建档</b>，并把"),
    # ⚠️ 下面四句是 `KIND_TXT`，使用处是 `${esc(KIND_TXT[…])}` ⇒ **只能去星号**
    ("shell/core.js",
     "但**单据名里认不出**是壳下哪个小微 ⇒ 出路：到「档案」页在该壳下**新建一个小微**",
     "但单据名里认不出是壳下哪个小微 ⇒ 出路：到「档案」页在该壳下新建一个小微"),
    ("shell/core.js",
     "（或给已有小微**补上**单据名里出现的关键词），补完**再抓一次**",
     "（或给已有小微补上单据名里出现的关键词），补完再抓一次"),
    ("shell/core.js",
     "单据名**同时命中壳下多个小微** ⇒ 出路：把关键词**补得更具体**，让它只命中一个，补完**再抓一次**",
     "单据名同时命中壳下多个小微 ⇒ 出路：把关键词补得更具体，让它只命中一个，补完再抓一次"),
    ("shell/core.js",
     "该项目**还没建档** ⇒ 出路：先在「档案」页建档（或同步 i8 常用项目），建成后**再抓一次**",
     "该项目还没建档 ⇒ 出路：先在「档案」页建档（或同步 i8 常用项目），建成后再抓一次"),
    ("shell/core.js",
     "<b>未落库</b>（**归属未走完** ⇒ 按口径**不纳管**）",
     "<b>未落库</b>（<b>归属未走完</b> ⇒ 按口径<b>不纳管</b>）"),
    # ---------------- shell/print-export.js ----------------
    ("shell/print-export.js",
     "条**已投递但未核实**）",
     "条<b>已投递但未核实</b>）"),
    ("shell/print-export.js",
     "条：请**看打印机实际出纸**，",
     "条：请<b>看打印机实际出纸</b>，"),
    # ⚠️ 这处是 `placeholder="…"` 属性 ⇒ 去星号
    ("shell/print-export.js",
     "（名字要**一字不差**）",
     "（名字要一字不差）"),
]

files: dict[str, str] = {}
bad: list[str] = []
for name, old, new in EDITS:
    if name not in files:
        files[name] = (W / name).read_text(encoding="utf-8", newline="")
    # ⚠️ 壳件是 **CRLF** ⇒ 多行 old **两套行尾各试一次**（⛔ 别全局 `\r\n`→`\n` 再写回：字节全变、
    #    `shell_verify` 与逐字节判据当场全乱）。
    for o, w in ((old, new), (old.replace("\n", "\r\n"), new.replace("\n", "\r\n"))):
        if files[name].count(o) == 1:
            files[name] = files[name].replace(o, w, 1)
            break
    else:
        bad.append(f"{name}: 命中 {files[name].count(old)} 次 ⇒ {old[:52]!r}")

if bad:
    print("⛔ 以下没命中（整批不写）：")
    for b in bad:
        print("   ", b)
    sys.exit(1)

# ② 内存里自检：剥注释后**全壳**都不该再有 `**`（含本轮没改到的件 —— 漏一处就退出 1）
leftovers = [
    f"{name}:{i}  {line.strip()[:110]}"
    for name, line, i in (
        (n, ln, i)
        for n, txt in files.items()
        for i, ln in enumerate(strip_comments(txt, html=n.endswith(".html")).splitlines(), 1)
        if "**" in ln
    )
]
if leftovers:
    print(f"⛔ 改完还剩 {len(leftovers)} 行含 `**`（同一批没收拾干净 ⇒ 不写盘）：")
    for x in leftovers:
        print("   ", x)
    sys.exit(1)

for name, text in files.items():
    (W / name).write_text(text, encoding="utf-8", newline="")
    print(f"✅ 已改 {name}（{len(text)} 字节）")
print(f"\n共 {len(EDITS)} 处替换 · 全部命中 1 次 ✔ · 剥注释后 0 个 `**` ✔")
