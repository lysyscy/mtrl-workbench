"""Project artifact entry using the fixed runtime deployed by setup."""
from pathlib import Path
import json
import sys

if __name__ == '__main__':
    if len(sys.argv) < 2: raise SystemExit('action required')
    own_args = sys.argv[2:sys.argv.index('--')] if '--' in sys.argv else sys.argv[2:]
    if any(x.split('=', 1)[0] in {'--r', '--ro', '--roo', '--root'} for x in own_args): raise SystemExit('Project output root is fixed')
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.audit.workspace_paths import _lifecycle
    try:
        runtime, root = _lifecycle()
        code = runtime.main([sys.argv[1], '--root', str(root), *sys.argv[2:]])
    except (OSError, ValueError, TypeError, RuntimeError) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        code = 1
    raise SystemExit(code)
