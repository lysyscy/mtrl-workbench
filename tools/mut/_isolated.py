"""机械存储反例的隔离后端配方：传原库与测试库供守卫核验，结束移除临时副本。"""

from pathlib import Path as _WorkspacePath
import sys as _workspace_sys
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2] / 'tools/audit'))
from workspace_paths import output as _run_output, output_dir as _run_dir
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
    settings = get_settings()
    test_url = settings.test_database_url
    with tempfile.TemporaryDirectory(prefix=prefix, dir=ROOT / _run_dir('work')) as folder:
        base = Path(folder) / 'backend'
        base.mkdir()
        for name in ('app', 'tests'):
            shutil.copytree(ROOT / 'backend' / name, base / name,
                            ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copy2(ROOT / 'backend/pytest.ini', base / 'pytest.ini')
        env = dict(os.environ, TEST_DATABASE_URL=test_url,
                   DATABASE_URL=settings.database_url, PYTHONIOENCODING='utf-8',
                   ACC_RESULTS_PATH=str(Path(folder) / 'results.json'))
        yield base, env
