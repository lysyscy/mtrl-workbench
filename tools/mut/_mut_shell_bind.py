"""守渲染加工追加的次数、顺序、两条重画路径及迁移判据，只变异隔离副本。

正常、缺步骤、反序和重复加工均调用真实壳与判据。
"""
from pathlib import Path
import shutil
import subprocess
import sys
from _isolated import isolated_backend

ROOT = Path(__file__).resolve().parents[2]
UI = 'tests/test_shell_bind.py'
CASES = [
    ('追加变覆盖', 'app/web/index.html', '(BIND[view] ||= []).push(step);', 'BIND[view]=[step];', UI+'::test_登记按原顺序且每次重画只跑一次'),
    ('执行反序', 'app/web/index.html', 'of BIND[view] || []', 'of [...(BIND[view] || [])].reverse()', UI+'::test_登记按原顺序且每次重画只跑一次'),
    ('加工登记反序', 'app/web/index.html', '(BIND[view] ||= []).push(step);', '(BIND[view] ||= []).unshift(step);', UI+'::test_登记按原顺序且每次重画只跑一次'),
    ('步骤跑两次', 'app/web/index.html', '[]) step();', '[]) {step();step();}', UI+'::test_登记按原顺序且每次重画只跑一次'),
    ('普通路径漏加工', 'app/web/shell/view.js', 'runBind(VIEW);\n  placePops();', '/* 漏加工 */\n  placePops();', UI+'::test_状态页不加工与引用工具不重复且事件只响应一次'),
    ('虚拟路径漏加工', 'app/web/shell/view.js', 'runBind(VIEW);\n  const live=[];', '/* 漏加工 */\n  const live=[];', UI+'::test_虚拟首画加工一次而滚动不重跑页加工'),
    ('漏返回步骤', 'app/web/shell/core.js', "for(const view of ['m03','m11','m08'])", "for(const view of ['m11','m08'])", UI+'::test_登记按原顺序且每次重画只跑一次'),
    ('漏钉列加工', 'app/web/shell/core.js', '  jcApplyPin();', '  /* 漏钉列 */', UI+'::test_集采回显隐藏钉列导出与返回逐次保持'),
    ('全选回显丢失', 'app/web/shell/pages-a.js', 'box.indeterminate = hit>0 && hit<vis.length;', 'box.half = hit>0 && hit<vis.length;', 'tests/test_acc_jc_shell.py::test_空态行跨列数派生且全选框回显三态'),
    ('回收站漏登记', 'app/web/shell/core.js', "addBind('m15', m15Trash);", "addBind('lost15', m15Trash);", 'tests/test_acc_usr_mgmt.py::test_软删的账号仍带出到界面_且在回收站里单独可见可恢复'),
    ('打印加工漏登记', 'app/web/shell/core.js', "addBind('m03', function () {", "addBind('lost03', function () {", 'tests/test_wired_m03_print.py::test_打印机设置入口在新壳里可发现且真读写后端'),
    ('过程加工漏登记', 'app/web/shell/core.js', "addBind('m06', function () {", "addBind('lost06', function () {", 'tests/test_wired_m06.py::test_卡头不再出现那枚永不出结果的导出按钮'),
    ('双渲染调用漏接', 'app/web/shell/view.js', 'runBind(VIEW);\n  const live=[];', '/* 漏加工 */\n  const live=[];', 'tests/test_shell_render.py::test_虚拟滚动的设计红线'),
    ('库存摘除漏登记', 'app/web/shell/core.js', "addBind('m08', function () {", "addBind('lost08', function () {", 'tests/test_tail04_export.py::test_库存单据只留真导出且透视提示与模板形态一致'),
    ('批录入口漏登记', 'app/web/shell/core.js', "addBind('m09', function () {", "addBind('lost09', function () {", 'tests/test_ux_pages.py::test_m09月度批量录入_入口挂BIND且提交交给后端'),
    ('语义读取只取首项', '../tools/audit/shell_api.py', 'return [src[m.start():scan_stmt(scan, m.start())] for m in start.finditer(scan)]', 'return [src[m.start():scan_stmt(scan, m.start())] for m in list(start.finditer(scan))[:1]]', UI+'::test_加工语义读取不吃下一个登记或注释伪登记'),
    ('登记直接赋值丢失', 'app/web/shell/core.js', "addBind('m15', m15Trash);", "addBind('lost15', m15Trash);", 'tests/test_shell_api.py::test_取_BIND_块_三种写法都要收'),
    ('语义多项不拒绝', '../tools/audit/shell_api.py', 'if len(bs) != 1:', 'if not bs:', 'tests/test_shell_api.py::test_取_BIND_块_多处命中必须抛'),
]


def main():
    with isolated_backend('tmp-shell-bind-') as (base, env):
        shutil.copytree(ROOT/'tools/audit', base.parent/'tools/audit', ignore=shutil.ignore_patterns('__pycache__'))
        # 浏览器只读取隔离副本，API 写动作由用例拦截；不复制凭据。
        env['MTRL_UI_FIXTURE_WEB'] = str(base/'app/web')
        env['PLAYWRIGHT_BROWSERS_PATH'] = 'C:/ProgramData/ms-playwright'
        def run(nodes):
            return subprocess.run([sys.executable, '-X', 'utf8', '-m', 'pytest', *nodes, '-q', '--tb=short'],
                                  cwd=base, env=env, capture_output=True, text=True, encoding='utf-8', timeout=60)
        normal=run(list(dict.fromkeys(c[4] for c in CASES)))
        assert normal.returncode == 0, normal.stdout+normal.stderr
        print('PASS 基线正常放行', flush=True)
        for label,rel,old,new,node in CASES:
            path=base/rel
            original=path.read_bytes()
            text=original.decode('utf-8').replace('\r\n','\n')
            assert old in text,(label,old)
            try:
                # 全选两处同义声明一起变异，其余靶唯一。
                assert text.count(old)==1 or label=='全选回显丢失', (label,text.count(old))
                path.write_text(text.replace(old,new),encoding='utf-8')
                red=run([node])
                assert red.returncode == 1 and ('FAILED '+node) in red.stdout.replace('\\','/'), label+'\n'+red.stdout+red.stderr
                print('PASS '+label+' → 指定判据红', flush=True)
            finally:
                path.write_bytes(original)
        restored=run(list(dict.fromkeys(c[4] for c in CASES)))
        assert restored.returncode == 0, restored.stdout+restored.stderr
        print(f'PASS {len(CASES)}/{len(CASES)}隔离靶，复原后正常放行',flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
