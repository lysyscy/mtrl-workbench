"""壳源码的**唯一读取出口**（性能 `P4`① 读取点收敛 · 2026-09-19 · 用户批准后动手）。

## 为什么要有它

壳原先是一个**单文件** `backend/app/web/index.html`，全仓有 **54 处**在直接读它：
26 个测试件 · 25 个**会复跑**的反向灵敏度脚本（`_mut_*.py`）· 两把尺子（`ui_parity` / `syntax_audit`）· `main.py`，
写法还有 5 种。`P4`② 要把**接线层**拆进 `web/shell/*.js` —— 那 54 处若各读各的，拆完就**集体读不到接线代码**
（而且是**静默**读不到：`in` 断言直接变假绿/假红）。
⇒ 先把读取收敛到这一处：**按 `index.html` 里 `<script src>` 的出现顺序**把各件拼起来。

## 对外暴露

| 名字 | 类型 | 给谁用 |
|---|---|---|
| `SHELL` | `str` | **合并后**的壳全文（= 测试/工具眼里的「壳源码」，`in` 断言都对着它） |
| `read_shell()` | `() -> str` | 同上，但要**现读**（不缓存）时用 |
| `SHELL_PARTS` / `part_paths()` | `list[Path]` | 逐件路径（`syntax_audit` 逐件 `node --check` 用） |
| `SHELL_PATH` | `Path` | ⚠️ **`index.html` 本体的路径** —— 只给「要**改文件字节**的变异脚本」用 |

## ⛔ 两条纪律

① **`index.html` 里的原型切片 `V.*` 不许搬走** —— `ui_parity` 的 `U1` 是**逐行**比原型 ⇄ 壳，搬了就是无谓风险；
② **拼接顺序 = 浏览器执行顺序**（内联 `script` 在前、外链按 `src` 出现顺序）—— ⛔ 别按文件名排序，
   也别把顺序写死在这里（顺序的真源 = `index.html` 里的标签顺序，改顺序只改那一处）。

⚠️ 缺件**显式抛**（⛔ 不静默少读一段 —— 「空输出 ≠ 通过」是本仓反复踩过的坑）。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WEB = REPO / "backend" / "app" / "web"
INDEX_HTML = WEB / "index.html"
SHELL_DIR = WEB / "shell"

#: `<script src="/static/shell/<name>.js">` ⇒ 取 `<name>.<ext>`（路由与文件名的唯一映射口径）
_SHELL_SRC_RE = re.compile(r"/static/shell/([\w.\-]+)")


def part_paths() -> list[Path]:
    """按**文档顺序**列出壳的每一件（`index.html` 永远第一件；后面按 `<script src>` 的出现顺序）。

    ⚠️ **别在这里写死件数与件名** —— 唯一口径就是 `index.html` 里的 `<script src>`（本函数照它现读，
    所以永远与浏览器执行顺序一致）。历史：`P4`②（2026-09-19）· 加 `api.js`（2026-09-24）· `P2-a` 六件（2026-09-28）
    都改过它；2026-09-24 曾在此写「已有 5 个外链 ⇒ 现为 6 件」，到 2026-09-28 就过期了 —— 那正是本条要防的。
    """
    html = INDEX_HTML.read_text(encoding="utf-8")
    return [INDEX_HTML] + [SHELL_DIR / name for name in _SHELL_SRC_RE.findall(html)]


def read_shell() -> str:
    """**合并后**的壳全文（缺件 ⇒ 显式抛，见模块头纪律）。"""
    chunks: list[str] = []
    for p in part_paths():
        if not p.exists():
            raise FileNotFoundError(
                f"壳的某一件不存在：{p} —— 拆件/改名后忘了同步 `index.html` 的 `<script src>`？"
            )
        chunks.append(p.read_text(encoding="utf-8"))
    return "\n".join(chunks)


def parts_text() -> list[tuple[str, str]]:
    """逐件 `(相对仓根的路径, 文本)` —— 给"**要逐件扫、并报出位置**"的检查用（如 `test_theme` 的色值扫描）。"""
    out: list[tuple[str, str]] = []
    for p in part_paths():
        try:
            name = str(p.relative_to(REPO)).replace("\\", "/")
        except ValueError:                                   # 件不在仓内（理论上不该发生）
            name = str(p)
        out.append((name, p.read_text(encoding="utf-8")))
    return out


def resolve(anchor: str) -> Path:
    """锚点文本**当前在哪一件**里 ⇒ 返回那一件的路径（⚠️ `P4`② 拆件后，锚点可能落在 `web/shell/*.js`）。

    ⛔ **找不到 / 多处命中都抛** —— ⛔ 绝不许静默回落到 `index.html`：
    那会让变异"改了个没人看的地方"却报成功（比 SKIP 更坏 —— SKIP 至少是**看得见**的未验证）。
    """
    hits = [p for p in part_paths() if anchor in p.read_text(encoding="utf-8")]
    if len(hits) != 1:
        raise LookupError(f"锚点在壳的 {len(hits)} 件里命中（期望 1）：{anchor[:70]!r}")
    return hits[0]


def pick(path: Path, *anchors: str) -> Path:
    """变异脚本专用：`path` 若是**壳的本体**（拆件前的 `SHELL_PATH`）⇒ 按锚点改判到**那一件**。

    用法：`path = pick(path, old, new)` —— 依次试各锚点（变异脚本只保证**旧**片段在壳里 ⇒ 旧的放前面）。
    `path` 不是壳本体（如后端 `.py`）⇒ 原样返回。
    """
    if path != INDEX_HTML:
        return path
    for a in anchors:
        try:
            return resolve(a)
        except LookupError:
            continue
    # ⚠️ 都找不到 ⇒ **回落到原 path**（`index.html`）：让调用方照常走"锚点命中 0 次 ⇒ **SKIP（未验证）**"
    #    那条路（⛔ 看得见的失败）。**不抛异常** —— 抛了会把整个脚本崩掉、连累同一脚本里其余的变异
    #    （2026-09-19 实测踩到：一条过期锚点让 `_mut_m06wired.py` 第 2 条起全没跑）。
    return path


#: `index.html` **本体**的路径（⚠️ `P4`② 之后**只有"拆件前"的老脚本**还用；
#:  新写的"改字节"脚本请用 `pick(path, old, new)` —— 壳是多件，锚点在哪件就改哪件）
SHELL_PATH: Path = INDEX_HTML
#: 壳的逐件路径（顺序 = 浏览器执行顺序）
SHELL_PARTS: list[Path] = part_paths()
#: **合并后**的壳源码（测试与工具的统一入口）
SHELL: str = read_shell()


def main() -> int:
    """`python tools/shell_source.py` —— 人看一眼当前件与规模（**不是判据**）。"""
    total = 0
    print("壳的件（顺序 = 浏览器执行顺序）：")
    for p in SHELL_PARTS:
        n = len(p.read_text(encoding="utf-8").splitlines()) if p.exists() else -1
        total += max(n, 0)
        rel = p.relative_to(REPO)
        print(f"  {n:>5} 行  {rel}")
    print(f"  {total:>5} 行  合计（合并后 SHELL = {len(SHELL.splitlines())} 行）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
