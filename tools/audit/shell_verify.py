"""壳的**完整性核对**：'四件的并集' ⇄ '某一版单文件壳'，**逐行多重集**比较。**工程自检**（不进 pytest）。

## 为什么要它（2026-09-19 实测踩到，代价很贵）

`P4`② 之后壳是**四件**（`index.html` ＋ `web/shell/*.js`）。任何"改一处忘了还原"——变异脚本异常中断、
手工编辑写错文件——**所有离线判据都看不见**：它们断言的是「壳里**含**某段文本」，
而**多出来的**变异文本不违反任何一条 ⇒ `pytest` rc=0 · 五把尺子全 0，**全绿但壳是坏的**。
实测的现场：`_mut_*` 脚本中断后，`shell/core.js` 里被留下两行**变异态**
（`if (!r || r.ok === false)` 与 `'特殊费用月报表X': reloadM09,`）⇒ 只有**真机**（探针看 console）与
**这份逐行核对**能发现。

## 跑法

```powershell
python tools/audit/shell_verify.py --snapshot        # ⭐ 先把**当前**并集存成基线（存 var/state/verification/shell-baselines/，留最近 5 份）
python tools/audit/shell_verify.py                   # 与**最新那份基线**比（没有基线才回落 git）
python tools/audit/shell_verify.py <某一版单文件壳的路径>   # 指定基准
```

⚠️⚠️ **2026-09-24 实测：默认基准（`git show HEAD:…/index.html`）已经失效过一次** ——
`7928c01`（09-22）那次提交里的 `index.html` **已经是拆件后**的版本 ⇒ 于是出现
「旧版非空行 3519 · 现并集 8252 · 只在现在 **4744 行**」这种满屏噪音，
**而它不判红、不 exit ⇒ 从 09-22 起就没人会喊**（典型的静默失效）。
⇒ 现在改成：**默认基准 = `var/state/verification/shell-baselines/` 里最新那份「壳单文件基线」**（没有基线 ⇒ **判红、要你建基线**）。
⭐ 规则：**壳动过（合法的改动）且复核通过后，就 `--snapshot` 刷一份新基线** —— 基线的含义 = "我上次确认过的样子"。

## ⭐⭐ 判定（2026-09-24 晚 · 给"僵尸闸门"接上真出口）

它是**盖章式闸门**（同 `git` 的 commit）：

- **默认基准（最新基线）且两边差集合计 > 0 ⇒ `rc=1`**；
- 差集 0 ⇒ `rc=0`；**没有基线 ⇒ `rc=1`**（闸门没有基准 = 闸门没在工作，⛔ 不静默放行）；
- ⚠️ **显式给基准路径**（用法 3）⇒ **只报不判**（那条用法本就是"我要看看跟那一版差在哪"，差异是**预期**的）。

⚠️ **为什么放行条件是"盖上章"而不是"没差异"**：合法改壳**必然**产生差异 ⇒ 不可能要求"零差异"。
⇒ 差异 = **提醒你确认**（"这是变异残留？还是我有意改的？"）；确认无误后 `--snapshot` 盖章 ⇒ 归零。
⛔ **盖章前的两道闸**（在污染态盖章 = 把污染**固化成基线**，从此洗白）：
① 真机 `tools/probe/_shell_smoke.py` **整支 rc=0**；② 确认**没在跑 / 没中断过**变异脚本。

## 怎么读

- **`只在旧版里`** 每一条都要能解释：正常的只有 `boot();`（它变成了 `index.html` 里的 `<script>boot();</script>`）
  ＋ 文件头注释带来的 `*` 之类；**出现代码行 ⇒ 十有八九是变异态残留**（去对应件里搜它）。
- **`只在现在`** 应只有：文件头注释、三行 `<script src>`、启动点那行。⚠️ 残留**也可能是"多出来"**
  （2026-09-19 实测就是 `core.js` 里**多**了两行变异态）⇒ ⛔ **别看单边**，判据是**两边合计**。
- ⚠️ **能力边界**：比的是**逐行多重集**（`Counter` 差集）⇒ **不比顺序、不看语义**。
  ⇒ 它**不等于**"壳完整性有守护"：把一段代码**原样挪到别处**它看不见（多重集**不看顺序**）。
   ⚠️ **2026-09-30 `TAIL-201`**：`ui_parity` 的 `U1`/`U5`（逐行对位）**已退场** ⇒ 这一层
      **现在没人守**，⭐ **本轮明确接受**这个缺口（见 §15 §四 `TAIL-201` 销号行）；
      要补就从"把本件改成**顺序**比对"下手（⛔ 别退回去再养一份"第二真源"）。
"""

from __future__ import annotations

import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shell_source import REPO, SHELL_PARTS  # noqa: E402

# ⚠️ 2026-09-24：原 `subprocess` 导入与 `REL` 常量随「回落 `git HEAD`」那条路一起删掉 ——
#    那条路**已退化成噪音**（拆件后 HEAD 里就是多件并集）⇒ 现在无基线**直接判红**（见文件头「判定」）。


def _lines(text: str) -> list[str]:
    return [l for l in text.replace("\r\n", "\n").split("\n") if l.strip()]


BACKUPS = REPO / "var/state/verification/shell-baselines"
SNAP_GLOB = "*_壳单文件基线.html"


def _newest_snapshot() -> Path | None:     # ⭐ 2026-09-30 `TAIL-201`：收回**私有**
    #   （`ui_parity` 的 `U1`/`U5` 已退场 ⇒ 本件是唯一用它的；⛔ 当年「提为公开」那个理由没了）
    """最新那份「壳单文件基线」（`var/state/verification/shell-baselines/` · 文件名 `YYYYMMDD-HHMM_壳单文件基线.html`）。"""
    if not BACKUPS.exists():
        return None
    hits = sorted(BACKUPS.glob(SNAP_GLOB))
    return hits[-1] if hits else None


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    new = "\n".join(p.read_text(encoding="utf-8") for p in SHELL_PARTS)

    if "--snapshot" in argv:
        BACKUPS.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d-%H%M")
        out = BACKUPS / f"{ts}_壳单文件基线.html"
        out.write_text(new, encoding="utf-8")
        too_old = sorted(BACKUPS.glob(SNAP_GLOB))[:-5]        # 只留最近 5 份
        for p in too_old:
            p.unlink()
        print(f"✅ 已存基线：{out.relative_to(REPO)}（非空行 {len(_lines(new))}）")
        if too_old:
            print(f"   顺手清掉 {len(too_old)} 份更旧的基线（只留最近 5 份）")
        return 0

    snap: Path | None = None
    explicit = bool(args)                     # 显式给基准 ⇒ 只报不判（见文件头「判定」）
    if explicit:
        old = Path(args[0]).read_text(encoding="utf-8")
        base = str(Path(args[0]))
    else:
        snap = _newest_snapshot()
        if snap is None:
            # ⛔ 不回落 `git HEAD`：拆件后那份对比**已退化成噪音**（2026-09-24 实测 4744 行）⇒ 宁可显式红。
            print("⛔ 没有基线快照 ⇒ 本闸门**无基准**（⛔ 不回落 git HEAD：拆件后那份对比已退化成噪音）")
            print("   修法：① 复核当前壳（真机 `tools/probe/_shell_smoke.py` 整支 rc=0 ＋ 确认没在变异态）")
            print("         ② 跑 `python tools/audit/shell_verify.py --snapshot` 建基线")
            return 1
        old = snap.read_text(encoding="utf-8")
        base = f"{snap.relative_to(REPO)}（最新一份基线）"

    c_old, c_new = Counter(_lines(old)), Counter(_lines(new))
    only_old = c_old - c_new
    only_new = c_new - c_old
    print(f"基准 {base}")
    print(f"  旧版非空行 {sum(c_old.values())} · 现并集非空行 {sum(c_new.values())}")
    print(f"  件：{' ＋ '.join(str(p.relative_to(REPO)) for p in SHELL_PARTS)}")
    print(f"\n⚠️ 只在旧版里（= 可能**丢了**或**被改动没还原**，逐条解释）：{sum(only_old.values())} 行")
    for l, n in list(only_old.items())[:20]:
        print(f"   {n}× {l.strip()[:100]}")
    print(f"\n只在现在（= 新增；⚠️ 残留也可能是「多出来」⇒ 别看单边）：{sum(only_new.values())} 行")
    for l, n in list(only_new.items())[:20]:
        print(f"   {n}× {l.strip()[:100]}")

    if explicit:
        print("\n（显式给了基准 ⇒ **只报不判**：这里的差异是**预期**结果）")
        return 0
    diff = sum(only_old.values()) + sum(only_new.values())      # ⭐ 两边**合计**（不是只看旧版）
    if diff:
        print(f"\n⛔ 与最新基线差 **{diff}** 行 ⇒ **判红**（盖章式闸门）")
        print("   两种可能：① **变异残留 / 改壳忘了还原** ⇒ 去对应件里搜上面那几行；")
        print("             ② **这一轮有意改了壳** ⇒ 复核通过后跑 `--snapshot` **盖章**（差异即归零）")
        print("   ⛔ 盖章前必过两道闸：真机 `tools/probe/_shell_smoke.py` **整支 rc=0** ＋ 确认**没在变异态**")
        return 1
    print("\n✅ 与最新基线**逐行一致**（多重集差 0）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
