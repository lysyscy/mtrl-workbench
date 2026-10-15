"""守两条Excel读取/预览入口的范围、类型和确认语义；只在隔离副本造红。"""

from pathlib import Path
import subprocess
import sys

from _isolated import isolated_backend

ROOT = Path(__file__).resolve().parents[2]
PY = ROOT / 'backend/.venv/Scripts/python.exe'
TEST = 'tests/test_excel_reading.py'
CASES = (
    ('import_kit/workbook.py', 'range(sh.nrows)', 'range(1, sh.nrows)',
     'test_xls_grid_keeps_coordinates_dates_bool_and_release'),
    ('import_kit/workbook.py', 'r2 - 1, c1, c2 - 1', 'r2 - 1, c1, c2 - 2',
     'test_xls_grid_keeps_coordinates_dates_bool_and_release'),
    ('import_kit/workbook.py', 'r.max_col - 1)', 'r.max_col - 2)',
     'test_merge_range_is_real_and_each_caller_keeps_its_extent'),
    ('import_kit/workbook.py', 'limit = len(grid) if rows is None else min(rows, len(grid))',
     'limit = len(grid)', 'test_merge_range_is_real_and_each_caller_keeps_its_extent'),
    ('import_kit/workbook.py', 'if value is None or str(value).strip() == "":',
     'if True:', 'test_merge_range_is_real_and_each_caller_keeps_its_extent'),
    ('import_kit/workbook.py', 'read_only=read_only)', 'read_only=False)',
     'test_xlsx_values_and_shape_keep_each_callers_policy'),
    ('import_kit/readers.py', 'return value if value is None or isinstance(value, (str, int, float, bool)) else cell_text(value)',
     'return cell_text(value)', 'test_xlsx_values_and_shape_keep_each_callers_policy'),
    ('import_kit/readers.py', 'clock = f" {rest[0]:02d}:{rest[1]:02d}:{rest[2]:02d}" if any(rest) else ""',
     'clock = ""', 'test_xls_grid_keeps_coordinates_dates_bool_and_release'),
)


def main():
    originals = {ROOT / 'backend/app' / rel: (ROOT / 'backend/app' / rel).read_bytes()
                 for rel, *_ in CASES}
    with isolated_backend('excel-reading-') as (base, env):
        def run(node=''):
            return subprocess.run([str(PY), '-X', 'utf8', '-B', '-m', 'pytest', TEST + node,
                                   '-o', 'addopts=-p tests.acc_plugin', '-q'], cwd=base, env=env,
                                  capture_output=True, encoding='utf-8', timeout=90)
        result = run()
        assert result.returncode == 0, result.stdout + result.stderr
        print('正常隔离基线：' + result.stdout.strip().splitlines()[-1])
        for rel, old, new, node in CASES:
            path = base / 'app' / rel
            raw = path.read_bytes()
            assert raw.count(old.encode()) == 1, (rel, old)
            try:
                path.write_bytes(raw.replace(old.encode(), new.encode()))
                for cached in base.rglob('*.pyc'):
                    cached.unlink()
                result = run('::' + node)
                assert result.returncode == 1 and (
                    'AssertionError' in result.stdout or 'Failed: DID NOT RAISE' in result.stdout
                ), result.stdout + result.stderr
                print(f'红已造出：{rel} -> {node}')
            finally:
                path.write_bytes(raw)
        for cached in base.rglob('*.pyc'):
            cached.unlink()
        result = run()
        assert result.returncode == 0, result.stdout + result.stderr
    assert all(path.read_bytes() == raw for path, raw in originals.items())
    print(f'反向灵敏度 {len(CASES)}/{len(CASES)}；复原：' + result.stdout.strip().splitlines()[-1] + '；正式源码未写靶')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
