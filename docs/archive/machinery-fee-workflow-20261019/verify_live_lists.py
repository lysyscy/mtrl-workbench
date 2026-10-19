"""User-authorized read-only SCY980803 probe; never opens a business database."""
from pathlib import Path
import json
import sys
from decimal import Decimal

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / 'backend'))
from app.core.config import get_settings
from app.mod02_i8.client import I8Client
from app.mod06_proc.workbench_i8 import fetch_lists

assert get_settings().i8_user == 'SCY980803', '仅允许本次明确授权账号'
client = I8Client(allow_kick=False)
original_post = client.post_json
def observed_post(path, **kwargs):
    response = original_post(path, **kwargs)
    if not isinstance(response, dict) or not isinstance(response.get('data'), list):
        print(json.dumps({'response_type': type(response).__name__, 'keys': list(response) if isinstance(response, dict) else [],
                          'status': response.get('status') if isinstance(response, dict) else None,
                          'message': str(response.get('msg', ''))[:300] if isinstance(response, dict) else '',
                          'data_type': type(response.get('data')).__name__ if isinstance(response, dict) else ''}, ensure_ascii=False))
    return response
client.post_json = observed_post
try:
    lists = fetch_lists(client)
finally:
    client.close()
out = root / '.artifacts/machinery-fee-workflow/implementation-20261019'
out.mkdir(parents=True, exist_ok=True)
(out / 'live-i8-lists.json').write_text(json.dumps(lists, ensure_ascii=False, indent=2), encoding='utf-8')
summary = {kind: {'count': source['total'],
                 'known_total': str(sum((Decimal(row['approval' if kind == 'team' else 'amount'])
                      for row in source['rows'] if row['approval' if kind == 'team' else 'amount'] is not None), Decimal(0))),
                 'unknown': sum(row['approval' if kind == 'team' else 'amount'] is None for row in source['rows'])}
           for kind, source in lists.items()}
(out / 'live-i8-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False))
