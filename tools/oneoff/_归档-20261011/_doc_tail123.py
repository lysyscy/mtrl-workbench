#!/usr/bin/env python
"""`TAIL-123`：把「壳呈现判据」登记进交付面契约（**一次性的契约面改动脚本** · 2026-09-28）。

**为什么有它**（本仓规矩：动交付面 `.json` **绝不文本替换**）：
  `PRD/验收/验收基线.json` 是**只读快照式**的机读基线（工程内不留副本）⇒
  ① 必须先 `json.loads` → 改 dict → `json.dumps(indent=1, ensure_ascii=False)`；
  ② 改前先做 **round-trip 逐字节比对**（证明"我这份 dumps 参数就是它原来的排版"）；
  ③ 换行 = **CRLF**、末尾**一个 CRLF**（实测格式，见 `MEMORY.md` 高危坑 #1）。

**它做什么**（三件）：
  1. `验收基线.json`：新增一条用例 **`ACC-UI-SHELL-001`「界面呈现与提示（按《前端设计守则》的机器判据）」**
     ＋ **36 个判据点**（逐一对应 `backend/tests/test_ux_*.py` 9 件里**已经存在**的测试 —— ⛔ 不是新写判据，
     是给"已经挂了但四态看不见"的判据**登记**，见 `TAIL-123` 的口径）；
  2. `backend/tests/test_ux_*.py` 9 件：把第 N 个 `@acc()` 换成 `@acc("ACC-UI-SHELL-001", "001-NN")`
     （**顺序对齐**，脚本内断言"该件的 `@acc()` 个数 == 映射个数"且"没有任何已绑定装饰器"）；
  3. 复核：重新 `json.loads` ⇒ 打印判据点总数（应 = 原 567 ＋ 36 = 603）。

用法（工程根）：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_doc_tail123.py`
  `--check`  只做 round-trip 与计数，**不写任何文件**
  `--write`  真的写（交付面先备份到 `.workbuddy/backups/交付面-<日期>-<时分>/`）
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
BASELINE = pathlib.Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用\PRD\验收\验收基线.json")
TESTS = REPO / "backend" / "tests"

CASE = "ACC-UI-SHELL-001"

#: 判据 → `(id, kind, claim, cover)`。⭐ 顺序 = 在各测试件里**出现的顺序**（绑定脚本照这个顺序改装饰器）。
POINTS: tuple[tuple[str, str, str, str], ...] = (
    # ── `test_ux_errors.py`（报错人话化 · `TAIL-117` 批次 1）
    ("001-01", "outcome", "造错的口只有一处：全壳 `new Error(` 只许出现在取数出口的人话函数里", "守则 §3.2"),
    ("001-02", "outcome", "五个取数失败点都走人话出口；原始串（方法 / 全路径 / 状态码）只进技术明细、不上屏", "守则 §3.7"),
    ("001-03", "outcome", "任何提示条那一行不许出现内部串（`HTTP …` / `/api/…`）", "守则 §3.1"),
    ("001-04", "must-report", "首屏取数失败：人话在外 ＋ 原始串折进「技术明细」＋ 有下一步", "守则 §3.7"),
    # ── `test_ux_feedback.py`（操作反馈）
    ("001-05", "outcome", "项目候选里「小微壳」默认置底；归档项仍在最底", "守则 §2.7"),
    ("001-06", "outcome", "抓取结果一律用弹窗呈现（不再只给一条提示条）", "守则 §2.2"),
    ("001-07", "outcome", "点导出即有反馈（不让人以为没点住）", "守则 §2.2"),
    ("001-08", "outcome", "库存单据导出走最近一次抓取的缓存，不因导出再碰 i8", "守则 §4.2"),
    ("001-09", "outcome", "源文件缓存：存取往返一致；未命中如实报出", "守则 §4.2"),
    ("001-10", "outcome", "接口清单表已删：壳与原型都没有（⛔ 不许回来）", "守则 §3.1"),
    # ── `test_ux_text.py`（上屏文案）
    ("001-11", "outcome", "上屏文案里不许出现内部编号 / 开发话术（整串墓碑，含卡头按钮与提示）", "守则 §3.1"),
    ("001-12", "outcome", "导入页域自报文案必须渲染成加粗（⛔ 不许把 `**` 原样给用户看）", "守则 §3.1"),
    # ── `test_ux_brief.py`（长文案与优先级）
    ("001-13", "outcome", "长文案整治删掉的实现话术整串不许回来", "守则 §3.1"),
    ("001-14", "outcome", "过长度关只能靠压短或折叠，⛔ 不许靠删光说明", "守则 §5.8"),
    ("001-15", "outcome", "真机 ㉖ 的长度判据本身在位（阈值 ＋ 那一段）", "守则 §3.4"),
    ("001-16", "outcome", "域自报文案（note / keep_note / rule_note / field_list_hint）渲染后 ≤ 200 字", "守则 §3.4"),
    # ── `test_ux_states.py`（页级四态）
    ("001-17", "outcome", "页级状态只有一处出口（正在读取 / 没能取到 / 就绪）", "守则 §2.1"),
    ("001-18", "outcome", "渲染前必须先过页级状态（数据没回来不画空表）", "守则 §4.2"),
    ("001-19", "outcome", "状态页必须给下一步（正在读取 / 没能取到 ＋ 重试）", "守则 §2.2"),
    ("001-20", "outcome", "空态只有一处出口，且要说清「为什么空 ＋ 下一步点哪儿」", "守则 §2.1"),
    ("001-21", "outcome", "取数一律过「连不上」的人话包装（⛔ 漏一处就漏出浏览器的英文原文）", "守则 §3.7"),
    ("001-22", "outcome", "逐路容错要按路记名（哪一路坏了说得出来）", "守则 §2.1"),
    ("001-23", "outcome", "真机 ㉗ 的判据还在（加载 / 错误 / 点重试真恢复）", "守则 §5.4"),
    # ── `test_ux_colors.py`（颜色语义）
    ("001-24", "outcome", "颜色语义错位（「还没发生的事」挂成功绿 / 纯说明挂警示黄）不许回来", "守则 §4.5"),
    ("001-25", "outcome", "壳不许替域挑颜色（域自报文案一律普通提示）", "守则 §4.5"),
    ("001-26", "outcome", "颜色判法本身必须留在守则里（人走了判法还在）", "守则 §4.5"),
    # ── `test_ux_buttons.py`（相似元素）
    ("001-27", "outcome", "语义相反的一对按钮不许同款（危险侧必须带危险色）", "守则 §4.4"),
    ("001-28", "outcome", "危险动作要让用户知道有退路（悬停写明怎么放回来）", "守则 §2.4"),
    # ── `test_ux_numbers.py`（数字口径）
    ("001-29", "outcome", "金额大数一律带单位与口径（走统一出口）", "守则 §2.3"),
    ("001-30", "outcome", "取不到的金额不许冒充 0（须与真 0 区分）", "守则 §4.2"),
    ("001-31", "outcome", "欠款大数要写清「什么时候的数」", "守则 §2.3"),
    ("001-32", "outcome", "验收术语（如「容差 0」）不许留在界面上", "守则 §3.3"),
    # ── `test_ux_deadcode.py`（残骸与留痕）
    ("001-33", "outcome", "零引用、从不上屏的接口清单表不许回来", "守则 §3.1"),
    ("001-34", "outcome", "过期实现话术墓碑（改掉的整串不许回来）", "守则 §3.1"),
    ("001-35", "outcome", "有意保留的留痕不许被顺手清掉（原型 / 壳同进同退）", "守则 §5.8"),
    ("001-36", "outcome", "判据的观测点必须是**会上屏**的东西（删掉的那张表不是判据要的）", "守则 §0"),
)

#: 测试件 → 该件里 `@acc()` 的**顺序**映射（断言个数一致）
BINDINGS: dict[str, list[str]] = {
    "test_ux_errors.py": ["001-01", "001-02", "001-03", "001-04"],
    "test_ux_feedback.py": ["001-05", "001-06", "001-07", "001-08", "001-09", "001-10"],
    "test_ux_text.py": ["001-11", "001-12"],
    "test_ux_brief.py": ["001-13", "001-14", "001-15", "001-16"],
    "test_ux_states.py": ["001-17", "001-18", "001-19", "001-20", "001-21", "001-22", "001-23"],
    "test_ux_colors.py": ["001-24", "001-25", "001-26"],
    "test_ux_buttons.py": ["001-27", "001-28"],
    "test_ux_numbers.py": ["001-29", "001-30", "001-31", "001-32"],
    "test_ux_deadcode.py": ["001-33", "001-34", "001-35", "001-36"],
}


def _dump(obj: dict) -> str:
    """基线实测格式（⭐ 2026-09-28 用 **round-trip 逐字节比对**实测，⛔ 不凭记忆）：

    `indent=2` · `ensure_ascii=False` · **每一行都是 CRLF**（CR 数 == LF 数）· 末尾**一个** CRLF。
    ⚠️ 订正：`MEMORY.md` §四 原写「`indent=1`」—— 实测**是 2**（写 1 会让 round-trip 当场不等）。
    """
    return json.dumps(obj, indent=2, ensure_ascii=False).replace("\n", "\r\n") + "\r\n"


def new_case() -> dict:
    return {
        "req": "—",
        "module": "跨域（前端壳 · 不占模块号）",
        "cover": ["守则 §2.1", "守则 §2.3", "守则 §3.1", "守则 §4.2", "守则 §4.5"],
        "source": "守则驱动的**既有**机器判据（离线 9 件：`backend/tests/test_ux_errors.py` · "
                  "`test_ux_feedback.py` · `test_ux_text.py` · `test_ux_brief.py` · `test_ux_states.py` · "
                  "`test_ux_colors.py` · `test_ux_buttons.py` · `test_ux_numbers.py` · `test_ux_deadcode.py`）"
                  "＋ 真机段 ㉔/㉕/㉖/㉗/㉙（`tools/probe/_shell_*`）",
        "criterion": "界面上的提示与呈现必须「说人话 · 状态真实 · 不误导」（《前端设计守则》）："
                     "报错转人话并给下一步、加载/空/错各有表达、颜色只承担语义、数字带单位与时点、"
                     "文案不泄内部编号与开发话术。",
        "points": [
            {"id": pid, "kind": kind, "claim": claim, "cover": cover}
            for pid, kind, claim, cover in POINTS
        ],
    }


def patch_tests(write: bool) -> list[str]:
    """把每个件里的 `@acc()` 按顺序换成带判据点的装饰器。→ 报告行。"""
    out: list[str] = []
    for name, ids in BINDINGS.items():
        path = TESTS / name
        lines = path.read_text(encoding="utf-8").split("\n")
        bare = sum(1 for ln in lines if ln.strip() == "@acc()")
        anyacc = sum(1 for ln in lines if ln.strip().startswith("@acc("))
        assert bare == len(ids), f"{name}：`@acc()` 有 {bare} 个，映射给了 {len(ids)} 个 ⇒ 别改"
        assert anyacc == bare, f"{name}：还有已绑定的 `@acc(...)` ⇒ 顺序映射不可靠，别改"
        i = 0
        for n, ln in enumerate(lines):
            if ln.strip() != "@acc()":
                continue
            lines[n] = ln.replace("@acc()", f'@acc("{CASE}", "{ids[i]}")')
            i += 1
        if write:
            path.write_text("\n".join(lines), encoding="utf-8")
        out.append(f"  {name:<26} @acc() × {len(ids)} ⇒ 已绑定 001-01..{ids[-1][-5:]}（{ids[0]}…{ids[-1]}）")
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    # ⚠️ 必须 `newline=""`：默认（universal newlines）会把 `\r\n` 折成 `\n`
    #    ⇒ round-trip 比对**永远不等**（实测：原文件全是 CRLF，CR=LF=4310）—— 别被这个假差异骗住。
    raw = BASELINE.read_text(encoding="utf-8", newline="")
    obj = json.loads(raw)

    rt = _dump(obj)
    same = rt == raw
    print(f"round-trip 逐字节比对：{'✅ 一致' if same else '⛔ 不一致（⛔ 别写！先用别的方式确认格式）'}")
    if not same:
        # 给出差异线索（不打印全文）
        for i, (a, b) in enumerate(zip(raw, rt)):
            if a != b:
                print(f"   首个差异 @{i}：原 {a!r} vs 我的 {b!r}")
                break
        print(f"   长度：原 {len(raw)} vs 我的 {len(rt)}")
        return 1

    cases = obj["cases"]
    before = sum(len(v.get("points") or []) for v in cases.values())
    print(f"现有用例 {len(cases)} 条 · 判据点合计 {before}")
    if CASE in cases:
        print(f"⚠️ `{CASE}` 已在基线里 ⇒ 本条脚本已跑过（本次不重复插入）")
        added = 0
    else:
        cases[CASE] = new_case()
        added = len(POINTS)
        print(f"＋ 新增用例 `{CASE}`（{added} 个判据点）")

    print("\n绑定（9 件）：")
    print("\n".join(patch_tests(args.write)))

    if args.write and added:
        BASELINE.write_text(_dump(obj), encoding="utf-8", newline="")
        back = json.loads(BASELINE.read_text(encoding="utf-8"))
        after = sum(len(v.get("points") or []) for v in back["cases"].values())
        print(f"\n✅ 已写回：判据点合计 {before} ⇒ **{after}**（用例 {len(back['cases'])} 条）")
        print(f"   落点：{BASELINE}")
    elif not args.write:
        print(f"\n（`--check` 模式：⛔ 未写任何文件；写的话判据点会变成 {before + added}）")
    elif added == 0:
        print("\n（基线已是最新 ⇒ 只跑了绑定那半）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
