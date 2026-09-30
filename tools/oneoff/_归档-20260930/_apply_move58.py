#!/usr/bin/env python
"""`TAIL-58`：`tools/` 分目录 —— **搬运 ＋ 同批改锚点**（一次脚本做完，⛔ 不留半截）。

四组：
  audit/   尺子＋基础设施（收尾必跑的那批 ＋ `shell_source` ＋ `mut_cover`）
  mut/     `_mut_*.py`（反向灵敏度）
  probe/   真机 / 端到端探针（`_e2e_*` · `_shell_*` · `i8_*` · render/print smoke…）
  oneoff/  一次性 / 留痕（`_apply_*` · `_doc_*` · `_acc_add_*` · `_fix_*`）

同批改的锚点：
  ① mut/ 里 30+ 处 `from shell_source import` ⇒ 先把 `tools/audit` 插进 `sys.path`（ bare import 保持不变）；
  ② oneoff 里 5 处 `from acc_report / audit_common import` ⇒ 同上；
  ③ `tests/shell_src.py` 的 `from tools.shell_source import` ⇒ `from tools.audit.shell_source import`；
  ④ **活文档**（MEMORY / 执行情况 / ops 现行口径）里的 `tools/<件名>` ⇒ 新路径（⛔ 归档件与 journal **不改** —— 那是留痕）。
⛔ 判据：全站 `compile()` ＋ 13 把尺子（新路径）＋ 4 个变异件 ＋ pytest 全套。
"""
from __future__ import annotations

import pathlib
import re
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"D:\dev\mtrl-workbench")
TOOLS = ROOT / "tools"

AUDIT = {"acc_report", "asset_audit", "audit_common", "audit_drift", "audit_meta",
         "chain_audit", "claim_audit", "cover_gap", "doc_audit", "mut_cover",
         "prg_form_audit", "shell_source", "shell_verify", "sticky_probe",
         "syntax_audit", "ui_parity", "wiring_audit"}


def group_of(name: str) -> str:
    stem = name[:-3] if name.endswith(".py") else name
    if stem in AUDIT:
        return "audit"
    if name.startswith("_mut_"):
        return "mut"
    if (name.startswith(("i8_", "m3_", "print_bills", "render_", "_audit_face", "_boot_time",
                         "_diag_", "_e2e_", "_m14_", "_probe_", "_shell_", "_run_"))
            or name.endswith("_smoke.py")):
        return "probe"
    return "oneoff"          # _apply_* / _doc_* / _acc_add_* / _fix_*


def main() -> int:
    moved: dict[str, str] = {}                     # 旧名 → 新相对路径（tools/ 下）
    for p in sorted(TOOLS.glob("*.py")):
        g = group_of(p.name)
        d = TOOLS / g
        d.mkdir(exist_ok=True)
        new = d / p.name
        shutil.move(str(p), str(new))
        moved[p.name] = f"tools/{g}/{p.name}"
    print(f"搬运 {len(moved)} 件：" +
          " · ".join(f"{g}={sum(1 for v in moved.values() if g in v)}" for g in ("audit", "mut", "probe", "oneoff")))

    # ① mut/：`from shell_source import` 前插 sys.path 引导
    n = 0
    for p in sorted((TOOLS / "mut").glob("_mut_*.py")):
        t = p.read_text(encoding="utf-8", errors="replace")
        if "from shell_source import" not in t or "TAIL-58 分目录" in t:
            continue
        L = t.replace("\r\n", "\n").split("\n")
        out, done = [], False
        has_pl = any(l.strip() == "import pathlib" for l in L)
        for l in L:
            if l.startswith("from shell_source import") and not done:
                if not has_pl:
                    out.append("import pathlib")
                out.append("sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / \"audit\"))"
                           "  # ⭐ `TAIL-58` 分目录：shell_source 在 audit/")
                done = True
            out.append(l)
        p.write_text("\n".join(out), encoding="utf-8", newline="")
        n += 1
    print(f"① mut/ 引导补丁：{n} 件")

    # ② oneoff/：acc_report / audit_common 同样处理
    n = 0
    for p in sorted((TOOLS / "oneoff").glob("*.py")):
        t = p.read_text(encoding="utf-8", errors="replace")
        if "TAIL-58 分目录" in t:
            continue
        L = t.replace("\r\n", "\n").split("\n")
        hit = [k for k, l in enumerate(L)
               if re.match(r"^from (acc_report|audit_common) import", l)]
        if not hit:
            continue
        out, done = [], False
        has_pl = any(l.strip() == "import pathlib" for l in L)
        has_sys = any(re.match(r"^import sys\b", l) for l in L)
        for l in L:
            if not done and re.match(r"^from (acc_report|audit_common) import", l):
                if not has_pl:
                    out.append("import pathlib")
                if not has_sys:
                    out.append("import sys")
                out.append("sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / \"audit\"))"
                           "  # ⭐ `TAIL-58` 分目录")
                done = True
            out.append(l)
        p.write_text("\n".join(out), encoding="utf-8", newline="")
        n += 1
    print(f"② oneoff/ 引导补丁：{n} 件")

    # ③ tests/shell_src.py
    p = ROOT / "backend" / "tests" / "shell_src.py"
    t = p.read_text(encoding="utf-8")
    if "tools.shell_source import" in t:
        p.write_text(t.replace("tools.shell_source import", "tools.audit.shell_source import"),
                     encoding="utf-8", newline="")
        print("③ tests/shell_src.py ⇒ tools.audit.shell_source")

    # ④ 活文档里的路径（映射表替换；⛔ 归档件 / journal / artifacts 不动）
    name_map = {k: v for k, v in moved.items()}
    doc_targets = ([ROOT / "README.md", ROOT / ".workbuddy" / "memory" / "MEMORY.md",
                    ROOT / ".workbuddy" / "plans" / "执行情况-主文档.md",
                    ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"]
                   + list((ROOT / "ops").glob("*.md"))
                   + list((ROOT / "backend" / "tests").glob("*.py"))
                   + list((ROOT / "backend" / "app" / "web" / "shell").glob("*.js")))
    total = 0
    for p in doc_targets:
        t = p.read_text(encoding="utf-8", errors="replace")
        orig = t
        for old, new_rel in name_map.items():
            t = t.replace(f"tools/{old}", f"{new_rel}").replace(f"tools\\{old}", new_rel.replace("/", "\\"))
        if t != orig:
            p.write_text(t, encoding="utf-8", newline="")
            total += 1
            print(f"④ 路径引用更新：{p.relative_to(ROOT)}")
    print(f"④ 更新 {total} 份文件的路径引用")
    print("完成 —— 下一步：compile 全站 ＋ 全闸门（新路径）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
