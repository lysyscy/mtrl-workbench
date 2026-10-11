"""守TAIL-301：行格由列id排列、合计按SUM_KEYS查位；隔离故障必须被各自判据看见。

靶只写isolated_backend副本；基线绿、变异rc=1且断言消息命中、MD5复原。
"""

from __future__ import annotations

import hashlib
import pathlib
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _isolated import isolated_backend  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]

T_API = "tests/test_tail301_columns.py::test_sum_keys_from_domain"
T_ROWS = "tests/test_tail301_columns.py::test_rows_follow_columns"
T_SUMS = "tests/test_tail301_columns.py::test_sums_follow_column_ids"
CASES = [
    ("app/mod11_jc/api.py", "M5 API转发漏键", '"sum_keys": list(data["sum_keys"]),',
     "", T_API, "API must forward sum_keys"),
    ("app/mod11_jc/service.py", "M1 API丢合计身份", '"sum_keys": list(D.SUM_KEYS)',
     '"sum_keys": []', T_API, "sum_keys must follow domain"),
    ("app/web/index.html", "M2 行仍用原始顺序", "JC_COLUMNS.map(c => cells[c.key] ?? jcDefaultCell(j,c))",
     "Object.values(cells)", T_ROWS, "row cell must follow column id"),
    ("app/web/shell/pages-b.js", "M3 合计查位少算控件列", "jcColIndex(key)+1",
     "jcColIndex(key)", T_SUMS, "sum must follow column id"),
    ("app/web/shell/pages-b.js", "M4 付款误加发票", "pay_sum: () => jcPay(j)",
     "pay_sum: () => jcInvSum(j)", T_SUMS, "sum must follow column id"),
]


def _run(base: pathlib.Path, env: dict, node: str) -> tuple[int, str]:
    r = subprocess.run([sys.executable, "-X", "utf8", "-m", "pytest", "-q", node, "--tb=line"],
                       cwd=str(base), env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    with isolated_backend("tail301-") as (base, env):
        # ① `tests/shell_src.py` 要 `tools.audit`（壳源码的唯一出口）⇒ 同批带过去（供壳读取与浏览器夹具使用）
        shutil.copytree(ROOT / "tools/audit", base.parent / "tools/audit",
                        ignore=shutil.ignore_patterns("__pycache__"))
        env["PYTHONPATH"] = str(base) + ";" + str(ROOT)

        nodes = [T_API, T_ROWS, T_SUMS]
        for node in nodes:                                   # 基线：三个节点必须全绿（⛔ 否则靶本身是坏的）
            rc, out = _run(base, env, node)
            print(f"基线 {node.rsplit('::', 1)[-1][:28]:30s} rc={rc}（应为 0）")
            if rc != 0:
                print("  ⛔ 基线就红 ⇒ 先清红再来跑本件")
                print(out[-1200:])
                return 1

        hit = 0
        dirty: list[str] = []
        for path, desc, old, new, node, needle in CASES:
            p = base / path
            raw = p.read_bytes()
            md5 = hashlib.md5(raw).hexdigest()
            text = raw.decode("utf-8")
            if text.count(old) != 1:
                print(f"  ⛔ {desc} —— 靶串在 `{path}` 里命中 {text.count(old)} 次（期望 1）⇒ **未验证**")
                continue
            try:
                p.write_bytes(text.replace(old, new).encode("utf-8"))
                rc, out = _run(base, env, node)
            finally:
                p.write_bytes(raw)                            # ⭐ 立刻按原 bytes 复原（副本内，仍照做）
            if hashlib.md5(p.read_bytes()).hexdigest() != md5:
                dirty.append(path)
            ok = rc == 1 and needle in out
            print(("  ✅ " if ok else "  ⛔ 未命中 ") + desc + f"  → rc={rc}"
                  + ("" if ok else f"（判据「{needle}」没出现在输出里）"))
            if not ok:
                print("      " + "\n      ".join(out.strip().splitlines()[-4:]))
            hit += ok

        print()
        print(f"  命中 {hit}/{len(CASES)}")
        print(f"  复原校验（MD5 逐字节）：{'✅ 已复原' if not dirty else '❌ 未复原 ' + ', '.join(dirty)}")
        print("  靶在临时副本内 ⇒ **正式文件与权威四态均未动**。")
        return 0 if (hit == len(CASES) and not dirty) else 1


if __name__ == "__main__":
    raise SystemExit(main())
