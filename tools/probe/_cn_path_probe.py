"""中文名引用的只读候选量测；默认只看D件，不新增T3闸门。

--documents读取既有文档扫描面，输出缺失候选与豁免读数，需逐条判断历史/简称。
绝对仓外路径已由T3原分支检查；本探针只补中文相对路径，绝不声称全仓无幽灵。
"""
from pathlib import Path
import argparse
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/audit'))
import audit_common as common
import audit_drift as drift

TOKENS = re.compile(r'`([^`\s]+\.(?:md|py|json|html|ps1|sql|ini|txt|js|css|xlsx))`')
CJK = re.compile(r'[\u4e00-\u9fff]')


def measure(lines, roots):
    """精确核中文相对引用，沿用T3前缀、模板、跳过和邻近历史豁免。"""
    counts = {'seen': 0, 'exact': 0, 'exempt': 0}
    missing = []
    for i,line in enumerate(lines,1):
        for token in TOKENS.findall(line):
            raw = token.replace('\\','/')
            if not CJK.search(raw) or not any(raw.startswith(d) for d in common.TOP_DIRS):
                continue
            if common._PLACEHOLDER.search(raw) or '…' in raw or any(raw.startswith(d) for d in common.T3_SKIP_PREFIXES):
                continue
            counts['seen'] += 1
            if any((root/pre/raw).exists() or (root/pre/raw).with_suffix('').exists()
                   for root in roots for pre in common.PATH_ROOTS):
                counts['exact'] += 1
            elif drift._hint_applies(line,raw):
                counts['exempt'] += 1
            else:
                missing.append((i,raw))
    return counts,missing


def selftest():
    import tempfile
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp); (root/'ops').mkdir(); (root/'ops/真源.md').write_text('source',encoding='utf-8')
        counts,missing=measure(['`ops/真源.md`','`ops/不存在.md`','旧路径 `ops/旧名.md`'],[root])
        assert counts=={'seen':3,'exact':1,'exempt':1} and missing==[(2,'ops/不存在.md')], '中文真幽灵必须列候选，正常与旧址不误伤'
    print('自测 中文存在、缺失及邻近豁免通过')
    return 0


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--documents',action='store_true')
    parser.add_argument('--selftest',action='store_true')
    args=parser.parse_args()
    if args.selftest:return selftest()
    docs=common.iter_docs()
    docs=[d for d in docs if args.documents or '/40-decisions/' in d[1].replace('\\','/')]
    roots=[ROOT]+([common.delivery_root()] if common.delivery_root() else [])
    totals={'seen':0,'exact':0,'exempt':0}; candidates=0
    for side,rel,path,lines,zones in docs:
        counts,missing=measure(lines,roots)
        for key,value in counts.items():totals[key]+=value
        for line,raw in missing:
            candidates+=1; print(f'候选 {rel}:{line} {raw}')
    print(f'中文相对路径量测：文档 {len(docs)} · {totals} · 缺失候选 {candidates}；仅量测，非T3结论')
    return 1 if candidates else 0


if __name__=='__main__':
    sys.exit(main())
