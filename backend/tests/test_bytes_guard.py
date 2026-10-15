"""归档行尾保护文件也必须受编码哨兵检查，未知二进制输入仍拒绝。"""
import importlib.util
from pathlib import Path

from tests.acc_plugin import acc


@acc()
def test_gitattributes_is_checked_and_unknown_binary_still_rejected(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[2] / 'tools/audit/bytes_guard.py'
    spec = importlib.util.spec_from_file_location('bytes_guard_fixture', path)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    monkeypatch.setattr(guard, 'ROOT', tmp_path)
    attr = tmp_path / '.gitattributes'
    attr.write_bytes(b'source/** -text\n')
    assert guard.iter_text() == [attr]
    assert guard.main(['--paths', '.gitattributes']) == 0
    attr.write_bytes(b'\xef\xbf\xbd\n')
    assert guard.main(['--paths', '.gitattributes']) == 1
    (tmp_path / 'unknown.bin').write_bytes(b'plain text')
    assert guard.main(['--paths', 'unknown.bin']) == 1
