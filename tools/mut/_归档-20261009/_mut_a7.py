"""守什么：`A7` 逐页（`m11` 集采台账）新写的守卫 ——
`tests/test_ux_pages.py` 的 `test_集采抓取按钮要写清后果`（`001-60`）与
`test_集采台账行身份区要钉住_且偏移必须是量出来的`（`001-61`）到底有没有区分力。

**为什么单开一件**：本仓纪律 = 新写/收紧判据 ⇒ 同批证明它**改坏了会红**。
靶（一次只碰一处、改完**立刻按 bytes 复原** ＋ 收尾 MD5）：
- `M1` **摘掉** `title`（回到"点了才知道会顶号"）⇒ `001-60` 必红（"有没有提示"那半）。
- `M2` 提示**留着但把后果删掉**（写成"刷新列表"这种白开水）⇒ `001-60` 必红（"提示写清没写清"那半）。
- `M3` 删掉 `BIND.m11` 里那次 `jcApplyPin()`（"渲染后不重量"）⇒ `001-61` 必红（调用点不够）。
- `M4` 把**量出来**的偏移换成**写死**的（`[0,29,76,161]`）⇒ `001-61` 必红
  （本页列宽随视口变 —— 写死就是 `TAIL-180` 里那条实测教训本身）。

跑法：`backend\\.venv\\Scripts\\python.exe tools\\mut\\_mut_a7.py`（rc=0 = 四靶都按预期变红且已复原）
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(ROOT / "tools" / "audit"))
from shell_source import SHELL_PATH as SHELL, pick  # noqa: E402

PY = str(BACKEND / ".venv" / "Scripts" / "python.exe")
#: ⚠️ **两件都要跑**：本批的判据分住在两处（`test_ux_pages.py` 的 `001-60…001-62` ·
#:   `test_imp_shell.py` 的 `001-63`）。2026-09-29 实测踩到：只跑一件 ⇒ M7（改 `legacy.js`）
#:   **根本没被跑到** ⇒ 报"假绿"（那是**变异脚本自己的假红/假绿**，不是断言没区分力）。
NODES = ("tests/test_ux_pages.py", "tests/test_imp_shell.py", "tests/test_ux_colors.py",
         "tests/test_tail04_export.py")

MUTATIONS: list[tuple[str, str, str]] = [
    (
        "M1 摘掉抓取按钮的 `title`（用户点了才知道会顶号）",
        ' data-act="jcFetch" title="从 i8 抓采购合同 —— 会登录 i8、需二次确认；⚠️ 可能顶掉该账号其它在线会话'
        '（同事正在用 i8 时先择时）"',
        ' data-act="jcFetch"',
    ),
    (
        "M2 提示留着、但把**后果**写成白开水（「刷新一下列表」）",
        'title="从 i8 抓采购合同 —— 会登录 i8、需二次确认；⚠️ 可能顶掉该账号其它在线会话（同事正在用 i8 时先择时）"',
        'title="刷新一下列表"',
    ),
    (
        "M3 删掉 `BIND.m11` 里那次 `jcApplyPin()`（渲染后不重量 ⇒ 一改筛选就露缝）",
        "  jcApplyPin();\n",
        "",
    ),
    (
        "M4 把量出来的偏移换成写死的（本页列宽随视口变 ⇒ 写死必错位）",
        "const off=i=>i===0?0:ths[i-1].getBoundingClientRect().right-L0;",
        "const off=i=>[0,29,76,161][i]||0;",
    ),
    (
        "M5 启动失败横幅又变回浮层（`position:fixed;top:0;z-index:9999`）⇒ 盖住页首、吃掉卡头点击",
        "el.style.cssText = 'flex:0 0 auto;margin:0;border-radius:0';",
        "el.style.cssText = 'position:fixed;left:0;right:0;top:0;z-index:9999;margin:0;border-radius:0';",
    ),
    (
        "M6 横幅改回挂在 `body` 上（`body` 是 `overflow:hidden` ⇒ 溢出被裁）",
        "  if (host && view && view.parentElement === host) host.insertBefore(el, view);\n"
        "  else (host || document.body).prepend(el);",
        "  document.body.prepend(el);",
    ),
    (
        "M7 `V.imp` 里又画了第二条四步条（＝用户 2026-09-26 报的那个 bug 原样回来）",
        "  return `${lgNotice(IMP)}${head}${mapCard}${prevCard}${repCard}`;",
        "  return `${lgSteps(IMP_STEPS, IMP.step)}${lgNotice(IMP)}${head}${mapCard}${prevCard}${repCard}`;",
    ),
    (
        "M8 `m08` 那句**机制说明**又挂回成功绿（守则 §4.5：绿只给「已经做完」的回执）",
        '<div class="tip" style="margin:0"><b>已验证：</b>',
        '<div class="tip ok" style="margin:0"><b>已验证：</b>',
    ),
    (
        "M10 `m14` 那句**口径说明**又挂回危险红（守则 §4.5：红只给危险 / 错）",
        '<div class="tip" style="margin:0"><b>分类只有三类</b>',
        '<div class="tip dg" style="margin:0"><b>分类只有三类</b>',
    ),
    (
        "M9 `BIND.m08` 不再摘那枚空转的朴素导出（用户 2026-09-29 裁定 `A` 要摘掉它）",
        # ⚠️ 锚点必须带上**本钩子那一行选择器**：`if (naive) naive.remove();` 这句 `BIND.m06` 里也有一份
        #    （实测：只写那一句命中 2 次 ⇒ 当场报"锚点命中 2 次"）
        '  const naive = host.querySelector(\'[data-act="exp"][data-t="库存单据明细总表"]\');\n'
        "  if (naive) naive.remove();\n",
        '  const naive = host.querySelector(\'[data-act="exp"][data-t="库存单据明细总表"]\');\n',
    ),
]


def run_one() -> bool:
    """跑这几件判据 ⇒ True = **通过**（⛔ 把"没跑起来"也当通过 —— 那是"假绿"的一种）。"""
    r = subprocess.run(
        [PY, "-m", "pytest", "-q", *NODES],
        cwd=str(BACKEND), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    out = (r.stdout or "") + (r.stderr or "")
    assert "no tests ran" not in out, "判据节点没跑起来（名字写错了？）"
    return r.returncode == 0


def main() -> int:
    before = SHELL.read_bytes()
    hits = 0
    for name, old, new in MUTATIONS:
        sh = pick(SHELL, old, new)
        sh0 = sh.read_bytes()
        text = sh.read_text(encoding="utf-8")
        if old not in text:
            print(f"⛔ {name}：**变异串没找到**（实现已改？）—— 本项作废")
            continue
        assert text.count(old) == 1, f"{name}：变异锚点命中 {text.count(old)} 次（要恰好 1 次）"
        sh.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
        passed = run_one()
        sh.write_bytes(sh0)                                   # ⭐ 每条改完立刻复原
        if passed:
            print(f"❌ {name}：改坏了却**仍然全绿** ⇒ 该断言是假绿")
        else:
            print(f"✅ {name}：对应断言**变红**（有区分力）")
            hits += 1
    ok = hashlib.md5(SHELL.read_bytes()).hexdigest() == hashlib.md5(before).hexdigest()
    print("\n  复原校验（MD5 逐字节）：", "✅ 已复原" if ok else "❌ 没复原！")
    print(f"\n结论：{hits}/{len(MUTATIONS)} 命中" + ("（rc=0）" if ok and hits == len(MUTATIONS) else "（需处理）"))
    return 0 if (ok and hits == len(MUTATIONS)) else 1


if __name__ == "__main__":
    sys.exit(main())
