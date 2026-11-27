"""离线工具：归档行尾保护文件受编码检查，未知二进制输入仍拒绝。"""
import importlib.util
from pathlib import Path



def load_guard(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[2] / 'tools/audit/bytes_guard.py'
    spec = importlib.util.spec_from_file_location('bytes_guard_fixture', path)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    monkeypatch.setattr(guard, 'ROOT', tmp_path)
    return guard


def test_gitattributes_is_checked_and_unknown_binary_still_rejected(tmp_path, monkeypatch):
    guard = load_guard(tmp_path, monkeypatch)
    attr = tmp_path / '.gitattributes'
    attr.write_bytes(b'source/** -text\n')
    assert guard.iter_text() == [attr]
    assert guard.main(['--paths', '.gitattributes']) == 0
    attr.write_bytes(b'\xef\xbf\xbd\n')
    assert guard.main(['--paths', '.gitattributes']) == 1
    (tmp_path / 'unknown.bin').write_bytes(b'plain text')
    assert guard.main(['--paths', 'unknown.bin']) == 1


def test_full_scan_skips_only_generated_frontend_dist(tmp_path, monkeypatch):
    guard = load_guard(tmp_path, monkeypatch)
    mixed = b'<html>\r\n</html>\n'
    generated = tmp_path / 'apps/frontend/dist/index.html'
    generated.parent.mkdir(parents=True)
    generated.write_bytes(mixed)
    source = tmp_path / 'apps/frontend/src/index.html'
    source.parent.mkdir()
    source.write_bytes(mixed)

    assert guard.iter_text() == [source]
    assert guard.main([]) == 1
    source.write_bytes(b'<html>\n</html>\n')
    assert guard.main([]) == 0
    assert guard.main(['--paths', 'apps/frontend/dist/index.html']) == 1
