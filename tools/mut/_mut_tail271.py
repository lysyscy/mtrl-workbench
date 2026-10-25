"""机械报表读取和项目规则的反向灵敏度；只修改隔离副本。"""

from pathlib import Path
import subprocess
import sys
from _isolated import isolated_backend

ROOT = Path(__file__).resolve().parents[2]
CASES = [
    ("无序号明细漏算", "mech_report.py", '                if current:', '                if isinstance(serial, (int, float)) and current:', "test_month_sources_history_and_aggregate_rounding"),
    ("非税明细错列", "mech_report.py", '(names[1], 9, "mech_4")', '(names[1], 8, "mech_4")', "test_month_sources_history_and_aggregate_rounding"),
    ("汇总错年月", "mech_report.py", 'min(dated)-1', 'min(dated)', "test_month_sources_history_and_aggregate_rounding"),
    ("分组重复相加", "mech_report.py", '                    continue  # 项目分组的汇总值不与明细重复相加。',
     '                    sums[current] = _value(sheet, formulas[sheet_name], row, column) or Decimal(0)\n                    continue', "test_month_sources_history_and_aggregate_rounding"),
    ("未知项目误写", "mech_matching.py", 'next(iter(matched), "")', 'next(iter(matched), rules[0]["warehouse"])', "test_same_full_name_never_matches_and_edit_takes_effect"),
    ("规则编辑无效", "mech_matching.py", 'row.aliases = values', 'row.aliases = []', "test_editing_stored_rule_changes_current_match")
]


def main():
    with isolated_backend("tmp-tail271-mut-") as (base, env):
        for label, filename, old, new, test in CASES:
            tests_file = "test_tail271_matching.py" if filename == "mech_matching.py" else "test_tail271_report.py"
            args = [str(ROOT / "backend/.venv/Scripts/python.exe"), "-X", "utf8", "-m", "pytest",
                    f"tests/{tests_file}::{test}", "-q", "--tb=short"]
            normal = subprocess.run(args, cwd=base, env=env, capture_output=True, text=True, encoding="utf-8", timeout=45)
            assert normal.returncode == 0, normal.stdout + normal.stderr
            path = base / "app/mod06_proc" / filename
            original = path.read_bytes()
            source = original.decode("utf-8").replace("\r\n", "\n")
            assert source.count(old) == 1, (label, source.count(old))
            path.write_text(source.replace(old, new), encoding="utf-8")
            try:
                red = subprocess.run(args, cwd=base, env=env, capture_output=True, text=True, encoding="utf-8", timeout=45)
                assert red.returncode and "FAILED " in red.stdout, red.stdout + red.stderr
                print("PASS 正常绿、指定缺陷红：" + label, flush=True)
            finally:
                path.write_bytes(original)
    return 0


if __name__ == "__main__":
    sys.exit(main())
