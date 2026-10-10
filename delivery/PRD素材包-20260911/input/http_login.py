# -*- coding: utf-8 -*-
"""
纯 HTTP 登录 i8（不起浏览器）：SM2 国密加密 + SupLogin → KillOnlineUser → SupLogin，返回 cookie。

背景（2026-09-10，方案 B「全自动获取 cookie」）：
- i8 登录接口 `POST /SUP/Login/SupLogin`，body 为 SM2 加密的 JSON（账号/密码/时间戳/sid）
- SM2 私钥硬编码在前端 JS（`sm2Key`），前端用它推导公钥加密，服务端用同一私钥解密
  （前端硬编码私钥是不安全但常见的做法，也因此能纯 HTTP 复现）
- 登录三步：第 1 次 SupLogin 探测（若在线冲突返回强踢提示）→ KillOnlineUser 强踢 → 第 2 次 SupLogin（带 isOnlineCheck）成功
- 依赖 gmssl（pip install gmssl）；服务跑 Session 0 也能登录，替代 playwright 浏览器登录
"""
import json
import time
import uuid
import urllib.request
import urllib.parse
from http.cookiejar import CookieJar

from gmssl import sm2

from consts import BASE_URL, LOGIN_USER

# 硬编码 SM2 私钥（从登录页前端 JS 逆向所得；勿改，改了服务端解不了密）
SM2_PRIVATE_KEY = 'f66e7342e648af68d9452ecaf9ae4524394c56cffb381bac4fe8d33110ca4bca'

_crypt = sm2.CryptSM2(SM2_PRIVATE_KEY, '', mode=1)  # mode=1 对应 C1C3C2（sm-crypto 默认）
SM2_PUBLIC_KEY = _crypt._kg(int(SM2_PRIVATE_KEY, 16), _crypt.ecc_table['g'])  # 私钥×G 推导公钥


def sm2_encrypt(plain_text):
    """用硬编码私钥推导的公钥做 SM2 加密，返回 hex 字符串。"""
    c = sm2.CryptSM2(SM2_PRIVATE_KEY, SM2_PUBLIC_KEY, mode=1)
    return c.encrypt(plain_text.encode('utf-8')).hex()


def _post(opener, url, form):
    data = urllib.parse.urlencode(form).encode('utf-8')
    req = urllib.request.Request(url, data=data, method='POST')
    req.add_header('Content-Type', 'application/x-www-form-urlencoded; charset=UTF-8')
    req.add_header('User-Agent', 'Mozilla/5.0')
    req.add_header('X-Requested-With', 'XMLHttpRequest')
    try:
        r = opener.open(req, timeout=30)
        return r.status, r.headers, r.read().decode('utf-8', 'ignore')
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read().decode('utf-8', 'ignore')


def http_login(user, password):
    """纯 HTTP 登录 i8，返回 cookie 字符串（成功）；失败返回 None。
    user/password：i8 账号（无密码传空串；user 为空回退默认 LOGIN_USER）。"""
    user = user or LOGIN_USER
    jar = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    sid = uuid.uuid4().hex  # sid 服务端不校验来源，自生成 UUID 即可

    def build_plain(is_online_check=None):
        d = {'orgCode': '', 'isWeb': 1, 'userId': user, 'userPwd': password or '',
             'dataBase': '0001', 'account': '0001', 'CustomerCode': '0001',
             'language': 'zh-Cn', 'tm': str(int(time.time() * 1000)), 'sid': sid}
        if is_online_check is not None:
            d['isOnlineCheck'] = is_online_check
        return json.dumps(d, separators=(',', ':'))

    # 1) 第 1 次 SupLogin：探测；若在线冲突返回强踢信息
    _st, _hd, bd = _post(opener, BASE_URL + '/SUP/Login/SupLogin', {'body': sm2_encrypt(build_plain())})
    try:
        resp = json.loads(bd)
        if not resp.get('success') and resp.get('msg'):
            inner = json.loads(resp['msg'])
            if inner.get('sessionID'):
                # 2) 强踢（挤掉同账号在线会话）
                _post(opener, BASE_URL + '/SUP/Login/KillOnlineUser', {
                    'ipAddress': inner.get('ipAddress') or '', 'sessionID': inner['sessionID'],
                    'userId': inner.get('userId') or '', 'account': inner.get('uCode') or '0001'})
    except Exception:
        pass

    # 3) 第 2 次 SupLogin（isOnlineCheck=1）：正式登录
    _st, _hd, bd = _post(opener, BASE_URL + '/SUP/Login/SupLogin', {'body': sm2_encrypt(build_plain('1'))})
    try:
        if not json.loads(bd).get('accesstoken'):
            return None
    except Exception:
        return None
    return '; '.join('%s=%s' % (c.name, c.value) for c in jar)


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    u = sys.argv[1] if len(sys.argv) > 1 else 'SCY980803'
    p = sys.argv[2] if len(sys.argv) > 2 else ''
    ck = http_login(u, p)
    print('登录%s：%s' % ('成功' if ck else '失败', u))
    if ck:
        print(ck)
