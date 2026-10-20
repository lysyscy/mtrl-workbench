"""归档脚本：审计历史机械报表车牌字段，不修改原件。"""
from pathlib import Path
import json,re,collections

root=Path('.artifacts/machinery-fee-workflow/prototype-20261017')
rows=json.loads((root/'jan-sep-seed.json').read_text(encoding='utf-8'))['data']['saved']
license_re=re.compile(r'^[\u4e00-\u9fff][A-Za-z][A-Za-z0-9·.]{4,8}$')
groups=collections.defaultdict(list)
for row in rows:groups[row['device']].append(row)
result=[]
for device,rs in sorted(groups.items()):
    plates=[r for r in rs if license_re.fullmatch(r['plate'].strip())]
    other=[r for r in rs if r['plate'].strip() and not license_re.fullmatch(r['plate'].strip())]
    result.append({'device':device,'rows':len(rs),'license_rows':len(plates),'blank_rows':sum(not r['plate'].strip() for r in rs),'other_text':dict(collections.Counter(r['plate'] for r in other)),'months':sorted({r['month'] for r in rs}),'projects':len({r['project'] for r in rs})})
(root/'plate-history-audit.json').write_text(json.dumps({'scope':'2026-01 to 2026-09, 1966 original report detail rows; read-only cached extraction','groups':result},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
