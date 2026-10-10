# -*- coding: utf-8 -*-
"""鉴权：用户名+密码登录 + session 装饰器（两人局域网共用，支持人员更迭，2026-09-09）。

用户账号存 users 表（见 db.py），密码用 PBKDF2 加盐哈希存储（不落明文）。
登录成功后 session 写入 authed / user(用户名) / display_name(显示名)，
付款域留痕 operator 取 display_name（空则回退 username）。
"""
import hashlib
import secrets
from functools import wraps

from flask import jsonify, session

# 固定随机串（本地内部工具，够用即可；勿外泄）
SECRET_KEY = 'mtrl-report-2026-09-08-4f2a9c1e7b3d6f8a'

# PBKDF2 迭代次数（登录非高频，100000 次安全且可接受）
_PBKDF2_ITER = 100000


def hash_password(password):
    """PBKDF2-SHA256 加盐哈希，返回 'salt$hexdigest' 字符串。"""
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), _PBKDF2_ITER)
    return '%s$%s' % (salt, dk.hex())


def verify_password(password, stored):
    """校验明文密码与存储哈希；格式非法/为空一律返回 False（恒时比较防时序攻击）。"""
    if not stored or not isinstance(stored, str):
        return False
    try:
        salt, hex_dk = stored.split('$', 1)
    except ValueError:
        return False
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), _PBKDF2_ITER)
    return secrets.compare_digest(dk.hex(), hex_dk)


def login_required(fn):
    """未登录返回 JSON 401 {'ok':False,'error':'未登录'}，前端据此跳转 /login。"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get('authed'):
            return jsonify({'ok': False, 'error': '未登录'}), 401
        return fn(*args, **kwargs)
    return wrapper


# ================= i8 账号密码（可逆混淆，非安全加密） =================
# i8 自动登录需把密码还原成明文填进登录框，故不能用单向哈希，只能可逆混淆
# （base64 + XOR）。注意：这不是安全加密，仅防"直接看到明文"；数据库文件仍须
# 按现有备份/权限纪律保护。

import base64 as _base64

_I8_OBF_KEY = 'mtrl-i8-2026-09-09'


def obfuscate_i8_password(plain):
    """i8 密码 → 可逆混淆串；空串原样返回。"""
    if not plain:
        return ''
    key = _I8_OBF_KEY.encode('utf-8')
    data = plain.encode('utf-8')
    xored = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
    return 'obf1$' + _base64.urlsafe_b64encode(xored).decode('ascii')


def deobfuscate_i8_password(stored):
    """混淆串 → i8 密码明文；非 obf1$ 前缀（历史明文/空）原样返回；解失败返回空。"""
    if not stored:
        return ''
    s = str(stored)
    if not s.startswith('obf1$'):
        return s   # 兼容历史明文
    try:
        xored = _base64.urlsafe_b64decode(s[5:].encode('ascii'))
        key = _I8_OBF_KEY.encode('utf-8')
        return bytes(b ^ key[i % len(key)] for i, b in enumerate(xored)).decode('utf-8')
    except Exception:
        return ''
