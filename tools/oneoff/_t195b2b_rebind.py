"""`TAIL-195` 批 2b（环① 案②）· **把业务包对导出层的直接 import 改成"按名取"**（一次性留痕）。

做两件事（逐文件、逐行、带命中数断言；⛔ 不动行尾）：
  1. `from app.report_export import <件> as X` ⇒ `from app import export_registry as EXP` ＋ `<indent>X = EXP.get("<名>")`
     （**保留原缩进** —— 这些 import 都在函数体内）；
  2. `mod05_flow/debt_export.py` 那处**模块级**用法 ⇒ 顶层只留 `export_registry`，
     真正取件挪到用它的函数里（模块级取件会在"注册表还没填"时炸）。

⚠️ 只改**这 12 处**：改完由 `tests/test_layering.py` **规则 B**（放行名单清空）每轮守着。

用法：python tools/oneoff/_t195b2b_rebind.py --dry-run / --write
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "backend" / "app"

#: 文件名 → 要被替换掉的 `import` 行（正则）→ (替换成两行的形态)
_RE_MOD_AS_X = re.compile(r"^(?P<i>\s*)from app\.report_export import (?P<mod>[a-z_]+) as (?P<alias>\w+)$")
_RE_JC = re.compile(r"^(?P<i>\s*)from app\.report_export import (?P<mod>jc_export)$")
_RE_SAVE = re.compile(r"^from app\.report_export\.save import save_workbook$")
_RE_SAVE_CALL = re.compile(r"^(?P<i>\s*)out = save_workbook\(")

#: 件名 → 注册名（装配层的绑定表见 `app/export_bindings.py`；⛔ 两处必须一致）
_NAME_OF = {"pj_export": "pj", "nt_export": "nt", "pl_export": "pl",
            "fl_export": "fl", "jc_export": "jc", "service": "service", "save": "save"}

TARGETS = [
    APP / "mod01_projects" / "router.py",
    APP / "mod03_notice" / "notice_api_router.py",
    APP / "mod04_plan" / "router.py",
    APP / "mod05_flow" / "debt_export.py",
    APP / "mod05_flow" / "router.py",
    APP / "mod06_proc" / "router.py",
    APP / "mod07_setl" / "api.py",
    APP / "mod08_inv" / "router.py",
    APP / "mod11_jc" / "service.py",
]


def _rewrite(path: Path) -> tuple[list[str], int]:
    """→ (新行, 改动数)。逐行扫，命中就换成两行（**保留缩进**）。"""
    raw = path.read_bytes().decode("utf-8")
    newline = "\r\n" if "\r\n" in raw else "\n"
    out: list[str] = []
    n = 0
    for line in raw.split(newline):
        m = _RE_MOD_AS_X.match(line)
        if m:
            name = _NAME_OF[m.group("mod")]
            out += [f'{m.group("i")}from app import export_registry as EXP',
                    f'{m.group("i")}{m.group("alias")} = EXP.get("{name}")']
            n += 1
            continue
        m = _RE_JC.match(line)
        if m:
            out += [f'{m.group("i")}from app import export_registry as EXP',
                    f'{m.group("i")}jc_export = EXP.get("jc")']
            n += 1
            continue
        if _RE_SAVE.match(line):
            out.append("from app import export_registry as EXP   # ⭐ 包间只按名取（表见 `app/export_bindings.py`）")
            n += 1
            continue
        m = _RE_SAVE_CALL.match(line)
        if m:
            out += [f'{m.group("i")}save_workbook = EXP.get("save").save_workbook', line]
            n += 1
            continue
        out.append(line)
    return out, n


def main() -> int:
    write = "--write" in sys.argv
    per: list[tuple[Path, int]] = []
    for p in TARGETS:
        _, n = _rewrite(p)
        per.append((p, n))
    total = sum(n for _, n in per)
    print(f"命中：{len(per)} 个文件 · 共 {total} 处")
    for p, n in per:
        print(f"    {p.relative_to(ROOT).as_posix()}  ×{n}")
    if total == 0:
        print("⛔ 一处都没命中 —— 写法变了？停手。")
        return 1
    if not write:
        print("\n（dry-run：未动任何文件）")
        return 0
    for p, n in per:
        assert n > 0, f"{p}：0 命中（停手）"
        new, n2 = _rewrite(p)
        assert n2 == n
        raw = p.read_bytes().decode("utf-8")
        newline = "\r\n" if "\r\n" in raw else "\n"
        p.write_bytes(newline.join(new).encode("utf-8"))
        assert "app.report_export" not in p.read_bytes().decode("utf-8"), f"{p}：仍有残留"
    print("✅ 已改 9 个文件（12 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
