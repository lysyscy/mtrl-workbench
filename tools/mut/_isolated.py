"""机械存储反例的隔离后端配方：传测试库、隔离四态，结束移除临时副本。"""
from contextlib import contextmanager
from pathlib import Path
import os
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]


@contextmanager
def isolated_backend(prefix):
    """供_mut_proc_split与_mut_tail270使用；正式源码和凭据不作变异靶。"""
    sys.path.insert(0, str(ROOT / 'backend'))
    from app.core.config import get_settings
    test_url = get_settings().test_database_url
    with tempfile.TemporaryDirectory(prefix=prefix, dir=ROOT / '.codebuddy/work/00-scratch') as folder:
        base = Path(folder) / 'backend'
        base.mkdir()
        for name in ('app', 'tests'):
            shutil.copytree(ROOT / 'backend' / name, base / name,
                            ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copy2(ROOT / 'backend/pytest.ini', base / 'pytest.ini')
        env = dict(os.environ, TEST_DATABASE_URL=test_url,
                   DATABASE_URL=test_url, PYTHONIOENCODING='utf-8',
                   ACC_RESULTS_PATH=str(Path(folder) / 'results.json'))
        yield base, env
