"""TAIL-318: HTTP validators on isolated files, through real app middleware."""
from email.utils import formatdate
import os
import time

import pytest
from fastapi.testclient import TestClient

from app import main


@pytest.fixture
def static_client(tmp_path, monkeypatch):
    web = tmp_path / "web"
    (web / "shell").mkdir(parents=True)
    for path in (web / "index.html", web / "shell" / "core.js"):
        path.write_bytes(b"/* isolated static fixture */" * 100)
    monkeypatch.setattr(main, "_APP_DIR", tmp_path)
    with TestClient(main.create_app(), client=("127.0.0.1", 50123)) as client:
        yield client, web


@pytest.mark.parametrize("path", ["/app", "/static/shell/core.js"])
@pytest.mark.parametrize("encoding", ["gzip", "identity"])
def test_conditional_get_precedence_and_headers(static_client, path, encoding):
    client, _ = static_client
    base = {"Accept-Encoding": encoding}
    first = client.get(path, headers=base)
    assert first.status_code == 200
    assert first.headers["cache-control"] == "no-cache"
    assert "Accept-Encoding" in first.headers["vary"]
    etag, date = first.headers["etag"], first.headers["last-modified"]
    assert etag.startswith('W/"')
    conditions = [
        {"If-None-Match": etag},
        {"If-None-Match": etag.removeprefix("W/")},
        {"If-None-Match": '"other", ' + etag},
        {"If-None-Match": "*"},
        {"If-Modified-Since": date},
    ]
    for condition in conditions:
        result = client.get(path, headers={**base, **condition})
        assert result.status_code == 304 and result.content == b""
        for key in ("etag", "last-modified", "cache-control"):
            assert result.headers[key] == first.headers[key]
        # CORS may merge Origin; 304 must preserve the same cache variation as 200.
        assert {token.strip().lower() for token in result.headers["vary"].split(",")} == {
            token.strip().lower() for token in first.headers["vary"].split(",")
        }
        assert "content-length" not in result.headers
        assert "content-encoding" not in result.headers
    for condition in [
        {"If-None-Match": '"other"', "If-Modified-Since": date},
        {"If-None-Match": "", "If-Modified-Since": date},
        {"If-None-Match": 'W/"malformed'},
        {"If-Modified-Since": "invalid"},
        {"If-Modified-Since": formatdate(0, usegmt=True)},
    ]:
        result = client.get(path, headers={**base, **condition})
        assert result.status_code == 200 and result.content == first.content
    other = client.get(path, headers={"Accept-Encoding": "identity" if encoding == "gzip" else "gzip"})
    assert other.content == first.content and other.headers["etag"] == etag


@pytest.mark.parametrize("path,filename", [("/app", "index.html"), ("/static/shell/core.js", "shell/core.js")])
def test_file_changes_and_missing_file_never_304(static_client, path, filename):
    client, web = static_client
    first = client.get(path)
    file = web / filename
    file.write_bytes(b"/* new version, different length */" * 101)
    future = time.time() + 2
    os.utime(file, (future, future))
    updated = client.get(path, headers={"If-None-Match": first.headers["etag"], "If-Modified-Since": first.headers["last-modified"]})
    assert updated.status_code == 200 and updated.content == file.read_bytes()
    assert updated.headers["etag"] != first.headers["etag"]
    assert client.get(path, headers={"If-Modified-Since": first.headers["last-modified"]}).status_code == 200
    file.unlink()
    with pytest.raises(RuntimeError, match="does not exist"):
        client.get(path, headers={"If-None-Match": "*"})


def test_static_validators_do_not_bypass_gates(static_client, monkeypatch):
    client, _ = static_client
    assert client.get("/app").status_code == 200  # existing anonymous read policy
    assert client.post("/app", headers={"If-None-Match": "*"}).status_code == 401
    settings = main.get_settings().model_copy(update={"allowed_ip_cidrs": "127.0.0.0/8"})
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    with TestClient(main.create_app(), client=("203.0.113.1", 50123)) as blocked:
        assert blocked.get("/app", headers={"If-None-Match": "*"}).status_code == 403
    assert client.get("/static/shell/unknown.js", headers={"If-None-Match": "*"}).status_code == 404
    theme = client.get("/static/theme.css", headers={"If-None-Match": "*"})
    assert theme.status_code == 200 and "etag" not in theme.headers
