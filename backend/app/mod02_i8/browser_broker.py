"""MOD-02 横切：**浏览器通道**的进程内 broker（排队 + 一次性回帖 + 会话失联清理）。

## 这是什么、为什么这么写

日常抓取要能用**用户 Edge 里已经登录的 i8 会话**，但不能让模型/Agent 在每条请求中间转接。
本模块只做一件事：把后端 `I8Client` 发起的**那一条具体请求**暂时**挂起**，交给
"已登录工作台页面 → Edge 扩展 → 已登录的 i8 标签"这条链去执行，然后把结果**原样交回**给
发起的那个线程。取数/校验/解析**一行都没搬**——仍然是 `I8Client.request()` 及其下游
（`_extract_records` / `_map_record` 等）。

⚠️ **不是**新的取数系统，也**不是**常驻服务：只是**单进程内的内存表**（`dict` + `deque`）
   + 每条请求自己的 `threading.Event`（等待方阻塞在它上面，回帖方 set 它唤醒）。
   ⛔ 这里**没有**条件变量（`threading.Condition`）：早先的注释这么写是错的，已改正。
   之所以能用进程内状态，是因为部署明确是 **uvicorn 单 worker**
   （`ops/nssm_install.ps1` 的 `-m uvicorn app.main:app` 与 `ops/frontend_release.py` 的同一条命令）。
   ⛔ 将来若改多 worker：本模块会"请求落在 A worker、回帖落在 B worker"直接失效 ⇒
   **必须**同时改造成跨进程队列（届时这条注释要一起改，别让它骗人）。

## 边界（每一条都有对应测试）

- **owner 只认服务端认证身份**（`current_name()`），⛔ 不信任客户端送来的账号声明。
  连接与队列一律按 `(owner, device)` 双键隔离；`device` 只是**页面级 nonce**，
  用来"同一账号开了两个页面/两台设备时不串号"，它**不能**提升任何权限。
- **一次性**：一个 `ticket` 只接受**第一条**回帖；重复回帖、过期回帖一律忽略（返回 False）。
- **失联/过期即清**：断开连接、账号变化、等待超时、回帖对不上代号，都会把挂起请求**当场判停**
  （`wait()` 抛 `StrictSessionEnded`，文案取自 `_REASONS` 的固定枚举），⛔ 不重试、⛔ 不回落 HTTP、⛔ 不登录。
- **不搬秘密**：这里只流转 method/url/headers（已过滤）/body，**Cookie 与 Authorization 永不进入**
  （浏览器自己带同源 Cookie；见 `browser_relay._safe_headers`）。

## 与产品原策略的关系

产品原有的「Cookie 磁盘缓存 + 401 单次重登 + 强踢需显式授权」（`client.py` / `cookie_store.py`）
**完全不动**；浏览器通道是**平行**的一条路，只由用户显式选择模式时才走。
"""

from __future__ import annotations

import base64
import secrets
import threading
import time
from collections import deque
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any

from app.core.logging import get_logger
from app.mod02_i8.browser_session import (
    StrictSessionEnded,
    StrictSessionUnavailable,
    StrictTargetMismatch,
    _origin_of,
)

logger = get_logger()

#: 一次挂起请求的**默认**等待上限（只在调用方没给预算时用）。
#: ⚠️ **不自创业务预算**：真正生效的是**每条 HTTP 请求自己的 read 超时**
#:    （`httpx.Request.extensions["timeout"]["read"]` —— 合同列表 200s、详情 60s、
#:    其余默认 30s），由 `BrowserRelayTransport` 从请求里取出来放进 `PendingRequest.timeout_seconds`。
#:    这里只是"请求里没带预算"时的兜底，与 `I8Client` 默认 `httpx.Timeout(30.0, connect=10.0)` 同口径。
#:    ⛔ 别拿这个常量去截断 200s 的合同列表请求 —— 那会把"i8 那边慢"错报成"浏览器没回音"。
RELAY_WAIT_SECONDS = 30.0

#: 长轮询（页面来取活）最多挂多久。比最小的请求预算短，
#: 这样页面总能先回来"再问一次"，而发起端不会因为长轮询本身耗光预算。
PENDING_WAIT_SECONDS = 10.0

#: 多久没有收到页面的轮询或有效回帖算断（页面关掉或设备睡眠）。
#: ⚠️ 只清**真的闲着**的连接：有挂起请求在等（在途）时不算空闲，见 `connection_of`。
CONNECTION_IDLE_SECONDS = 120.0


class BrowserRelayUnavailable(StrictSessionUnavailable):
    """浏览器连接不在（没连、已断、或模式选了浏览器但根本没连上）⇒ 当场停。"""

    code = "i8_browser_relay_unavailable"


@dataclass(frozen=True)
class ConnectionInfo:
    """一条"页面 ↔ 后端"的浏览器连接。`origin` 是**页面报告的 i8 站点**，用来做目标校验。"""

    owner: str
    device: str
    origin: str
    connected_at: float = field(default=0.0)
    last_seen: float = field(default=0.0)
    #: 本次连接的**代号**：由 broker 的进程内发号器给，**每次 connect 都新建**
    #: （包括"断开之后再连"，不会回到 1）。
    #: ⚠️ 用途只有一个：断开重连后，旧连接上迟到的回帖（票还是旧的）**不许**被
    #:    当成本次连接的结果 —— 票 + 代号都对上才算数。
    generation: int = 0

    def to_payload(self) -> dict[str, Any]:
        """给前端的连接状态（去敏：不含任何会话材料，只报站点原点与时间）。"""
        return {
            "connected": True,
            "origin": self.origin,
            "device_id": self.device,
            "generation": self.generation,
            "connected_at": datetime.fromtimestamp(self.connected_at).isoformat(timespec="seconds"),
        }


@dataclass
class PendingRequest:
    """一条挂在 broker 上、等浏览器回帖的请求。字段全部是"要发出去的东西"，不含秘密。"""

    #: **不透明唯一票**：随机串，不含时间戳/序号/对象地址 ⇒ 既不可猜也不泄漏任何状态。
    #: ⚠️ 票只是一次性令牌，**不是**授权凭据：归属仍由 `(服务端身份, device)` 决定。
    ticket: str
    owner: str
    device: str
    method: str
    url: str
    headers: dict[str, str]
    body: bytes
    created_at: float
    #: 这条请求属于哪一代连接（见 `ConnectionInfo.generation`）。回帖必须对上。
    generation: int = 0
    #: 本次请求自己的**等待预算**（秒）—— 来自后端原 HTTP read 超时（见 `RELAY_WAIT_SECONDS`）。
    timeout_seconds: float = RELAY_WAIT_SECONDS
    done: threading.Event = field(default_factory=threading.Event, repr=False)
    #: 回帖结果；`None` 表示"还没回来"。
    status: int | None = None
    reply_headers: dict[str, str] = field(default_factory=dict)
    reply_body: bytes = b""
    #: 扩展/页面自报的响应字节数（用于**完整性**核对）。`None` = 对方没报。
    reply_declared_length: int | None = None
    #: 通道明确失败与上游 HTTP 状态分开保存，不保存异常原文。
    relay_failure: str | None = None
    #: 被判定失效/断连/超时时的受控原因（取值见 `_REASONS`），不是异常原文。
    stopped: str = ""

    def outbound_payload(self) -> dict[str, Any]:
        """交给页面的那一份（`body` 走 base64，二进制安全；headers 已经过滤过秘密）。"""
        return {
            "ticket": self.ticket,
            "generation": self.generation,
            "method": self.method,
            "url": self.url,
            "headers": dict(self.headers),
            "body_b64": base64.b64encode(self.body).decode("ascii"),
            # 页面把它交给扩展当 `AbortController` 的预算：超了就在浏览器侧中止，
            # 别让"i8 那边慢"变成"浏览器一直挂着不吭声"。
            "timeout_ms": max(1, int(self.timeout_seconds * 1000)),
        }


#: 受控停止原因（会出现在给用户看的诊断里 ⇒ **只能是固定枚举**，⛔ 不拼异常原文）。
_REASONS = {
    "disconnected": "浏览器连接已断开，本次已停止（没有重新登录，也没有顶掉任何在线会话）。",
    "timeout": "浏览器那边一直没有回音，本次已停止（没有重新登录，也没有重试）。",
    "replaced": "同一次连接被新的连接替换，本次已停止。",
    "switched": "当前登录账号已变化，本次已停止。",
    "rejected": "浏览器回的那份结果对不上这次连接，本次已停止（没有重试，也没有改走登录）。",
}


class BrowserBroker:
    """进程内的连接表 + 请求队列。所有状态都在 `_lock` 下读写（单 worker 假设）。"""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._connections: dict[tuple[str, str], ConnectionInfo] = {}
        #: 还没被页面取走的请求（按到达顺序）。
        self._queues: dict[tuple[str, str], deque[PendingRequest]] = {}
        #: 已被页面取走、正在浏览器里执行的那一条（按票索引）——
        #: ⚠️ 取走并不等于"交给页面了事"：回帖要按票找到它，所以必须单独登记。
        self._inflight: dict[tuple[str, str], dict[str, PendingRequest]] = {}
        #: 请求代号发号器：**进程内单调递增**，断开重连也继续往后发。
        #: ⚠️ 不能用"当前连接代号 + 1"——断开时连接已被摘掉，那样重连又会从 1 开始，
        #:    旧代迟到的回帖就能撞上新代（正是多设备/断连场景要防的）。
        self._generation_seq: int = 0

    # ------------------------------------------------------------- 连接管理

    def connect(self, owner: str, device: str, origin: str) -> ConnectionInfo:
        """登记/刷新一条连接。

        ⚠️ `origin` 必须已经是**规范化过的站点原点**（由调用方校验），这里只做"非空"兜底。
        ⚠️ 同一 `(owner, device)` 重复连：旧连接的挂起请求**当场判停**（`replaced`），
           避免"页面刷新后旧请求永远挂着"。
        """
        if not owner:
            raise BrowserRelayUnavailable("登录后才能连接浏览器会话。")
        if not device:
            raise BrowserRelayUnavailable("浏览器连接缺少页面标识，请刷新页面后重连。")
        origin_text = str(origin or "").strip()
        if not origin_text or not _origin_of(origin_text):
            raise StrictTargetMismatch("浏览器标签的地址不完整，无法核对是否为已配置的 i8 站点。")
        key = (owner, device)
        now = time.time()
        with self._lock:
            old = self._connections.get(key)
            if old is not None:
                # 旧连接上的挂起请求一律当场判停（`replaced`）——换站点如此，
                # 页面刷新后同站点重连也如此：旧那句话已经没人听了，挂着只会等超时。
                self._fail_queue(key, "replaced")
            # 代号**每次连接都新建**，且由进程内发号器给（只增不减）：
            # 断开 → 重连也换新代号，旧代迟到的回帖因此不可能被当成本次结果。
            self._generation_seq += 1
            generation = self._generation_seq
            self._connections[key] = ConnectionInfo(
                owner=owner,
                device=device,
                origin=origin_text,
                connected_at=now,
                last_seen=now,
                generation=generation,
            )
            self._queues.setdefault(key, deque())
        logger.info("i8 浏览器通道：连接已登记（站点原点 {}，代号 {}）", origin_text, generation)
        return self._connections[key]

    def disconnect(self, owner: str, device: str) -> bool:
        """主动断开：连接与队列一起清，挂起的请求当场判停。

        ⚠️ **幂等**：连接本来就不在时照样返回 False（并清一遍残留队列），⛔ 不抛异常。
           用户连点两次"断开"、或页面刷新后才点，都不该看到一个 500。
        """
        key = (owner, device)
        with self._lock:
            existed = self._connections.pop(key, None) is not None
            self._fail_queue(key, "disconnected")
        if existed:
            logger.info("i8 浏览器通道：连接已断开（挂起请求已判停）")
        return existed

    def clear_owner(self, owner: str) -> None:
        """账号变化/退出登录时，把这个 owner 的连接与队列全清。

        ⚠️ 由**服务端**在明确的账号事件里调用（登录、退出、身份切换）；
           ⛔ 别指望前端发一句"我要清"就清——客户端声明不是授权。
        ⚠️ 判停原因用 `switched`（不是 `disconnected`）：用户看到的是"账号变了"，
           而不是"你自己断的"，两者的下一步动作不同。
        """
        cleared = 0
        with self._lock:
            keys = {key for key in list(self._connections) if key[0] == owner}
            keys |= {key for key in list(self._queues) if key[0] == owner}
            keys |= {key for key in list(self._inflight) if key[0] == owner}
            for key in keys:
                self._connections.pop(key, None)
                self._fail_queue(key, "switched")
            cleared = len(keys)
        if cleared:
            logger.info("i8 浏览器通道：账号变化，已清理 {} 条连接", cleared)

    def connection_of(self, owner: str, device: str) -> ConnectionInfo | None:
        """取连接（顺带做空闲超时清理）。返回 `None` ⇒ 调用方必须**停止**，⛔ 不许回落 HTTP。

        ⚠️ 空闲清理**不碰还在跑的取数**：只要有请求在排队或已在浏览器里执行，
           这条连接就不算空闲 —— 否则一个慢慢跑的合同列表（200s 预算）会在第 121 秒
           被当成"页面关了"而判停，报出来的还是"连接已断开"，完全是另一回事。
        """
        key = (owner, device)
        with self._lock:
            info = self._connections.get(key)
            if info is None:
                return None
            busy = bool(self._queues.get(key)) or bool(self._inflight.get(key))
            if not busy and info.last_seen and time.time() - info.last_seen > CONNECTION_IDLE_SECONDS:
                self._connections.pop(key, None)
                self._fail_queue(key, "timeout")
                logger.info("i8 浏览器通道：连接空闲超时，已清理")
                return None
            return info

    # ------------------------------------------------------------- 请求排队

    def enqueue(self, owner: str, device: str, *, method: str, url: str,
                headers: dict[str, str], body: bytes,
                timeout_seconds: float = RELAY_WAIT_SECONDS) -> PendingRequest:
        """挂起一条请求（调用线程随后 `wait()` 阻塞，直到回帖或判停）。

        `timeout_seconds` 是**这条请求自己的**预算（调用方从 httpx 请求的 read 超时取），
        ⛔ 不要在这里统一压成默认值 —— 合同列表 200s 被压成 30s 就是假超时。
        """
        key = (owner, device)
        with self._lock:
            connection = self._connections.get(key)
            if connection is None:
                raise BrowserRelayUnavailable(
                    "浏览器连接不在（可能已断开或页面已关闭），本次已停止；没有回退到登录方式。"
                )
            # 不透明唯一票：随机、不含时间戳/序号/对象地址（那些既会泄漏状态、又能被猜）。
            ticket = secrets.token_urlsafe(16)
            request = PendingRequest(
                ticket=ticket, owner=owner, device=device, method=method, url=url,
                headers=dict(headers), body=body, created_at=time.time(),
                generation=connection.generation,
                timeout_seconds=max(1.0, float(timeout_seconds or RELAY_WAIT_SECONDS)),
            )
            queue = self._queues.setdefault(key, deque())
            # 队列里堆积说明页面根本没在跑（关掉了/卡住了）⇒ 只保留最新的少数几条，
            # 更早的直接判停，避免"页面回来了一次就以为都通了"。
            while len(queue) >= 2:
                stale = queue.popleft()
                stale.stopped = "timeout"
                stale.done.set()
            queue.append(request)
        return request

    def take_pending(self, owner: str, device: str, *, timeout: float = PENDING_WAIT_SECONDS) -> PendingRequest | None:
        """页面来取活（长轮询）。超时返回 `None`——这是**正常状态**，不是错误。

        ⚠️ 取走的那一刻把请求转入 `_inflight`：**票只有在 inflight 里才认**，
           否则页面可以反复取同一条活，而回帖永远对不上。
        """
        key = (owner, device)
        deadline = time.time() + max(0.0, timeout)

        def _take(item: PendingRequest) -> PendingRequest:
            self._inflight.setdefault(key, {})[item.ticket] = item
            return item

        with self._lock:
            connection = self.connection_of(owner, device)
            if connection is None:
                raise BrowserRelayUnavailable("浏览器连接不在，请重新连接后再试。")
            self._connections[key] = replace(connection, last_seen=time.time())
            queue = self._queues.setdefault(key, deque())
            item = queue.popleft() if queue else None
            if item is not None:
                return _take(item)
        while time.time() < deadline:
            time.sleep(0.05)
            with self._lock:
                current = self._connections.get(key)
                if current is None or current.generation != connection.generation:
                    raise BrowserRelayUnavailable("浏览器连接已断开，请重新连接后再试。")
                queue = self._queues.setdefault(key, deque())
                if queue:
                    return _take(queue.popleft())
        return None

    def complete(self, owner: str, device: str, ticket: str, *, status: int,
                 headers: dict[str, str], body: bytes,
                 declared_length: int | None = None,
                 relay_failure: str | None = None,
                 generation: int | None = None) -> bool:
        """回帖（**一次性**）。返回 False 表示这张票已经作废/已用过/不属于本连接。

        `declared_length` 是浏览器那边自报的字节数（可选）：留着让 transport 做完整性核对 ——
        真截断了就是"没拿到可信结果"，⛔ 不许拿半截响应继续解析。
        `generation` **必须**是正整数且等于这张票的代号：⛔ 缺省/0/负数一律拒绝
        （早先写成 `if generation and ...`，于是传 0 就把代号校验整个绕过去了）。
        """
        key = (owner, device)
        try:
            generation_text = int(generation) if generation is not None else 0
        except (TypeError, ValueError):
            generation_text = 0
        with self._lock:
            connection = self._connections.get(key)
            inflight = self._inflight.get(key) or {}
            item = inflight.get(ticket)
            if item is None:
                return False
            if generation_text <= 0 or generation_text != item.generation:
                inflight.pop(ticket, None)
                # ⚠️ 这条不是"连接被替换"：是页面回了一份对不上代号的票。
                # 用单独的受控原因，别让用户以为自己的连接被别人顶了。
                item.stopped = "rejected"
                item.done.set()
                logger.info("i8 浏览器通道：丢弃一份代号缺失或过代的回帖")
                return False
            if connection is None or item.generation != connection.generation:
                inflight.pop(ticket, None)
                item.stopped = "replaced"
                item.done.set()
                logger.info("i8 浏览器通道：丢弃一份过代回帖（票属于旧连接）")
                return False
            inflight.pop(ticket, None)
            item.status = int(status)
            item.reply_headers = dict(headers)
            item.reply_body = body
            item.reply_declared_length = declared_length
            item.relay_failure = relay_failure
            self._connections[key] = replace(connection, last_seen=time.time())
            item.done.set()
            return True

    def wait(self, request: PendingRequest, *, timeout: float | None = None) -> PendingRequest:
        """等回帖。超时/断连/被替换都在这里变成**受控停止**。

        ⚠️ 默认用**这条请求自己的预算**（`request.timeout_seconds`，来自原 HTTP read 超时），
           不是全局常量：否则 200s 的合同列表会被 30s 截断，且报成"浏览器没回音"。
        ⚠️ 超时的语义是**超时**（`_REASONS["timeout"]`），⛔ 不谎称"会话失效"——
           两者对用户的下一步动作完全不同（等一会儿再试 vs 重新登录）。
        """
        budget = request.timeout_seconds if timeout is None else timeout
        if not request.done.wait(budget):
            key = (request.owner, request.device)
            with self._lock:
                if not request.done.is_set():
                    inflight = self._inflight.get(key)
                    if inflight and inflight.get(request.ticket) is request:
                        inflight.pop(request.ticket)
                    queue = self._queues.get(key)
                    if queue:
                        for index, item in enumerate(queue):
                            if item is request:
                                del queue[index]
                                break
                    request.stopped = "timeout"
                    request.done.set()
        if request.stopped:
            raise StrictSessionEnded(_REASONS.get(request.stopped, _REASONS["timeout"]))
        return request

    # ------------------------------------------------------------- 内部

    def _fail_queue(self, key: tuple[str, str], reason: str) -> None:
        """把这把键上**还没回帖的**请求全判停（排队中的 + 已在浏览器里执行的）。

        ⚠️ 幂等：队列/在途本来就是空的时候什么都不做，⛔ 不要对 `pop` 出来的 `None` 调方法
           （这里曾经 `queue.clear()` 直接崩出 `AttributeError: 'NoneType' object has no attribute 'clear'`，
            在"断开一条不存在的连接"和"空闲清理"两条路径上都能踩到）。
        """
        for item in self._queues.pop(key, None) or ():
            item.stopped = reason
            item.done.set()
        for item in (self._inflight.pop(key, None) or {}).values():
            item.stopped = reason
            item.done.set()


#: 进程内唯一实例（单 worker 假设；见模块头注释）。
_BROKER = BrowserBroker()


def broker() -> BrowserBroker:
    """取进程内 broker。测试可直接 `monkeypatch.setattr(browser_broker, "_BROKER", BrowserBroker())`。"""
    return _BROKER
