"""签名图的**取值与绑定**（把 i8 审批流程里的签名贴到版式的图片格上）。

## 契约（**2026-09-15 真机对照确定**，不是猜的）

拿"模板图片格的「办理节点」名"与"流程节点字段"逐个对照，结果是：

| 模板侧 | 流程侧 | 证据 |
|---|---|---|
| 图片格 `cellData.dataFilter` 里 `fieldId="办理节点"` 的 `value` | 流程节点的 **`task_des`** | `项目经理` / `工程公司主管审核` / `分公司经理` / `核算部部长` 全部逐字命中 |
| 图片格 `cellData.dataFilter` 里 `fieldId="task_des"` 的 `value`（**第 2 种写法**） | 同上（**本来就是同一个字段**） | `i8_print_design_sample.json` 的 `row=15 col=3`（核算部部长）用的就是它 |
| 图片的地址 | 同一个节点的 **`signature`** | 该字段实测 200+ 字符（相对路径，带 `?s=<token>`）；`actionname`/`nodeid`/`username` 都对不上模板名 |
| 兜底地址 | `signcode`（16 字符） | 目前**未用到**；`signature` 为空而 `signcode` 有值时再说（**不猜**） |

⚠️ **两种筛选写法都要认**（2026-09-16 补）：漏认第 2 种 ⇒ 那格**连槽位都不算** ⇒
既不在 `missing` 也不在 `blank_by_design` ⇒ 静默印出缺签名的件（实测：其他支出的核算部部长）。
⇒ 配套 `unresolved_image_slots()` + `check_signature_coverage()` 的报警，把"不认识的写法"变成**停单报错**。

## 取图（照素材包 `print_paynotice.download_sig` 的口径）

- `signature` 是**相对路径**（以 `http` 开头则直接用），拼到 `I8_BASE_URL` 后 **GET**（带会话 cookie）；
- 按**魔术字节**定 MIME（jpeg / gif / bmp，默认 png），编码成 `data:<mime>;base64,...` 直接嵌进 HTML；
- **缓存键 = 去掉 query 的 path**（`?s=<token>` 每次都变，带 query 会永不命中）；
- 缓存 TTL = 15 天（签名图是"按人固定"的图片）。
"""

from __future__ import annotations

import base64
import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path

from app.core.errors import ExternalServiceError, MustReportError
from app.core.logging import get_logger

logger = get_logger()

SIG_TTL_DAYS = 15
SIG_MIN_BYTES = 100          # 太小的响应视为坏图（素材包同阈值）

# ⚠️ **本模块不声明"办理节点"这个字段名** —— 它只有一处口径 = `print/template.py::NODE_FILTER_FIELD`；
#    `signature_slots()` 直接复用那边的 `node_of()`，所以这里**不需要**自己再来一份（曾有一份死常量，已删）。

_MAGIC = ((b"\xff\xd8\xff", "image/jpeg"), (b"GIF87a", "image/gif"),
          (b"GIF89a", "image/gif"), (b"BM", "image/bmp"))


# ---------------------------------------------------------------- 纯函数：节点名 → 地址


def collect_signature_paths(flow: list[dict] | None) -> dict[str, str]:
    """流程节点 → `{task_des: 签名图相对路径}`。

    - **节点名 = `task_des`**（见模块头对照表）；
    - 空 `task_des` / 空 `signature` 的节点**跳过**（如"流程发起"、"流程结束"没有签名）；
    - **同名取靠后的那个** —— 流程数组是按时间正序的，靠后 = 更新的一次处理。
    """
    out: dict[str, str] = {}
    for node in flow or ():
        if not isinstance(node, dict):
            continue
        name = str(node.get("task_des") or "").strip()
        rel = str(node.get("signature") or "").strip()
        if name and rel:
            out[name] = rel
    return out


def signature_slots(tpl) -> list[str]:
    """模板里的**签名格节点名**（去重、保序）—— 用于"零命中报警"。"""
    from app.mod03_notice.print.template import is_image_cell, node_of

    out: list[str] = []
    for c in tpl.field_cells():
        if not is_image_cell(c):
            continue
        name = node_of(c)
        if name and name not in out:
            out.append(name)
    return out


def reached_nodes(flow: list[dict] | None) -> list[str]:
    """流程**走到过**的节点名（`task_des` 非空；去重保序）。

    ⚠️ 与 `collect_signature_paths()` 的区别：那个只收**有签名**的节点，
       本函数收**所有走到过**的节点 —— 「走到过、但没签名」正是 `001-06` 要鉴别的形态。
    """
    out: list[str] = []
    for node in flow or ():
        if not isinstance(node, dict):
            continue
        name = str(node.get("task_des") or "").strip()
        if name and name not in out:
            out.append(name)
    return out


def unresolved_image_slots(tpl) -> list[tuple]:
    """版式里**带了筛选条件、却取不到审批节点名**的图片格 → `[(row, col, dataFilter)]`。

    ⚠️ 与「**无筛选**」**不是一回事**，别合并：
    - 无筛选（`dataFilter` 为空）⇒ i8 本身也印空（真实打印件验证）⇒ **合法**，不报；
    - 有筛选却解析不出节点 ⇒ **我们不认识的写法** ⇒ 静默留白 = **漏印一个签名**，
      而且它连 `signature_slots()` 都进不去（既不 `missing` 也不 `blank_by_design`）⇒ **必须报警**。

    2026-09-16：正是这一格（其他支出 · 核算部部长）暴露了 `node_of()` 漏认第 2 种筛选写法。
    """
    from app.mod03_notice.print.template import is_image_cell, node_of

    out: list[tuple] = []
    for c in tpl.field_cells():
        if not is_image_cell(c):
            continue
        filters = (c.get("cellData") or {}).get("dataFilter") or []
        if filters and not node_of(c):
            out.append((c.get("row"), c.get("col"), filters))
    return out


@dataclass
class SignatureCoverage:
    """一次渲染的**签名覆盖情况**（`001-04` / `001-05` / `001-06` 的判定依据）。"""

    slots: list[str] = field(default_factory=list)          # 模板要的签名格（节点名，去重保序）
    reached: list[str] = field(default_factory=list)        # 流程走到过的节点名
    filled: list[str] = field(default_factory=list)         # 模板要 ∧ 流程有 ∧ 图**取到了**
    missing: list[str] = field(default_factory=list)        # 模板要 ∧ 流程有 ∧ 图**没取到**（掉图）
    blank_by_design: list[str] = field(default_factory=list)  # 模板要 ∧ 流程**没走到** ⇒ 留空正确（001-05）
    unresolved: list[tuple] = field(default_factory=list)   # 版式有筛选、却认不出节点名（不认识的写法）

    @property
    def silent_risk(self) -> bool:
        """`001-06` 的触发条件：**槽位存在 ＋ 流程有数据 ＋ 一个签名都没命中**。"""
        return bool(self.slots) and bool(self.reached) and not self.filled


def _brief_unresolved(unresolved: list[tuple]) -> str:
    """把"认不出的图片格"写成人能读的一行（定位到 row/col + 原筛选条件）。"""
    parts: list[str] = []
    for row, col, filters in unresolved:
        ids = [str((f or {}).get("fieldId") or "") for f in filters if isinstance(f, dict)]
        parts.append(f"row{row}col{col}（筛选字段={'/'.join(x or '?' for x in ids)}）")
    return "；".join(parts)


def check_signature_coverage(tpl, flow: list[dict] | None, bound: dict | None) -> SignatureCoverage:
    """算签名覆盖情况；**`001-06` / 认不出写法 触发即抛错**（禁止静默产出缺签名件）。

    - `001-04`：命中 = 模板槽位名 ∧ 流程节点名（逐字相同）∧ 图**真取到**；
    - `001-05`：模板有槽位但流程**没走到** ⇒ 计入 `blank_by_design`，**留空且不报错**；
    - `001-06`：槽位存在 ＋ 流程有数据 ＋ 命中数为 0 ⇒ **必须显式报警**；
    - **认不出的签名格**（有筛选却解析不出节点名）⇒ **必须显式报警**：它连槽位都不算，
      不报的话 `001-04/05/06` 三条一条都盖不住它（2026-09-16 实测踩到）。

    ⚠️ 「流程有数据」= 至少走到过一个节点（不是"有签名"）—— 全是「流程发起」这类无签名节点也算有数据。
    """
    slots = signature_slots(tpl)
    reached = reached_nodes(flow)
    unresolved = unresolved_image_slots(tpl)
    bound = dict(bound or {})
    filled = [n for n in slots if str(bound.get(n) or "").strip()]
    missing = [n for n in slots if n in reached and not str(bound.get(n) or "").strip()]
    blank = [n for n in slots if n not in reached]
    cov = SignatureCoverage(
        slots=slots, reached=reached, filled=filled, missing=missing,
        blank_by_design=blank, unresolved=unresolved,
    )
    if cov.unresolved:
        raise MustReportError(
            "签名绑定失败：版式里有签名格**带了筛选条件、却取不到审批节点名**（写法不认识）"
            f"—— 共 {len(cov.unresolved)} 格：{_brief_unresolved(cov.unresolved)}。"
            "已停止打印，禁止静默留白（留白 = 漏印一个签名，且它连槽位都不算、三条签名判据都盖不住）。"
        )
    if cov.silent_risk:
        raise MustReportError(
            "签名绑定失败：版式有签名槽位、审批流程也走到过节点，但**一个签名都未命中**"
            f"（版式槽位={slots}；流程已走到={reached}；取图失败={missing or '无'}）。"
            "已停止打印，禁止静默产出无签名件。"
        )
    return cov


def cache_key(rel_or_url: str) -> str:
    """缓存键 = **去掉 query 的 path** 的 md5（`?s=<token>` 每次变，带 query 会永不命中）。"""
    from urllib.parse import urlparse

    path = urlparse(str(rel_or_url)).path or str(rel_or_url)
    return hashlib.md5(path.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- 取图（带缓存）


class SignatureStore:
    """签名图取用器：内存 + 目录缓存（照素材包 `_sigcache` 的做法）。"""

    def __init__(self, client, cache_dir: Path | None = None) -> None:  # noqa: ANN001
        self._client = client
        self._dir = Path(cache_dir) if cache_dir else None
        if self._dir:
            self._dir.mkdir(parents=True, exist_ok=True)
        self._mem: dict[str, str] = {}

    def uri_for(self, rel: str) -> str:
        """相对路径 → `data:<mime>;base64,...`；取不到 ⇒ **空串**（留空，不编造）。"""
        rel = str(rel or "").strip()
        if not rel:
            return ""
        key = cache_key(rel)
        if key in self._mem:
            return self._mem[key]

        blob = self._read_cache(key)
        if blob is None:
            blob = self._download(rel)
            if blob:
                self._write_cache(key, blob)
        if not blob or len(blob) < SIG_MIN_BYTES:
            logger.warning("签名图取不到或过小（{} 字节）：{}", len(blob or b""), rel[:60])
            return ""
        uri = _to_data_uri(blob)
        self._mem[key] = uri
        return uri

    # --- 内部 ---
    def _download(self, rel: str) -> bytes:
        from app.core.config import get_settings

        base = i8_base_of(get_settings())
        url = rel if rel.startswith("http") else f"{base}/{rel.lstrip('/')}"
        try:
            resp = self._client.request("GET", url)
        except Exception as exc:  # noqa: BLE001
            logger.warning("签名图下载异常：{}", exc)
            return b""
        if resp.status_code >= 400:
            raise ExternalServiceError(f"签名图下载失败 HTTP {resp.status_code}：{url[:80]}")
        return resp.content or b""

    def _cache_path(self, key: str) -> Path | None:
        return (self._dir / f"{key}.bin") if self._dir else None

    def _read_cache(self, key: str) -> bytes | None:
        p = self._cache_path(key)
        if p is None or not p.exists():
            return None
        if time.time() - p.stat().st_mtime > SIG_TTL_DAYS * 86400:
            return None
        data = p.read_bytes()
        return data if data else None

    def _write_cache(self, key: str, blob: bytes) -> None:
        p = self._cache_path(key)
        if p is not None:
            p.write_bytes(blob)


def _to_data_uri(blob: bytes) -> str:
    mime = "image/png"
    for magic, kind in _MAGIC:
        if blob.startswith(magic):
            mime = kind
            break
    return f"data:{mime};base64,{base64.b64encode(blob).decode('ascii')}"


def bind_signatures(store: SignatureStore, flow: list[dict] | None) -> dict[str, str]:
    """流程 → `{节点名: data:URI}`（渲染器要的形态）。"""
    return {name: store.uri_for(rel) for name, rel in collect_signature_paths(flow).items()}


__all__ = [
    "SIG_TTL_DAYS",
    "collect_signature_paths", "signature_slots", "reached_nodes", "unresolved_image_slots", "cache_key",
    "SignatureCoverage", "check_signature_coverage",
    "SignatureStore", "bind_signatures",
]
