"""`m14` 接线后的两件工具侧收尾：

⛔⛔ **2026-09-30 `TAIL-201`：本件已失效**（它伺候的 `U1`/`U5` 与 `ui_parity_expected.txt` 登记簿
都已退场 ⇒ 照着跑会找不到东西）。**留作留痕**，⛔ 别照它执行。

① `ui_parity.py` 的 `U2b` 登记表加 `m14`（否则它**不看**这一页 ⇒ 「演示数组清干净了没」没人管）
② 把 `V.m14` 那 1 行漂移登记进 `ui_parity_expected.txt`（指纹算法 = `md5(原型行 + '||' + 壳行)[:8]`，
   取自 `ui_parity.py` 的 `fp(a + "||" + b)`，两边都是 `rstrip()` 后的行）

⛔ 不用 `--write-expected`：它会把已有备注冲成自动摘要（m05 那条被冲过一次）。
"""

from __future__ import annotations

import hashlib
import pathlib

ROOT = pathlib.Path(r"D:\dev\mtrl-workbench")
PROTO = pathlib.Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用\demo\材料报表自动化工作台-交互原型.html")
SHELL = ROOT / "backend" / "app" / "web" / "index.html"
UI = ROOT / "tools" / "ui_parity.py"
EXPECTED = ROOT / "tools" / "ui_parity_expected.txt"

# ---------------------------------------------------------------- ① DEMO_BY_PAGE
ui = UI.read_text(encoding="utf-8")
old = '                    "m09": ("AWF", "const|let|var")}'
new = '                    "m09": ("AWF", "const|let|var"), "m14": ("RULE_EX", "const|let|var")}'
if ui.count(old) != 1:
    raise SystemExit(f"⛔ DEMO_BY_PAGE 锚命中 {ui.count(old)} 次")
if '"m14"' in ui:
    print("① DEMO_BY_PAGE 已含 m14，跳过")
else:
    UI.write_text(ui.replace(old, new, 1), encoding="utf-8")
    print("① DEMO_BY_PAGE 已加 m14")

# ---------------------------------------------------------------- ② 登记漂移
VIEW_RE_HEAD = "V.m14="


def lines(p: pathlib.Path) -> list[str]:
    return p.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")


def slice_of(text: str, name: str) -> list[str]:
    """按 ui_parity 的切法取切片：从 `V.<name>=` 到下一个顶层声明为止。"""
    import re
    out: list[str] = []
    cur = False
    for ln in text.split("\n"):
        if re.match(rf"^{re.escape(name)}\s*=", ln):
            cur = True
            out.append(ln)
            continue
        if cur:
            if re.match(r"^(?:V\.|BIND\.|const |let |function )", ln):
                break
            out.append(ln)
    return out


proto = PROTO.read_text(encoding="utf-8").replace("\r\n", "\n")
shell = SHELL.read_text(encoding="utf-8").replace("\r\n", "\n")
p = [x.rstrip() for x in slice_of(proto, "V.m14")]
s = [x.rstrip() for x in slice_of(shell, "V.m14")]
print(f"② 切片行数：原型 {len(p)} · 壳 {len(s)}")

diffs = []
for i in range(max(len(p), len(s))):
    a = p[i] if i < len(p) else "<无此行>"
    b = s[i] if i < len(s) else "<无此行>"
    if a != b:
        diffs.append((i + 1, a, b, hashlib.md5((a + "||" + b).encode("utf-8")).hexdigest()[:8]))

print(f"   差异行数 = {len(diffs)}")
for ln, a, b, f in diffs:
    print(f"   L{ln} fp={f}")
    print(f"     原型: {a[:110]}")
    print(f"     壳  : {b[:110]}")

if len(diffs) != 1:
    raise SystemExit("⛔ 差异不是 1 行 —— 先看上面，别急着登记")

fp = diffs[0][3]
exp = EXPECTED.read_text(encoding="utf-8")
if f"m14 {fp}" in exp:
    print("② 该指纹已登记，跳过")
else:
    block = (
        f"\nm14 {fp}  # 接线即清演示（不是「改交互」）：V.m14 那句「本页各条「命中值」为演示值（原型数据全虚构）」"
        "在接线后是**假话**（值已改从 `/api/m14/rules` 读）⇒ 改成「本页「命中值」以系统配置为准（当前来源："
        "<后端给的 `source_label`>）」；\n"
        "#              壳 = 用**真数据**说同一件事，并把「改的只是这张演示表本身」更正为「改动**只影响后续抓取**」\n"
        "#              （后者原文与 §4.2.2 的「不重算历史剔除标记」口径不一致，接线后必须改）。\n"
        "#              ⚠️ 这是 `TAIL-40` 里 V.m14 的**唯一**改动；表格结构 / 三个动作 / 判据（分类规则只读、规则表不可排序）**一行未动**。\n"
    )
    EXPECTED.write_text(exp.rstrip("\n") + "\n" + block, encoding="utf-8")
    print("② 已登记漂移", fp)
