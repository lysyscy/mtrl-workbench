"""收口闸门一把跑：`CMDS` 里的每一把逐个跑、只打印"该读的那几行"，rc≠0 的列进 `BAD`。
⚠️ **条数别抄在这里**（⛔ 抄了必漂，`tools/README.md` 纪律）—— 清单的**唯一出处 = 本件 `CMDS`**。

⭐ 2026-10-01（`TAIL-205`）起**末尾多一步**：**守尺子的变异自证**（`tools/oneoff/_run_muts.py` ·
  ⛔ 支数看那件自己的输出）—— `tools/mut/**` 原先不在任何闸门里
  ⇒ "加了反向灵敏度却没人跑" ⇒ 一天抓到 4 例假绿。
⭐ 2026-10-05（`TAIL-236` 批 2）：`CMDS` 里也多了 `refs_query.py --selftest`
  —— 同族：命令自身的自测不在闸门里 ⇒ 它的检索逻辑坏了没人知道。

**为什么单独落成文件**：2026-09-29 实测 —— 这套命令用 `python -c "…\\nfor …"` 的**内联多行**写法
在 PowerShell 里**反复被吃掉换行**（`unexpected character after line continuation character` ✗）。
⇒ 凡是"反复要跑的一串命令"，落成脚本；⛔ 别在命令行里拼多行 Python。

跑法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_run_rulers.py`
      `… --all`   #: 连 pytest 一起跑（默认只跑尺子 —— 没动代码时不必）
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PY = str(ROOT / "backend" / ".venv" / "Scripts" / "python.exe")

KEEP = ("必须修", "结论：", "_smoke", "_links", "_ids", "_doccheck", "台账一致", "逐行一致",
        "判据点合计", "幽灵", "[T6]", "[T10]", "[T13]", "[T20]",
        "自测 ")          # ⭐ `refs_query --selftest` 的"自测 N/N"那一行（2026-10-05 加）
# ⚠️ 「结论**：**」带冒号：光靠 `结论` 会把**文件名里带"结论"两字**的件名也抓进来
#    （实测 `refs` 那一行后面跟了两行 `ops/…-实测结论.md` ⇒ 闸门输出里全是噪声）。

CMDS: list[tuple[str, list[str]]] = [
    ("tools/audit/doc_audit.py", ["--ui"]),
    ("tools/audit/audit_drift.py", []),
    ("tools/audit/audit_meta.py", []),
    # ⭐ 2026-10-05（`/retro` 候选④）：`audit_work` 此前**不在闸门里** ⇒ 它的输出没人看
    #   （`T14`/`T15`/`T20` 三条黄档 · 单跑过是 0/0）⇒ 「工具上了没人跑」的第一例。
    ("tools/audit/audit_work.py", []),
    ("tools/audit/syntax_audit.py", []),
    ("tools/audit/ui_parity.py", []),
    ("tools/audit/wiring_audit.py", []),
    ("tools/audit/chain_audit.py", []),
    ("tools/audit/asset_audit.py", []),
    ("tools/audit/claim_audit.py", []),
    ("tools/audit/cover_gap.py", []),
    ("tools/audit/prg_form_audit.py", []),
    ("tools/audit/shell_verify.py", []),
    ("tools/audit/sticky_probe.py", []),
    ("tools/audit/mut_cover.py", ["--check"]),
    ("tools/audit/acc_report.py", []),
    # ⭐ 2026-10-05（`TAIL-236` 批 2 · `/code-review` 指出）：`refs` 命令**自身的自测**
    #   原先不在任何闸门里 ⇒ "命令的检索逻辑坏了没人知道"（同 `tools/mut/**` 那族假绿）。
    #   ⛔ 只进收工闸门、不进 `pre-commit`（那个只跑便宜子集）。
    ("tools/audit/refs_query.py", ["--selftest"]),
    ("tools/probe/_audit_face.py", []),
]


def main() -> int:
    with_pytest = "--all" in sys.argv
    bad: list[str] = []
    for rel, args in CMDS:
        p = subprocess.run([PY, "-X", "utf8", str(ROOT / rel)] + args, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", cwd=str(ROOT))
        ls = [x for x in (p.stdout or "").strip().splitlines() if x.strip()]
        keep = [x for x in ls if any(k in x for k in KEEP)]
        print("%-34s rc=%d  %s" % (rel, p.returncode, " || ".join(keep[:3])[:175]))
        if p.returncode:
            bad.append(rel)
    # ⭐⭐ 2026-10-01（`TAIL-205`）：**守尺子的变异自证** —— `tools/mut/**` 原先**不在任何闸门里**
    #    ⇒ "加了反向灵敏度却没人跑" ⇒ 2026-10-01 一天抓到 4 例"靶烂掉 / 判法烂掉"（假绿）。
    #    这几支的**靶是尺子自己**（`doc_audit` 的 T1–T19 / T4 锚点 / claim / 四检 / T12 / T14T15 / T20），
    #    它们烂掉 = **一整片守卫静默失效** ⇒ **每次收工都跑**（8 支 · 实测约 33 秒 · 完全值）。
    p = subprocess.run([PY, "-X", "utf8", str(ROOT / "tools" / "oneoff" / "_run_muts.py")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(ROOT))
    keep2 = [x for x in (p.stdout or "").strip().splitlines() if x.strip()][-1:]
    print("%-34s rc=%d  %s" % ("守尺子的变异自证(_run_muts)", p.returncode, " || ".join(keep2)[:175]))
    if p.returncode:
        bad.append("守尺子的变异自证(_run_muts.py)")
    if with_pytest:
        env = {"ACC_RESULTS_PATH": str(ROOT / "artifacts" / "acc_results.json"),
               "PLAYWRIGHT_BROWSERS_PATH": r"C:\ProgramData\ms-playwright",
               "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
        import os
        e = dict(os.environ, **env)
        p = subprocess.run([PY, "-m", "pytest", "-q", "tests/", "-p", "no:cacheprovider", "--tb=line"],
                           cwd=str(ROOT / "backend"), env=e, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        tail = [x for x in (p.stdout or "").strip().splitlines() if x.strip()][-2:]
        print("%-34s rc=%d  %s" % ("pytest", p.returncode, " || ".join(tail)[:175]))
        if p.returncode:
            bad.append("pytest")
    print("BAD:", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
