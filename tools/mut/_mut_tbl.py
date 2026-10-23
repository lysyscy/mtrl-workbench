"""TBL必要隔离自证：共享tbody/列定义内核，以及过程、付款计划、集采代表委托。

旧逐页源码形态与失效锚点快照在 tools/mut/_归档-20261009/_mut_tbl_legacy.py。
只跑实际目标断言，不混跑数据库业务或其他列排序。基线失败、锚未命中、
执行异常均报失败；工作文件和仓外交付面不作靶，局部结果不刷新权威四态。
"""
from __future__ import annotations

from pathlib import Path as _WorkspacePath
import sys as _workspace_sys
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2] / 'tools/audit'))
from workspace_paths import output as _run_output, output_dir as _run_dir
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import shutil
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
PY = pathlib.Path(sys.executable)
SHELL = ROOT/'backend/app/web/index.html'
PROJ = ROOT/'backend/app/web/shell/proj.js'
PARTIAL_ACC = ROOT/str(_run_output('_mut_acc_results.json'))
TARGETS = (
    'tests/test_wired_m06.py::test_合计行格数由表头派生',
    'tests/test_acc_jc_shell.py::test_空态行跨列数派生且全选框回显三态',
    'tests/test_ux_pages.py::test_表格件支持列定义式_试点已接上',
)

def _b(s: str) -> bytes:
    return s.encode('utf-8')

CASES = [
    (PROJ, "M2 掏空内核（`TBL` 不再把 rows 拼进 tbody）", _b("+rows.join('')+(rows.length"),
     _b("+''+(rows.length"), "内核没有把 rows 拼进 `tbody`"),
    (SHELL, "M3 去掉委托（`m06` 差异表不再走 `TBL`）", _b("TBL({head:DIFF_THEAD,"),
     _b("TBLBROKEN({head:DIFF_THEAD,"), "差异表的表外壳没走统一出口"),
    (SHELL, "M4 去掉委托（`m06` 主表 表①·表② 不再走 `TBL`）", _b("TBL({head,rows:body,sum:sumRow+totRow})"),
     _b("TBLBROKEN({head,rows:body,sum:sumRow+totRow})"), "主表（表①/表②）的表外壳没走统一出口"),
    # ⚠️ 2026-10-11（`TAIL-298`）：`m11` 的表头由 `JC_THEAD` 字面量改成 `jcThead()`（按后端列清单现生成）
    #    ⇒ 本锚点同批跟上（⛔ 不改 = 靶串命中 0 次 ⇒ 这一支静默失效，本件自己会打「未验证」）。
    (SHELL, "M15 去掉委托（`m11` 集采台账表 不再走 `TBL`）", _b("TBL({head:jcThead(),key:'m11:jc',"),
     _b("TBLBROKEN({head:jcThead(),key:'m11:jc',"), "集采台账表没走统一出口"),
    (PROJ, "M40 内核不按 `cols` 派生（`c.t` 改名 ⇒ 给了 `cols` 的表没有表头）",
     _b("head=cols.map(c=>c.t).join('')"), _b("head=cols.map(c=>c.tt).join('')"),
     "没有从 `cols` 派生")
]

# pytest只记录真实失败阶段与断言；每轮清除旧报告，缺报告不能算命中。
WITNESS_PLUGIN = '''
import json, os, pytest
from pathlib import Path
failures = []
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    report = (yield).get_result()
    if report.failed:
        failures.append({"nodeid": item.nodeid, "phase": report.when,
                         "assertion": bool(call.excinfo and issubclass(call.excinfo.type, AssertionError)),
                         "message": str(call.excinfo.value) if call.excinfo else ""})
def pytest_sessionfinish(session, exitstatus):
    Path(os.environ["TBL_WITNESS"]).write_text(json.dumps(failures), encoding="utf-8")
'''

def witness_hit(rc: int, out: str, failures: list[dict], needle: str) -> bool:
    """非目标、setup/collection/执行异常与失效报告不能充当反向命中。"""
    return (rc == 1 and needle in out and bool(failures) and
            all(f['phase'] == 'call' and f['assertion'] and f['nodeid'] in TARGETS for f in failures) and
            any(needle in f['message'] for f in failures))

def run_target() -> tuple[int, str, list[dict]]:
    PARTIAL_ACC.parent.mkdir(parents=True, exist_ok=True)
    plugin = PARTIAL_ACC.parent/'_tbl_witness.py'
    plugin.write_text(WITNESS_PLUGIN, encoding='utf-8', newline='')
    report = PARTIAL_ACC.parent/'_tbl_witness.json'
    report.unlink(missing_ok=True)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1",
           "PYTHONPATH": str(plugin.parent)+os.pathsep+os.environ.get('PYTHONPATH',''),
           "TBL_WITNESS": str(report)}
    r = subprocess.run([str(PY), "-X", "utf8", "-m", "pytest", "-q", *TARGETS,
                        "-p", "_tbl_witness", "-p", "no:cacheprovider", "--tb=line"],
                       cwd=str(ROOT / "backend"), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env=env)
    failures = json.loads(report.read_text(encoding='utf-8')) if report.is_file() else []
    return r.returncode, (r.stdout or "") + (r.stderr or ""), failures


def _main() -> int:
    files = sorted({c[0] for c in CASES})
    orig = {p: p.read_bytes() for p in files}
    md5_before = {p: hashlib.md5(b).hexdigest() for p, b in orig.items()}

    rc0, out0, _ = run_target()
    print(f"基线（未改坏）{' + '.join(TARGETS)} rc={rc0}（应为 0）")
    if rc0 != 0:
        print("  ⛔ 基线就红 ⇒ 先清红再来跑本件")
        return 1

    hit = 0
    for path, desc, old, new, needle in CASES:
        src = orig[path]
        if src.count(old) != 1:
            print(f"  ⛔ {desc} —— 靶串在 `{path.name}` 里命中 {src.count(old)} 次（期望 1）⇒ **未验证**")
            continue
        try:
            path.write_bytes(src.replace(old, new, 1))
            rc, out, failures = run_target()
        finally:
            path.write_bytes(src)                     # ⭐ 立刻按原 bytes 复原
        ok = witness_hit(rc, out, failures, needle)
        print(("  ✅ " if ok else "  ⛔ 未命中 ") + desc + f"  → rc={rc}"
              + ("" if ok else f"（判据「{needle}」没出现在输出里）"))
        hit += ok

    bad = [p.name for p in files
           if hashlib.md5(p.read_bytes()).hexdigest() != md5_before[p]]
    print()
    print(f"  命中 {hit}/{len(CASES)}")
    print(f"  复原校验（MD5 逐字节 · {len(files)} 件）："
          + ("✅ 复原" if not bad else "❌ 未复原 " + ", ".join(bad)))
    print("局部结果隔离；权威四态未刷新，不要求为本件再跑全套。")
    return 0 if (hit == len(CASES) and not bad) else 1



def main() -> int:
    """原生入口在隔离副本执行同一实现与断言。"""
    if '--in-copy' in sys.argv:
        return _main()
    with tempfile.TemporaryDirectory(prefix='mtrl-tbl-proof-') as temp:
        root = pathlib.Path(temp)
        for name in ('tools', 'backend/app', 'backend/tests'):
            shutil.copytree(ROOT/name, root/name,
                            ignore=shutil.ignore_patterns('__pycache__', '_归档-*'))
        result = subprocess.run([str(PY), '-X', 'utf8', str(root/'tools/mut/_mut_tbl.py'), '--in-copy'],
                                cwd=root, capture_output=True, text=True, encoding='utf-8', errors='replace',
                                env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        print(result.stdout)
        print(result.stderr)
        return result.returncode

if __name__ == '__main__':
    sys.exit(main())
