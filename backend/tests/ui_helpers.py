"""浏览器回归共用夹具：每个场景独立页面和假接口。"""
import os
from pathlib import Path
from urllib.parse import urlparse
import pytest
from playwright.sync_api import sync_playwright
from tests.shell_src import SHELL_PATH
from app.mod03_notice.page import render_theme


def search_notices(page, query):
    """Wait for the debounced search to replace the actual input and results."""
    old = page.locator('#ntSearch').element_handle()
    old.fill(query)
    page.wait_for_function('old=>!old.isConnected', arg=old)

@pytest.fixture
def ui_page():
    web = Path(os.environ.get('MTRL_UI_FIXTURE_WEB', str(SHELL_PATH.parent)))
    os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH', 'C:/ProgramData/ms-playwright')
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={'width': 1440, 'height': 1000})

        def route(req):
            path = urlparse(req.request.url).path
            if path == '/app':
                html = (web / 'index.html').read_text(encoding='utf-8')
                assert html.count('<script>boot();</script>') == 1
                req.fulfill(body=html.replace('<script>boot();</script>', '<script>window.testReady=true;</script>'), content_type='text/html')
            elif path.startswith('/static/shell/'):
                req.fulfill(body=(web / 'shell' / path.rsplit('/', 1)[-1]).read_text(encoding='utf-8'), content_type='text/css' if path.endswith('.css') else 'application/javascript')
            elif path.startswith('/static/fonts/'):
                req.fulfill(body=(web / 'fonts' / path.rsplit('/', 1)[-1]).read_bytes(), content_type='font/woff2')
            elif path == '/static/theme.css':
                req.fulfill(body=render_theme('默认'), content_type='text/css')
            else:
                req.fulfill(body='', content_type='text/css')

        page.route('http://fixture.test/**', route)
        page.goto('http://fixture.test/app', wait_until='load')
        page.wait_for_function('window.testReady')
        page.evaluate('''() => {
          CUR.role='admin'; CUR.name='测试';
          FAILED.clear(); PENDING.clear(); Object.keys(LOADERS).forEach(x=>LOADED.add(x));
          PJs=[{id:'1',type:'normal',name:'测试仓库',disp:'测试项目',full:'测试项目全名',status:'在建',phid:'1',kw:''}];
          NO=[{id:'101',date:bjMonth()+'-02',code:'DOC-101',proj:'测试项目全名',cat:'集采',astat:'已审批',doc:'甲乙材料',biz:'业务列唯一词',recv:'收款列唯一词',sup:'',entry:'录入列唯一词',approve:12345.67,pay:12345.67,ss:12345.67,sp:12345.67,excl:false,manual:false}];
          window.originalPaymentContext=API.paymentContext;
          API.paymentContext=async body=>({ok:true,pay_date:body.pay_date,rows:body.ids.map(id=>({notice_id:id,default_pay_method:NO.find(n=>n.id===String(id))?.plannedPayMethod||'现汇',term_warning:null}))});
          JCs.splice(0); FLs.splice(0); VIEW='m03'; fNt.month='全部';fNt.stat='全部';
          API.jcSupplier=async b=>{window.savedSupplier=b;return {ok:false,message:'隔离写出口已捕获'};};
          render();
        }''')
        page.evaluate('document.fonts.ready')
        yield page
        browser.close()
