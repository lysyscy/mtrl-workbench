# -*- coding: utf-8 -*-
"""付款通知书导出 cookie 三段流程回归测试（2026-09-10 fix）。

背景：付款通知书导出原实现只做了「缓存空→登录、缓存非空→直接用」两步，
缺 probe_cookie 探测 + 失败重登重试。导致缓存里的过期 cookie 直接抛
HTTPError 401 给前端，触发「cookie 可能过期，请在桌面环境刷新」笼统提示。

本测试覆盖：
  1. 缓存有效：probe_cookie 通过 → 复用缓存，不重登
  2. 缓存过期：probe_cookie 失败 → 触发真 login_cookie → save_cookie 后 fetch 成功
  3. 抓取中途失败：再触发一次 login_cookie 重试一次
  4. 端点层永远不应回传 "HTTP Error 401" 笼统提示
"""
import os
import json
import pytest


# === 把 input/ 加入 sys.path，让测试直接 import pay_notice_export_http ===
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, 'input'))

import pay_notice_export_http as peh  # noqa: E402


@pytest.fixture
def fake_cookie_path(monkeypatch, tmp_path):
    """把 CONFIG_DIR 隔离到 tmp，避免污染真实 var/cache/。"""
    cfg = tmp_path / 'cache'
    cfg.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(peh.ce, 'CONFIG_DIR', str(cfg))
    # user 参数走 _cookie_path 拼出该 cfg/信息化cookie_<user>.json
    return cfg


def test_cached_cookie_valid_reuse(monkeypatch, fake_cookie_path):
    """路径 1：缓存中 cookie 存在且 probe_cookie 返回 True → 复用、不触发登录/落盘"""
    peh.ce.save_cookie('valid-cookie', source='browser', user='tester')

    login_calls = {'n': 0}
    fetch_calls = {'n': 0}

    def fake_login(u, p):
        login_calls['n'] += 1
        return 'fresh-cookie'

    def fake_probe(c):
        return True   # 探测通过：cookie 有效

    def fake_fetch(ge, le, cookie):
        fetch_calls['n'] += 1
        assert cookie == 'valid-cookie'
        # 返回一条假数据，模拟成功
        return [{'BillNo': 'FKTZSDEMO001', 'BillName': 'demo', 'BillDt': '2026-08-01',
                 'PhidPc_EXName': 'demo项目', 'PhidRecPayType_EXName': '',
                 'PhidBusType_EXName': '', 'PhidPayOrg_EXName': '',
                 'user_skdw_EXName': '', 'ApproveAmt': 100.0,
                 'PhidFillPsn_EXName': '', 'AppStatus': '1', 'Remark': ''}]

    monkeypatch.setattr(peh.ce, 'login_cookie', fake_login)
    monkeypatch.setattr(peh.ce, 'probe_cookie', fake_probe)
    # 不 mock save_cookie：缓存有效分支根本不调它，验证「未触发落盘」用 on_disk 间接断言
    monkeypatch.setattr(peh, 'fetch', fake_fetch)

    on_disk_before = peh.ce.load_cookie('tester')
    out = peh.export(2026, 8, 2026, 8, user='tester', password='')

    assert out is not None and os.path.basename(out).startswith('付款通知书_202608')
    assert login_calls['n'] == 0   # 缓存有效，不应触发登录
    assert fetch_calls['n'] == 1   # 只抓一次
    assert peh.ce.load_cookie('tester') == on_disk_before == 'valid-cookie'


def test_cached_cookie_expired_probe_fail_relogin(monkeypatch, fake_cookie_path):
    """路径 2：缓存中 cookie 过期 → probe_cookie 失败 → 真登录 + save_cookie + fetch 成功"""
    peh.ce.save_cookie('expired-cookie', source='browser', user='tester')

    login_calls = {'n': 0}

    def fake_login(u, p):
        login_calls['n'] += 1
        return 'fresh-cookie'

    def fake_probe(c):
        return False   # 探测失败：过期

    def fake_fetch(ge, le, cookie):
        assert cookie == 'fresh-cookie'
        return [{'BillNo': 'FKTZSDEMO002', 'BillName': 'demo', 'BillDt': '2026-08-01',
                 'PhidPc_EXName': 'demo项目', 'PhidRecPayType_EXName': '',
                 'PhidBusType_EXName': '', 'PhidPayOrg_EXName': '',
                 'user_skdw_EXName': '', 'ApproveAmt': 200.0,
                 'PhidFillPsn_EXName': '', 'AppStatus': '1', 'Remark': ''}]

    monkeypatch.setattr(peh.ce, 'login_cookie', fake_login)
    monkeypatch.setattr(peh.ce, 'probe_cookie', fake_probe)
    # 不 mock peh.ce.save_cookie：保留真写盘行为，便于用 load_cookie 断言盘上数据
    monkeypatch.setattr(peh, 'fetch', fake_fetch)

    out = peh.export(2026, 8, 2026, 8, user='tester', password='')

    assert out is not None and os.path.basename(out).startswith('付款通知书_202608')
    assert login_calls['n'] == 1   # 探测失败 → 触发一次登录
    # 落盘文件内容确实是新 cookie（不是过期的）
    on_disk = peh.ce.load_cookie('tester')
    assert on_disk == 'fresh-cookie'


def test_fetch_midway_failure_triggers_relogin_retry(monkeypatch, fake_cookie_path):
    """路径 3：缓存探测通过、但抓取中途过期 → 再 login_cookie + 二次 fetch 成功"""
    peh.ce.save_cookie('first-cookie', source='browser', user='tester')

    login_calls = {'n': 0}

    def fake_login(u, p):
        login_calls['n'] += 1
        return 'second-cookie'

    def fake_probe(c):
        return True   # 首次探测通过

    fetch_calls = {'n': 0}

    def fake_fetch(ge, le, cookie):
        fetch_calls['n'] += 1
        if cookie == 'first-cookie':
            return None   # 模拟中途过期
        assert cookie == 'second-cookie'
        return [{'BillNo': 'FKTZSDEMO003', 'BillName': 'demo', 'BillDt': '2026-08-01',
                 'PhidPc_EXName': 'demo项目', 'PhidRecPayType_EXName': '',
                 'PhidBusType_EXName': '', 'PhidPayOrg_EXName': '',
                 'user_skdw_EXName': '', 'ApproveAmt': 300.0,
                 'PhidFillPsn_EXName': '', 'AppStatus': '1', 'Remark': ''}]

    monkeypatch.setattr(peh.ce, 'login_cookie', fake_login)
    monkeypatch.setattr(peh.ce, 'probe_cookie', fake_probe)
    monkeypatch.setattr(peh, 'fetch', fake_fetch)

    out = peh.export(2026, 8, 2026, 8, user='tester', password='')

    assert out is not None and os.path.basename(out).startswith('付款通知书_202608')
    assert fetch_calls['n'] == 2          # 首次失败 + 重试成功
    assert login_calls['n'] == 1          # 触发一次登录
    assert peh.ce.load_cookie('tester') == 'second-cookie'


def test_no_cookie_login_then_fetch(monkeypatch, fake_cookie_path):
    """路径 4：完全无缓存 cookie → 直接 login_cookie → save_cookie → fetch"""
    login_calls = {'n': 0}

    def fake_login(u, p):
        login_calls['n'] += 1
        return 'fresh-cookie'

    def fake_fetch(ge, le, cookie):
        assert cookie == 'fresh-cookie'
        return [{'BillNo': 'FKTZSDEMO004', 'BillName': 'demo', 'BillDt': '2026-08-01',
                 'PhidPc_EXName': 'demo项目', 'PhidRecPayType_EXName': '',
                 'PhidBusType_EXName': '', 'PhidPayOrg_EXName': '',
                 'user_skdw_EXName': '', 'ApproveAmt': 400.0,
                 'PhidFillPsn_EXName': '', 'AppStatus': '1', 'Remark': ''}]

    monkeypatch.setattr(peh.ce, 'login_cookie', fake_login)
    monkeypatch.setattr(peh, 'fetch', fake_fetch)

    out = peh.export(2026, 8, 2026, 8, user='tester', password='')

    assert out is not None
    assert login_calls['n'] == 1
    assert peh.ce.load_cookie('tester') == 'fresh-cookie'


def test_three_stage_all_fail_returns_none(monkeypatch, fake_cookie_path):
    """路径 5：三段都失败（登录也失败）→ 返回 None，由上层 pay_api 给明确提示"""
    peh.ce.save_cookie('expired', source='browser', user='tester')

    def fake_login(u, p):
        raise RuntimeError('模拟网络/鉴权异常')

    def fake_probe(c):
        return False   # 探测失败

    monkeypatch.setattr(peh.ce, 'login_cookie', fake_login)
    monkeypatch.setattr(peh.ce, 'probe_cookie', fake_probe)

    out = peh.export(2026, 8, 2026, 8, user='tester', password='')

    assert out is None   # 失败时不再抛 HTTPError，而是显式 None


# === 端点层：永远不应回传 "HTTP Error" 笼统提示 ===
def test_endpoint_no_http_error_text(client, monkeypatch):
    """pay_api.pay_notice_export 即便底层 export() 抛异常也不应回传 "HTTP Error xxx" 原文。

    修复前：底层 urllib HTTPError 冒泡，pay_api except 直接用 str(e) 拼接 →
        "抓取失败：HTTP Error 401: (cookie 可能过期，请在桌面环境刷新)"
    修复后：底层 export() 不会抛 HTTPError，三段全部消化 → 端点的笼统提示兜底但
        不暴露 HTTP 错误细节。
    """
    import sys, os as _os
    sys.path.insert(0, _os.path.join(_ROOT, 'input'))

    # 模拟 export 抛异常（任何类型），验证端点只回包过的错误消息
    def boom(*a, **kw):
        raise RuntimeError('模拟内部失败')

    import pay_api
    monkeypatch.setattr(pay_api, 'importer', type('M', (), {
        'import_pay_notice': lambda *a, **kw: None,
        'import_file': lambda *a, **kw: {},
    })())
    monkeypatch.setattr('pay_notice_export_http.export', boom)
    # monkeypatch 的模块路径跟 import 路径要一致：
    # pay_api 里是 `import pay_notice_export_http as peh`，模块被注入 sys.modules
    import pay_notice_export_http
    monkeypatch.setattr(pay_notice_export_http, 'export', boom)

    r = client.post('/api/pay_notice/export',
                    json={'sy': 2026, 'sm': 8, 'ey': 2026, 'em': 8})
    body = r.get_json()
    assert body['ok'] is False
    # 关键：不应出现裸 HTTP Error 字样
    assert 'HTTP Error' not in body.get('error', ''), body


def test_pay_notice_export_passes_start_end_to_peh(client, monkeypatch):
    """端点接收 start_date/end_date（新契约）→ 解析后以起止日期传给 peh.export。
    验证「归约到起止日期」契约在端点层正确传递。"""
    import sys, os as _os
    sys.path.insert(0, _os.path.join(_ROOT, 'input'))
    import pay_notice_export_http as peh

    captured = {}
    def fake_export(**kw):
        captured.update(kw)
        import tempfile
        f = tempfile.mktemp(suffix='.xlsx')
        with open(f, 'wb') as fh:
            fh.write(b'PK')
        return f
    monkeypatch.setattr(peh, 'export', fake_export)

    import pay_api
    monkeypatch.setattr(pay_api, 'importer', type('M', (), {
        'import_pay_notice': lambda *a, **kw: {'inserted': 0, 'skipped': 0, 'biz_class_stat': {}},
        'import_file': lambda *a, **kw: {},
    })())

    r = client.post('/api/pay_notice/export',
                    json={'start_date': '2026-08-01', 'end_date': '2026-08-31'})
    body = r.get_json()
    assert body['ok'] is True, body
    assert captured.get('start_date') == '2026-08-01'
    assert captured.get('end_date') == '2026-08-31'


def test_pay_notice_export_compat_sy_sm(client, monkeypatch):
    """旧契约 sy/sm 仍兼容：后端归一化为起止日期传给 peh.export。"""
    import sys, os as _os
    sys.path.insert(0, _os.path.join(_ROOT, 'input'))
    import pay_notice_export_http as peh

    captured = {}
    def fake_export(**kw):
        captured.update(kw)
        import tempfile
        f = tempfile.mktemp(suffix='.xlsx')
        with open(f, 'wb') as fh:
            fh.write(b'PK')
        return f
    monkeypatch.setattr(peh, 'export', fake_export)

    import pay_api
    monkeypatch.setattr(pay_api, 'importer', type('M', (), {
        'import_pay_notice': lambda *a, **kw: {'inserted': 0, 'skipped': 0, 'biz_class_stat': {}},
        'import_file': lambda *a, **kw: {},
    })())

    r = client.post('/api/pay_notice/export', json={'sy': 2026, 'sm': 8})
    body = r.get_json()
    assert body['ok'] is True, body
    assert captured.get('start_date') == '2026-08-01'
    assert captured.get('end_date') == '2026-08-31'


@pytest.fixture
def client(monkeypatch, tmp_path):
    """复用现有 db 备份隔离 fixture 风格，再叠加 flask client 注册。"""
    monkeypatch.setattr('db.DB_PATH', str(tmp_path / 'test.db'))
    import db as _db
    _db.init_db()
    from flask import Flask
    import auth
    from api import api as api_bp
    from pay_api import pay_api as pay_bp
    app = Flask(__name__)
    app.config['JSON_AS_ASCII'] = False
    app.secret_key = auth.SECRET_KEY
    app.register_blueprint(api_bp)
    app.register_blueprint(pay_bp)
    c = app.test_client()
    c.post('/api/login', json={'username': 'admin', 'password': '123456'})
    return c
