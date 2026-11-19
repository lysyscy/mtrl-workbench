"""单机收发结存。所有项目编号来自本次登录的常用项目名单。"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from zipfile import is_zipfile
from io import BytesIO

import httpx
from gmssl.sm2 import CryptSM2

from app.core.config import I8_PATH_COMMON_PROJECT, I8_PATH_REPORT_EXPORT
from app.mod02_i8.login import login_at
from app.mod02_i8.report_export import build_body, single_month
from app.mod07_setl.importer import parse_rows
from app.report_export.setl_export import build_zip

ASSETS = Path(__file__).resolve().parent / "assets"
GUIDE = "请先在 i8 的项目选择窗口，将本月要报的项目加入「常用项目」。回到这里点「刷新常用项目」，核对名单后生成。"


def site_address(text):
    url = urlsplit(text.strip())
    if (url.scheme not in ("http", "https") or not url.hostname or url.username is not None
            or url.password is not None or url.query or url.fragment):
        raise ValueError("请填写 i8 登录站点地址，例如 https://i8.example.com。")
    return f"{url.scheme}://{url.netloc}"


def connect(site, user, password):
    if not user.strip():
        raise ValueError("请填写 i8 账号。")
    public = (ASSETS / "public.txt").read_text(encoding="ascii").strip()
    cipher = CryptSM2(private_key="", public_key=public, mode=1)
    result = login_at(site, user.strip(), password, allow_kick=True, follow_redirects=False,
                      encrypt=lambda text: cipher.encrypt(text.encode("utf-8")).hex())
    if not result.ok or not result.cookie:
        raise ValueError("登录未成功。请核对 i8 地址、账号、密码，以及当前网络能否打开 i8。")
    return httpx.Client(base_url=site, timeout=httpx.Timeout(120, connect=12),
                        headers={"Cookie": result.cookie, "X-Requested-With": "XMLHttpRequest",
                                 "User-Agent": "Mozilla/5.0"}, follow_redirects=False)


def projects(client):
    response = client.get(I8_PATH_COMMON_PROJECT)
    response.raise_for_status()
    try:
        data = response.json()
    except ValueError:
        raise ValueError("i8 返回了登录页或无法识别的项目名单，请重新连接。") from None
    if isinstance(data, dict):
        if data.get("Success") is False or data.get("success") is False:
            raise ValueError("i8 未返回常用项目，请重新连接并核对账号权限。")
        rows = next((data[k] for k in ("Record", "record", "records", "data", "list", "rows")
                     if isinstance(data.get(k), list)), None)
        total = data.get("totalRows")
        if total is not None and rows is not None and int(total) > len(rows):
            raise ValueError("i8 只返回了部分项目，请核对常用项目名单后刷新。")
    else:
        rows = data
    if not isinstance(rows, list):
        raise ValueError("i8 返回的项目名单格式异常，请核对登录状态后刷新。")
    found = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("常用项目名单格式异常，请刷新。")
        key = str(row.get("PhId") or row.get("phid") or row.get("ProjectId") or "").strip()
        name = str(row.get("BillName") or row.get("ProjectName") or row.get("Name") or "").strip()
        if not key.isascii() or not key.isdecimal() or not name:
            raise ValueError("有常用项目缺少有效编号或名称，请在 i8 核对后刷新。")
        if key in found and found[key] != name:
            raise ValueError("i8 返回了编号相同、名称不同的项目，请核对后刷新。")
        found[key] = name
    return found


def validate_name(name):
    if (not name or name in (".", "..") or re.search(r'[<>:"/\\|?*\x00-\x1f]', name)
            or os.path.isreserved(name)):
        raise ValueError(f"「{name}」不能用作 Windows 文件名，请核对名称。")


def generate(client, month, keys, company, destination):
    if not keys:
        raise ValueError(GUIDE)
    year, number, _, _ = single_month(month)
    label = f"{year}年{number}月"
    validate_name(company)
    body = build_body(spec_key="setl", year_month=month, proj_ids=",".join(keys))
    response = client.post(I8_PATH_REPORT_EXPORT, json=body)
    response.raise_for_status()
    if not is_zipfile(BytesIO(response.content)):
        raise ValueError("i8 未返回 Excel 报表，请重新连接并核对报表权限。")
    rows = parse_rows(response.content, ym=month)
    if not rows:
        raise ValueError("所选月份和项目没有收发结存明细。请核对核算月及 i8 常用项目。")
    warehouses = dict.fromkeys(row["warehouse_name"] for row in rows)
    names = {"_work", f"{company}{label}收发结存表".casefold()}
    for name in warehouses:
        validate_name(name)
        if name.casefold() in names:
            raise ValueError(f"仓库「{name}」会产生同名文件，请核对仓库名称。")
        names.add(name.casefold())
    with tempfile.TemporaryDirectory() as scratch:
        package = build_zip(rows, scratch, label, company=company, template=ASSETS / "layout.xlsx")
        # 只在成品核对通过且完整写入后替换用户选定的文件。
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as staging:
            staged = Path(staging.name)
        try:
            shutil.copyfile(package, staged)
            os.replace(staged, destination)
        finally:
            staged.unlink(missing_ok=True)
    return len(warehouses), len(rows)
