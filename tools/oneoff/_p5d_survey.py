"""`P5-d` 的**铺量前量测**（⛔ 只读）：`TBL({rows:html[]})` ⇒ `TBL({cols:[{t,r,s}]})` 到底要动多少、动哪几处。

**为什么必须先量**（施工图 §7.4 对 `P5-d` 的原文要求：⚠️ **另一件大事** ⇒ **先出量测再定批**）：
`rows:` 里那串行模板**住在 `V.*` 切片里**（`index.html` 的内联脚本）⇒ 改写法会让 `ui_parity` 的
`U1`（**逐行对位**比原型 ⇄ 壳）**级联报漂移** ⇒ 动之前必须知道"哪几处在切片里、每处要动几行"。

**量什么**（每处 `TBL({…})` 调用点）：

  ① 在哪件 · 落在哪个 `V.<页>` 切片（或哪一层：`BIND` 钩子 / 弹窗动作 / 接线层）；
  ② `rows:` 是**怎么写的** —— `xxx.map(…)` 内联模板 / 直接引用一个变量 / 字符串，以及这串模板
     **有几行 · 几个 `<tr>` · 几个 `<td>`**（＝列数：`cols` 化的规模）；
  ③ 模板里有没有**条件列 / 派生列**（`${cond?…:…}` / 嵌套 `.map` / 计算）—— 有 ⇒ `r` 那格就不只是取值；
  ④ ⚠️ **`U1` 级联面** = "落在 `V.*` 切片里的调用点"（`U1` 只比这些）＋ 每处改动会碰掉的行数。

用法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_p5d_survey.py`
"""

from __future__ import annotations

from pathlib import Path as _WorkspacePath
import sys as _workspace_sys
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2] / 'tools/audit'))
from workspace_paths import output as _run_output, output_dir as _run_dir

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "audit"))

from shell_source import parts_text  # noqa: E402

OUT = ROOT / _run_dir() / "_p5d_survey.json"


def _scan_call(t: str, i: int) -> str:
    """从 `TBL({` 的 `{` 起，按**括号深度 ＋ 引号状态**取出整段调用文本（⛔ 别用正则硬切）。"""
    j = t.index("{", i)
    depth, k, q = 0, j, ""
    while k < len(t):
        c = t[k]
        if q:                                        # 在字符串里：只在同一种引号上收尾（⚠️ 反斜杠转义一并跳过）
            if c == "\\":
                k += 2
                continue
            if c == q:
                q = ""
        elif c in "\"'`":
            q = c
        elif c in "{[(":
            depth += 1
        elif c in "}])":
            depth -= 1
            if depth == 0:
                return t[j:k + 1]
        k += 1
    raise ValueError("⛔ 这段 `TBL({` 的括号没收住（模板串里的反引号？）")


def _arg(call: str, name: str) -> str:
    """取 `name:` 后面那一整段实参（同 `_scan_call` 的括号/引号口径）。"""
    m = re.search(r"(?<![\w$])" + name + r"\s*:", call)
    if not m:
        return ""
    k = m.end()
    while k < len(call) and call[k] == " ":
        k += 1
    start, depth, q = k, 0, ""
    while k < len(call):
        c = call[k]
        if q:
            if c == "\\":
                k += 2
                continue
            if c == q:
                q = ""
        elif c in "\"'`":
            q = c
        elif c in "{[(":
            depth += 1
        elif c in "}])":
            if depth == 0:
                break
            depth -= 1
        elif c == "," and depth == 0:
            break
        k += 1
    return call[start:k].strip()


def _slice_of(t: str, i: int) -> str:
    """这一处在哪个 `V.<页>` 切片里（取它前面最近的一处 `V.xxx=`）。"""
    m = None
    for m in re.finditer(r"\n\s*V\.([\w]+)\s*=", t[:i]):
        pass
    return m.group(1) if m else ""


def main() -> int:
    rows: list[dict] = []
    for name, t in parts_text():
        for m in re.finditer(r"TBL\(\{", t):
            if name.endswith("shell/proj.js") and t[:m.start()].rstrip().endswith("const TBL=("):
                continue                                        # 定义处，不是调用
            call = _scan_call(t, m.start())
            rows_expr = _arg(call, "rows")
            key = _arg(call, "key")
            line = t[:m.start()].count("\n") + 1
            sl = _slice_of(t, m.start())
            cond = len(re.findall(r"\$\{[^}]*\?", rows_expr)) + len(re.findall(r"\.map\(", rows_expr)) - 1
            #: ⭐⭐ **表头来源**（`P5-d-b` 补量）：**决定"能不能转列定义式"** ——
            #: 表头来自 `*_THEAD` 常量的调用点**不能**转（`t` 会把表头**抄第二份**，而那个常量还被
            #: `thCount` / `sumRowOf` / `U5` 吃着）⇒ 只有**内联**的那些能安全转。
            hm = re.search(r"(?<![\w$])head\s*:\s*([^,]+)", call)
            h = (hm.group(1).strip() if hm else "")
            head_src = ("（无 head）" if not h
                        else ("内联" if h[:1] in "'\"`"
                              else ("常量" if re.fullmatch(r"[A-Z][A-Z0-9_]*", h.split("(")[0].strip())
                                    else "表达式")))
            rows.append({
                "part": name.replace("backend/app/web/", ""),
                "line": line, "slice": sl, "key": key.strip(), "head_src": head_src,
                "call_lines": call.count("\n") + 1,
                "rows_lines": rows_expr.count("\n") + 1 if rows_expr else 0,
                "tr": rows_expr.count("<tr"), "td": rows_expr.count("<td"),
                "rows_form": ("内联 .map" if ".map(" in rows_expr else
                              ("变量/表达式" if rows_expr else "（缺 `rows`）")),
                "cond": max(cond, 0),                # 条件/派生列个数（粗量：`${…?…:…}` ＋ 嵌套 `.map`）
                "rows_expr": (" ".join(rows_expr.split()))[:80],
            })

    print(f"{'件':<18}{'行':<7}{'切片':<8}{'key':<22}{'表头':<9}{'rows 写法':<12}{'调用行':<7}{'模板行':<7}"
          f"{'tr/td':<9}{'条件/嵌套'}")
    print("-" * 132)
    for r in rows:
        print(f"{r['part']:<18}{r['line']:<7}{r['slice'] or '—':<8}{r['key'][:20]:<22}"
              f"{r['head_src']:<9}{r['rows_form']:<12}{r['call_lines']:<7}{r['rows_lines']:<7}"
              f"{str(r['tr']) + '/' + str(r['td']):<9}{r['cond']}")

    in_slice = [r for r in rows if r["slice"]]
    print("\n" + "=" * 124)
    print(f"① 调用点合计 **{len(rows)}** 处 —— 落在 `V.*` 切片里（⇒ **`U1` 会级联**）：**{len(in_slice)}** 处")
    by_part: dict[str, int] = {}
    for r in rows:
        by_part[r["part"]] = by_part.get(r["part"], 0) + 1
    print("   逐件：" + " · ".join(f"{k} {v}" for k, v in sorted(by_part.items(), key=lambda x: -x[1])))
    print(f"② `rows:` 写法：内联 `.map` **{sum(1 for r in rows if r['rows_form'] == '内联 .map')}** 处 · "
          f"变量/表达式 **{sum(1 for r in rows if r['rows_form'] == '变量/表达式')}** 处"
          f"{' · 缺 `rows` ' + str(sum(1 for r in rows if r['rows_form'].startswith('（缺'))) if any(r['rows_form'].startswith('（缺') for r in rows) else ''}")
    print(f"③ 行模板规模（`cols` 化的规模）：`<td>` 总数 **{sum(r['td'] for r in rows)}** · "
          f"`<tr>` 总数 **{sum(r['tr'] for r in rows)}** · 模板总行数 **{sum(r['rows_lines'] for r in rows)}** 行")
    print(f"④ 带**条件 / 派生列 / 嵌套**的：**{sum(1 for r in rows if r['cond'])}** 处"
          f"（⇒ 这些的 `r` 那格不只是取值，得逐个看）")
    pure = [r for r in rows if r["cond"] == 0 and r["rows_form"] == "内联 .map"]
    print(f"⑤ ⭐ 「**纯逐列取值**」＝可机械换的第一梯队：**{len(pure)}** 处 ——")
    for r in pure[:12]:
        print(f"     {r['part']}:{r['line']}  slice={r['slice'] or '—'}  key={r['key'] or '（无）'}  "
              f"td={r['td']}  模板 {r['rows_lines']} 行")
    by_head: dict[str, int] = {}
    for r in rows:
        by_head[r["head_src"]] = by_head.get(r["head_src"], 0) + 1
    print("⑥ ⭐⭐ **表头来源**（`P5-d-b` 补量 —— 它决定「能不能转列定义式」）："
          + " · ".join(f"{k} **{v}**" for k, v in sorted(by_head.items(), key=lambda x: -x[1])))
    print("     ⛔ **表头来自 `*_THEAD` 常量的不能转** —— `cols[].t` 会把表头**抄第二份**，"
          "而那个常量还被 `thCount` / `sumRowOf` / `U5` 吃着（见施工图 §7.12 必读①）；")
    print("     ⚠️ 多行行模板的站点撞「**空白差**」口径（`\n` ＋ 缩进会进渲染字节）⇒ 必读②。")
    can = [r for r in rows if r["head_src"] == "内联" and r["rows_form"] == "内联 .map"
           and r["cond"] == 0 and not r["slice"] and r["rows_lines"] == 1]
    print(f"     ✅ **本批口径下可安全转的**（内联表头 ＋ 纯取值 ＋ 单行模板 ＋ 不在 `V.*` ⇒ 零级联）：**{len(can)}** 处 ——")
    for r in can:
        print(f"        {r['part']}:{r['line']}  key={r['key'] or '（无）'}  td={r['td']}")
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n逐处读数已落：{OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
