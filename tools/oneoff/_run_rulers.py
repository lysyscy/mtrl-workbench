"""按实际影响运行登记检查；提交、新删件与旧dirty不自动触发全量。

--start <scratch基点> 保存开工字节，--since <基点> 只计新增影响；快照不是通过证明。
--explain 显示选择，--paths <实际差异...> 明确本轮范围并打印未验差异。
默认/--related/--all均按使用者选择；--full为明确请求全部检查和pytest。
判据自证按被改机制在隔离副本运行，不随完整pytest附带全部KEY。
范围与流程主人为 ops/agents/issue-tracker.md §四，CMDS是检查登记的唯一出口。
"""
from __future__ import annotations

import pathlib
import json
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
PY = str(ROOT / "backend" / ".venv" / "Scripts" / "python.exe")
sys.path.insert(0, str(ROOT / "tools" / "oneoff"))
import _pytestscope as _scope      # noqa: E402
import _gatescope as _gate         # noqa: E402

KEEP = ("必须修", "结论：", "_smoke", "_links", "_ids", "_doccheck", "台账一致", "逐行一致",
        "判据点合计", "幽灵", "[T6]", "[T10]", "[T13]", "[T20]",
        "自测 ")          # ⭐ `refs_query --selftest` 的"自测 N/N"那一行（2026-10-05 加）

CMDS: list[tuple[str, list[str]]] = [
    ("tools/audit/doc_audit.py", ["--ui"]),
    ("tools/audit/audit_drift.py", []),
    ("tools/audit/audit_meta.py", []),
    ("tools/audit/audit_work.py", []),
    ("tools/audit/syntax_audit.py", []),
    ("tools/audit/bytes_guard.py", []),
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
    ("tools/probe/_audit_face.py", []),
]

# 工具自测另行登记；显式完整检查也仅按工具及依赖变化选中。
SELFTESTS: list[tuple[str, list[str]]] = [
    ("tools/audit/refs_query.py", ["--selftest"]),
    ("tools/oneoff/_doc_downgrade.py", ["--selftest"]),
    ("tools/oneoff/_gatescope.py", ["--selftest"]),
]

def _main() -> int:
    import argparse
    import _impactscope as impact
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', type=pathlib.Path)
    parser.add_argument('--since', type=pathlib.Path)
    parser.add_argument('--explain', action='store_true')
    parser.add_argument('--paths', nargs='+')
    parser.add_argument('--related', action='store_true')
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--full', action='store_true')
    args = parser.parse_args()
    if args.start:
        impact.snapshot(args.start)
        return 0
    try:
        if _gate.commands(ROOT) != CMDS or _gate.commands(ROOT, 'SELFTESTS') != SELFTESTS:
            raise ValueError('执行清单与CMDS定义不一致')
        delta = impact.since_snapshot(args.since) if args.since else impact.git_changes()
        if args.paths:
            unknown_paths = set(args.paths) - set(delta)
            if unknown_paths:
                raise ValueError('指定路径不在实际差异中：'+str(sorted(unknown_paths)))
            print('显式本轮范围；其他差异未验：', sorted(set(delta)-set(args.paths)))
            delta = {n: delta[n] for n in args.paths}
        return impact.run_selected(delta, CMDS + SELFTESTS, PY, explain=args.explain, force_full=args.full)
    except (OSError, ValueError, KeyError, TypeError, SyntaxError, subprocess.SubprocessError) as exc:
        print('待查影响，不能报告通过：', type(exc).__name__, str(exc))
        return 2


def main() -> int:
    """入口任何失败或中断都销毁旧证明，包括参数和清单自检提前失败。"""
    try:
        rc = _main()
    except BaseException:
        (ROOT/'artifacts/_gate_receipts.json').unlink(missing_ok=True)
        raise
    if rc:
        path = ROOT/'artifacts/_gate_receipts.json'
        try:
            failed = json.loads(path.read_text(encoding='utf-8')).get('passed') is False
        except (OSError, ValueError, AttributeError):
            failed = False
        if not failed:
            path.unlink(missing_ok=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())
