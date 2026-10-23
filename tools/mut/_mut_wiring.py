"""Existing W2 alias, local-router and exclusion cases, in a temporary source fixture."""
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'audit'))
import wiring_audit as W


def main():
    with tempfile.TemporaryDirectory(prefix='mtrl-wiring-') as folder:
        path=Path(folder)/'sample.py'
        text='''from source import domains_router as alias
alias()
def domains_router(): pass
@r.get('/schema')
def api_schema(): pass
def try_money(): pass
'''
        def names(source, expected=()):
            path.write_text(source,encoding='utf-8')
            defs,refs=W.scan([path])
            return {d.name for d in W.candidates(defs,refs,set(expected))}
        key=f'W2 {W.rel(path)}:try_money'
        assert names(text,{key})==set()
        assert names(text.replace('alias()',''),{key})=={'domains_router'}
        assert names(text.replace("@r.get('/schema')",''),{key})=={'api_schema'}
        assert names(text)=={'try_money'}
        defs,refs=W.scan([path])
        live={f'W2 {d.file}:{d.name}' for d in defs if d.public and not d.framework_wired and not W.external_refs(d,refs)}
        assert key in live and 'W2 missing.py:gone' not in live
    print('4 W2 fixture cases passed; production sources untouched')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
