"""Normalize the configured i8 site for transport and credential boundaries."""

import httpx


def _parse_url(value: str) -> httpx.URL | None:
    """解析成 `httpx.URL`；解析不出来（缺协议 / 缺主机）时返回 None。"""
    text = (value or "").strip()
    if not text:
        return None
    try:
        parsed = httpx.URL(text)
    except Exception:  # noqa: BLE001
        return None
    if parsed.scheme not in ("http", "https") or not parsed.host:
        return None
    return parsed


def _origin_of(value: str) -> str:
    """去敏的站点标识：只留 `协议://主机[:端口]`（去掉用户信息、路径、查询串与片段）。

    解析不出来时返回空串 ⇒ 调用方据此判定"目标未通过核验"而停止（保守方向）。
    默认端口（https:443 / http:80）由 httpx 归一成 None ⇒ 不写端口，与其他来源可直接比。
    """
    parsed = _parse_url(value)
    if parsed is None:
        return ""
    scheme = parsed.scheme.lower()
    host = parsed.raw_host.decode("ascii").lower()
    if ":" in host:
        host = f"[{host}]"
    try:
        port = parsed.port
    except ValueError:  # 端口写得不像端口 ⇒ 当作"核验不过"
        return ""
    return f"{scheme}://{host}:{port}" if port is not None else f"{scheme}://{host}"
