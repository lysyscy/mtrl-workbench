"""Apply only the explicitly approved notice-method preview, atomically."""
from __future__ import annotations

import argparse
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path

from snapshot import configure
from remote import call


def load_approved(path, approved_sha256):
    raw = Path(path).read_bytes()
    if sha256(raw).hexdigest() != approved_sha256:
        raise ValueError('预览SHA与已确认版本不符，未写入')
    preview = json.loads(raw)
    if preview.get('schema') != 1 or not preview.get('changes'):
        raise ValueError('没有可回写的变更')
    if sha256(Path(preview['source']).read_bytes()).hexdigest() != preview['source_sha256']:
        raise ValueError('原表已改变，须重新核对并确认预览')
    from app.mod05_flow.models import PAY_METHODS
    from app.core.money import to_money
    seen = set()
    for c in preview['changes']:
        if type(c.get('id')) is not int or c['id'] in seen or not c.get('bill_no'):
            raise ValueError('回写清单定位无效或重复')
        seen.add(c['id'])
        if c.get('new') not in PAY_METHODS or c.get('old') not in ('', *PAY_METHODS):
            raise ValueError('回写清单含无效付款方式')
        if not c.get('ownership_id') or type(c.get('source_row')) is not int:
            raise ValueError('回写清单缺少归属或来源行')
        approved, paid, flow, planned = (to_money(c.get(k)) for k in
                                        ('approved', 'paid', 'flow_amount', 'planned_amount'))
        if flow != approved or planned <= 0 or planned > approved-paid:
            raise ValueError('回写清单不满足金额核对条件')
    return preview


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repo')
    ap.add_argument('--server')
    ap.add_argument('--session-file')
    ap.add_argument('--preview', required=True)
    ap.add_argument('--approved-sha256', required=True)
    ap.add_argument('--receipt', required=True)
    args = ap.parse_args()
    configure(args.repo)
    preview = load_approved(args.preview, args.approved_sha256)
    receipt = Path(args.receipt).resolve()
    receipt.parent.mkdir(parents=True, exist_ok=True)
    # 先保留回执路径；数据库提交后回执失败也不能谎报未写入。
    with receipt.open('x', encoding='utf-8') as out:
        record = {'status': 'pending', 'preview_sha256': args.approved_sha256,
                  'source_sha256': preview['source_sha256'], 'changes': preview['changes']}
        json.dump(record, out, ensure_ascii=False, indent=2)
        out.flush()
        result = call('/api/m03/plan-audit/methods', server=args.server, session_file=args.session_file,
                      data={'preview_json': Path(args.preview).read_bytes().decode('utf-8'),
                            'approved_sha256': args.approved_sha256})
        if (result.get('status') != 'committed' or result.get('count') != len(preview['changes'])
                or result.get('preview_sha256') != args.approved_sha256
                or result.get('source_sha256') != preview['source_sha256']):
            raise ValueError('接口回执不完整；写入结果待核实，请勿直接重试')
        record.update(status='committed', applied_at=datetime.now().astimezone().isoformat())
        out.seek(0)
        json.dump(record, out, ensure_ascii=False, indent=2)
        out.truncate()
    print(json.dumps({'status': 'committed', 'count': len(preview['changes']), 'receipt': str(receipt)}, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except ValueError as exc:
        raise SystemExit(str(exc)+'；若已生成pending回执，先核实系统原值，不要直接重试') from None
    except Exception as exc:
        raise SystemExit(f'回写异常：{type(exc).__name__}；核对回执及数据库原值后再决定是否重试') from None
