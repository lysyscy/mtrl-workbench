"""**变异覆盖台账生成器**（`TAIL-57` · 2026-09-21）。

## 它解决什么

本仓的判据有两层：① **判据本身**（pytest 1138 条 ＋ 13 把尺子）；② **判据的反向灵敏度**
（变异脚本 `tools/**/_mut_*.py`：把实现**故意改坏** ⇒ 对应断言必须变红，否则是**假绿**）。
⚠️② 这一层**没有台账** ⇒ "哪些代码区被变异验过、哪些**从没验过**"没人答得上来 ——
   且已有实测教训：`_mut_boot` / `_mut_m03pay` 曾因 `pick()` 签名变化**静默崩掉**（**守卫自己烂了**）。
⇒ 本件把 ② 生成成一张台账（`artifacts/变异覆盖台账.md`），每条变异件列出：
   **守什么 / 改坏谁 / 用哪条判据验 / 怎么跑**；并列出**登记在案的"尚未有变异覆盖"的守卫**。

## 用法

    backend/.venv/Scripts/python.exe tools/mut_cover.py            # 重新生成台账（覆盖写）
    backend/.venv/Scripts/python.exe tools/mut_cover.py --check    # 只比对，变了 ⇒ rc=1（可挂闸门）

## 设计约束

- **rglob `tools/**/_mut_*.py`**（⛔ 不写死 `tools/` 一层）—— `TAIL-58` 分目录后本件**不失效**；
- 台账是**生成物**（`artifacts/`，⛔ 不手改）—— 手改会被下次生成覆盖；要改内容去改本件；
- ⛔ **只读源码**，本件不执行任何变异（跑变异请逐个跑对应脚本）。
"""

from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding="utf-8")

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "变异覆盖台账.md"

#: ⭐ **登记在案：还没有变异覆盖的守卫**（⛔ 手工维护 —— 加一条守卫时来这里登记，
#:    补了变异脚本就从这里删掉；**这条清单本身是台账的一半**，只生成"有 _mut 的"会漏掉这一半）。
#: 判"有没有"的方法：守卫文件名 / 守的代码区 是否出现在某个 `_mut_*.py` 的目标或说明里。
UNCOVERED: tuple[tuple[str, str, str], ...] = (
    ("doc_audit 的 T1/T2/T3（漂移）", "文档里的过期口径 / 已删字段 / 断链路径",
     "`_mut_docaudit` 只覆盖 T4 扩面＋T6 落点", "照 `_mut_docaudit` 的做法：改坏一处真源 ⇒ T 必须红"),
    ("doc_audit 的 T5/T9/T10/T11/T12", "行数 / 纪律出处 / 读预算 / 报告回执 / 分层约定",
     "2026-09-21 新立，还没配变异", "每条造一处违规 ⇒ 必须红（`T12` 已有 `tools/_mut_t12.py` ⇒ 从本表挪到已覆盖）"),
    ("ui_parity 的 U2/U3/U4", "演示数组残留 / WIRED 自洽 / 接线存在", "U1 由各页变异间接覆盖，U2–U4 无",
     "塞回一个 `const NT=[…]` ⇒ U2 必须红"),
    ("syntax_audit / cover_gap / claim_audit / prg_form_audit / shell_verify", "五把独立尺子",
     "从未做过反向灵敏度", "各改坏一处 ⇒ 对应尺子必须红"),
    ("sticky_probe（合计置底）", "200px / 30 行 实测参数", "真机探针，变异成本高", "低优先；改参数 ⇒ 真机必红"),
    ("交付面四检（_smoke/_doccheck/_links/_ids）", "原型 ⇄ 壳的四类一致性", "在交付面，变异要动原型", "冻结后随批次 2 一起"),
)


def _docstring_head(t: str, n: int = 130) -> str:
    """docstring 的**第一行**当「守什么」⇒ ⛔ 不抓整段（变异件的 docstring 常带 Markdown 表格，
    里面的 `|` 会把台账的表格撑破 —— 2026-09-21 首版就栽在这）。"""
    m = re.search(r'"""(.{0,600})', t, re.S)
    if not m:
        return "（无 docstring —— ⛔ 补一段「守什么」）"
    line = m.group(1).splitlines()[0] if m.group(1).splitlines() else ""
    line = line.replace("|", "／").strip()
    return line[:n] + ("…" if len(line) > n else "")


def _file_index() -> dict[str, list[str]]:
    """`文件名 → [相对路径]`（一次建好；裸文件名的目标靠它解析）。"""
    idx: dict[str, list[str]] = {}
    for base in ("backend/app", "backend/tests", "tools", ""):
        for p in (ROOT / base).glob("**/*") if base else ROOT.glob("*.html"):
            if p.is_file() and p.suffix in (".py", ".js", ".html"):
                idx.setdefault(p.name, []).append(str(p.relative_to(ROOT)).replace("\\", "/"))
    return idx


def scan() -> list[dict]:
    idx = _file_index()
    rows: list[dict] = []
    for p in sorted(ROOT.glob("tools/**/_mut_*.py")):
        t = p.read_text(encoding="utf-8", errors="replace")
        rel = str(p.relative_to(ROOT)).replace("\\", "/")
        raw = sorted({x.replace("\\", "/") for x in
                      re.findall(r'["\']([\w\-\\/\.]+\.(?:py|html|js))["\']', t)
                      if not x.startswith("tests/")})
        exists: list[tuple[str, bool]] = []
        for x in raw:
            if "/" in x:
                ok = (ROOT / "backend" / x).exists() or (ROOT / x).exists()
            else:
                ok = x in idx                       # 裸文件名 ⇒ 全站按名找（⛔ 不是"必须带路径"）
            exists.append((x, ok))
        rows.append({
            "name": p.name,
            "rel": rel,
            "guards": _docstring_head(t),
            "targets": raw,
            "exists": exists,
            "tests": sorted(set(re.findall(r"(tests/[\w\.]+\.py)", t))),
        })
    return rows


def render(rows: list[dict]) -> str:
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    L = [
        "# 变异覆盖台账（**生成物** · `tools/mut_cover.py` 生成 ⛔ 不手改）",
        "",
        f"> 生成于 {now} · 变异件 **{len(rows)}** 个 · 判据线见计划 §0（本台账只管**反向灵敏度**这一层）。",
        "> ⭐ 读法：**表 A** = 已有的变异（改坏谁 ⇒ 哪条判据必须红）；**表 B** = 登记在案的**尚未覆盖**的守卫。",
        "> ⚠️ 已有实测教训：变异脚本会**静默烂掉**（`_mut_boot`/`_mut_m03pay` 因 `pick()` 签名变化崩过）",
        "> ⇒ **重构成批改了某模块后，把表 A 里涉及它的变异件重跑一遍**。",
        "",
        "## 表 A · 已有变异（按件）",
        "",
        "| 变异件 | 守什么 | 改坏谁（目标） | 验的判据 |",
        "|---|---|---|---|",
    ]
    for r in rows:
        tg = "、".join(f"`{x}`" + ("" if ok else "⚠️找不到") for x, ok in r["exists"]) or "（脚本内联）"
        ts = "、".join(f"`{x}`" for x in r["tests"]) or "（自验）"
        L.append(f"| `{r['rel']}` | {r['guards']} | {tg} | {ts} |")
    missing = [f"`{r['rel']}` 里引用的 `{x}`" for r in rows for x, ok in r["exists"] if not ok]
    if missing:
        L += ["", f"⚠️ **{len(missing)} 个目标文件找不到**（多半是路径写法变了）：", ""] + \
             [f"- {m}" for m in missing]
    L += [
        "", "## 表 B · 尚未有变异覆盖的守卫（**手工登记**，源头 = `mut_cover.py::UNCOVERED`）", "",
        "| 守卫 | 守什么 | 现状 | 建议补法 |", "|---|---|---|---|",
    ]
    for name, what, why, how in UNCOVERED:
        L.append(f"| {name} | {what} | {why} | {how} |")
    L += [
        "", "## 怎么补一条变异", "",
        "1. 照任意表 A 件的骨架：**改坏 → 跑指定判据（期望红）→ 逐字节复原 → MD5 校验**；",
        "2. 脚本 docstring **第一段必须写「守什么」**（本台账的「守什么」列就是抓它）；",
        "3. 放 `tools/mut/`（`TAIL-58` 分目录后），名字 `_mut_<主题>.py`；",
        "4. 重跑本件 ⇒ 台账自动多一行；若它守的原来是表 B 里那条 ⇒ **把那行从 `UNCOVERED` 删掉**。",
        "",
        "---",
        f"_{len(rows)} 变异件 · {sum(len(r['tests']) for r in rows)} 条判据引用 · 生成器 `tools/mut_cover.py`_",
        "",
    ]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description="变异覆盖台账生成器")
    ap.add_argument("--check", action="store_true", help="只比对不写（变了 ⇒ rc=1）")
    a = ap.parse_args()
    rows = scan()
    text = render(rows)
    if a.check:
        # ⭐ 排除「生成于」行再比 —— 否则每过一分钟 --check 都会假报"不一致"（首版就栽在这）
        norm = lambda s: "\n".join(l for l in s.splitlines() if not l.startswith("> 生成于"))
        old = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if norm(old) != norm(text):
            print("⚠️ 台账与生成结果不一致 ⇒ 重跑 `tools/mut_cover.py`")
            return 1
        print(f"台账一致 ✔（{len(rows)} 变异件）")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8", newline="")
    print(f"已生成 {OUT.relative_to(ROOT)}（{len(rows)} 个变异件 · {len(UNCOVERED)} 条未覆盖登记）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
