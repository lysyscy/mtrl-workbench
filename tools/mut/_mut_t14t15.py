"""T14/T15 隔离反例：运行超期、旧混合目录、散件与证据期限。"""
from pathlib import Path
import json
import os
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/audit'))
import audit_work as W


def main():
    original = W.REPO_ROOT
    cases = 0
    try:
        with tempfile.TemporaryDirectory(prefix='mtrl-t14-t15-') as folder:
            root = Path(folder)
            W.REPO_ROOT = root
            def hits():
                return W.check_scratch_ttl()
            baseline = len(hits())
            stale = root/'.artifacts/active/fixture/one/reports/stale.json'
            stale.parent.mkdir(parents=True)
            stale.write_text('{}')
            old = time.time() - 20 * 86400
            os.utime(stale, (old, old))
            assert len(hits()) > baseline, '超期 active 仍须可见'
            stale.unlink()
            cases += 1
            for rel in ('artifacts/_probe.md', 'tools/_probe.py'):
                p = root/rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text('# fixture')
                assert len(hits()) > baseline, rel
                p.unlink()
                if rel.startswith('artifacts/'):
                    p.parent.rmdir()
                cases += 1
            policy = root/'.artifacts/archive/fixture/retention.json'
            policy.parent.mkdir(parents=True)
            policy.write_text(json.dumps({'reason':'fixture', 'expires_on':'2000-01-01'}))
            assert len(hits()) > baseline, '过期归档仍须可见'
            policy.unlink()
            policy.parent.rmdir()
            cases += 1
            assert len(hits()) == baseline, '隔离现场须复原'
        assert not Path(folder).exists(), '临时目录须实际退出'
    finally:
        W.REPO_ROOT = original
    print(f'通过 {cases} 项隔离反例；正式源码、原件和运行数据未作靶')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
