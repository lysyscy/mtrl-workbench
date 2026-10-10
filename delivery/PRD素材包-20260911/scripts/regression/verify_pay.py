# -*- coding: utf-8 -*-
"""付款域回归：pay_service 防御性测试（复制库到临时文件跑，不污染真实库）。

用法: python scripts/regression/verify_pay.py
"""
import os
import sys
import shutil
import sqlite3
import tempfile

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'app'))
import pay_service as ps

tmp = os.path.join(tempfile.gettempdir(), 'pay_test.db')
if os.path.exists(tmp):
    os.remove(tmp)
shutil.copy(os.path.join(ROOT, 'app', 'data', 'workbench.db'), tmp)
conn = sqlite3.connect(tmp)
conn.row_factory = sqlite3.Row


def show(title, fn):
    try:
        r = fn()
        print('  ✅ %-28s → %s' % (title, r))
    except ps.PayError as e:
        print('  🛡  %-28s → 拦截: %s' % (title, e.msg))
    except Exception as e:
        print('  ❌ %-28s → 异常: %s' % (title, e))


print('=== 1. 金额转分 ===')
print('  0.1+0.2 =', ps.to_cents(0.1) + ps.to_cents(0.2), '(应为 30 分，浮点直接加是 0.30000000000000004)')

print()
print('=== 2. 付款方式模糊匹配 ===')
for t in ['现汇', '银行承兑', '电子承兑汇票', '供应链保理', '微信支付', '']:
    print('  %-10s → %s' % (t or '(空)', ps.match_pay_way(t)))

print()
print('=== 3. 找一个已审批单据 ===')
row = conn.execute(
    "SELECT id, 单据编码, 审批金额, 审批状态, source FROM pay_notice "
    "WHERE deleted=0 AND 审批状态='已审批' AND (source IS NULL OR source!='manual') LIMIT 1").fetchone()
if not row:
    print('  ❌ 没有已审批单据，无法测试')
    conn.close(); os.remove(tmp); sys.exit(0)
nid, code = row['id'], row['单据编码']
approve = float(row['审批金额'] or 0)
print('  单据 %s 金额 %.2f 状态=%s source=%s' % (code, approve, row['审批状态'], row['source']))

print()
print('=== 4. 付款（部分：一半）===')
show('付一半(%.2f)' % round(approve / 2, 2),
     lambda: ps.pay(conn, nid, round(approve / 2, 2), '现汇', pay_date='2026-09-10',
                    operator='测试', request_id='REQ-1'))
print('  派生 →', ps.notice_view(conn, conn.execute('SELECT * FROM pay_notice WHERE id=?', (nid,)).fetchone())['付款状态'],
      '已付=%.2f' % ps.paid_amount(conn, nid))

print()
print('=== 5. 防连点（同 request_id 再付一次）===')
show('重复 request_id=REQ-1',
     lambda: ps.pay(conn, nid, round(approve / 2, 2), '现汇', request_id='REQ-1', operator='测试'))
print('  已付应仍为 %.2f → 实为 %.2f' % (round(approve / 2, 2), ps.paid_amount(conn, nid)))

print()
print('=== 6. 防超付（再付全额 → 应拦截）===')
show('再付全额(超付)', lambda: ps.pay(conn, nid, approve, '现汇', request_id='REQ-2', operator='测试'))

print()
print('=== 7. 允许超付（allow_over=True）===')
show('允许超付再付全额',
     lambda: ps.pay(conn, nid, approve, '现汇', request_id='REQ-3', operator='测试', allow_over=True))

print()
print('=== 8. 撤销（不填原因 → 应拦截）===')
fid = conn.execute('SELECT id FROM pay_flow WHERE notice_id=? AND voided=0 LIMIT 1', (nid,)).fetchone()['id']
show('撤销不填原因', lambda: ps.void_flow(conn, fid, operator='测试', reason=''))

print()
print('=== 9. 撤销（填原因）===')
show('撤销填原因', lambda: ps.void_flow(conn, fid, operator='测试', reason='测试撤销'))
print('  已付 → %.2f，状态=%s' % (
    ps.paid_amount(conn, nid),
    ps.notice_view(conn, conn.execute('SELECT * FROM pay_notice WHERE id=?', (nid,)).fetchone())['付款状态']))

print()
print('=== 10. 未审批单据不可付款 ===')
un = conn.execute(
    "SELECT id FROM pay_notice WHERE deleted=0 AND 审批状态!='已审批' LIMIT 1").fetchone()
if un:
    show('未审批单据付款', lambda: ps.pay(conn, un['id'], 100, '现汇', operator='测试'))
else:
    print('  (无未审批单据，跳过)')

conn.close()
os.remove(tmp)
print()
print('临时库已删除，真实库未受影响')
