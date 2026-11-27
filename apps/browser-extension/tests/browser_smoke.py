"""用独立 Chromium profile 验证交付扩展协议及真实工作台的抓取、打印和导出入口。

⚠️ 这个脚本能证明什么、不能证明什么（读完再引用结论）：

  能证明（真实浏览器、真实扩展加载）：
    1. MV3 扩展能被未打包加载，`manifest.key` 推出的扩展 ID 就是工作台硬编码的
       `jfkgliolimmpceandogfimjkadplidem`；
    2. `externally_connectable` 真的生效：列进去的 origin 能 `chrome.runtime.sendMessage`
       进扩展，没列进去的 origin 进不来；
    3. i8 标签没有账号菜单时，扩展仍能读取站点来源、建立连接并取数；
    4. 注入脚本里的 `fetch` 沿页面 origin 发出、`credentials:'same-origin'` 生效；
       跳转在真机上是**不透明响应**（`redirect:'manual'` 给 `opaqueredirect`、status 0、
       读不到 Location）⇒ 一律停下，读不出"跳到哪了"（这一点原来是替身伪造的，
       是这台真浏览器把它纠正过来的）；
    5. 端点白名单在真浏览器里同样拦住登录/强踢/保存/伪装地址，服务器上一条记录都没有；
    6. **HttpOnly 会话 Cookie 的真实行为**（主控在隔离 Chromium 里已证明过一次，这里固化成
       判据）：i8 站点种下的 `HttpOnly` Cookie 由浏览器**自动携带**在同源 fetch 上（页面脚本
       一个字都不用碰）；`document.cookie` **读不到**它；页面手工塞 `Cookie` 头会被浏览器
       **过滤**（服务端看到的是浏览器自己的那份，不是页面写的）。这正是本通道"不导出、
       不解密、不读 Cookie 也能复用会话"的机制基础。
    7. 原入口的自动接入、等待取消、签名制单、整批 A4 闸门，以及原批恢复和投递回执。

  不能证明（⛔ 别拿它当验收）：
    - 不是 Edge：这里是 Chromium（`ms-playwright/chromium-1248`），Edge 上的实际行为未验；
    - 不是真实 i8：所有地址都是本机假页面与假接口，无真实业务数据；
    - activeTab 的浏览器工具栏点击仍需现场验证。样机使用交付清单中的可选站点权限。
    - 不碰用户 profile、不连真实 i8、不装新依赖、不改系统设置。

用法（只用仓库里已有的运行时）：

    backend/.venv/Scripts/python.exe -B -X utf8 apps/browser-extension/tests/browser_smoke.py --source-env <来源.env>

真实工作台使用已登记的空白测试 schema，i8 和 IPP 均为本机替身。
交付扩展原样加载，工作台使用清单已允许的 127.0.0.1:8065；端口占用时直接退出。

退出码：0 = 全部判据通过；1 = 有判据不通过（打印哪一条）。
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
from contextlib import ExitStack, contextmanager
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from time import monotonic, sleep
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[3]
EXT_DIR = ROOT / "apps" / "browser-extension"
EXT_ID = "jfkgliolimmpceandogfimjkadplidem"

BILL_NOS = ("SMOKE-1", "SMOKE-2", "SMOKE-3")
FAKE_RECORD = {
    "PhidRecPayType_EXName": "其他支出",
    "PhidPc_EXName": "样机项目",
    "AppStatus": 1,
    "ApproveAmt": "12345.67",
    "BillDt": datetime.now(timezone(timedelta(hours=8))).date().isoformat(),
    "PhidBusType_EXName": "付材料款",
    "Remark": "样机用假数据",
}
FAKE_BODY = json.dumps({"Success": True, "Record": [
    dict(FAKE_RECORD, PhId=bill_no, BillNo=bill_no) for bill_no in BILL_NOS
]}, ensure_ascii=False).encode("utf-8")

# 假会话 Cookie：真 i8 的会话是 HttpOnly 的。值带哨兵前缀，方便在服务端日志里辨认。
HTTPONLY_NAME = "MTRLSESSION"
HTTPONLY_VALUE = "httponly-sentinel-9f3a"
FORGED_COOKIE = "forged-by-page-should-be-dropped"

# 服务器收到过的每一条请求（用来证明"被拦的请求一个字节都没出去"）。
RECEIVED: list[dict] = []
BATCH_PATH = "/api/m03/print-batches"
IPP_REQUESTS: list[tuple[int, dict, bytes]] = []
BLOCK_A4 = threading.Event()
BLOCK_A4.set()
BAD_SIGNATURE = threading.Event()
HOLD_SECOND_PRINT = threading.Event()
SECOND_PRINT_RECEIVED = threading.Event()
# Synthetic 32 × 16 grayscale image, above the signature reader's minimum valid size.
SIGNATURE_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAQCAAAAABSayKFAAAARklEQVR4nI2QQQ4AIAjD9oT+/7N40og6hCNr0oEg8hwL"
    "ffJQmQYswKlkk0thwNzhgcnbNwUF0gEaik9JF80zu4/yry4bwABZGMb7NPN+DAAAAABJRU5ErkJggg=="
)

WORKBENCH_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>工作台（样机）</title></head>
<body><p>workbench</p>
<script>
  window.__relay = (message) => new Promise((resolve) => {
    try {
      chrome.runtime.sendMessage("%s", message, (reply) => {
        const failed = chrome.runtime.lastError;
        resolve(reply === undefined ? { ok: false, message: String(failed && failed.message) } : reply);
      });
    } catch (error) {
      resolve({ ok: false, message: String(error && error.message) });
    }
  });
</script>
</body></html>
""" % (EXT_ID,)

I8_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>i8 业务页（样机）</title></head>
<body><p>i8 业务页</p></body></html>
"""


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # 静音：样机输出只留判据
        pass

    def _send(self, status: int, body: bytes, content_type: str = "application/json;charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        url = urlsplit(self.path)
        i8 = self.headers.get("Host") == urlsplit(I8_ORIGIN).netloc
        if i8 and url.path == "/":
            self._send(200, I8_HTML.encode("utf-8"), "text/html;charset=utf-8")
            return
        if self.path == "/workbench":
            self._send(200, WORKBENCH_HTML.encode("utf-8"), "text/html;charset=utf-8")
            return
        if url.path == "/i8/business":
            # 种一个 **HttpOnly** 会话 Cookie：真 i8 的会话就是这种形态。
            # 页面脚本读不到它，但浏览器会在同源 fetch 上自动带上 —— 本通道复用会话靠的就是这个。
            body = I8_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html;charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header(
                "Set-Cookie", f"{HTTPONLY_NAME}={HTTPONLY_VALUE}; Path=/; HttpOnly; SameSite=Lax"
            )
            self.end_headers()
            self.wfile.write(body)
            return
        if url.path == "/SUP/RichHelp/GetCommonUseList" and url.query:
            if HTTPONLY_VALUE in self.headers.get("Cookie", ""):
                self._json({"Record": []})
            elif f"{HTTPONLY_NAME}=expired" in self.headers.get("Cookie", ""):
                self._json({"Code": "200", "Success": False, "Msg": "No SessionInfo found"})
            else:
                self.send_response(302)
                self.send_header("Location", f"{I8_ORIGIN}/login")
                self.send_header("Content-Length", "0")
                self.end_headers()
            return
        if url.path == "/login":
            self._send(200, b"<title>Login</title>", "text/html;charset=utf-8")
            return
        if self.path == "/SUP/RichHelp/GetCommonUseList":
            RECEIVED.append({"method": "GET", "path": self.path, "headers": dict(self.headers)})
            self.send_response(302)
            self.send_header("Location", f"{I8_ORIGIN}/i8/business")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if url.path.endswith(("/getPrintDesign", "/getFlowHisForPrint")) or url.path.startswith("/sig/"):
            self._i8_business("GET", url, b"")
            return
        self._send(404, b"{}")

    def _i8_business(self, method, url, body):
        RECEIVED.append({"method": method, "path": url.path, "headers": dict(self.headers),
                         "body": body.decode("utf-8", "replace")})
        if HTTPONLY_VALUE not in self.headers.get("Cookie", ""):
            self._send(401, b"{}")
            return
        if url.path.endswith(("/getList", "/GetCntMList")):
            self._send(200, FAKE_BODY)
        elif url.path.endswith("/getPrintDesign"):
            from tests.m03_helpers import sign_cell, text_cell

            sheet = {
                "cells": [text_cell(0, 0, "Isolated payment notice"),
                          sign_cell(0, 1, "项目经理"), sign_cell(0, 2, "未到达节点")],
                "globalSettings": {"cols": 3, "rows": 1},
            }
            margins = {"top": 5, "left": 5, "right": 5, "down": 5}
            self._json({"Data": {"printSchema": json.dumps([sheet]),
                                "printSetting": json.dumps([{"printConfig": {"margin": margins}}])}})
        elif url.path.endswith("/getInfo"):
            self._json({"Data": {"BillNo": parse_qs(body.decode())["id"][0]}})
        elif url.path.endswith("/getDetInfo"):
            self._json({"Record": [{"ApplyAmt": 5}]})
        elif url.path.endswith("/getFlowHisForPrint"):
            ph_id = parse_qs(url.query)["bizPk"][0]
            self._json({"data": [{"task_des": "项目经理", "signature": f"/sig/{ph_id}.png?s=smoke"}]})
        elif url.path.startswith("/sig/"):
            if BAD_SIGNATURE.is_set() and url.path == "/sig/SMOKE-2.png":
                self._send(200, b"invalid signature", "image/png")
            else:
                self._send(200, SIGNATURE_PNG, "image/png")
        else:
            self._send(404, b"{}")

    def do_POST(self):  # noqa: N802
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        url = urlsplit(self.path)
        if url.path == "/ipp/print":
            self._ipp(body)
        else:
            self._i8_business("POST", url, body)

    def _ipp(self, body):
        operation, attributes, pdf = decode_ipp(body)
        IPP_REQUESTS.append((operation, attributes, pdf))
        if operation == 0x0004:
            status = 0x040B if BLOCK_A4.is_set() else 0
            tail = ipp_message("A4 unavailable on smoke printer") if status else b""
        else:
            assert operation == 0x0002
            attempt = sum(op == 0x0002 for op, _, _ in IPP_REQUESTS)
            status = 0
            tail = b"\x02\x21\x00\x06job-id\x00\x04" + (100 + attempt).to_bytes(4, "big")
            if attempt == 2:
                SECOND_PRINT_RECEIVED.set()
                assert HOLD_SECOND_PRINT.wait(15), "did not observe reload during dispatch"
                self.close_connection = True
                return
            if attempt == 3:
                status, tail = 0x040B, ipp_message("queue rejected third notice")
        self._send(200, struct.pack(">BBH", 1, 1, status) + body[4:8] + tail + b"\x03", "application/ipp")

    def _json(self, value):
        self._send(200, json.dumps(value).encode("utf-8"))


def decode_ipp(body):
    _, _, operation, _ = struct.unpack_from(">BBHI", body)
    cursor, group = 8, 0
    attributes = {}
    while (tag := body[cursor]) != 3:
        cursor += 1
        if tag < 0x10:
            group = tag
            continue
        size = int.from_bytes(body[cursor:cursor + 2], "big")
        name = body[cursor + 2:cursor + 2 + size]
        cursor += 2 + size
        size = int.from_bytes(body[cursor:cursor + 2], "big")
        attributes[name] = group, tag, body[cursor + 2:cursor + 2 + size]
        cursor += 2 + size
    return operation, attributes, body[cursor + 1:]


def ipp_message(message):
    value = message.encode()
    return b"\x01\x41\x00\x0estatus-message" + len(value).to_bytes(2, "big") + value


def free_port(start: int = 8071) -> int:
    for port in range(start, start + 40):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError("找不到空闲端口")


PORT = free_port()
ORIGIN = "http://127.0.0.1:8065"
FORBIDDEN_ORIGIN = f"http://127.0.0.1:{PORT}"
I8_ORIGIN = f"http://localhost:{PORT}"
OTHER_ORIGIN = f"http://127.0.0.1:{PORT + 1}"


FAILURES: list[str] = []
CHECKS: list[str] = []

# 与工作台页面 / 后端共用的消息形状（closure 第 3 节）：连接按 `device_id` 隔离，
# `bind` 必须带服务端给的正整数 `generation`。⛔ 字段名别改。
DEVICE = "dev-smoke-1"
GENERATION = 1


def check(name: str, ok: bool, detail: object = "") -> None:
    CHECKS.append(name)
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f" —— {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(name)


def build_frontend(target: Path) -> None:
    frontend = ROOT / "apps" / "frontend"
    subprocess.run(
        ["node", "node_modules/vite/bin/vite.js", "build", "--configLoader", "runner", "--outDir", str(target)],
        cwd=frontend, env={**os.environ, "MTRL_FRONTEND_BASE": "/app/"},
        check=True, capture_output=True, encoding="utf-8",
    )


def worker_ids(context) -> list[str]:
    """`chrome-extension://<id>/service_worker.js` ⇒ 取中间的 <id>。"""
    return [worker.url.split("/")[2] for worker in context.service_workers if "/" in worker.url]


def page_message(page, message: dict):
    return page.evaluate("message => window.__relay(message)", message)


def identity_message(device=DEVICE, **extra):
    return {"type": "i8-relay:identity", "device_id": device, "origin": I8_ORIGIN, **extra}


def notice_flow(context, protocol_page):
    app = context.new_page()
    app.set_default_timeout(15_000)
    app.goto(f"{ORIGIN}/app/notices")
    submitted = []
    prepare = []
    dispatch = []

    fetch_jobs = "/api/m03/notices/fetch-jobs"

    def completed_fetch(response):
        assert response.status == 202, response.status
        job = response.json()
        app.bring_to_front()
        result_dialog = app.get_by_role("dialog", name="付款通知书抓取完成", exact=True)
        result_dialog.wait_for()
        final = app.request.get(f"{ORIGIN}{fetch_jobs}/{job['id']}").json()
        assert final["status"] == "completed", final
        result_dialog.get_by_role("button", name="关闭", exact=True).click()
        result_dialog.wait_for(state="hidden")
        return final["result"]

    def observe(request):
        if request.method != "POST":
            return
        path = urlsplit(request.url).path
        if path == fetch_jobs:
            submitted.append(request.post_data_json)
        elif path == BATCH_PATH + "/prepare":
            prepare.append(request.post_data_json)
        elif path.startswith(BATCH_PATH + "/") and path.endswith("/dispatch"):
            dispatch.append(path)

    app.on("request", observe)
    app.get_by_role("button", name="按月抓取 i8", exact=True).click()
    app.get_by_role("button", name="确认抓取", exact=True).click()
    app.get_by_text("请授权工作台扩展访问当前 i8 站点", exact=False).wait_for()
    check("确认后缺权限时等待，当前没有 i8 标签或业务提交", app.get_by_role("button", name="取消等待").is_visible()
          and not [tab for tab in context.pages if tab.url.startswith(I8_ORIGIN)] and not submitted)

    with context.expect_page() as opened:
        app.get_by_role("button", name="授权 i8 站点").click()
    permission = opened.value
    permission.get_by_role("button", name="授权此站点").wait_for()
    permission.wait_for_function("() => !document.querySelector('button').disabled")
    check("授权页只显示工作台当前配置站点", permission.locator("#origin").inner_text() == I8_ORIGIN)
    # Headless Playwright cannot accept browser-chrome dialogs. Exercise the same
    # site consent through Chromium's settings before clicking the real request button.
    settings = context.new_page()
    settings.goto("chrome://extensions/")
    settings.evaluate("""async ({id, origin}) => {
        await chrome.developerPrivate.addHostPermission(id, origin + '/*');
    }""", {"id": EXT_ID, "origin": I8_ORIGIN})
    settings.close()
    permission.bring_to_front()
    with permission.expect_event("close", timeout=5000):
        permission.get_by_role("button", name="授权此站点").click()
    app.bring_to_front()
    worker = context.service_workers[0]
    origins = worker.evaluate("async () => (await chrome.permissions.getAll()).origins")
    check("使用交付清单的可选站点权限完成授权", origins == [I8_ORIGIN + "/*"], origins)

    # Two additional callers race the actual dialog's retry with the same configured site.
    protocol_page.evaluate(
        "messages => Promise.all(messages.map(window.__relay))",
        [identity_message(f"dev-concurrent-{index}", openIfMissing=True) for index in range(3)],
    )
    app.get_by_text("请在 i8 标签页登录", exact=False).first.wait_for()
    i8_tabs = [tab for tab in context.pages if tab.url.startswith(I8_ORIGIN)]
    check("并发尝试只后台打开一张 i8 页，工作台仍有焦点", len(i8_tabs) == 1
          and app.evaluate("() => document.hasFocus()"), [tab.url for tab in i8_tabs])
    check("探测遇到未登录跳转时没有提交或跟随登录跳转", not submitted and i8_tabs[0].url == I8_ORIGIN + "/")
    i8 = i8_tabs[0]
    with app.expect_response(lambda res: urlsplit(res.url).path == fetch_jobs and res.request.method == "POST") as fetched:
        i8.goto(f"{I8_ORIGIN}/i8/business")
    receipt = completed_fetch(fetched.value)
    app.get_by_role("dialog").wait_for(state="hidden")
    notice_hits = [hit for hit in RECEIVED if hit["path"] == "/FC/FM/PaymentBill/getList"]
    check("登录后无需再次确认，原工作台只抓取一次并写入三条", len(submitted) == len(notice_hits) == 1
          and submitted[0]["expected_account"] == "smoke" and receipt.get("upserted") == 3, receipt)
    app.get_by_role("button", name="按月抓取 i8", exact=True).click()
    app.get_by_role("button", name="确认抓取", exact=True).wait_for()

    # A login page and a healthy page share the origin. Only the healthy page can satisfy the probe.
    login_tab = context.new_page()
    login_tab.goto(f"{I8_ORIGIN}/login")
    i8.bring_to_front()
    app.bring_to_front()
    multi = page_message(protocol_page, identity_message())
    check("两个同站标签自动选可用会话，未点扩展图标", multi.get("sessionReady") is True, multi)

    # Discard the currently bound tab and leave a usable tab on the configured origin.
    replacement = context.new_page()
    replacement.goto(f"{I8_ORIGIN}/i8/business?replacement=1")
    app.bring_to_front()
    device = submitted[0]["device_id"]
    discarded = worker.evaluate("""async (device) => {
        const key = 'i8RelayBound:' + device;
        const {[key]: binding} = await chrome.storage.session.get(key);
        return (await chrome.tabs.discard(binding.tabId))?.discarded;
    }""", device)
    check("真实 Chromium 已释放原绑定标签", discarded)
    with app.expect_response(lambda res: urlsplit(res.url).path == fetch_jobs and res.request.method == "POST") as fetched:
        app.get_by_role("button", name="确认抓取", exact=True).click()
    state = app.request.get(ORIGIN + "/api/m02/browser/state", params={"device_id": device}).json()
    completed_fetch(fetched.value)
    app.get_by_role("dialog").wait_for(state="hidden")
    check("已登录会话及标签释放时均无需点扩展，仅提交本次确认", len(submitted) == 2
          and state["generation"] > 1 and fetched.value.ok, state)
    app.get_by_role("button", name="按月抓取 i8", exact=True).click()

    # The next confirmation probes the existing binding. Simulate i8's JSON expiry response.
    context.add_cookies([{"name": HTTPONLY_NAME, "value": "expired", "url": I8_ORIGIN, "httpOnly": True}])
    app.get_by_role("button", name="确认抓取", exact=True).click()
    app.get_by_text("请在 i8 标签页登录", exact=False).first.wait_for()
    app.get_by_role("button", name="取消等待", exact=True).click()
    with app.expect_response(lambda res: res.url.endswith("/api/m02/browser/connect") and res.ok):
        replacement.goto(f"{I8_ORIGIN}/i8/business")
    check("取消等待后，迟到的登录恢复没有再次提交", len(submitted) == 2)
    app.get_by_role("dialog").get_by_role("button", name="取消", exact=True).click()
    print_flow(app, replacement, device, prepare, dispatch)
    app.close()
    login_tab.close()
    return replacement


def assert_pdf(content):
    from pypdf import PdfReader

    pdf = PdfReader(io.BytesIO(content))
    page, = pdf.pages
    assert abs(float(page.mediabox.width) - 595.3) < 2
    assert abs(float(page.mediabox.height) - 841.9) < 2
    text = page.extract_text()
    assert "Isolatedpaymentnotice" in "".join(text.split()), text
    assert len(page.images) == 1, "The relayed signature did not reach the rendered PDF"


def print_flow(app, i8, device, prepare, dispatch):
    def open_dialog(name):
        app.get_by_role("button", name=name, exact=True).click()
        return app.get_by_role("dialog")

    def confirm(dialog):
        dialog.get_by_role("button", name="确认本批", exact=True).click()

    def expire():
        app.context.add_cookies([{"name": HTTPONLY_NAME, "value": "expired",
                                  "url": I8_ORIGIN, "httpOnly": True}])

    def sign_in():
        i8.goto(I8_ORIGIN + "/i8/business")

    first = app.get_by_role("checkbox", name="勾选" + BILL_NOS[0], exact=True)
    first.check()
    dialog = open_dialog("导出 PDF")
    expire()
    confirm(dialog)
    dialog.get_by_text("请在 i8 标签页登录", exact=False).wait_for()
    dialog.get_by_role("button", name="取消等待").click()
    with app.expect_response(lambda res: res.url.endswith("/api/m02/browser/connect") and res.ok):
        sign_in()
    check("PDF 取消等待后，迟到就绪未发起准备", not prepare and not IPP_REQUESTS)

    expire()
    confirm(dialog)
    dialog.get_by_text("请在 i8 标签页登录", exact=False).wait_for()
    with app.expect_response(lambda res: urlsplit(res.url).path.startswith("/api/m03/pdf/") and res.ok) as downloaded:
        sign_in()
    dialog.get_by_text("已生成 1 / 共 1 条", exact=False).wait_for()
    assert_pdf(downloaded.value.body())
    check("导出自动续接一次，实际 PDF 含签名和 A4 页，未投递",
          len(prepare) == 1 and prepare[0]["mode"] == "pdf" and not IPP_REQUESTS)
    dialog.get_by_role("button", name="关闭", exact=True).first.click()
    dialog.wait_for(state="hidden")

    app.get_by_role("checkbox", name="全选当前筛选结果").click()
    app.get_by_text("已勾选 3 行", exact=False).wait_for()
    dialog = open_dialog("批量打印")
    expire()
    BAD_SIGNATURE.set()
    confirm(dialog)
    dialog.get_by_text("请在 i8 标签页登录", exact=False).wait_for()
    check("打印等待同一浏览器登录态时零提交", len(prepare) == 1)
    sign_in()
    dialog.get_by_role("alert").filter(has_text="已投递 0 张").wait_for()
    check("第二张签名失败拦停整批，零 IPP 请求及零投递",
          "SMOKE-2" in dialog.get_by_role("alert").inner_text()
          and "签名" in dialog.get_by_role("alert").inner_text()
          and len(prepare) == 2 and not dispatch and not IPP_REQUESTS)

    BAD_SIGNATURE.clear()
    dialog.get_by_role("button", name="重试全批", exact=True).click()
    blocked = dialog.get_by_role("alert").filter(has_text="无法确认本批按 A4 出纸")
    blocked.wait_for()
    assert "A4 unavailable on smoke printer" in blocked.inner_text(), blocked.inner_text()
    check("A4 拒绝时保留设备原因，零打印作业", [op for op, _, _ in IPP_REQUESTS] == [4])
    check("打印和导出沿用抓取的浏览器连接标识，所有业务请求携带同一 HttpOnly 会话",
          len(prepare) == 3 and len(dispatch) == 1
          and all(item["device_id"] == device and item["session_mode"] == "browser" for item in prepare)
          and all(HTTPONLY_VALUE in hit["headers"].get("Cookie", "") for hit in RECEIVED)
          and len([hit for hit in RECEIVED if hit["path"].startswith("/sig/")]) == 6,
          [hit["path"] for hit in RECEIVED])

    BLOCK_A4.clear()
    with app.expect_response(lambda res: res.url.endswith("/dispatch") and res.ok) as started:
        dialog.get_by_role("button", name="使用此 IPP 地址打印本批", exact=True).click()
    batch = started.value.json()
    batch_url = ORIGIN + BATCH_PATH + "/" + batch["batch_id"]
    assert SECOND_PRINT_RECEIVED.wait(10), "second Print-Job did not reach IPP stub"
    try:
        with app.expect_response(lambda res: res.url == batch_url and res.request.method == "GET") as recovered:
            app.reload()
        assert recovered.value.json()["batch_id"] == batch["batch_id"]
        app.get_by_text("投递打印机 1/3", exact=False).wait_for()
        app.get_by_text("作业号 101", exact=False).first.wait_for()
    finally:
        HOLD_SECOND_PRINT.set()
    receipts = app.get_by_role("region", name="逐张投递回执")
    receipts.get_by_text(f'{batch["items"][1]["bill_no"]}：结果待核实', exact=False).wait_for()
    receipts.get_by_text("queue rejected third notice", exact=False).wait_for()
    with app.expect_response(lambda res: res.url == batch_url and res.request.method == "GET") as recovered:
        app.reload()
    final = recovered.value.json()
    check("投递中和完成后刷新均恢复同批，保留三种逐张回执及设备原因",
          final["batch_id"] == batch["batch_id"] and final["status"] == "complete"
          and [(item["delivery_status"], item["job_id"]) for item in final["items"]]
          == [("accepted", 101), ("unknown", None), ("failed", None)]
          and "queue rejected third notice" in final["items"][2]["attempts"][0]["reason"],
          final)
    # Even an explicit retry of the same HTTP dispatch can only read its existing result.
    replay = app.request.post(batch_url + "/dispatch").json()
    check("重复投递原批只返回原回执，接收未知时零重投",
          replay == final and len(prepare) == 3 and len(dispatch) == 2
          and [op for op, _, _ in IPP_REQUESTS] == [4, 4, 2, 2, 2])
    check("真实发送的校验和逐张投递显式要求 A4 与属性严格匹配",
          all(attrs[b"media"] == (2, 0x44, b"iso_a4_210x297mm")
              and attrs[b"ipp-attribute-fidelity"] == (1, 0x22, b"\x01")
              and attrs[b"document-format"] == (1, 0x49, b"application/pdf")
              and (pdf.startswith(b"%PDF") if op == 2 else not pdf) for op, attrs, pdf in IPP_REQUESTS))


@contextmanager
def isolated_workbench(source_env, frontend):
    """Serve the real application on an allowlisted loopback origin in an empty test schema."""
    sys.path[:0] = [str(ROOT), str(ROOT / "backend")]
    from tools.audit.workspace_paths import close_runs, development_run
    from tools.dev.frontend_preview import isolated_database

    success = False
    with socket.socket() as listener:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        listener.bind(("127.0.0.1", urlsplit(ORIGIN).port))
        listener.listen()
        development_run()
        try:
            with isolated_database(source_env, preview=False) as env:
                env.update(ALLOWED_IP_CIDRS="127.0.0.1/32", FRONTEND_APP_DIR=str(frontend),
                           I8_BASE_URL=I8_ORIGIN, I8_PRINT_ID_MATERIAL="isolated-template",
                           PRINT_MODE="auto", PRINTER_IPP_URL=f"ipp://127.0.0.1:{PORT}/ipp/print")
                with patch.dict(os.environ, env):
                    from fastapi.responses import HTMLResponse
                    from uvicorn import Config, Server
                    from app.core.db import session_scope
                    from app.core.session import COOKIE_NAME, make
                    from app.main import create_app
                    from app.mod01_projects.models import Project
                    from app.mod15_user.models import UserAccount

                    app = create_app()
                    with session_scope() as db:
                        db.add(UserAccount(account="smoke", name="隔离验收", role="admin", i8_user="i8-smoke"))
                        db.add(Project(project_type="normal", name_full="样机项目", warehouse_name="样机仓库", disp="样机项目"))

                    @app.get("/workbench", response_class=HTMLResponse)
                    def protocol_page():
                        return WORKBENCH_HTML

                    server = Server(Config(app, access_log=False, log_level="warning"))
                    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
                    thread.start()
                    try:
                        deadline = monotonic() + 10
                        while not server.started and thread.is_alive() and monotonic() < deadline:
                            sleep(0.05)
                        assert server.started, "isolated workbench did not start"
                        yield {"name": COOKIE_NAME, "value": make("smoke"), "url": ORIGIN, "httpOnly": True}
                    finally:
                        server.should_exit = True
                        thread.join(timeout=15)
                        assert not thread.is_alive(), "isolated workbench did not stop"
            success = not FAILURES
        finally:
            close_runs(success=success)


def boot(p, extension_dir: Path, origin: str):
    profile = tempfile.mkdtemp(prefix="i8-smoke-profile-")
    context = p.chromium.launch_persistent_context(
        profile,
        channel="chromium",
        headless=True,
        args=[f"--disable-extensions-except={extension_dir}", f"--load-extension={extension_dir}"],
    )
    page = context.pages[0] if context.pages else context.new_page()
    page.goto(f"{origin}/workbench", wait_until="load")
    # 页面发一条消息会唤醒 service worker。
    page_message(page, {"type": "i8-relay:identity", "device_id": DEVICE})
    for _ in range(80):
        if context.service_workers:
            break
        context.wait_for_timeout(100)
    return profile, context, page


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-env", type=Path, required=True)
    parser.add_argument("--frontend-dist", type=Path, help="Existing production build with base /app/")
    args = parser.parse_args()
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # noqa: BLE001
        print(f"没有可用的 playwright：{type(exc).__name__}")
        return 1

    build_dir = tempfile.mkdtemp(prefix="i8-smoke-frontend-")
    frontend = args.frontend_dist.resolve() if args.frontend_dist else Path(build_dir) / "dist"
    try:
        if args.frontend_dist is None:
            build_frontend(frontend)
        assert (frontend / "index.html").is_file(), "missing frontend build"
    except subprocess.CalledProcessError as exc:
        print(exc.stderr)
        shutil.rmtree(build_dir, ignore_errors=True)
        return 1

    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    tempdirs = [build_dir]
    print(f"隔离工作台 {ORIGIN} · 模拟 i8/IPP {I8_ORIGIN}", flush=True)
    try:
        with sync_playwright() as p, ExitStack() as resources:
            # ---------- A 段：原样包。样机 origin 不在 externally_connectable ⇒ 应当连不进来 ----------
            profile_a, ctx_a, page_a = boot(p, EXT_DIR, FORBIDDEN_ORIGIN)
            tempdirs.append(profile_a)
            try:
                check(
                    "原样包被真实浏览器加载，扩展 ID 与工作台硬编码一致",
                    worker_ids(ctx_a)[:1] == [EXT_ID],
                    [w.url for w in ctx_a.service_workers],
                )
                reply = page_message(page_a, {"type": "i8-relay:identity", "device_id": DEVICE})
                check(
                    "externally_connectable 生效：未列进去的 origin 进不来扩展",
                    isinstance(reply, dict) and reply.get("ok") is False,
                    reply,
                )
            finally:
                ctx_a.close()

            cookie = resources.enter_context(isolated_workbench(args.source_env, frontend))
            profile_c, ctx_c, page_c = boot(p, EXT_DIR, ORIGIN)
            ctx_c.add_cookies([cookie])
            tempdirs.append(profile_c)
            try:
                i8 = notice_flow(ctx_c, page_c)

                # ---------- 站点与代号的协议 ----------
                device = DEVICE
                generation = GENERATION

                # 待绑定站点按连接隔离。
                no_device = page_message(page_c, {"type": "i8-relay:identity"})
                check(
                    "没有连接标识时读站点被拒",
                    no_device.get("ok") is False,
                    no_device,
                )

                identity = page_message(page_c, identity_message(device))
                check(
                    "i8 业务页没有账号菜单时仍能读到站点来源",
                    identity == {"ok": True, "origin": I8_ORIGIN, "sessionReady": True},
                    identity,
                )
                pending = {"origin": identity.get("origin")}
                check(
                    "bind 必须带正整数代号（缺代号即拒，且不留下基准）",
                    page_message(page_c, {
                        "type": "i8-relay:bind", "device_id": device, "identity": pending,
                    }).get("ok") is False,
                    "",
                )
                bound = page_message(page_c, {
                    "type": "i8-relay:bind",
                    "device_id": device,
                    "generation": generation,
                    "identity": pending,
                })
                check(
                    "bind 用服务端代号和扩展自己读到的站点来源建立连接",
                    bound.get("ok") is True and bound.get("generation") == generation,
                    bound,
                )

                # ---------- HttpOnly 会话：本通道复用会话的真实机制 ----------
                RECEIVED.clear()
                cookie_reply = page_message(page_c, {
                    "type": "i8-relay:execute",
                    "device_id": device,
                    "request": {
                        "ticket": "t-cookie",
                        "generation": generation,
                        "timeout_ms": 30_000,
                        "method": "POST",
                        "url": f"{I8_ORIGIN}/FC/FM/PaymentBill/getList",
                        "headers": {"Content-Type": "application/json"},
                        "body_b64": base64.b64encode(b'{"limit":"5"}').decode("ascii"),
                    },
                })
                cookie_hits = [
                    item for item in RECEIVED
                    if item["path"].startswith("/FC/FM/PaymentBill/getList")
                ]
                seen_cookie = (cookie_hits[0]["headers"].get("Cookie") or "") if cookie_hits else ""
                check(
                    "HttpOnly 会话 Cookie 由浏览器自动带上（页面/扩展都没碰它）",
                    cookie_reply.get("ok") is True and HTTPONLY_VALUE in seen_cookie,
                    {"reply": cookie_reply, "cookie": seen_cookie},
                )
                # `document.cookie` 读不到 HttpOnly 主 Cookie —— 这就是"无法导出会话"的直接证据。
                visible = i8.evaluate("() => document.cookie")
                check(
                    "document.cookie 里读不到 HttpOnly 会话 Cookie",
                    HTTPONLY_VALUE not in (visible or ""),
                    visible,
                )
                # 页面手工塞 Cookie 头会被浏览器过滤（禁止脚本伪造/覆盖会话）。
                RECEIVED.clear()
                forged = page_message(page_c, {
                    "type": "i8-relay:execute",
                    "device_id": device,
                    "request": {
                        "ticket": "t-forged",
                        "generation": generation,
                        "timeout_ms": 30_000,
                        "method": "POST",
                        "url": f"{I8_ORIGIN}/FC/FM/PaymentBill/getList",
                        "headers": {
                            "Content-Type": "application/json",
                            "Cookie": f"{HTTPONLY_NAME}={FORGED_COOKIE}",
                        },
                        "body_b64": base64.b64encode(b'{"limit":"5"}').decode("ascii"),
                    },
                })
                forged_hits = [
                    item for item in RECEIVED
                    if item["path"].startswith("/FC/FM/PaymentBill/getList")
                ]
                forged_cookie = (forged_hits[0]["headers"].get("Cookie") or "") if forged_hits else ""
                check(
                    "页面手塞的 Cookie 被浏览器过滤，服务端看到的仍是浏览器自己那份",
                    forged.get("ok") is True
                    and FORGED_COOKIE not in forged_cookie
                    and HTTPONLY_VALUE in forged_cookie,
                    {"reply": forged, "cookie": forged_cookie},
                )

                RECEIVED.clear()
                reply = page_message(page_c, {
                    "type": "i8-relay:execute",
                    "device_id": device,
                    "request": {
                        "ticket": "t-1",
                        "generation": generation,
                        "timeout_ms": 30_000,
                        "method": "POST",
                        "url": f"{I8_ORIGIN}/FC/FM/PaymentBill/getList",
                        "headers": {"Content-Type": "application/json", "Cookie": "sentinel-should-not-leak"},
                        "body_b64": base64.b64encode(b'{"limit":"5"}').decode("ascii"),
                    },
                })
                sent = [item for item in RECEIVED if item["path"].startswith("/FC/FM/PaymentBill/getList")]
                check(
                    "i8 业务页没有账号菜单时，同源取数仍完整返回响应字节",
                    reply.get("ok") is True
                    and len(sent) == 1
                    and reply.get("status") == 200
                    and reply.get("declared_length") == len(FAKE_BODY)
                    and base64.b64decode(reply.get("body_b64") or "") == FAKE_BODY,
                    {"reply": reply, "sent": sent[:1]},
                )
                check(
                    "扩展没有把页面给的 Cookie 头转给 i8（服务端看到的只有浏览器自己那份）",
                    bool(sent)
                    and "sentinel-should-not-leak" not in (sent[0]["headers"].get("Cookie") or "")
                    and FORGED_COOKIE not in (sent[0]["headers"].get("Cookie") or ""),
                    sent[:1],
                )

                RECEIVED.clear()
                redirect = page_message(page_c, {
                    "type": "i8-relay:execute",
                    "device_id": device,
                    "request": {
                        "ticket": "t-2",
                        "generation": generation,
                        "timeout_ms": 30_000,
                        "method": "GET",
                        "url": f"{I8_ORIGIN}/SUP/RichHelp/GetCommonUseList",
                        "headers": {},
                        "body_b64": "",
                    },
                })
                check(
                    "跳转一律停：真机 redirect:'manual' 给的是不透明响应，读不出跳转目标",
                    redirect.get("ok") is False
                    and "不透明响应" in (redirect.get("message") or "")
                    and not [item for item in RECEIVED if item["path"] == "/i8/business"],
                    redirect,
                )

                RECEIVED.clear()
                blocked_cases = [
                    ("登录", {"method": "POST", "url": f"{I8_ORIGIN}/SUP/Login/SupLogin"}),
                    ("强踢", {"method": "POST", "url": f"{I8_ORIGIN}/SUP/Login/KillOnlineUser"}),
                    ("保存", {"method": "POST", "url": f"{I8_ORIGIN}/FC/FM/PaymentBill/save"}),
                    ("伪装 ..", {"method": "GET", "url": f"{I8_ORIGIN}/SUP/RichHelp/../Login/SupLogin"}),
                    ("跨站", {"method": "GET", "url": "http://127.0.0.1:1/SUP/RichHelp/GetCommonUseList"}),
                    ("删除方法", {"method": "DELETE", "url": f"{I8_ORIGIN}/FC/FM/PaymentBill/getList"}),
                ]
                for name, request in blocked_cases:
                    blocked = page_message(page_c, {
                        "type": "i8-relay:execute",
                        "device_id": device,
                        "request": {
                            "ticket": "t-3", "generation": generation, "timeout_ms": 30_000,
                            "headers": {}, "body_b64": "", **request,
                        },
                    })
                    check(f"真浏览器里「{name}」被拒且没发出去", blocked.get("ok") is False, blocked)
                check("被拒的越界请求在服务器上一条记录都没有", RECEIVED == [], RECEIVED)

                # 采购合同列表使用同一站点的固定 POST 路径。
                RECEIVED.clear()
                contract = page_message(page_c, {
                    "type": "i8-relay:execute",
                    "device_id": device,
                    "request": {
                        "ticket": "t-contract",
                        "generation": generation,
                        "timeout_ms": 200_000,
                        "method": "POST",
                        "url": f"{I8_ORIGIN}/PMS/PCM/Contract/GetCntMList",
                        "headers": {"Content-Type": "application/json"},
                        "body_b64": base64.b64encode(b"{}").decode("ascii"),
                    },
                })
                contract_hits = [
                    item for item in RECEIVED if item["path"].startswith("/PMS/PCM/Contract/GetCntMList")
                ]
                check(
                    "采购合同列表口在浏览器方式下能发出去（不必改回直连）",
                    contract.get("ok") is True and len(contract_hits) == 1,
                    {"reply": contract, "sent": contract_hits[:1]},
                )

                check(
                    "unbind 成功",
                    page_message(page_c, {"type": "i8-relay:unbind", "device_id": device}).get("ok") is True,
                )
                after = page_message(page_c, {
                    "type": "i8-relay:execute",
                    "device_id": device,
                    "request": {
                        "ticket": "t-4",
                        "generation": generation,
                        "timeout_ms": 30_000,
                        "method": "GET",
                        "url": f"{I8_ORIGIN}/SUP/RichHelp/GetCommonUseList",
                        "headers": {},
                        "body_b64": "",
                    },
                })
                check("断开后同一请求被拒绝", after.get("ok") is False, after)

                # ---------- 代号、站点与发送页面归属 ----------
                # 断开时清除了待绑定站点，重新连接前先读取站点。
                page_message(page_c, identity_message(device))
                re_bound = page_message(page_c, {
                    "type": "i8-relay:bind",
                    "device_id": device,
                    "generation": generation,
                    "identity": pending,
                })
                check("重新绑定以便验证代号闸", re_bound.get("ok") is True, re_bound)

                # (1) 代号不是这条连接当前的 ⇒ 零请求。真浏览器里"零注入"的可见证据是
                #     服务器一条记录都没有（注入成功就会真的发出 fetch）。
                RECEIVED.clear()
                for label, bad_generation in (
                    ("缺代号", None),
                    ("代号为 0", 0),
                    ("旧代号", generation + 5),
                    ("代号不成形", "x"),
                ):
                    message = {
                        "type": "i8-relay:execute",
                        "device_id": device,
                        "request": {
                            "ticket": "t-gen",
                            "timeout_ms": 30_000,
                            "method": "GET",
                            "url": f"{I8_ORIGIN}/SUP/RichHelp/GetCommonUseList",
                            "headers": {},
                            "body_b64": "",
                        },
                    }
                    if bad_generation is not None:
                        message["request"]["generation"] = bad_generation
                    answer = page_message(page_c, message)
                    check(
                        f"真浏览器里「{label}」的请求被拒且一条都没发出去",
                        answer.get("ok") is False and RECEIVED == [],
                        {"reply": answer, "received": RECEIVED},
                    )

                # (2) 绑定需要使用扩展刚为当前连接读到的站点。
                invalid_bind_origins = [
                    ("完全没带", None),
                    ("缺站点", {}),
                    ("站点不符", {"origin": OTHER_ORIGIN}),
                ]
                for label, identity_value in invalid_bind_origins:
                    message = {
                        "type": "i8-relay:bind",
                        "device_id": "dev-incomplete",
                        "generation": generation,
                    }
                    # 先让这个连接有待绑定站点，再验证请求里的站点字段。
                    page_message(page_c, identity_message("dev-incomplete"))
                    if identity_value is not None:
                        message["identity"] = identity_value
                    answer = page_message(page_c, message)
                    check(
                        f"真浏览器里 bind 「{label}」被拒且没留下基准",
                        answer.get("ok") is False
                        and page_message(page_c, {
                            "type": "i8-relay:execute",
                            "device_id": "dev-incomplete",
                            "request": {
                                "ticket": "t-inc", "generation": generation, "timeout_ms": 30_000,
                                "method": "GET", "url": f"{I8_ORIGIN}/SUP/RichHelp/GetCommonUseList",
                                "headers": {}, "body_b64": "",
                            },
                        }).get("ok") is False,
                        answer,
                    )

                # (3) 另一个工作台页面（同源、不同标签/文档）借同一个 device_id：
                #     不能执行、不能顶绑、不能撤绑 —— 这正是 closure 要的 sender 隔离。
                page_c2 = ctx_c.new_page()
                page_c2.goto(f"{ORIGIN}/workbench", wait_until="load")
                RECEIVED.clear()
                stolen_exec = page_message(page_c2, {
                    "type": "i8-relay:execute",
                    "device_id": device,
                    "request": {
                        "ticket": "t-steal", "generation": generation, "timeout_ms": 30_000,
                        "method": "GET", "url": f"{I8_ORIGIN}/SUP/RichHelp/GetCommonUseList",
                        "headers": {}, "body_b64": "",
                    },
                })
                check(
                    "另一个工作台页面借同一 device_id 不能取数（且没碰标签）",
                    stolen_exec.get("ok") is False and RECEIVED == [],
                    {"reply": stolen_exec, "received": RECEIVED},
                )
                stolen_read = page_message(page_c2, identity_message(device))
                stolen_bind = page_message(page_c2, {
                    "type": "i8-relay:bind",
                    "device_id": device,
                    "generation": generation,
                    "identity": {"origin": stolen_read.get("origin")},
                })
                check(
                    "另一个工作台页面不能顶掉已有连接",
                    stolen_bind.get("ok") is False and stolen_bind.get("code") == "sender-mismatch",
                    stolen_bind,
                )
                stolen_unbind = page_message(page_c2, {"type": "i8-relay:unbind", "device_id": device})
                check("另一个工作台页面不能撤掉已有连接", stolen_unbind.get("ok") is False, stolen_unbind)
                # 原页面仍走得通：用一个正常返回的接口，证明基准没被别的页面动过。
                RECEIVED.clear()
                still_ok = page_message(page_c, {
                    "type": "i8-relay:execute",
                    "device_id": device,
                    "request": {
                        "ticket": "t-own", "generation": generation, "timeout_ms": 30_000,
                        "method": "POST", "url": f"{I8_ORIGIN}/FC/FM/PaymentBill/getList",
                        "headers": {"Content-Type": "application/json"},
                        "body_b64": base64.b64encode(b"{}").decode("ascii"),
                    },
                })
                still_hits = [item for item in RECEIVED if item["path"].startswith("/FC/FM/PaymentBill/getList")]
                check(
                    "建立连接的页面本身仍可正常取数（基准没被动过）",
                    still_ok.get("ok") is True and len(still_hits) == 1,
                    {"reply": still_ok, "sent": still_hits[:1]},
                )
                page_c2.close()
            finally:
                ctx_c.close()
    finally:
        server.shutdown()
        server.server_close()
        for path in tempdirs:
            shutil.rmtree(path, ignore_errors=True)

    print()
    if FAILURES:
        print(f"样机未通过 {len(FAILURES)} 条：")
        for name in FAILURES:
            print(f"  - {name}")
        return 1
    print(f"隔离 Chromium + 工作台 + 模拟 i8/IPP 的 {len(CHECKS)} 项判据全部通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
