# -*- coding: utf-8 -*-
"""
材料科数字化工作台 · 程序壳入口
用法: python app/server.py [--port 8000]  然后浏览器打开 http://127.0.0.1:8000
"""
import argparse
import os
import sys
import webbrowser
import threading

# 统一 stdout/stderr = UTF-8 + 容错：避免任何 print 中文/特殊字符（✓）时 Windows GBK 编码失败
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from flask import Flask, render_template  # noqa
from waitress import serve  # noqa

import db  # noqa
import auth  # noqa
from api import api  # noqa
from pay_api import pay_api  # noqa        # 付款域蓝图（从 api.py 拆分，路径不变）


def create_app():
    db.init_db()
    db.backup_if_needed()          # 每天首次启动自动备份（保留最近 8 份）
    app = Flask(__name__, template_folder=os.path.join(BASE, 'templates'),
                static_folder=os.path.join(BASE, 'static'))
    app.register_blueprint(api)
    app.register_blueprint(pay_api)         # 付款域（/api/pay/*、/api/debt），端点路径不变
    app.config['JSON_AS_ASCII'] = False
    app.config['TEMPLATES_AUTO_RELOAD'] = True  # 改模板无需重启服务
    app.secret_key = auth.SECRET_KEY             # 鉴权 session 签名（R1）

    @app.after_request
    def no_cache(resp):
        resp.headers['Cache-Control'] = 'no-store'
        return resp

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/login')
    def login_page():
        return render_template('login.html')

    @app.route('/import')
    def import_page():
        return render_template('import.html')

    @app.route('/pay')
    def pay_page():
        return render_template('pay.html')

    @app.route('/config')
    def config_page():
        return render_template('config.html')

    return app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--host', default='127.0.0.1',
                        help='监听地址；科室两台电脑共用时用 --host 0.0.0.0，并在防火墙放行 8000（仅内网）')
    parser.add_argument('--no-browser', action='store_true', help='不自动打开浏览器')
    args = parser.parse_args()

    app = create_app()
    url = 'http://127.0.0.1:%d' % args.port
    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    print('材料科数字化工作台已启动: %s (host=%s)' % (url, args.host))
    # waitress 生产级 WSGI（R2）：多线程承载，替代 Flask 开发服务器 app.run()
    serve(app, host=args.host, port=args.port, threads=8)


if __name__ == '__main__':
    main()
