"""守 test_report_query.py 的首值/0/多值/空格/缺席与各页差异，隔离改坏后真跑判据见红。"""
from pathlib import Path
import subprocess
import sys

from _isolated import isolated_backend

ROOT = Path(__file__).resolve().parents[2]
PY = ROOT / 'backend/.venv/Scripts/python.exe'
TEST = 'tests/test_report_query.py'
CASES = (
    ('core/query.py', 'value = value[0] if value else ""', 'value = value[-1] if value else ""', 'test_single_value_contract'),
    ('core/query.py', 'return str(value).strip()', 'return str(value or "").strip()', 'test_single_value_contract'),
    ('core/query.py', 'vals if len(vals) > 1 else (vals[0] if vals else "")', '(vals[0] if vals else "")', 'test_flatten_keeps_empty_order_and_duplicates'),
    ('core/query.py', 'out[key] = vals', 'out[key] = [v.strip() for v in vals]', 'test_flatten_keeps_empty_order_and_duplicates'),
    ('mod07_setl/service.py', 'if "ext_period" in p else', 'if p.get("ext_period") else', 'test_page_defaults_validation_and_explicit_empty'),
    ('mod08_inv/service.py', '"projects": many("pj"),', '"projects": tuple(dict.fromkeys(many("pj"))),', 'test_multivalue_business_differences'),
    ('mod07_setl/api.py', 'st = BS.parse_state(flatten_query(request.query_params))', 'st = BS.parse_state({})', 'test_actual_big_and_extract_export_entries'),
    ('mod07_setl/api.py', 'q = flatten_query(request.query_params)', 'q = {}', 'test_actual_big_and_extract_export_entries'),
)


def main():
    originals = {p: p.read_bytes() for p in [ROOT / 'backend/app' / rel for rel, *_ in CASES]}
    with isolated_backend('report-query-') as (base, env):
        def run(node=''):
            return subprocess.run([str(PY), '-X', 'utf8', '-B', '-m', 'pytest', TEST + node, '-q'],
                                  cwd=base, env=env, capture_output=True, encoding='utf-8')
        result = run()
        assert result.returncode == 0, result.stdout + result.stderr
        print('正常隔离基线：7 passed')
        for rel, old, new, node in CASES:
            path = base / 'app' / rel
            raw = path.read_bytes()
            assert raw.count(old.encode()) == 1, (rel, old)
            try:
                path.write_bytes(raw.replace(old.encode(), new.encode()))
                # 禁止旧 pyc 掩盖同长度/同秒改动；只清理隔离副本的编译缓存。
                for cached in base.rglob('*.pyc'):
                    cached.unlink()
                result = run('::' + node)
                assert result.returncode == 1 and 'AssertionError' in result.stdout, result.stdout + result.stderr
                print(f'红已造出：{rel} -> {node}')
            finally:
                path.write_bytes(raw)
        result = run()
        assert result.returncode == 0, result.stdout + result.stderr
    assert all(p.read_bytes() == raw for p, raw in originals.items())
    print('反向灵敏度 8/8；复原基线 7 passed；正式文件字节未变')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
