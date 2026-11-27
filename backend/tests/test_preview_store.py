"""Preview persistence is bounded by age and mtime without touching unrelated files."""

from concurrent.futures import ThreadPoolExecutor
import os
import time

import pytest

from app.core import preview_store as store
from app.core.errors import MustReportError


@pytest.fixture
def previews(tmp_path, monkeypatch):
    directory = tmp_path / 'previews'
    directory.mkdir()
    monkeypatch.setattr(store, 'PREVIEW_DIR', directory)
    return directory


def write_preview(directory, token, age):
    path = directory / f'{token}.json'
    path.write_text('{"fixture": true}', encoding='utf-8')
    mtime = time.time() - age
    os.utime(path, (mtime, mtime))
    return path


def test_load_expires_stale_token_and_save_prunes_only_generated_names(previews):
    expired = write_preview(previews, 'a' * 32, store.PREVIEW_TTL_SECONDS + 60)
    fresh = write_preview(previews, 'b' * 32, store.PREVIEW_TTL_SECONDS - 60)
    unrelated = write_preview(previews, 'fade', store.PREVIEW_TTL_SECONDS + 60)
    with pytest.raises(MustReportError) as error:
        store.load(expired.stem)
    assert str(error.value) == store.EXPIRE_TIP
    assert store.load(fresh.stem) == {'fixture': True}

    token = store.save({'rows': ['新数据']})
    assert not expired.exists()
    assert fresh.is_file() and unrelated.read_text(encoding='utf-8') == '{"fixture": true}'
    assert store.load(token) == {'rows': ['新数据']}


def test_save_evicts_oldest_by_mtime_and_keeps_latest(previews, monkeypatch):
    monkeypatch.setattr(store, 'PREVIEW_MAX_FILES', 2)
    oldest = write_preview(previews, 'f' * 32, 300)
    newer = write_preview(previews, '1' * 32, 60)
    non_file = previews / ('a' * 32 + '.json')
    non_file.mkdir()

    token = store.save({'rows': [3]})
    assert not oldest.exists()
    assert non_file.is_dir()
    assert store.load(newer.stem) == {'fixture': True}
    assert store.load(token) == {'rows': [3]}


def test_concurrent_saves_leave_complete_previews_at_the_cap(previews, monkeypatch):
    monkeypatch.setattr(store, 'PREVIEW_MAX_FILES', 2)
    with ThreadPoolExecutor(max_workers=4) as executor:
        tokens = list(executor.map(lambda n: store.save({'value': n}), range(4)))

    remaining = {path.stem for path in previews.glob('*.json')}
    assert len(remaining) == 2
    assert {store.load(token)['value'] for token in remaining} == {tokens.index(token) for token in remaining}
