"""TAIL-300金额/批量/事务反例；只改临时副本并运行真实测试，正式文件不作靶。"""
from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import sys

from _isolated import isolated_backend

ROOT = Path(__file__).resolve().parents[2]
TARGETS = ('tests/test_tail300_sources.py',)
TEST = TARGETS[0]
CASES = (
    ('app/mod08_inv/service.py', '原单混入调整', '    return R.list_details(session, **kw)',
     '    from types import SimpleNamespace\n    return [SimpleNamespace(ym=r["ym"], warehouse_name=r["warehouse"], direction=r["direction"], cbs_name=r["cbs_name"], amount=r.get("adj_amount", r["amount"])) for r in R.load_rows(session, **kw)]',
     'test_fee_original_excludes_adjustment'),
    ('app/mod05_flow/repository.py', '最近日期混入撤销',
     'PaymentFlow.notice_id.in_(notice_ids), PaymentFlow.status == FLOW_EFFECTIVE',
     'PaymentFlow.notice_id.in_(notice_ids)', 'test_jc_batch_facts_and_query_count'),
    ('app/mod11_jc/repository.py', '批量退成N+1',
     'stats = notices.stat_paid_of_many(s, notice_ids)',
     'stats = {nid: notices.stat_paid_of_many(s, [nid]).get(nid) for nid in notice_ids}',
     'test_jc_batch_facts_and_query_count'),
    ('app/mod03_notice/repository.py', '统计金额误读会话旧缓存',
     'return {int(nid): amount for nid, amount in session.execute(stmt).all()}',
     'return {int(n.id): n.stat_paid for n in get_notices_by_ids(session, ids)}',
     'test_jc_stat_reads_database_fact_not_cached_notice'),
    ('app/mod03_notice/service.py', '丢锁定重读参数',
     'return repository.get_notice(session, notice_id, **kw)',
     'return repository.get_notice(session, notice_id)', 'test_notice_full_input_and_lock_parameters'),
    ('app/mod05_flow/repository.py', '统计同步漏传锁参数',
     'notices_service.get_notice(s, int(notice_id), with_for_update={"key_share": True}, populate_existing=True)',
     'notices_service.get_notice(s, int(notice_id))', 'test_notice_full_input_and_lock_parameters'),
    ('app/mod03_notice/repository.py', '完整事实被列表上限截断',
     'select(PaymentNotice).order_by(PaymentNotice.id.asc())',
     'select(PaymentNotice).order_by(PaymentNotice.id.asc()).limit(5000)',
     'test_notice_full_input_and_lock_parameters'),
)


def digest():
    return {str(p): hashlib.sha256(p.read_bytes()).digest()
            for base in (ROOT/'backend/app', ROOT/'backend/tests')
            for p in base.rglob('*') if p.is_file() and '__pycache__' not in p.parts}


def run(base, env, node):
    r = subprocess.run([sys.executable, '-X', 'utf8', '-m', 'pytest', '-q', node, '--tb=short'],
                       cwd=base, env=env, capture_output=True, text=True, encoding='utf-8')
    return r.returncode, r.stdout + r.stderr


def main():
    before = digest()
    with isolated_backend('tail300-') as (base, env):
        env['PYTHONPATH'] = str(base) + ';' + str(ROOT)
        rc, out = run(base, env, TEST)
        assert rc == 0, out
        print('基线4条真实判据绿')
        for path, name, old, new, test in CASES:
            p = base/path; raw = p.read_bytes()
            text = raw.decode().replace('\r\n', '\n')
            assert text.count(old) == 1, (name, text.count(old))
            try:
                p.write_text(text.replace(old, new), encoding='utf-8')
                rc, out = run(base, env, TEST+'::'+test)
                assert rc == 1 and ('AssertionError' in out or 'E   assert ' in out) and test in out, (name,rc,out)
            finally:
                p.write_bytes(raw)
            print(name, '真实断言红，副本已复原')
    assert digest() == before, '正式源码被改写'
    print('命中7/7；正式源码与权威四态未写靶')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
