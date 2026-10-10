# -*- coding: utf-8 -*-
"""
独立导出工作进程：由 /api/export/run Popen 启动（CREATE_NEW_CONSOLE），
与 Flask 进程完全解耦；跑完（成功/失败）自行更新任务文件状态。

2026-09-08 加固：双保险
  ① 最外层 try/except/finally + sys.excepthook 覆盖所有未被捕获的异常
  ② atexit 兜底：任何正常或异常退出都强制刷一次任务状态 + 删锁
  历史教训：worker 进程 13852 在 import_sfjc 阶段凭空消失（无 export_error.log），
  当时 UI 永远卡在 55%，等 15 分钟心跳超时才能自动接管。
"""
import atexit
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# worker 进程 stdout/stderr 统一 UTF-8 + 容错（修复 ✓ 等 GBK 无法编码字符抛 UnicodeEncodeError）。
# 必须放最顶部：export_runner / sfjc_process 等 import 后跑的 print 才会用新编码。
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

import export_runner  # noqa


def _emergency_release(reason):
    """兜底：任何异常/退出路径都强制把任务标 failed + 删锁"""
    try:
        t = export_runner._read_task()
        if t and t.get('status') == 'running':
            t['status'] = 'failed'
            t['finished'] = time.strftime('%Y-%m-%d %H:%M:%S')
            t['result'] = '[worker 兜底] ' + reason + '（' + time.strftime('%H:%M:%S') + '）'
            export_runner._write_task(t)
    except Exception:
        pass
    try:
        export_runner.release_lock()
    except Exception:
        pass
    # 完整堆栈也写一份
    try:
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               'logs')
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, 'export_error.log'), 'a', encoding='utf-8') as f:
            f.write('\n===== %s [worker emergency] %s =====\n' %
                    (time.strftime('%Y-%m-%d %H:%M:%S'), reason))
            f.write(traceback.format_exc())
    except OSError:
        pass


# atexit 兜底：atexit.register 在进程正常退出时被调用；如果进程被信号 kill，atexit 不跑
# 所以这只是双保险之一。15 分钟无心跳自动接管是最后兜底（已实现）。
atexit.register(_emergency_release, 'atexit 触发')


def _excepthook(exc_type, exc_value, exc_tb):
    """捕获所有未处理的 BaseException（包括 SystemExit、KeyboardInterrupt 之外的）"""
    msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))[-800:]
    sys.stderr.write('[worker uncaught] ' + msg + '\n')
    _emergency_release('uncaught ' + exc_type.__name__ + ': ' + str(exc_value)[:200])
    # 不要再调 sys.__excepthook__：会弹控制台对话框（CREATE_NEW_CONSOLE 下没人看）
sys.excepthook = _excepthook


def main():
    task = export_runner._read_task()
    if not task:
        print('没有待执行的任务', flush=True)
        return 1
    # 两人共用：文件锁互斥（api 侧发起前已查过，这里是最后防线）
    lock, holder = export_runner.acquire_lock()
    if not lock:
        msg = '导出被占用：另一台电脑（%s）正在执行（%s 开始），请稍候' % (
            holder.get('host') or '?', holder.get('at') or '?')
        print(msg, flush=True)
        if task.get('status') == 'running':
            task['status'] = 'failed'
            task['result'] = msg
            task['finished'] = time.strftime('%Y-%m-%d %H:%M:%S')
            export_runner._write_task(task)
        return 2
    try:
        print('开始执行任务: %s %d-%02d' % (task.get('type'), task.get('sy'), task.get('sm')), flush=True)
        result = export_runner.run_once()
        print('完成:', result.get('result'), flush=True)
        return 0
    except Exception:
        msg = traceback.format_exc()[-800:]
        task['status'] = 'failed'
        task['finished'] = time.strftime('%Y-%m-%d %H:%M:%S')
        task['result'] = msg
        export_runner._write_task(task)
        # 完整 traceback 另落日志（结果字段只存尾部，排障看全文）
        try:
            log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                   'logs')
            os.makedirs(log_dir, exist_ok=True)
            with open(os.path.join(log_dir, 'export_error.log'), 'a', encoding='utf-8') as f:
                f.write('\n===== %s =====\n' % time.strftime('%Y-%m-%d %H:%M:%S'))
                f.write(traceback.format_exc())
        except OSError:
            pass
        print('失败:', task['result'], flush=True)
        return 1
    except BaseException as e:
        # 捕获 SystemExit 等非 Exception 的退出信号（os._exit 仍绕过这里）
        _emergency_release('BaseException: ' + type(e).__name__ + ': ' + str(e)[:200])
        raise
    finally:
        export_runner.release_lock()


if __name__ == '__main__':
    sys.exit(main())
