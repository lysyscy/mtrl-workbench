"""Use an existing workbench login over HTTP; never connect to its database."""
import argparse
from getpass import getpass
from http.cookies import SimpleCookie
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

PROFILE = Path.home()/'.mtrl-workbench/payment-plan-audit-session.json'


def origin(url):
    u=urlsplit(str(url))
    if (u.scheme not in ('http','https') or not u.hostname or u.username or u.password
            or u.query or u.fragment or u.path not in ('','/')):
        raise ValueError('系统地址须为http或https的主机及端口，不含账号、路径或查询参数')
    return str(url).rstrip('/')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def exchange(url, *, body=None, cookie=None, content_type='application/json'):
    headers={'Accept':'application/json'}
    if body is not None: headers['Content-Type']=content_type
    if cookie: headers['Cookie']='mw_session='+cookie
    try:
        with build_opener(NoRedirect).open(Request(url,data=body,headers=headers),timeout=30) as r:
            return r.status,r.headers,r.read()
    except HTTPError as exc:
        if exc.code == 303:
            return exc.code,exc.headers,b''
        if exc.code==401: raise ValueError('工作台登录已失效，请重新连接登录') from None
        if exc.code==403: raise ValueError('账号或这台电脑不在允许访问范围，请核对系统权限') from None
        if exc.code==404: raise ValueError('系统尚未加载付款计划核对接口，请先加载服务更新') from None
        if exc.code in (409,422):
            try: message=json.loads(exc.read()).get('detail')
            except (ValueError,AttributeError): message=None
            raise ValueError(message if isinstance(message,str) else '核对请求与当前系统状态不符，请重新核对') from None
        raise ValueError('系统接口未正常返回，请检查工作台服务') from None
    except (URLError,TimeoutError):
        raise ValueError('无法连接工作台，请检查系统地址及局域网连接') from None


def call(path, *, server=None, session_file=None, data=None):
    file=Path(session_file) if session_file else PROFILE
    if not file.is_file(): raise ValueError('尚未连接工作台，请先运行remote.py登录一次')
    profile=json.loads(file.read_text(encoding='utf-8'))
    base=origin(profile['server'])
    if server and origin(server)!=base:
        raise ValueError('当前登录属于另一个系统地址，请先连接目标工作台')
    status,_,raw=exchange(base+path,body=json.dumps(data,ensure_ascii=False).encode('utf-8') if data is not None else None,
                          cookie=profile['cookie'])
    if status!=200: raise ValueError('系统要求重新登录，未跟随跳转或发送凭据到其他地址')
    try: return json.loads(raw)
    except ValueError: raise ValueError('系统未返回核对数据，请检查地址和服务版本') from None


def login(server, account, password, session_file=None):
    base=origin(server)
    status,headers,_=exchange(base+'/m15/login',body=urlencode({'account':account,'password':password,'next':'/app'}).encode(),
                              content_type='application/x-www-form-urlencoded')
    cookies=SimpleCookie()
    for h in headers.get_all('Set-Cookie',[]): cookies.load(h)
    if status!=303 or 'mw_session' not in cookies:
        raise ValueError('登录未成功，请核对工作台账号和密码')
    file=Path(session_file) if session_file else PROFILE
    file.parent.mkdir(parents=True,exist_ok=True)
    # 只保存会话，不保存密码；新文件按当前用户权限创建。
    fd=os.open(file,os.O_CREAT|os.O_WRONLY|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as out:
        json.dump({'server':base,'cookie':cookies['mw_session'].value},out)
    return file


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--server',required=True)
    ap.add_argument('--account')
    ap.add_argument('--session-file')
    args=ap.parse_args()
    file=login(args.server,args.account or input('工作台账号：'),getpass('工作台密码：'),args.session_file)
    print('已连接工作台；密码未保存，会话文件：'+str(file))


if __name__=='__main__':
    try: main()
    except ValueError as exc: raise SystemExit(str(exc)) from None
