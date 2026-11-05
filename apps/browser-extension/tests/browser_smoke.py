"""扩展真机样机：在**独立临时 profile** 的 Chromium 里跑一遍 runtime / executeScript / fetch。

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

  不能证明（⛔ 别拿它当验收）：
    - 不是 Edge：这里是 Chromium（`ms-playwright/chromium-1248`），Edge 上的实际行为未验；
    - 不是真实 i8：所有地址都是本机假页面与假接口，无真实业务数据；
    - 不是 activeTab 的真实授权路径：`chrome.action.onClicked` 无法被程序化触发。样机用
      **临时副本**把本机样机 origin 加进 `host_permissions` 才能跑通注入；副本不改 `key`，
      所以扩展 ID 不变。原样包（只有 `activeTab`）在没有人点图标时被浏览器拒绝注入 ——
      这正是设计的正确表现，样机会把它作为**期望**断言。
    - 不碰用户 profile、不连真实 i8、不装新依赖、不改系统设置。

用法（只用仓库里已有的运行时）：

    backend/.venv/Scripts/python.exe -B -X utf8 apps/browser-extension/tests/browser_smoke.py

端口：默认从 8071 起找一个空闲端口（不使用 8000/8065，避免碰他人的预览服务）。
退出码：0 = 全部判据通过；1 = 有判据不通过（打印哪一条）。
"""

from __future__ import annotations

import base64
import json
import shutil
import socket
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EXT_DIR = ROOT / "apps" / "browser-extension"
EXT_ID = "jfkgliolimmpceandogfimjkadplidem"

FAKE_RECORD = {
    "PhId": "3700000000000521",
    "BillNo": "FKTZS2026090001",
    "PhidRecPayType_EXName": "其他支出",
    "PhidPc_EXName": "第四工程公司",
    "AppStatus": 1,
    "ApproveAmt": 12345.67,
    "Remark": "样机用假数据",
}
FAKE_BODY = json.dumps({"Success": True, "Record": [FAKE_RECORD]}, ensure_ascii=False).encode("utf-8")

# 假会话 Cookie：真 i8 的会话是 HttpOnly 的。值带哨兵前缀，方便在服务端日志里辨认。
HTTPONLY_NAME = "MTRLSESSION"
HTTPONLY_VALUE = "httponly-sentinel-9f3a"
FORGED_COOKIE = "forged-by-page-should-be-dropped"

# 服务器收到过的每一条请求（用来证明"被拦的请求一个字节都没出去"）。
RECEIVED: list[dict] = []

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
        if self.path == "/workbench":
            self._send(200, WORKBENCH_HTML.encode("utf-8"), "text/html;charset=utf-8")
            return
        if self.path == "/i8/business":
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
        if self.path == "/SUP/RichHelp/GetCommonUseList":
            RECEIVED.append({"method": "GET", "path": self.path, "headers": dict(self.headers)})
            self.send_response(302)
            self.send_header("Location", f"{ORIGIN}/i8/business")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self._send(404, b"{}")

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        RECEIVED.append({
            "method": "POST",
            "path": self.path,
            "headers": dict(self.headers),
            "body": body.decode("utf-8", "replace"),
        })
        if self.path.startswith(("/FC/FM/PaymentBill/getList", "/PMS/PCM/Contract/GetCntMList")):
            self._send(200, FAKE_BODY)
            return
        self._send(404, b"{}")


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
ORIGIN = f"http://127.0.0.1:{PORT}"
OTHER_ORIGIN = f"http://localhost:{PORT}"


FAILURES: list[str] = []

# 与工作台页面 / 后端共用的消息形状（closure 第 3 节）：连接按 `device_id` 隔离，
# `bind` 必须带服务端给的正整数 `generation`。⛔ 字段名别改。
DEVICE = "dev-smoke-1"
GENERATION = 1


def check(name: str, ok: bool, detail: object = "") -> None:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f" —— {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(name)


def make_copy(
    target: Path,
    *,
    matches: list[str] | None,
    host_permissions: list[str] | None,
    workbench_origins: list[str] | None = None,
    extra_permissions: list[str] | None = None,
) -> None:
    """复制一份扩展用于样机。

    ⚠️ 副本必须原样保留 `key`：扩展 ID 由它决定。
    ⚠️ 样机端口不可能正好是 8000/8065（那两个被别人占着，不能动），而
       `service_worker.js` 的 `WORKBENCH_ORIGINS` 与 manifest 的
       `externally_connectable.matches` 是**两份手工同步的常量**，
       所以副本里要一起改。这个"两份必须一起改"本身就是维护风险，
       样机之所以要把两边都改，正是因为它证明了这份耦合真实存在。
    ⚠️ `extra_permissions=["tabs"]` 只在样机副本里出现，用途只有一个：
       替身"用户点扩展图标"这一步需要一个**数字型 tab.id**（真包由浏览器在点击时给出）。
       真包**不申请** `tabs`。
    """
    shutil.copytree(EXT_DIR, target, ignore=shutil.ignore_patterns("tests", "__pycache__"))
    manifest_path = target / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if matches is not None:
        manifest["externally_connectable"]["matches"] = matches
    if host_permissions is not None:
        manifest["host_permissions"] = host_permissions
    if extra_permissions:
        manifest["permissions"] = list(dict.fromkeys([*manifest["permissions"], *extra_permissions]))
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if workbench_origins is not None:
        worker_path = target / "service_worker.js"
        source = worker_path.read_text(encoding="utf-8")
        start = source.index("const WORKBENCH_ORIGINS = [")
        end = source.index("];", start) + 2
        replacement = "const WORKBENCH_ORIGINS = [\n" + "".join(
            f"  '{item}',\n" for item in workbench_origins
        ) + "];"
        worker_path.write_text(source[:start] + replacement + source[end:], encoding="utf-8")


def worker_ids(context) -> list[str]:
    """`chrome-extension://<id>/service_worker.js` ⇒ 取中间的 <id>。"""
    return [worker.url.split("/")[2] for worker in context.service_workers if "/" in worker.url]


def page_message(page, message: dict):
    return page.evaluate("message => window.__relay(message)", message)


def tab_id_of(context, page) -> str:
    cdp = context.new_cdp_session(page)
    return cdp.send("Target.getTargetInfo")["targetInfo"]["targetId"]


def select_tab(context, page) -> None:
    """替代"用户点扩展图标"：把 i8 标签写进扩展的标签基准。

    真包这一步由 `chrome.action.onClicked` 完成 —— 点击时浏览器给出**数字型 tab.id**，
    并同时授予 activeTab。样机无法程序化点击，所以在**副本**里临时申请 `tabs` 权限，
    用 `chrome.tabs.query` 拿到同一个数字 id（CDP 给的是 targetId 字符串，两者不同）。
    ⛔ 真包不申请 `tabs`。
    """
    worker = context.service_workers[0]
    result = worker.evaluate(
        """async (origin) => {
          const tabs = await chrome.tabs.query({});
          const hit = tabs.find(tab => (tab.url || '').startsWith(origin + '/i8/business'));
          if (!hit) return { ok: false, seen: tabs.map(tab => tab.url) };
          await chrome.storage.session.set({ i8RelayTab: { tabId: hit.id, origin, selectedAt: Date.now() } });
          return { ok: true, tabId: hit.id };
        }""",
        ORIGIN,
    )
    if not result.get("ok"):
        raise RuntimeError(f"样机没能选中 i8 标签：{result}")


def boot(p, extension_dir: Path):
    profile = tempfile.mkdtemp(prefix="i8-smoke-profile-")
    context = p.chromium.launch_persistent_context(
        profile,
        channel="chromium",
        headless=True,
        args=[f"--disable-extensions-except={extension_dir}", f"--load-extension={extension_dir}"],
    )
    page = context.pages[0] if context.pages else context.new_page()
    page.goto(f"{ORIGIN}/workbench", wait_until="load")
    # 页面发一条消息会唤醒 service worker。
    page_message(page, {"type": "i8-relay:identity", "device_id": DEVICE})
    for _ in range(80):
        if context.service_workers:
            break
        context.wait_for_timeout(100)
    return profile, context, page


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # noqa: BLE001
        print(f"没有可用的 playwright：{type(exc).__name__}")
        return 1

    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    tempdirs: list[str] = []
    print(f"样机端口 {ORIGIN}（不使用 8000/8065）")
    try:
        with sync_playwright() as p:
            # ---------- A 段：原样包。样机 origin 不在 externally_connectable ⇒ 应当连不进来 ----------
            profile_a, ctx_a, page_a = boot(p, EXT_DIR)
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

            # ---------- B 段：只把样机 origin 列进 externally_connectable，不加 host_permissions ----------
            ext_b = Path(tempfile.mkdtemp(prefix="i8-smoke-extb-")) / "ext"
            tempdirs.append(str(ext_b.parent))
            make_copy(
                ext_b,
                matches=[f"{ORIGIN}/*"],
                host_permissions=None,
                workbench_origins=[ORIGIN],
                extra_permissions=["tabs"],
            )
            profile_b, ctx_b, page_b = boot(p, ext_b)
            tempdirs.append(profile_b)
            try:
                check(
                    "副本仍以同一固定 ID 加载（`key` 原样保留）",
                    worker_ids(ctx_b)[:1] == [EXT_ID],
                    [w.url for w in ctx_b.service_workers],
                )
                reply = page_message(page_b, {"type": "i8-relay:identity", "device_id": DEVICE})
                check(
                    "列进去的 origin 能进扩展（未选标签 ⇒ need-tab）",
                    isinstance(reply, dict) and reply.get("code") == "need-tab",
                    reply,
                )
                i8_b = ctx_b.new_page()
                i8_b.goto(f"{ORIGIN}/i8/business", wait_until="load")
                select_tab(ctx_b, i8_b)
                reply = page_message(page_b, {"type": "i8-relay:identity", "device_id": DEVICE})
                check(
                    "没有 activeTab/host 授权时注入被浏览器拒绝（activeTab 需用户点图标，无法程序化授予）",
                    isinstance(reply, dict) and reply.get("ok") is False,
                    reply,
                )
            finally:
                ctx_b.close()

            # ---------- C 段：临时副本加 host_permissions，跑通注入 + 取数 ----------
            ext_c = Path(tempfile.mkdtemp(prefix="i8-smoke-extc-")) / "ext"
            tempdirs.append(str(ext_c.parent))
            make_copy(
                ext_c,
                matches=[f"{ORIGIN}/*"],
                host_permissions=[f"{ORIGIN}/*"],
                workbench_origins=[ORIGIN],
                extra_permissions=["tabs"],
            )
            profile_c, ctx_c, page_c = boot(p, ext_c)
            tempdirs.append(profile_c)
            try:
                i8 = ctx_c.new_page()
                i8.goto(f"{ORIGIN}/i8/business", wait_until="load")
                select_tab(ctx_c, i8)

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

                identity = page_message(page_c, {"type": "i8-relay:identity", "device_id": device})
                check(
                    "i8 业务页没有账号菜单时仍能读到站点来源",
                    identity == {"ok": True, "origin": ORIGIN},
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
                        "url": f"{ORIGIN}/FC/FM/PaymentBill/getList",
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
                        "url": f"{ORIGIN}/FC/FM/PaymentBill/getList",
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
                        "url": f"{ORIGIN}/FC/FM/PaymentBill/getList",
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
                        "url": f"{ORIGIN}/SUP/RichHelp/GetCommonUseList",
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
                    ("登录", {"method": "POST", "url": f"{ORIGIN}/SUP/Login/SupLogin"}),
                    ("强踢", {"method": "POST", "url": f"{ORIGIN}/SUP/Login/KillOnlineUser"}),
                    ("保存", {"method": "POST", "url": f"{ORIGIN}/FC/FM/PaymentBill/save"}),
                    ("伪装 ..", {"method": "GET", "url": f"{ORIGIN}/SUP/RichHelp/../Login/SupLogin"}),
                    ("跨站", {"method": "GET", "url": "http://127.0.0.1:1/SUP/RichHelp/GetCommonUseList"}),
                    ("删除方法", {"method": "DELETE", "url": f"{ORIGIN}/FC/FM/PaymentBill/getList"}),
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

                # 采购合同列表口（正式部署 `I8_CONTRACT_LIST_URL` 的实测值）在浏览器方式下能走。
                RECEIVED.clear()
                contract = page_message(page_c, {
                    "type": "i8-relay:execute",
                    "device_id": device,
                    "request": {
                        "ticket": "t-contract",
                        "generation": generation,
                        "timeout_ms": 200_000,
                        "method": "POST",
                        "url": f"{ORIGIN}/PMS/PCM/Contract/GetCntMList",
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
                        "url": f"{ORIGIN}/SUP/RichHelp/GetCommonUseList",
                        "headers": {},
                        "body_b64": "",
                    },
                })
                check("断开后同一请求被拒绝", after.get("ok") is False, after)

                # ---------- 代号、站点与发送页面归属 ----------
                # 断开时清除了待绑定站点，重新连接前先读取站点。
                page_message(page_c, {"type": "i8-relay:identity", "device_id": device})
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
                            "url": f"{ORIGIN}/SUP/RichHelp/GetCommonUseList",
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
                    page_message(page_c, {"type": "i8-relay:identity", "device_id": "dev-incomplete"})
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
                                "method": "GET", "url": f"{ORIGIN}/SUP/RichHelp/GetCommonUseList",
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
                        "method": "GET", "url": f"{ORIGIN}/SUP/RichHelp/GetCommonUseList",
                        "headers": {}, "body_b64": "",
                    },
                })
                check(
                    "另一个工作台页面借同一 device_id 不能取数（且没碰标签）",
                    stolen_exec.get("ok") is False and RECEIVED == [],
                    {"reply": stolen_exec, "received": RECEIVED},
                )
                stolen_read = page_message(page_c2, {"type": "i8-relay:identity", "device_id": device})
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
                        "method": "POST", "url": f"{ORIGIN}/FC/FM/PaymentBill/getList",
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
        for path in tempdirs:
            shutil.rmtree(path, ignore_errors=True)

    print()
    if FAILURES:
        print(f"样机未通过 {len(FAILURES)} 条：")
        for name in FAILURES:
            print(f"  - {name}")
        return 1
    print("样机判据全部通过（仅证明通路；不等于 Edge 真机，也不等于真实 i8 业务验收）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
