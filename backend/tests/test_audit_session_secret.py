"""临时密钥仅用假配置与临时文件，真实 .env 和账号不参与。"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core import config, session


@pytest.fixture
def isolated_secret(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    settings = SimpleNamespace(session_secret="")
    monkeypatch.setattr(config, "get_settings", lambda: settings)
    monkeypatch.setattr(session, "_env_path", lambda: env_file)
    monkeypatch.setattr(session, "_temporary_secret", None, raising=False)
    write = Path.write_text

    def deny_env_write(path, *args, **kwargs):
        if path == env_file:
            raise PermissionError("isolated read-only configuration")
        return write(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", deny_env_write)
    return env_file, settings


def test_unwritable_config_keeps_multiple_tickets_valid(isolated_secret):
    first = session.make("audit.first")
    second = session.make("audit.second")
    assert session.read(first) == "audit.first"
    assert session.read(second) == "audit.second"
    assert session.read(first[:-1] + ("A" if first[-1] != "A" else "B")) is None
    assert not isolated_secret[0].exists()


def test_parallel_first_logins_share_temporary_secret(isolated_secret):
    accounts = ["audit.first", "audit.second"]
    with ThreadPoolExecutor(max_workers=2) as workers:
        tickets = list(workers.map(session.make, accounts))
    assert [session.read(ticket) for ticket in tickets] == accounts


@pytest.mark.parametrize("source", ["settings", "file"])
def test_existing_secret_takes_priority_over_temporary(isolated_secret, source):
    env_file, settings = isolated_secret
    temporary_ticket = session.make("audit.first")
    if source == "settings":
        settings.session_secret = "isolated-configured-key"
    else:
        env_file.write_bytes(b"SESSION_SECRET=isolated-file-key\n")
    assert session.read(temporary_ticket) is None
    ticket = session.make("audit.second")
    assert session.read(ticket) == "audit.second"
