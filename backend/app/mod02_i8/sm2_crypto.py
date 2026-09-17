"""i8 登录用 SM2 加密（C1C3C2 / mode=1）。

依据：
- `PRD素材包-20260911/input/http_login.py`（**实现参考**）
- 《材料科业务全流程说明书》**§3.1.2**（已实现**纯 HTTP 登录**、不依赖浏览器）

关于内置私钥：它来自 **i8 登录页前端 JS 的逆向**（前端硬编码私钥是不安全但常见的做法），
**属 i8 前端的公开资产，不是本系统的凭据** ⇒ 内置为默认值；如需替换，用 `.env` 的
`I8_SM2_PRIVATE_KEY` 覆盖。
⚠️ **勿随意改动**：改了服务端就解不了密。
"""

from __future__ import annotations

from functools import lru_cache

from gmssl import sm2

# i8 前端 JS 中硬编码的私钥（逆向所得）—— 改这里服务端会解不了密
_BUILTIN_PRIVATE_KEY = "f66e7342e648af68d9452ecaf9ae4524394c56cffb381bac4fe8d33110ca4bca"


def _private_key() -> str:
    from app.core.config import get_settings

    return (get_settings().i8_sm2_private_key or "").strip() or _BUILTIN_PRIVATE_KEY


@lru_cache
def _crypt(priv: str) -> sm2.CryptSM2:
    """用私钥推导公钥（P = d·G），得到可用于加密的实例。"""
    probe = sm2.CryptSM2(priv, "", mode=1)
    public_key = probe._kg(int(priv, 16), probe.ecc_table["g"])  # noqa: SLF001
    return sm2.CryptSM2(priv, public_key, mode=1)


def sm2_encrypt(plain_text: str) -> str:
    """SM2 加密，返回 **hex 字符串**（i8 的 `body` 参数就吃这个形态）。"""
    plain_text = plain_text if isinstance(plain_text, str) else str(plain_text)
    return _crypt(_private_key()).encrypt(plain_text.encode("utf-8")).hex()
