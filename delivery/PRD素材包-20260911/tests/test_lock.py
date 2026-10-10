# -*- coding: utf-8 -*-
"""导出互斥锁测试（R3 补强）：原子创建 / 占用拒绝 / 心跳刷新 / 死锁接管。"""
import json
import os
import time

import export_runner


def test_lock_atomic_acquire_and_release(monkeypatch, tmp_path):
    lock = tmp_path / 'export.lock'
    monkeypatch.setattr(export_runner, 'LOCK_FILE', str(lock))

    p, holder = export_runner.acquire_lock()
    assert holder is None
    assert p == str(lock)
    assert lock.exists()
    info = json.loads(lock.read_text(encoding='utf-8'))
    assert 'pid' in info and 'ts' in info and 'host' in info

    export_runner.release_lock()
    assert not lock.exists()


def test_lock_occupied_reject(monkeypatch, tmp_path):
    lock = tmp_path / 'export.lock'
    monkeypatch.setattr(export_runner, 'LOCK_FILE', str(lock))

    export_runner.acquire_lock()
    p, holder = export_runner.acquire_lock()
    assert p is None
    assert holder is not None
    assert holder.get('pid') is not None

    export_runner.release_lock()


def test_lock_heartbeat_refresh(monkeypatch, tmp_path):
    lock = tmp_path / 'export.lock'
    monkeypatch.setattr(export_runner, 'LOCK_FILE', str(lock))

    export_runner.acquire_lock()
    before = json.loads(lock.read_text(encoding='utf-8'))['ts']
    time.sleep(0.02)
    export_runner.heartbeat_lock()
    after = json.loads(lock.read_text(encoding='utf-8'))['ts']
    assert after >= before

    export_runner.release_lock()


def test_lock_stale_takeover(monkeypatch, tmp_path):
    lock = tmp_path / 'export.lock'
    monkeypatch.setattr(export_runner, 'LOCK_FILE', str(lock))

    # 模拟过期死锁（ts 早于 LOCK_STALE=900 秒）
    stale = {'pid': 9999, 'host': 'DEAD', 'ts': time.time() - 1000, 'at': 'x'}
    lock.write_text(json.dumps(stale), encoding='utf-8')

    p, holder = export_runner.acquire_lock()
    assert holder is None
    assert p == str(lock)

    info = json.loads(lock.read_text(encoding='utf-8'))
    assert info['pid'] == os.getpid()

    export_runner.release_lock()
