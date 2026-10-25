"""运行目录迁移的边界：唯一状态、相对cwd、越界与真实收尾。"""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/audit'))
import workspace_paths as W


def test_run_outputs_close_and_release_work(tmp_path, monkeypatch):
    monkeypatch.delenv('MTRL_RUN_ID', raising=False)
    monkeypatch.setenv('MTRL_EFFORT', 'migration-fixture')
    report = W.output('result.json', root=tmp_path)
    report.write_text('verified', encoding='utf-8')
    work = W.output('private.tmp', kind='work', root=tmp_path)
    work.write_text('temporary', encoding='utf-8')
    W.close_runs()
    assert not (tmp_path / '.artifacts/active/migration-fixture').exists()
    archive = tmp_path / '.artifacts/archive/migration-fixture'
    assert list(archive.rglob('result.json'))[0].read_text() == 'verified'
    assert not list(archive.rglob('private.tmp'))
    assert json.loads((archive / 'retention.json').read_text(encoding='utf-8'))['expires_on']


def test_output_rejects_path_traversal(tmp_path, monkeypatch):
    import pytest
    for name in ('../secret', 'D:/secret', 'a\\secret'):
        with pytest.raises(ValueError):
            W.output(name, root=tmp_path)
    monkeypatch.setenv('MTRL_EFFORT', '../bad')
    with pytest.raises(ValueError):
        W.output('result.json', root=tmp_path)


def test_runtime_paths_are_absolute_and_separate(monkeypatch, tmp_path):
    from app.core.config import Settings
    from app.core import preview_store
    from app.mod02_i8 import cookie_store, source_cache, wh_cache
    monkeypatch.chdir(tmp_path)
    settings = Settings(_env_file=None)
    root = Path(__file__).resolve().parents[2]
    assert settings.exports_path == root / 'exports'
    assert settings.logs_path == root / 'var/log'
    assert settings.artifacts_path == root / 'var/data'
    assert preview_store.PREVIEW_DIR == root / 'var/state/import_preview'
    assert cookie_store.CACHE_DIR == root / 'var/state/i8_cookie'
    assert source_cache.DIR == root / 'var/data/i8_source'
    assert wh_cache.CACHE_DIR == root / 'var/cache/i8_warehouse'




def test_stale_runs_and_expired_archives_remain_visible(tmp_path, monkeypatch):
    import audit_work
    import os
    import time
    monkeypatch.setattr(audit_work, 'REPO_ROOT', tmp_path)
    report = tmp_path/'.artifacts/active/fixture/old/reports/result.json'
    report.parent.mkdir(parents=True)
    report.write_text('{}')
    old = time.time() - 15 * 86400
    os.utime(report, (old, old))
    archive = tmp_path/'.artifacts/archive/fixture'
    archive.mkdir(parents=True)
    (archive/'retention.json').write_text('{"reason":"fixture", "expires_on":"2000-01-01"}')
    hits = audit_work.check_scratch_ttl()
    assert any(h['rel'].endswith('result.json') for h in hits)
    assert any(h['rel'] == '.artifacts/archive/fixture' for h in hits)
