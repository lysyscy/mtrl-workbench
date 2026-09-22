"""壳的**完整性核对**：'四件的并集' ⇄ '某一版单文件壳'，**逐行多重集**比较。**工程自检**（不进 pytest）。

## 为什么要它（2026-09-19 实测踩到，代价很贵）

`P4`② 之后壳是**四件**（`index.html` ＋ `web/shell/*.js`）。任何"改一处忘了还原"——变异脚本异常中断、
手工编辑写错文件——**所有离线判据都看不见**：它们断言的是「壳里**含**某段文本」，
而**多出来的**变异文本不违反任何一条 ⇒ `pytest` rc=0 · 五把尺子全 0，**全绿但壳是坏的**。
实测的现场：`_mut_*` 脚本中断后，`shell/core.js` 里被留下两行**变异态**
（`if (!r || r.ok === false)` 与 `'特殊费用月报表X': reloadM09,`）⇒ 只有**真机**（探针看 console）与
**这份逐行核对**能发现。

## 跑法

`python tools/shell_verify.py`（默认基准 = `git show HEAD:backend/app/web/index.html`）
`python tools/shell_verify.py <任意一版单文件壳的路径>`

## 怎么读

- **`只在旧版里`** 每一条都要能解释：正常的只有 `boot();`（它变成了 `index.html` 里的 `<script>boot();</script>`）
  ＋ 文件头注释带来的 `*` 之类；**出现代码行 ⇒ 十有八九是变异态残留**（去对应件里搜它）。
- **`只在现在`** 应只有：文件头注释、三行 `<script src>`、启动点那行。
- ⚠️ 它**不判红也不判绿**（不 exit 非零）：是**给你看的清单** ⇒ 用途是"动过壳 / 跑过变异脚本之后扫一眼"。
"""

from __future__ import annotations

import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shell_source import REPO, SHELL_PARTS  # noqa: E402

REL = "backend/app/web/index.html"


def _lines(text: str) -> list[str]:
    return [l for l in text.replace("\r\n", "\n").split("\n") if l.strip()]


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        old = Path(argv[1]).read_text(encoding="utf-8")
        base = str(Path(argv[1]))
    else:
        old = subprocess.run(["git", "show", f"HEAD:{REL}"], capture_output=True,
                             cwd=REPO).stdout.decode("utf-8")
        base = f"HEAD:{REL}"
    new = "\n".join(p.read_text(encoding="utf-8") for p in SHELL_PARTS)

    c_old, c_new = Counter(_lines(old)), Counter(_lines(new))
    only_old = c_old - c_new
    only_new = c_new - c_old
    print(f"基准 {base}")
    print(f"  旧版非空行 {sum(c_old.values())} · 现四件非空行 {sum(c_new.values())}")
    print(f"  件：{' ＋ '.join(str(p.relative_to(REPO)) for p in SHELL_PARTS)}")
    print(f"\n⚠️ 只在旧版里（= 可能**丢了**或**被改动没还原**，逐条解释）：{sum(only_old.values())} 行")
    for l, n in list(only_old.items())[:20]:
        print(f"   {n}× {l.strip()[:100]}")
    print(f"\n只在现在（= 新增，正常应只有文件头注释 / `<script src>` / 启动点）：{sum(only_new.values())} 行")
    for l, n in list(only_new.items())[:20]:
        print(f"   {n}× {l.strip()[:100]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
