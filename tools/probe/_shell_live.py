"""真机自检㉘：只读核现行报表契约及通用导入入口退役。"""
from __future__ import annotations

REQUIRED_ROUTES = {
    "/api/m06/matrix": "get",
    "/api/m06/export": "get",
    "/api/m06/mech": "get",
    "/api/m06/workbench": "get",
    "/api/m06/workbench/preview": "get",
    "/api/m06/workbench/export": "get",
    "/api/m06/workbench/{name}": "post",
}
RETIRED_PATHS = ("/api/imp/domains", *(f"/api/imp/{domain}/{endpoint}"
    for domain in ("m06_proc", "m06_mech_report")
    for endpoint in ("schema", "options", "parse", "preview", "commit", "rollback")))


def check(errors: list[str], base: str) -> None:
    """OpenAPI拒全部通用导入；GET探查退役路径，保纯只读且不依赖写会话。"""
    import httpx

    try:
        response = httpx.get(base + "/openapi.json", timeout=20)
        response.raise_for_status()
        paths = response.json()["paths"]
        bad = [f"退役导入仍挂载：{path}" for path in paths if path.startswith("/api/imp/")]
        bad.extend(f"现行报表出口缺失：{method.upper()} {path}"
                   for path, method in REQUIRED_ROUTES.items() if method not in paths.get(path, {}))
        for path in RETIRED_PATHS:
            # 残留的POST路由会对GET回405，仍会失败；不发送可能写库的请求。
            status = httpx.get(base + path, timeout=20).status_code
            if status != 404:
                bad.append(f"退役路径 {path} 返回 {status}，预期404")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"㉘ 读取现行报表与退役入口失败：{type(exc).__name__}: {exc}")
        return
    if bad:
        errors.extend("㉘ " + message for message in bad)
        for message in bad:
            print("   ⛔ " + message)
    else:
        print("㉘ 现行机械/过程报表出口存在，通用导入路径全部404")
