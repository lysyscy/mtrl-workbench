"""保存本机使用者的报表偏好，密码由 Windows 当前用户的 DPAPI 密钥保护。"""

import base64
import json
import os
import tempfile
from pathlib import Path

import win32crypt


ROUTES = {f"{name} · {address}": f"http://{address}" for name, address in (
    ("电信", "106.46.169.212:30785"),
    ("联通", "123.7.182.39:30785"),
    ("内网", "192.168.8.80:30785"),
)}


def route_for(saved_url):
    return next((label for label, url in ROUTES.items() if url == saved_url),
                next(iter(ROUTES)))


def protect(password):
    if not password:
        return ""
    data = win32crypt.CryptProtectData(password.encode("utf-8"), "收发结存", None, None, None, 1)
    return base64.b64encode(data).decode("ascii")


def unprotect(encoded):
    if not encoded:
        return ""
    data = base64.b64decode(encoded, validate=True)
    return win32crypt.CryptUnprotectData(data, None, None, None, 1)[1].decode("utf-8")


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
    try:
        temporary.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
