"""
信息化报表 HTTP 导出通用引擎（sfjc/kcdj 共用，新表导出直接复用）：
- 项目 ID（phid）抓一次后持久化到 var/cache/项目列表.json，之后直接复用（--refresh 强制重抓）
- cookie 按 i8 账号分文件缓存在 var/cache/信息化cookie_{账号}.json，失效时优先纯 HTTP 登录（0.3s）、浏览器兜底
- 支持直接传项目 ID（程序壳 export_runner 从库读 phid 传入，零浏览器）
- 导出 = 纯 HTTP POST /reportcenter/reportExport/export，响应直接是 xlsx（PK 开头）

各表只需提供：report_id / dataset_id / 项目参数key(proj_param) / 报表名 / 报表URL
"""
import sys
import os
import time
import json
import urllib.request
import urllib.error
import urllib.parse
import calendar

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from consts import PORTAL_URL, BASE_URL, LOGIN_USER
import playwright_ops as ops

# 子进程 stdio 统一 UTF-8 + 容错（避免父进程 utf-8 解码 0xd3 等 GBK 字节时抛 UnicodeDecodeError；
# 子进程入口 sfjc/kcdj_export_http.py import 本模块时即生效）
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

EXPORT_URL = BASE_URL + '/reportcenter/reportExport/export'
_BASE = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(_BASE, '..', 'var', 'downloads')
CONFIG_DIR = os.path.join(_BASE, '..', 'var', 'cache')
PROJ_CACHE = os.path.join(CONFIG_DIR, '项目列表.json')

_T0 = time.time()


def log(m):
    print('[%4.1fs] %s' % (time.time() - _T0, m), flush=True)


# ---------- 缓存读写（所有报表共用项目列表/cookie） ----------
def load_proj():
    try:
        with open(PROJ_CACHE, encoding='utf-8') as f:
            d = json.load(f)
        if d.get('ids'):
            return d['ids'], d.get('fetched_at', '')
    except Exception:
        pass
    return None, ''


def save_proj(ids):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(PROJ_CACHE, 'w', encoding='utf-8') as f:
        json.dump({'ids': ids, 'fetched_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                   'count': len(ids.split(','))}, f, ensure_ascii=False, indent=2)
    log('项目列表已缓存(%d个项目)' % len(ids.split(',')))


def _cookie_path(user=None):
    """按 i8 账号分 cookie 文件（账号绑定阶段二）；无账号回退 LOGIN_USER。"""
    u = (user or LOGIN_USER).strip() or LOGIN_USER
    safe = ''.join(ch for ch in u if ch.isalnum() or ch in '_-')
    return os.path.join(CONFIG_DIR, '信息化cookie_%s.json' % (safe or LOGIN_USER))


def load_cookie(user=None):
    """读取指定账号的 cookie 字符串；兼容新 JSON 格式与旧纯文本格式。"""
    c, _, _ = load_cookie_meta(user)
    return c


def load_cookie_meta(user=None):
    """返回 (cookie, fetched_at, source)。新格式为 JSON（带元数据），旧格式为纯文本（无元数据）。"""
    try:
        with open(_cookie_path(user), encoding='utf-8') as f:
            raw = f.read().strip()
        if not raw:
            return None, '', ''
        try:
            d = json.loads(raw)
            if isinstance(d, dict) and d.get('cookie'):
                return d['cookie'], d.get('fetched_at', ''), d.get('source', '')
        except Exception:
            pass
        return raw, '', 'legacy'   # 旧纯文本格式，向后兼容
    except Exception:
        return None, '', ''


def save_cookie(c, source='browser', user=None):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(_cookie_path(user), 'w', encoding='utf-8') as f:
        json.dump({'cookie': c, 'fetched_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                   'source': source}, f, ensure_ascii=False, indent=2)
    log('cookie 已缓存(%d字符, %s, 账号=%s)' % (len(c), source, user or LOGIN_USER))


def probe_cookie(cookie):
    """轻量探测 cookie 是否有效：getList 抓当前月 limit=1。
    返回 True=有效；False=失效或网络异常（401/HTTPError/JSON异常均视为失效）。
    目的：导出前主动发现失效，避免一次完整导出失败才被动重试。"""
    now = time.localtime()
    y, m = now.tm_year, now.tm_mon
    ge = '%04d-%02d-01' % (y, m)
    le = '%04d-%02d-%02d' % (y, m, calendar.monthrange(y, m)[1])
    queryfilter = json.dumps({'queryFilter': json.dumps({
        'BillDt*date*ge*1': ge, 'BillDt*date*le*1': le})}, ensure_ascii=False)
    form = {
        'busType': 'PaymentBill', 'pageId': 'Web:PaymentBill', 'isLoadHistory': '1',
        'relateId': '14', 'inputSource': '2', 'queryfilter': queryfilter,
        'phidOrgList': '3700000000000014', 'phidProjList': '', 'dataKey': '',
        'saveTableName': 'fc3_code_table', 'payStatus': '0',
        'summaryCols': 'ApplyAmtFc,ApplyAmt,ApproveAmtFc,ApproveAmt',
        'limit': '1', 'page': '0', 'start': '0',
    }
    body = urllib.parse.urlencode(form).encode('utf-8')
    req = urllib.request.Request(BASE_URL + '/FC/FM/PaymentBill/getList', data=body, method='POST')
    req.add_header('Content-Type', 'application/x-www-form-urlencoded; charset=UTF-8')
    req.add_header('Cookie', cookie)
    req.add_header('User-Agent', 'Mozilla/5.0')
    req.add_header('X-Requested-With', 'XMLHttpRequest')
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            j = json.loads(r.read().decode('utf-8', 'ignore'))
        return bool(j.get('ok') or j.get('Record') is not None)
    except urllib.error.HTTPError as e:
        log('probe_cookie: HTTP %s（cookie 失效或不可用）' % e.code)
        return False
    except Exception as e:
        log('probe_cookie: 异常 %s' % type(e).__name__)
        return False


# ---------- 浏览器动作（仅需时用） ----------
def login_cookie(user=None, password=None):
    """会话过期时重新登录拿 cookie。
    优先纯 HTTP 登录（http_login：SM2 加密 + SupLogin，不起浏览器，Session 0 也能用）；
    失败回退浏览器 playwright 真登录（桌面会话）。
    user/password 为 i8 账号（账号绑定阶段二：按人传各自账号，默认回退 SCY980803）。"""
    # 优先：纯 HTTP 登录（方案 B，全自动获取 cookie，不依赖浏览器/桌面）
    try:
        import http_login as hl
        c = hl.http_login(user, password)
        if c:
            log('纯 HTTP 登录成功（账号=%s）' % (user or LOGIN_USER))
            return c
        log('纯 HTTP 登录返回空 cookie，回退浏览器登录')
    except Exception as e:
        log('纯 HTTP 登录失败，回退浏览器登录：%s' % e)
    # 回退：浏览器 playwright 真登录（Session 0 下会失败，提示桌面刷新）
    p = ops.PW()
    p.start()
    try:
        p.page.goto(PORTAL_URL, timeout=60000)
        try:
            p.page.wait_for_load_state('domcontentloaded', timeout=15000)
        except Exception:
            pass
        time.sleep(1)
        # 清登录态强制回登录页（避免 localStorage 缓存导致"已登录"误判，取到过期 cookie）
        p.ctx.clear_cookies()
        try:
            p.page.evaluate('localStorage.clear(); sessionStorage.clear();')
        except Exception:
            pass
        p.page.goto(PORTAL_URL, timeout=60000)
        try:
            p.page.wait_for_load_state('domcontentloaded', timeout=15000)
        except Exception:
            pass
        time.sleep(2)
        if p.is_login_page():
            p.do_login(log, user, password)
            for _ in range(20):          # 等登录跳转完成（登录页消失即已进门户）
                time.sleep(1.5)
                if not p.is_login_page():
                    break
            time.sleep(2)
        else:
            log('  浏览器已是登录态，直接取 cookie')
        return '; '.join('%s=%s' % (c['name'], c['value']) for c in p.ctx.cookies())
    finally:
        try:
            p.stop()
        except Exception:
            pass


def fetch_proj(report_url, proj_param, y1, m1, y2, m2):
    """进报表页选条件，点查询抓 getReportData 的项目参数（跑完自动关页）"""
    p = ops.PW()
    p.start()
    try:
        if not p.ensure_report_page(report_url, log):
            raise RuntimeError('进报表页失败')
        fx, fy = p.frame_off()
        p.expand_more(fx, fy, log)
        p.set_period(y1, m1, y2, m2, fx, fy, log)
        captured = {}

        def on_req(req):
            if 'getReportData' in req.url:
                captured['data'] = req.post_data

        p.page.on('request', on_req)
        p.select_all_projects(fx, fy, log)
        # '排污泵' 为任意非空文本占位：click_query 用它等待页面出现内容，从而触发查询；
        # 抓的是 getReportData 的请求参数，过滤结果不依赖该文本本身。
        p.click_query(['排污泵'], fx, fy, log)
        time.sleep(3)
        if 'data' not in captured:
            raise RuntimeError('未抓到 getReportData')
        qd = json.loads(captured['data'])
        for sp in qd.get('queryParams', []):
            for q in sp.get('sheetQueryParams', []):
                if q.get('paramKey') == proj_param:
                    ids = q.get('paramValue')
        if not ids:
            raise RuntimeError('%s 为空' % proj_param)
        log('项目ID(%d个): %s' % (len(ids.split(',')), ids))
        return ids
    finally:
        try:
            p.stop()
        except Exception:
            pass


# ---------- HTTP 导出 ----------
def build_body(y1, m1, y2, m2, proj_ids, report_id, dataset_id, proj_param, report_name=None):
    """构造导出请求体（服务器按 paramKey 识别参数，顺序无关）"""
    return {
        "reportId": report_id,
        "reportName": report_name,
        "dataSetIds": [],
        "queryParams": [{
            "sheetKey": "0",
            "sheetQueryParams": [
                {"paramKey": "a", "dataSetId": dataset_id, "paramValueSource": "user_input",
                 "operator": "in", "fieldType": None, "paramValue": y1, "paramType": "1", "label": "开始核算年"},
                {"paramKey": "b", "dataSetId": dataset_id, "paramValueSource": "user_input",
                 "operator": "in", "fieldType": None, "paramValue": m1, "paramType": "1", "label": "开始核算月"},
                {"paramKey": "aa", "dataSetId": dataset_id, "paramValueSource": "user_input",
                 "operator": "in", "fieldType": None, "paramValue": y2, "paramType": "1", "label": "结束核算年"},
                {"paramKey": "bb", "dataSetId": dataset_id, "paramValueSource": "user_input",
                 "operator": "in", "fieldType": None, "paramValue": m2, "paramType": "1", "label": "结束核算月"},
                {"paramKey": proj_param, "dataSetId": dataset_id, "paramValueSource": "user_input",
                 "operator": "in", "fieldType": "0", "paramValue": proj_ids, "paramType": "0", "label": "项目信息"}
            ]
        }],
        "querySetting": None,
        "exportType": "excel",
        "filters": []
    }


def http_export(y1, m1, y2, m2, proj_ids, cookie_str, report_id, dataset_id, proj_param, report_name=None):
    """纯 HTTP 导出，成功返回 xlsx bytes，失败返回 None"""
    body = build_body(y1, m1, y2, m2, proj_ids, report_id, dataset_id, proj_param, report_name)
    req = urllib.request.Request(EXPORT_URL, data=json.dumps(body).encode('utf-8'), method='POST')
    req.add_header('Content-Type', 'application/json;charset=UTF-8')
    req.add_header('Cookie', cookie_str)
    req.add_header('User-Agent', 'Mozilla/5.0')
    req.add_header('X-Requested-With', 'XMLHttpRequest')
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            resp = r.read()
        if len(resp) < 10000 or resp[:2] != b'PK':
            log('!! 导出响应异常: %s' % resp[:200])
            return None
        return resp
    except urllib.error.HTTPError as e:
        log('!! 导出 HTTP %s: %s' % (e.code, e.read().decode('utf-8', 'ignore')[:150]))
        return None
    except Exception as e:
        log('!! 导出异常: %s' % e)
        return None


def export_report(y1, m1, y2, m2, *, report_id, dataset_id, proj_param,
                  report_name=None, file_name=None, report_url=None, proj_ids=None, refresh=False,
                  user=None, password=None):
    """完整导出流程：项目ID(直传>缓存>浏览器抓) → cookie(缓存>浏览器) → HTTP导出(+cookie刷新重试) → 落盘
    report_name 为请求体字段（kcdj 需 None）；file_name 为落盘文件名（缺省用 report_name）
    成功返回输出文件绝对路径（stdout 打印 RESULT_PATH=...），失败返回 None"""
    # 1) 项目 ID
    if proj_ids:
        log('使用数据库项目ID(%d个)' % len(proj_ids.split(',')))
    elif refresh:
        log('--refresh：强制重新抓项目列表')
        proj_ids = fetch_proj(report_url, proj_param, y1, m1, y2, m2)
        save_proj(proj_ids)
    else:
        proj_ids, fetched_at = load_proj()
        if proj_ids:
            log('使用缓存项目列表(%d个，抓取于 %s)；有新项目请加 --refresh' % (
                len(proj_ids.split(',')), fetched_at or '未知'))
        else:
            log('无缓存项目列表，用浏览器抓取...')
            proj_ids = fetch_proj(report_url, proj_param, y1, m1, y2, m2)
            save_proj(proj_ids)

    # 2) cookie（按账号）：优先缓存 → 主动探测 → 失效则浏览器刷新
    cookie = load_cookie(user)
    if not cookie:
        log('无缓存cookie（账号=%s），浏览器登录后获取...' % (user or LOGIN_USER))
        cookie = login_cookie(user, password)
        save_cookie(cookie, user=user)
    elif not probe_cookie(cookie):
        log('cookie 已失效（账号=%s），浏览器重新登录...' % (user or LOGIN_USER))
        try:
            cookie = login_cookie(user, password)
            save_cookie(cookie, user=user)
        except Exception as e:
            log('!! 浏览器登录失败（服务跑在 Session 0 时无桌面，请改用桌面执行 scripts/refresh_cookie.py）：%s' % e)
            return None

    log('正在请求信息化导出...')
    resp = http_export(y1, m1, y2, m2, proj_ids, cookie, report_id, dataset_id, proj_param, report_name)
    if resp is None:
        log('导出失败，浏览器重新登录后重试一次...')
        cookie = login_cookie(user, password)          # 真登录（纯 HTTP 优先，失败回退浏览器）
        save_cookie(cookie, user=user)
        resp = http_export(y1, m1, y2, m2, proj_ids, cookie, report_id, dataset_id, proj_param, report_name)
        if resp is None:
            return None
    log('导出完成')

    name = file_name or report_name or '报表'
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    out = os.path.join(DOWNLOAD_DIR, '%s_%s.xlsx' % (name, time.strftime('%Y%m%d%H%M%S')))
    with open(out, 'wb') as f:
        f.write(resp)
    print('RESULT_PATH=%s' % out)
    return out
