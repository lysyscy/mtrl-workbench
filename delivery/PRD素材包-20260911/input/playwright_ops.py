"""
信息化通用操作模块 playwright 版（脱离 bu，本地独立运行）
供各表导出脚本复用：导航/登录/iframe穿透/antd控件/导出下载/关页
坐标系统：像素。报表iframe内元素坐标 + iframe偏移 = 视口坐标 -> mouse.click(px)
视口固定 1400x900，不受用户窗口大小影响（解决分辨率漂移问题）。
"""
import os
import time
from playwright.sync_api import sync_playwright

from consts import LOGIN_USER

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILE_DIR = os.path.join(ROOT, 'browser_profile')          # 持久化登录态
DOWNLOAD_DIR = os.path.join(ROOT, 'var', 'downloads')            # 导出文件落盘
VIEWPORT = {'width': 1400, 'height': 900}

_REP_IF = ("(function(){var fs=document.querySelectorAll('iframe');"
           "for(var i=0;i<fs.length;i++){if((fs[i].src||'').indexOf('report')>=0)return fs[i];}"
           "var f=null,ma=0;for(var j=0;j<fs.length;j++){var b=fs[j].getBoundingClientRect();"
           "var a=b.width*b.height;if(a>ma){ma=a;f=fs[j];}}return f;})")


class PW:
    def __init__(self):
        self._pw = None
        self.ctx = None
        self.page = None

    # ---------- 生命周期 ----------
    def start(self, headless=False, hidden=True):
        os.makedirs(PROFILE_DIR, exist_ok=True)
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        self._pw = sync_playwright().start()
        args = ['--window-position=-32000,-32000'] if hidden else []
        self.ctx = self._pw.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            channel='msedge',
            headless=headless,
            viewport=VIEWPORT,
            accept_downloads=True,
            args=args,
        )
        self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()

    def stop(self):
        try:
            if self.ctx:
                self.ctx.close()
        except Exception:
            pass
        try:
            if self._pw:
                self._pw.stop()
        except Exception:
            pass

    # ---------- 基础 ----------
    def js(self, expr):
        return self.page.evaluate(expr)

    def page_text(self):
        try:
            return self.page.inner_text('body')
        except Exception:
            return ''

    def cur_url(self):
        try:
            return self.page.url
        except Exception:
            return ''

    def wait_until(self, cond_js, timeout=6, interval=0.25):
        t = time.time()
        while time.time() - t < timeout:
            try:
                if self.js(cond_js) == 'true':
                    return True
            except Exception:
                pass
            time.sleep(interval)
        return False

    def wait_until_f(self, cond_js, timeout=6, interval=0.25):
        """iframe内条件等待"""
        t = time.time()
        while time.time() - t < timeout:
            try:
                if self.jsf(cond_js) == 'true':
                    return True
            except Exception:
                pass
            time.sleep(interval)
        return False

    def click(self, x, y):
        self.page.mouse.click(x, y)

    def press(self, key):
        self.page.keyboard.press(key)

    def sleep(self, s):
        time.sleep(s)

    # ---------- 报表iframe穿透 ----------
    def rep_frame(self, retry=5):
        """返回真正的报表iframe frame（优先 ngweb/report 开头的），并校验其可执行"""
        for _ in range(retry):
            f = None
            for x in self.page.frames:
                u = x.url or ''
                if 'ngweb/report' in u:
                    f = x
                    break
            if f is None:
                # 退而求其次：顶层最大iframe
                r = self.js("(function(){var f=" + _REP_IF + "();return f?f.getAttribute('src')||'':'';})()")
                if r:
                    for x in self.page.frames:
                        if r and r in (x.url or ''):
                            f = x
                            break
            if f is not None:
                try:
                    f.evaluate('1+1')
                    return f
                except Exception:
                    pass  # frame 正在替换/加载，等待重试
            time.sleep(1)
        return None

    def jsf(self, expr, retry=3):
        """在报表iframe文档内执行JS：顶层定位iframe -> contentWindow.eval（避开 frame.evaluate 通道）"""
        import json as _json
        body = expr
        if expr.startswith('(function(){') and expr.endswith('})()'):
            body = expr[len('(function(){'):-len('})()')]
        inner = _json.dumps('(function(){' + body + '})()')
        wrapped = ("(function(){var f=" + _REP_IF + "();"
                   "if(!f||!f.contentWindow)return '__NOFRAME__';"
                   "var w=f.contentWindow;try{var r=w.eval(" + inner + ");return r===undefined?'__UNDEF__':r;}"
                   "catch(e){return '__EVALERR__:'+e.message;}})()")
        last = None
        for _ in range(retry):
            try:
                r = self.page.evaluate(wrapped)
                if r == '__NOFRAME__':
                    last = '报表iframe未找到'
                elif isinstance(r, str) and r.startswith('__EVALERR__'):
                    last = r
                else:
                    return r
            except Exception as e:
                last = e
            time.sleep(0.8)
        raise RuntimeError('报表iframe不可用: %s' % (last,))

    def frame_off(self):
        """报表iframe在视口中的偏移(px)"""
        try:
            r = self.js("(function(){var f=" + _REP_IF + "();if(!f)return '0,0';"
                        "var r=f.getBoundingClientRect();return Math.round(r.x)+','+Math.round(r.y);})()")
            x, y = r.split(',')
            return int(x), int(y)
        except Exception:
            return 0, 0

    def vp(self, x, y, fx, fy):
        """iframe内坐标 -> 视口像素坐标"""
        return x + fx, y + fy

    def click_vp(self, x, y, fx, fy):
        self.click(x + fx, y + fy)

    def wait_table_rows(self, min_rows, timeout=15):
        cond = ("(function(){var f=" + _REP_IF + "();var d=f.contentDocument;"
                "var tb=d.querySelectorAll('table tbody tr');"
                "var rows=[].filter.call(tb,function(r){return r.cells.length>2;});"
                "return rows.length>" + str(min_rows) + "?'true':'false';})()")
        return self.wait_until_f(cond, timeout=timeout)

    # ---------- 报表iframe内元素定位（返回px坐标） ----------
    def sel_rect(self, idx):
        r = self.jsf("(function(){var d=document;var s=d.querySelectorAll('.ant-select')[" + str(idx) + "];"
                     "if(!s)return 'none';var r=s.getBoundingClientRect();"
                     "return Math.round(r.x)+','+Math.round(r.y)+','+Math.round(r.width)+','+Math.round(r.height);})()")
        if r == 'none':
            return None
        x, y, w, h = map(int, r.split(','))
        return x, y, w, h

    def arrow_pos(self, idx):
        r = self.jsf("(function(){var d=document;var s=d.querySelectorAll('.ant-select')[" + str(idx) + "];"
                     "if(!s)return 'none';var a=s.querySelector('.ant-select-arrow');if(!a)return 'none';"
                     "var r=a.getBoundingClientRect();if(r.width===0&&r.height===0)return 'none';"
                     "return Math.round(r.x)+','+Math.round(r.y);})()")
        if r == 'none':
            return None
        x, y = map(int, r.split(','))
        return x, y

    def sel_open_js(self, idx):
        return ("(function(){var d=document;var s=d.querySelectorAll('.ant-select')[" + str(idx) + "];"
                "return s&&s.className.indexOf('ant-select-open')>=0?'true':'false';})()")

    def sel_val_js(self, idx, val):
        return ("(function(){var d=document;var s=d.querySelectorAll('.ant-select')[" + str(idx) + "];"
                "var st=s.querySelector('.ant-select-selection-item');"
                "return (st&&st.textContent.trim()==='" + val + "')?'true':'false';})()")

    def dd_active(self):
        return self.jsf("(function(){var d=document;var dds=d.querySelectorAll('.ant-select-dropdown');"
                        "for(var i=0;i<dds.length;i++){var r=dds[i].getBoundingClientRect();"
                        "if(r.width>0&&r.height>0){var a=dds[i].querySelector('.ant-select-item-option-active');"
                        "if(a)return a.textContent.trim();}}return 'none';})()")

    def find_text(self, text):
        r = self.jsf("(function(){var d=document;var all=d.querySelectorAll('button,.ant-dropdown-trigger,[class*=btn]');"
                     "for(var i=0;i<all.length;i++){if((all[i].textContent||'').trim()==='" + text + "'){"
                     "var r=all[i].getBoundingClientRect();if(r.width>0&&r.height>0)"
                     "return Math.round(r.x)+','+Math.round(r.y)+','+Math.round(r.width)+','+Math.round(r.height);}}"
                     "return 'none';})()")
        if r == 'none':
            return None
        return tuple(map(int, r.split(',')))

    def find_icon(self, cls_sub, xmin=0, xmax=99999, ymax=99999):
        r = self.jsf("(function(){var d=document;var els=d.querySelectorAll('[class*=" + cls_sub + "]');"
                     "for(var i=0;i<els.length;i++){var r=els[i].getBoundingClientRect();"
                     "if(r.width>0&&r.height>0&&r.x>=" + str(xmin) + "&&r.x<=" + str(xmax) + "&&r.y<=" + str(ymax) + ")"
                     "return Math.round(r.x)+','+Math.round(r.y)+','+Math.round(r.width)+','+Math.round(r.height);}"
                     "return 'none';})()")
        if r == 'none':
            return None
        return tuple(map(int, r.split(',')))

    def find_in_modal(self, text):
        r = self.jsf("(function(){var d=document;var m=d.querySelector('.ant-modal-content')||d.querySelector('.ant-modal-wrap');"
                     "if(!m)return 'none';var all=m.querySelectorAll('button,a,[class*=btn]');"
                     "for(var i=0;i<all.length;i++){if((all[i].textContent||'').trim()==='" + text + "'){"
                     "var r=all[i].getBoundingClientRect();if(r.width>0&&r.height>0)"
                     "return Math.round(r.x)+','+Math.round(r.y)+','+Math.round(r.width)+','+Math.round(r.height);}}"
                     "return 'none';})()")
        if r == 'none':
            return None
        return tuple(map(int, r.split(',')))

    def find_icon_in_modal(self, cls_sub):
        r = self.jsf("(function(){var d=document;var m=d.querySelector('.ant-modal-content')||d.querySelector('.ant-modal-wrap');"
                     "if(!m)return 'none';var els=m.querySelectorAll('[class*=" + cls_sub + "]');"
                     "for(var i=0;i<els.length;i++){var r=els[i].getBoundingClientRect();"
                     "if(r.width>8&&r.height>8)return Math.round(r.x)+','+Math.round(r.y)+','+Math.round(r.width)+','+Math.round(r.height);}"
                     "return 'none';})()")
        if r == 'none':
            return None
        return tuple(map(int, r.split(',')))

    # ---------- antd 下拉键盘选择 ----------
    def pick_select(self, idx, val, fx, fy):
        for attempt in range(2):
            try:
                self.click_vp(700, 520, fx, fy)
                self.sleep(0.3)
            except Exception:
                pass
            ar = self.arrow_pos(idx)
            if not ar:
                p = self.sel_rect(idx)
                if not p:
                    return False
                ar = (p[0] + p[2] // 2, p[1] + p[3] // 2)
            self.click_vp(ar[0], ar[1], fx, fy)
            if self.wait_until_f(self.sel_open_js(idx), timeout=3):
                break
        else:
            return False
        cur = 'none'
        t = time.time()
        while time.time() - t < 2:
            cur = self.dd_active()
            if cur != 'none':
                break
            time.sleep(0.2)
        try:
            diff = int(val) - int(cur)
        except Exception:
            try:
                self.click_vp(700, 520, fx, fy)
            except Exception:
                pass
            return False
        for _ in range(min(abs(diff), 20)):
            self.press('ArrowDown' if diff > 0 else 'ArrowUp')
            time.sleep(0.07)
        time.sleep(0.3)
        self.press('Enter')
        ok = self.wait_until_f(self.sel_val_js(idx, val), timeout=3)
        time.sleep(0.3)
        return ok

    # ---------- 导航与登录 ----------
    def top_btn(self, text):
        r = self.js("(function(){var all=document.querySelectorAll('button,a');"
                    "for(var i=0;i<all.length;i++){if((all[i].textContent||'').trim().indexOf('" + text + "')>=0){"
                    "var r=all[i].getBoundingClientRect();if(r.width>0&&r.height>0)"
                    "return Math.round(r.x)+','+Math.round(r.y)+','+Math.round(r.width)+','+Math.round(r.height);}}"
                    "return 'none';})()")
        if r == 'none':
            return None
        return tuple(map(int, r.split(',')))

    def do_login(self, log, user=None, password=None):
        u = user or LOGIN_USER
        log('检测到登录页，自动登录 %s%s' % (u, '（带密码）' if password else ''))
        self.js("(function(){var i=document.querySelector('#userId');if(!i)return 'no';"
                "var s=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;"
                "s.call(i,'" + u + "');i.dispatchEvent(new Event('input',{bubbles:true}));"
                "i.dispatchEvent(new Event('change',{bubbles:true}));return 'ok';})()")
        time.sleep(0.5)
        v = self.js("(function(){var i=document.querySelector('#userId');return i?i.value:'no';})()")
        if v != u:
            try:
                r = self.js("(function(){var i=document.querySelector('#userId');"
                            "var r=i.getBoundingClientRect();"
                            "return Math.round(r.x)+','+Math.round(r.y)+','+Math.round(r.width)+','+Math.round(r.height);})()")
                if r != 'none':
                    x, y, w, h = map(int, r.split(','))
                    self.click(x + w // 2, y + h // 2)
                    time.sleep(0.3)
            except Exception:
                pass
            self.page.keyboard.type(u)
        # 密码框（有密码才填）：input[type=password] 通用定位（i8 登录页账号 #userId + 密码框）
        if password:
            self.js("(function(){var i=document.querySelector('input[type=password]');if(!i)return 'no';"
                    "var s=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;"
                    "s.call(i,'" + password + "');i.dispatchEvent(new Event('input',{bubbles:true}));"
                    "i.dispatchEvent(new Event('change',{bubbles:true}));return 'ok';})()")
        btn = self.top_btn('登 录') or self.top_btn('登录')
        if btn:
            self.click(btn[0] + btn[2] // 2, btn[1] + btn[3] // 2)
            log('  已点登录')
        for _ in range(8):
            if '强行登录' in self.page_text():
                ok = self.top_btn('确 定') or self.top_btn('确定')
                if ok:
                    self.click(ok[0] + ok[2] // 2, ok[1] + ok[3] // 2)
                    log('  已确认强踢（挤掉其他登录）')
                    break
            time.sleep(1)

    def at_report_url(self):
        return self.js("(function(){var h=location.href;"
                       "return (h.indexOf('sub/iframe')>=0||h.indexOf('sub/report')>=0)?'yes':'no';})()") == 'yes'

    def report_ready(self):
        return self.js("(function(){var h=location.href;"
                       "if(h.indexOf('sub/iframe')<0&&h.indexOf('sub/report')<0)return 'no';"
                       "var fs=document.querySelectorAll('iframe');"
                       "for(var i=0;i<fs.length;i++){var b=fs[i].getBoundingClientRect();"
                       "if(b.width>500&&b.height>200&&(fs[i].src||'').indexOf('report')>=0)return 'yes';}"
                       "return 'no';})()") == 'yes'

    def is_login_page(self):
        txt = self.page_text()
        return '用户名' in txt and '登' in txt and '录' in txt

    def ensure_report_page(self, url, log):
        log('导航到报表页')
        try:
            self.page.goto(url, timeout=60000)
        except Exception:
            pass
        try:
            self.page.wait_for_load_state('domcontentloaded', timeout=15000)
        except Exception:
            pass
        for _ in range(20):
            time.sleep(1.5)
            if self.report_ready():
                t = time.time()
                while time.time() - t < 30:
                    p = self.sel_rect(0)
                    if p and p[2] > 20:
                        return True
                    time.sleep(0.5)
                return True
            if self.is_login_page():
                self.do_login(log)
                time.sleep(1.5)
                continue
            if not self.at_report_url():
                log('  页面未在报表链接，JS跳转')
                self.js("window.location.replace('" + url + "')")
            else:
                log('  报表页加载中，继续等待')
        log('  !! 报表页加载超时')
        return False

    # ---------- 通用交互 ----------
    def expand_more(self, fx, fy, log):
        for attempt in range(3):
            down = self.find_icon('anticon-down', xmin=500, ymax=150)
            if not down:
                return True
            self.click_vp(down[0] + down[2] // 2, down[1] + down[3] // 2, fx, fy)
            t = time.time()
            while time.time() - t < 12:
                p = self.sel_rect(4)
                if p and p[2] > 20:
                    log('  更多条件已展开（第%d次点击）' % (attempt + 1))
                    time.sleep(1.2)
                    return True
                time.sleep(0.4)
            log('  第%d次点击后未展开，1秒后重试' % (attempt + 1))
            time.sleep(1.0)
        return False

    def set_period(self, sy, sm, ey, em, fx, fy, log):
        targets = [(0, str(int(sy))), (1, '%02d' % int(sm)), (2, str(int(ey))), (3, '%02d' % int(em))]
        for attempt in range(2):
            ok_all = True
            for idx, val in targets:
                if self.pick_select(idx, val, fx, fy):
                    log('  下拉%d=%s ✓' % (idx, val))
                else:
                    log('  下拉%d=%s 失败%s' % (idx, val, '（重试中）' if attempt == 0 else ''))
                    ok_all = False
            if ok_all:
                return True
            if attempt == 0:
                time.sleep(1.0)
        return False

    def select_all_projects(self, fx, fy, log):
        mag = self.find_icon('anticon-search', xmin=200, xmax=500, ymax=250)
        if not mag:
            p = self.sel_rect(4)
            if p and p[2] > 20:
                mag = (p[0] + p[2] - 12, p[1] + p[3] // 2 - 6, 12, 12)
        if mag:
            mx, my = mag[0] + mag[2] // 2, mag[1] + mag[3] // 2
            if mx > 0 and my > 0:
                self.click_vp(mx, my, fx, fy)
                log('  已点放大镜')
            self.wait_until_f("(function(){var d=document;var m=d.querySelector('.ant-modal-wrap');"
                              "var r=m?m.getBoundingClientRect():{width:0,height:0};"
                              "return (r.width>0&&r.height>0)?'true':'false';})()", timeout=5)
            dr = None
            t = time.time()
            while time.time() - t < 6:
                d1 = self.find_icon_in_modal('anticon-double-right')
                if d1:
                    time.sleep(0.4)
                    d2 = self.find_icon_in_modal('anticon-double-right')
                    if d2 and abs(d1[0] - d2[0]) < 3 and abs(d1[1] - d2[1]) < 3:
                        dr = d2
                        break
                time.sleep(0.3)
            if dr:
                log('  double-right位置: %s' % (dr,))
                self.click_vp(dr[0] + dr[2] // 2, dr[1] + dr[3] // 2, fx, fy)
                log('  已点全部添加')
                time.sleep(0.6)
                ok = self.find_in_modal('确 定') or self.find_in_modal('确定')
                if ok:
                    self.click_vp(ok[0] + ok[2] // 2, ok[1] + ok[3] // 2, fx, fy)
                    log('  已点确定')
                    self.wait_until_f("(function(){var d=document;var m=d.querySelector('.ant-modal-wrap');"
                                      "var r=m?m.getBoundingClientRect():{width:0,height:0};"
                                      "return (r.width===0&&r.height===0)?'true':'false';})()", timeout=5)
                    return True
                log('  未找到确定按钮')
            else:
                log('  未找到全部添加按钮')
        else:
            log('  未找到放大镜图标')
        return False

    def click_query(self, wait_texts, fx, fy, log):
        q = self.find_text('查 询')
        if q:
            self.click_vp(q[0] + q[2] // 2, q[1] + q[3] // 2, fx, fy)
            cond = ("(function(){var d=document;var t=d.body.innerText||'';return (" +
                    "||".join(["t.indexOf('" + w + "')>=0" for w in wait_texts]) + ")?'true':'false';})()")
            self.wait_until_f(cond, timeout=20)
            return True
        return False

    def export_excel(self, fx, fy, tries=3):
        """hover展开导出菜单并点导出EXCEL，返回Download对象；失败返回None"""
        for attempt in range(tries):
            exp = self.find_text('导出')
            if exp:
                self.jsf("(function(){var d=document;var all=d.querySelectorAll('button,.ant-dropdown-trigger');"
                         "for(var i=0;i<all.length;i++){if((all[i].textContent||'').trim()==='导出'){"
                         "var r=all[i].getBoundingClientRect();"
                         "['mouseenter','mouseover','mousemove'].forEach(function(t){"
                         "all[i].dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true,view:window,"
                         "clientX:r.x+20,clientY:r.y+10}));});break;}}return 'ok';})()")
                self.wait_until_f("(function(){var d=document;var items=d.querySelectorAll('.ant-dropdown-menu-item');"
                                  "for(var i=0;i<items.length;i++){var r=items[i].getBoundingClientRect();"
                                  "if(r.width>0&&r.height>0&&items[i].offsetParent!==null&&"
                                  "(items[i].textContent||'').trim()==='导出EXCEL')return 'true';}return 'false';})()",
                                  timeout=4)
                ex = self.find_text('导出EXCEL')
                if ex:
                    try:
                        with self.page.expect_download(timeout=60000) as dl_info:
                            self.click_vp(ex[0] + ex[2] // 2, ex[1] + ex[3] // 2, fx, fy)
                        return dl_info.value
                    except Exception:
                        return None
            time.sleep(1.5)
        return None

    def save_download(self, dl):
        """把下载保存到 var/downloads/，返回本地绝对路径（浏览器存活期间尽快落盘）"""
        import shutil
        fname = dl.suggested_filename or ('export_%s.xlsx' % time.strftime('%Y%m%d%H%M%S'))
        dst = os.path.join(DOWNLOAD_DIR, fname)
        try:
            dl.save_as(dst)
        except Exception:
            tmp = dl.path()
            if not tmp or not os.path.exists(tmp):
                raise RuntimeError('下载临时文件不可用')
            shutil.move(tmp, dst)
        return dst, os.path.getsize(dst)
