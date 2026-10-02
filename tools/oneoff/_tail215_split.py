"""`TAIL-215` 批 2 的**机械拆分**：把 15 个 `seg_*` 段函数从 `_shell_smoke.py` 移成**每段一件**。

## 为什么

`TAIL-215` 的病根 = 「**每加一段都要改主文件**」（689 行 ⇒ 批 1 后 614 行，仍 >600 黄）。
批 1 把「顺序」收进了注册表；批 2 把「段的代码」也搬出去 ⇒
主件只留 **引导 ＋ 遍历注册表 ＋ 汇总**，此后加一段 = **加一个文件 ＋ 注册表加一行**。

## 它做四件（全是机械的，**代码一字不改**）

1. 15 个 `seg_<名>(page, errors)` ⇒ `tools/probe/_shell_<新名>.py` 里的 `check(page, errors)`（**函数体原样**）；
   · 用 `_goto(page, …)` 的 ⇒ 改成 `goto(page, …)` 并加 `from _shell_common import goto`（`_goto` 本来就只是它的薄壳）；
   · ⓪ 用的 `_session_cookie()` ⇒ `session_cookie()`（**函数搬进 `_shell_common.py`**，因为它被 `tools/oneoff/_p5c_survey.py` 也用着）；
   · ㉒ 用的 `_db_hygiene()` ⇒ 那个函数**跟着搬进** `_shell_dbhygiene.py`。
2. 主件重建 = 头部（docstring ＋ import）＋ `_boot` ＋ `_run_segment` ＋ `main` ＋ 尾部；
   ⛔ `_goto` / `_session_cookie` / `_db_hygiene` / 15 个 `seg_*` **一律从主件删掉**。
3. `_shell_segments.py` 的 `entry`：`"self:seg_x"` ⇒ `"_shell_xxx:check"`。
4. 干跑会断言：**每个块搬完仍逐字连续** · 主件里再没有 `seg_` · 新件 `py_compile` 全过 · 主件 `py_compile` 过。

用法（**先干跑**）：
    backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_tail215_split.py
    backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_tail215_split.py --apply
"""
from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
PROBE = REPO / "tools" / "probe"
SMOKE = PROBE / "_shell_smoke.py"
COMMON = PROBE / "_shell_common.py"
SEGMENTS = PROBE / "_shell_segments.py"
SURVEY = REPO / "tools" / "oneoff" / "_p5c_survey.py"
PY = REPO / "backend" / ".venv" / "Scripts" / "python.exe"

#: (段函数名, 段号, 一句话, 新件的模块名)
SEGS: tuple[tuple[str, str, str, str], ...] = (
    ("seg_session", "⓪", "播种会话票（以在用管理员身份）", "_shell_session"),
    ("seg_dbhygiene", "㉒", "开发库卫生：自检 / 调试脚本的残留不许留", "_shell_dbhygiene"),
    ("seg_nav", "①", "侧栏项数", "_shell_nav"),
    ("seg_ttl", "②", "顶栏标题", "_shell_ttl"),
    ("seg_data", "③", "数据层 NO / PJs（证明真拉到后端）", "_shell_data"),
    ("seg_m03", "④", "m03 结构件（对照 `ui_parity` 口径）", "_shell_m03"),
    ("seg_m01", "⑤", "m01 渲染真数据（⛔ 不是「页面空着但不报错」）", "_shell_m01"),
    ("seg_m04", "⑥", "m04 付款计划：结构件在线 ＋ 筛选条条数 == 数据源", "_shell_m04"),
    ("seg_m04draft", "⑥b", "m04 手动行：点得出草稿行（**不落库**，验完收起）", "_shell_m04draft"),
    ("seg_m05", "⑦", "m05 付款流水与欠款：KPI 墓碑 ＋ 表在线 ＋ 后端欠款可取", "_shell_m05"),
    ("seg_panel", "⑦′", "台账「项目」面板展开/收起 round-trip", "_shell_panel"),
    ("seg_m08", "⑧", "m08 库存单据：全量行数 == 后端 ＋ **真滚轮**滚得动", "_shell_m08"),
    ("seg_m06", "⑨", "m06 过程资料：`procPj` 必须有值", "_shell_m06"),
    ("seg_m07", "⑩", "m07 收发结存与活动大表", "_shell_m07"),
    ("seg_m07bal", "⑩b", "m07 提取表「结余」列 == 后端 `balances`", "_shell_m07bal"),
)

#: 主件里要**删掉**（搬走）的：定义名 → 提取用的正则
EXTRACT: dict[str, str] = {
    "_db_hygiene": r"^def _db_hygiene\(\) -> list\[str\]:\n(?:.*\n)*?(?=^def |\Z)",
    "_goto": r"^def _goto\(page, key: str, timeout: int = 15000\) -> None:\n(?:.*\n)*?(?=^def |\Z)",
    "_session_cookie": r"^def _session_cookie\(\) -> tuple\[str, str\]:\n(?:.*\n)*?(?=^def |\Z)",
}
#: 主件里要**留**的
KEEP: dict[str, str] = {
    "_boot": r"^def _boot\(page\) -> None:\n(?:.*\n)*?(?=^def |\Z)",
    "_run_segment": r"^def _run_segment\(seg, page, errors, self_scope\) -> None:\n(?:.*\n)*?(?=^def |\Z)",
    "main": r"^def main\(\) -> int:\n(?:.*\n)*?(?=^if __name__)",
    "tail": r"^if __name__.*\n(?:.*\n)*\Z",
}

FILE_TMPL = '''"""{tag} · {what}

**为什么单独立一件**（`TAIL-215` 批 2）：主自检件 `_shell_smoke.py` 只留**引导 ＋ 遍历注册表 ＋ 汇总**；
本段的**位置与理由**唯一出处 = `tools/probe/_shell_segments.py`（⛔ 别在本件讨论顺序）。

⚠️ 由 `tools/oneoff/_tail215_split.py` 从 `_shell_smoke.main()` **机械搬迁**而来 —— ⛔ **代码一字未改**。
"""

from __future__ import annotations

{extra}

def check(page, errors) -> None:
{body}'''


def sub1(text: str, old: str, new: str, what: str, bad: list[str]) -> str:
    n = text.count(old)
    if n != 1:
        bad.append(f"{what}：锚点命中 {n} 次（期望 1）")
        return text
    return text.replace(old, new)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="TAIL-215 批 2：15 个段函数移成每段一件")
    ap.add_argument("--apply", action="store_true", help="真写盘（默认只干跑）")
    a = ap.parse_args(argv)

    smoke = SMOKE.read_text(encoding="utf-8")
    common = COMMON.read_text(encoding="utf-8")
    regs = SEGMENTS.read_text(encoding="utf-8")
    survey = SURVEY.read_text(encoding="utf-8")
    bad: list[str] = []

    # ---------- ① 抽块 ----------
    moved: dict[str, str] = {}
    for name, tag, what, modname in SEGS:
        pat = rf"^def {name}\(page, errors\) -> None:\n(?:.*\n)*?(?=^def |\Z)"
        ms = re.findall(pat, smoke, re.M)
        if len(ms) != 1:
            bad.append(f"{tag}({name}) 在 `_shell_smoke.py` 里命中 {len(ms)} 次（期望 1）")
            continue
        moved[tag] = ms[0]
    for key, pat in EXTRACT.items():
        ms = re.findall(pat, smoke, re.M)
        if len(ms) != 1:
            bad.append(f"`{key}` 命中 {len(ms)} 次（期望 1）")
        else:
            moved[f"priv:{key}"] = ms[0]                 # ⚠️ 前缀别用下划线（`_db_hygiene` 会变三个）
    keep: dict[str, str] = {}
    for key, pat in KEEP.items():
        ms = re.findall(pat, smoke, re.M)
        if len(ms) != 1:
            bad.append(f"保留块 `{key}` 命中 {len(ms)} 次（期望 1）")
        else:
            keep[key] = ms[0]

    # ---------- ①b **不丢代码**的两条完备性断言 ----------
    def _nb(t: str) -> list[str]:
        return sorted(x for x in t.splitlines() if x.strip())

    mid = smoke[smoke.index("def _goto("):smoke.index("def seg_session(")]
    removed = "".join(moved[f"priv:{k}"] for k in EXTRACT)
    if _nb(mid) != _nb(removed):
        bad.append("「`def _goto` → 第一个 `seg_`」之间**除了那三个私有件还有别的代码**"
                   " ⇒ 这样重建会**丢东西**（本件只搬它们三个）")
    last_seg = moved[SEGS[-1][1]]
    gap = smoke[smoke.index(last_seg) + len(last_seg):smoke.index("def _boot(")]
    if _nb(gap):
        bad.append(f"最后一个段函数与 `_boot` 之间还有代码 ⇒ 会丢：{_nb(gap)[:3]}")
    if bad:
        print("⛔ 抽取未过 ⇒ **一个字节都不写**：")
        for b in bad:
            print("   ", b)
        return 1

    # ---------- ② 造 15 个新件 ----------
    new_files: dict[pathlib.Path, str] = {}
    for name, tag, what, modname in SEGS:
        body = moved[tag]
        # ⚠️ 抽出来的块**自带 `def` 行** ⇒ 这里把它**去掉**（模板里已经有 `def check(...)` 了；
        #    不去掉 = 两行 `def` 叠着 ⇒ `IndentationError`（实测：首跑就撞上，回滚兜住了）
        body2 = re.sub(rf"^def {re.escape(name)}\(page, errors\) -> None:\n", "", body, count=1)
        if body2 == body:
            bad.append(f"{tag}({name}) 的 `def` 行没被去掉（抽取形态变了？）")
        body = body2
        extra = ""
        if "_goto(page," in body:
            body = body.replace("_goto(page,", "goto(page,")
            extra += "from _shell_common import goto\n"
        if re.search(r"\bBASE\b", body):
            # ⚠️ `BASE` 的唯一出处是 `_shell_segments`（原来是 `_shell_smoke` 的模块级常量）
            extra += "from _shell_segments import BASE\n"
        if name == "seg_session":
            if body.count("_session_cookie(") != 1:
                bad.append("⓪ 里 `_session_cookie(` 不是 1 处")
            body = body.replace("_session_cookie(", "session_cookie(")
            extra += "from _shell_common import session_cookie\n"
        if name == "seg_dbhygiene":
            extra += "\n" + moved["priv:_db_hygiene"].rstrip("\n") + "\n"
        p = PROBE / f"{modname}.py"
        if p.exists():
            bad.append(f"目标件已存在（会覆盖）：{p.name}")
        new_files[p] = FILE_TMPL.format(tag=tag, what=what, extra=extra, body=body)
    if bad:
        print("⛔ 造件未过 ⇒ **一个字节都不写**：")
        for b in bad:
            print("   ", b)
        return 1

    # ---------- ③ 新主件 ----------
    head_end = smoke.index("def _goto(")
    head = smoke[:head_end]
    # ⚠️ `head` 止于 `def _goto(` ⇒ `_goto`/`_session_cookie`/`_db_hygiene` 与 15 个 `seg_*`
    #     **本来就在被丢掉的那一段里**（上面 ①b 两条完备性断言已证明：那一段只有它们三个 ＋ 空格）
    main_new = head + "\n" + keep["_boot"].rstrip("\n") + "\n\n\n" \
        + keep["_run_segment"].rstrip("\n") + "\n\n\n" \
        + keep["main"].rstrip("\n") + "\n\n\n" + keep["tail"]
    # ⚠️ 主件那两条完备性断言**放到 ③b 之后**再判 —— 放在这里会判在"还没删 `self_scope`"的中间态上
    # 头部要补一句：主件现在只剩引导 ＋ 遍历 ＋ 汇总
    main_new = sub1(
        main_new,
        "用法：先起服务，再 `python -u tools/probe/_shell_smoke.py`。\n",
        "⭐ `TAIL-215` 批 2 起：**本件只留「引导 ＋ 遍历注册表 ＋ 汇总」** —— 段的代码在 "
        "`tools/probe/_shell_*.py`（每段一件），段的**位置与理由**在 `tools/probe/_shell_segments.py`。\n"
        "⇒ ⛔ 加一段别再改本件（加一个段件 ＋ 注册表加一行即可）。\n\n"
        "用法：先起服务，再 `python -u tools/probe/_shell_smoke.py`。\n",
        "头部补注", bad)

    # ---- ③b 拆完后**没有 `self:` 段了** ⇒ 把"自解析"那一支整条去掉（⛔ 不留"把段写回主件"的后门）
    main_new = sub1(main_new, "def _run_segment(seg, page, errors, self_scope) -> None:",
                    "def _run_segment(seg, page, errors) -> None:", "`_run_segment` 签名", bad)
    main_new = sub1(
        main_new,
        '    """跑一段 —— `entry` 三种形态：可调用 / `"self:<名>"`（本文件的段函数）/ `"模块:函数"`（外移件）。"""',
        '    """跑一段 —— `entry` 两种形态：**可调用** / `"模块:函数"`（每段一件，见 `_shell_segments.py`）。\n\n'
        '    ⚠️ `TAIL-215` 批 2 起**没有**「段函数放在编排件里」这一支 —— ⛔ 别加回来\n'
        '       （那等于把段代码塞回主件，正是本轮要治的病）。\n'
        '    """', "`_run_segment` 的 docstring", bad)
    main_new = sub1(
        main_new,
        '    elif entry.startswith("self:"):\n'
        '        name = entry[5:]\n'
        '        if name not in self_scope:\n'
        '            raise RuntimeError(\n'
        '                f"⛔ 注册表里的 `{entry}` 在本文件里找不到 —— 段函数改名了却没同批改 "\n'
        '                "`tools/probe/_shell_segments.py`（或反过来）")\n'
        '        fn = self_scope[name]\n',
        "", "`_run_segment` 的 `self:` 分支", bad)
    main_new = sub1(main_new, "        #    · `self_scope` 由**本文件的 `seg_*` 函数名**自动导出（⛔ 不另列一份清单）。\n"
                             "        self_scope = {k: v for k, v in globals().items() if k.startswith(\"seg_\")}\n",
                    "", "`main` 里的 `self_scope`", bad)
    main_new = sub1(main_new, "_run_segment(seg, page, errors, self_scope)",
                    "_run_segment(seg, page, errors)", "`_run_segment` 的调用点", bad)

    # ---------- ④ 改注册表 / `_shell_common` / `_p5c_survey` ----------
    regs_new = regs
    for name, tag, what, modname in SEGS:
        regs_new = sub1(regs_new, f'"self:{name}"', f'"{modname}:check"', f"注册表 {tag}", bad)
    regs_new = sub1(
        regs_new,
        '| `entry` | `"self:<名>"` = 段函数在**编排件**里（`_shell_smoke.py` 的 `seg_*`）；`模块:函数` = 外移件；或直接给可调用 |',
        '| `entry` | `模块:函数`（**每段一件**）或**直接给可调用** —— ⛔ `TAIL-215` 批 2 起'
        '**没有**「段函数放在编排件里」这一支（别把段代码塞回 `_shell_smoke.py`） |',
        "注册表的字段表 `entry` 行", bad)
    regs_new = sub1(regs_new, '    entry: object                               # "self:<名>" / "模块:函数" / 直接给可调用',
                    '    entry: object                               # "模块:函数" / 直接给可调用',
                    "注册表 `Seg.entry` 的行内注释", bad)

    # ---- ④b 主件的两条完备性断言（⚠️ 必须等 ③b 的删改都做完再判）
    if "seg_" in main_new:
        bad.append("新主件里仍出现 `seg_`："
                   + " ｜ ".join(x.strip()[:80] for x in main_new.splitlines() if "seg_" in x)[:400])
    if "_goto(" in main_new or "_session_cookie(" in main_new or "_db_hygiene(" in main_new:
        bad.append("新主件里仍出现已搬走的私有件")
    if '"self:' in regs_new:
        bad.append("注册表里仍有 `self:` 形态的 entry（应全改成 `模块:check`）："
                   + " ｜ ".join(x.strip()[:80] for x in regs_new.splitlines() if '"self:' in x)[:400])

    #: `_session_cookie` 搬进 `_shell_common`（⛔ 名字去掉下划线 —— 它是**对外**的，`_p5c_survey` 也用）
    block = moved["priv:_session_cookie"].replace("def _session_cookie()", "def session_cookie()", 1).rstrip("\n")
    i = common.index('__all__ = [')
    common_new = (common[:i] + block + "\n\n\n"
                  + '__all__ = ["goto", "session_cookie", "wait_db"]\n')
    common_new = sub1(common_new, "本件只放**与具体页面无关**的两件：\n  · `goto()`    —— 切页（等\"这一屏画完\"）\n  · `wait_db()` —— 等**库里的结果**出现（写动作的判据本来就是库里的行）",
                      "本件只放**与具体页面无关**的三件：\n"
                      "  · `goto()`          —— 切页（等\"这一屏画完\"）\n"
                      "  · `wait_db()`       —— 等**库里的结果**出现（写动作的判据本来就是库里的行）\n"
                      "  · `session_cookie()` —— 造一张「以**在用管理员**身份登录」的会话票\n"
                      "    （⭐ `TAIL-215` 批 2 从 `_shell_smoke.py` 搬来 —— ⓪ 段与 `tools/oneoff/_p5c_survey.py` 共用）",
                      "`_shell_common` 的件说明", bad)
    survey_new = sub1(survey, "    from _shell_smoke import _session_cookie",
                      "    from _shell_common import session_cookie", "`_p5c_survey` 的 import", bad)
    survey_new = sub1(survey_new, "ck, val = _session_cookie()", "ck, val = session_cookie()",
                      "`_p5c_survey` 的调用", bad)

    if bad:
        print("⛔ 组装未过 ⇒ **一个字节都不写**：")
        for b in bad:
            print("   ", b)
        return 1

    # ---------- ⑤ 报告 ----------
    print(f"主件：{len(smoke.splitlines())} → {len(main_new.splitlines())} 行")
    for p, t in sorted(new_files.items()):
        print(f"  新件 {p.name:28s} {len(t.splitlines()):4d} 行")
    print(f"  改件 {COMMON.name} ＋ {SEGMENTS.name} ＋ {SURVEY.name}")

    if not a.apply:
        print("\n（干跑 —— 要真写盘加 --apply）")
        return 0

    # ---------- ⑥ 写盘（先全部 `py_compile`，任一件不过 ⇒ 回滚）----------
    written: list[pathlib.Path] = []
    backups = {p: p.read_bytes() for p in (SMOKE, COMMON, SEGMENTS, SURVEY)}
    try:
        for p, t in new_files.items():
            p.write_bytes(t.encode("utf-8"))
            written.append(p)
        SMOKE.write_bytes(main_new.encode("utf-8"))
        COMMON.write_bytes(common_new.encode("utf-8"))
        SEGMENTS.write_bytes(regs_new.encode("utf-8"))
        SURVEY.write_bytes(survey_new.encode("utf-8"))
        r = subprocess.run([str(PY), "-X", "utf8", "-m", "py_compile", *[str(p) for p in written],
                            str(SMOKE), str(COMMON), str(SEGMENTS), str(SURVEY)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            print("⛔ `py_compile` 不过 ⇒ **回滚**：")
            print((r.stdout or "") + (r.stderr or ""))
            raise RuntimeError("compile failed")
    except Exception:                                     # noqa: BLE001
        for p, b in backups.items():
            p.write_bytes(b)
        for p in written:
            p.unlink(missing_ok=True)
        print("⛔ 已回滚（⛔ 没留半成品）")
        return 1
    print(f"\n✅ 已写盘：新件 {len(written)} 个 · 主件 {len(main_new.splitlines())} 行 · `py_compile` 全过")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
