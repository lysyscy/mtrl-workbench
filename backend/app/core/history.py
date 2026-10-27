"""按账号保存可逆事务；业务模型和允许恢复的字段由装配层登记。"""
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from hashlib import sha256
import json
import re

from sqlalchemy import DateTime, Integer, JSON, String, event, literal_column, select, update
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.ddl import sort_tables

from app.core.db import Base
from app.core.errors import MustReportError


class OperationHistory(Base):
    __tablename__ = 'operation_history'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor: Mapped[str] = mapped_column(String(128), index=True)
    label: Mapped[str] = mapped_column(String(128))
    state: Mapped[str] = mapped_column(String(16), index=True)
    changes: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


@dataclass(frozen=True)
class Rule:
    model: type
    fields: frozenset[str]
    create_delete: bool = False


@dataclass
class RequestHistory:
    actor: str
    policy: tuple | None
    result: str = ''
    root: object = None


_request: ContextVar[RequestHistory | None] = ContextVar('operation_history', default=None)
_policies = []
_rules = {}
_TECHNICAL = {'updated_at'}


def actor_key(actor):
    # 账号原有口径不限长度；历史只存固定长度绑定键，不截断账号。
    return sha256(actor.encode('utf-8')).hexdigest()


def bind_policies(policies):
    global _policies, _rules
    _policies = [(method, re.compile(path), label, rules) for method, path, label, rules in policies]
    _rules = {rule.model.__tablename__: rule for *_, rules in policies for rule in rules}


def begin_request(actor, method, path):
    ignored = (method not in {'POST', 'PUT', 'PATCH', 'DELETE'}
               or path.startswith('/api/history/')
               or path in {'/m15/login', '/api/m15/logout', '/api/m15/theme', '/api/m15/ui-scale'})
    policy = next(((label, rules) for verb, pattern, label, rules in _policies
                   if verb == method and pattern.fullmatch(path)), None)
    state = None if ignored or not actor else RequestHistory(str(actor), policy)
    return _request.set(state), state


def end_request(token):
    _request.reset(token)


def _encode(row):
    return {key: str(value) if isinstance(value, Decimal) else value.isoformat()
            if isinstance(value, (date, datetime)) else value for key, value in row.items()}


def _decode(table, row):
    values = dict(row)
    for key, value in values.items():
        if value is None:
            continue
        kind = table.c[key].type.python_type
        if kind is Decimal:
            values[key] = Decimal(value)
        elif kind is datetime:
            values[key] = datetime.fromisoformat(value)
        elif kind is date:
            values[key] = date.fromisoformat(value)
    return values


def _same(a, b):
    if a is None or b is None:
        return a is b
    return {k: v for k, v in a.items() if k not in _TECHNICAL} == {
        k: v for k, v in b.items() if k not in _TECHNICAL}


def _read(session, table, key, *, lock=False):
    query = select(table, literal_column('xmin::text').label('_history_version')).where(table.c.id == key)
    row = session.connection().execute(query.with_for_update() if lock else query).mappings().first()
    if row is None:
        return None, None
    values = dict(row)
    version = values.pop('_history_version')
    return _encode(values), version


def lock_actor(session, actor):
    # 同一账号的写入和撤销按事务串行；不锁其他账号的普通读取。
    key = int.from_bytes(sha256(actor.encode('utf-8')).digest()[:4], 'big', signed=True)
    session.connection().exec_driver_sql('SELECT pg_advisory_xact_lock(%s, %s)', (384, key))


class Tracker:
    def __init__(self, session, state):
        self.session, self.state = session, state
        self.parent = state.root
        self.mutated = self.unsupported = self.preparing = False
        self.records = {}
        self.operation = None
        if self.parent is None:
            lock_actor(session, state.actor)
            state.root = self
        event.listen(session, 'before_flush', self._before_flush)
        event.listen(session, 'do_orm_execute', self._execute)

    def _execute(self, execution):
        if self.preparing:
            return
        statement = execution.statement
        raw = str(getattr(statement, 'text', '')).lstrip().lower()
        if (execution.is_insert or execution.is_update or execution.is_delete
                or raw.startswith(('insert', 'update', 'delete', 'merge', 'with'))):
            self.mutated = self.unsupported = True

    def _before_flush(self, session, *_):
        if self.preparing:
            return
        rules = {r.model: r for r in self.state.policy[1]} if self.state.policy else {}
        objects = set(session.new) | set(session.dirty) | set(session.deleted)
        for obj in sorted(objects, key=lambda row: (row.__tablename__, getattr(row, 'id', 0) or 0)):
            if isinstance(obj, OperationHistory):
                continue
            if obj in session.dirty and not session.is_modified(obj, include_collections=False):
                continue
            self.mutated = True
            rule = rules.get(type(obj))
            if rule is None or self.parent is not None:
                self.unsupported = True
                continue
            if (obj in session.new or obj in session.deleted) and not rule.create_delete:
                self.unsupported = True
                continue
            if id(obj) not in self.records:
                before, before_version = (None, None) if obj in session.new else _read(session, obj.__table__, obj.id, lock=True)
                self.records[id(obj)] = (obj, rule, before, before_version)

    def prepare(self):
        self.session.flush()
        if self.parent is not None:
            if self.mutated:
                self.parent.mutated = self.parent.unsupported = True
            return
        if not self.mutated:
            return
        self.preparing = True
        changes = []
        parents = {}
        for obj, rule, before, before_version in self.records.values():
            after, version = _read(self.session, obj.__table__, obj.id)
            if _same(before, after):
                continue
            if before is not None and after is not None:
                fields = {k for k in before if before[k] != after[k]} - _TECHNICAL
                if not fields <= rule.fields:
                    self.unsupported = True
            guards = []
            for foreign_key in obj.__table__.foreign_keys:
                parent_table = foreign_key.column.table
                key = (after or before)[foreign_key.parent.name]
                if key is None:
                    continue
                if parent_table.name not in _rules or foreign_key.column.name != 'id':
                    self.unsupported = True
                    continue
                identity = (parent_table.name, key)
                if identity not in parents:
                    data, parent_version = _read(self.session, parent_table, key)
                    parents[identity] = {'table': parent_table.name, 'id': key,
                                         'data': data, 'version': parent_version}
                guards.append(parents[identity])
            changes.append({'table': obj.__tablename__, 'id': obj.id, 'before': before,
                            'after': after, 'version': version, 'target_version': before_version, 'parents': guards})
        # 同事务父项由其完整变更及版本校验，不再作为不变的外部依赖。
        changed = {(change['table'], change['id']) for change in changes}
        for change in changes:
            change['parents'] = [parent for parent in change['parents']
                                 if (parent['table'], parent['id']) not in changed]
        if not changes and not self.unsupported:
            return
        self.session.connection().execute(update(OperationHistory).where(
            OperationHistory.actor == actor_key(self.state.actor), OperationHistory.state == 'undone'
        ).values(state='discarded'))
        self.operation = OperationHistory(
            actor=actor_key(self.state.actor),
            label=self.state.policy[0] if self.state.policy else '此项操作暂不支持撤销',
            state='barrier' if self.unsupported else 'applied',
            changes=[] if self.unsupported else changes,
        )
        self.session.add(self.operation)
        self.session.flush()

    def committed(self):
        if self.operation is not None:
            result = 'unsupported' if self.operation.state == 'barrier' else 'recorded'
            if self.state.result != 'unsupported':
                self.state.result = result

    def close(self):
        event.remove(self.session, 'before_flush', self._before_flush)
        event.remove(self.session, 'do_orm_execute', self._execute)
        if self.parent is None:
            self.state.root = None


def track(session):
    state = _request.get()
    return Tracker(session, state) if state is not None else None


def record_barrier(session, actor, label):
    """在调用者的业务事务内截断历史并使旧重做失效。"""
    lock_actor(session, actor)
    session.connection().execute(update(OperationHistory).where(
        OperationHistory.actor == actor_key(actor), OperationHistory.state == 'undone'
    ).values(state='discarded'))
    session.add(OperationHistory(actor=actor_key(actor), label=label, state='barrier', changes=[]))


def _barrier_id(session, actor):
    return session.scalar(select(OperationHistory.id).where(
        OperationHistory.actor == actor_key(actor), OperationHistory.state == 'barrier'
    ).order_by(OperationHistory.id.desc()).limit(1)) or 0


def _top(session, actor, direction):
    barrier = _barrier_id(session, actor)
    state = 'applied' if direction == 'undo' else 'undone'
    order = OperationHistory.id.desc() if direction == 'undo' else OperationHistory.id.asc()
    return session.scalar(select(OperationHistory).where(
        OperationHistory.actor == actor_key(actor), OperationHistory.id > barrier,
        OperationHistory.state == state,
    ).order_by(order).limit(1))


def status(session, actor):
    def summary(row):
        return {'id': row.id, 'label': row.label, 'count': len(row.changes)} if row else None
    result = {key: summary(_top(session, actor, key)) for key in ('undo', 'redo')}
    latest = session.scalar(select(OperationHistory).where(OperationHistory.actor == actor_key(actor)
                            ).order_by(OperationHistory.id.desc()).limit(1))
    if latest and latest.state == 'barrier':
        result['notice'] = '上一步暂不支持撤销／重做'
    return result


def replay(session, actor, direction, expected_id):
    if direction not in {'undo', 'redo'}:
        raise MustReportError('请选择撤销或重做')
    lock_actor(session, actor)
    operation = _top(session, actor, direction)
    if operation is None or operation.id != expected_id:
        raise MustReportError('操作历史已变化，请刷新后再试；本次未修改数据')
    source, target = ('after', 'before') if direction == 'undo' else ('before', 'after')
    prepared = []
    changes = json.loads(json.dumps(operation.changes))
    # 先锁定并验证整批，任何一条冲突都不开始修改。
    parents = {(p['table'], p['id']): p for change in changes for p in change.get('parents', [])}
    for identity, parent in sorted(parents.items()):
        parent_rule = _rules.get(identity[0])
        if parent_rule is None:
            raise MustReportError('相关数据的恢复规则已变化，未修改数据')
        current, version = _read(session, parent_rule.model.__table__, identity[1], lock=True)
        if not _same(current, parent['data']) or version != parent['version']:
            raise MustReportError('所属项目等相关记录已被后续操作修改，未撤销或重做；请核对')
    for change in sorted(changes, key=lambda x: (x['table'], x['id'])):
        rule = _rules.get(change['table'])
        if rule is None:
            raise MustReportError('这项历史不再受支持，未修改数据')
        table = rule.model.__table__
        if any(value is not None and set(value) != set(table.c.keys())
               for value in (change['before'], change['after'])):
            raise MustReportError('历史字段结构已变化，未修改数据')
        if change['before'] is not None and change['after'] is not None:
            fields = {key for key in change['before']
                      if change['before'][key] != change['after'][key]} - _TECHNICAL
            if not fields <= rule.fields:
                raise MustReportError('这项历史的恢复规则已变化，未修改数据')
        current, version = _read(session, table, change['id'], lock=True)
        if not _same(current, change[source]) or version != change['version']:
            raise MustReportError('相关记录已被后续操作修改，未撤销或重做；请刷新后核对')
        if (change[source] is None or change[target] is None) and not rule.create_delete:
            raise MustReportError('这项历史不支持新增或删除恢复，未修改数据')
        prepared.append((rule, change))
    # 全部校验完成后按真实外键顺序分表 flush；失败仍回滚整个业务事务。
    tables = list(sort_tables({rule.model.__table__ for rule, _ in prepared}))
    for table in reversed(tables):
        for rule, change in prepared:
            if rule.model.__table__ is table and change[target] is None:
                session.delete(session.get(rule.model, change['id']))
        session.flush()
    for table in tables:
        for rule, change in prepared:
            if rule.model.__table__ is not table or change[target] is None:
                continue
            wanted, current = change[target], change[source]
            if current is None:
                session.add(rule.model(**_decode(table, wanted)))
            else:
                obj = session.get(rule.model, change['id'])
                values = _decode(table, wanted)
                for field in rule.fields:
                    if wanted[field] != current[field]:
                        setattr(obj, field, values[field])
        session.flush()
    operation.state = 'undone' if direction == 'undo' else 'applied'
    restored = {}
    for rule, change in prepared:
        row, version = _read(session, rule.model.__table__, change['id'])
        # 目标旧版本是可信链的凭据；旧条目缺失时不猜测续接。
        if 'target_version' in change:
            restored[(change['table'], change['id'])] = (row, version, change['target_version'])
        change['target_version'], change['version'] = change['version'], version
    operation.changes = changes
    session.flush()
    state = 'applied' if direction == 'undo' else 'undone'
    order = OperationHistory.id.desc() if direction == 'undo' else OperationHistory.id.asc()
    pending = session.scalars(select(OperationHistory).where(
        OperationHistory.actor == actor_key(actor), OperationHistory.state == state,
        OperationHistory.id > _barrier_id(session, actor),
        OperationHistory.id < operation.id if direction == 'undo' else OperationHistory.id > operation.id,
    ).order_by(order))
    for next_op in pending:
        if not restored:
            break
        next_changes = json.loads(json.dumps(next_op.changes))
        changed = False
        for change in next_changes:
            for parent in change.get('parents', []):
                identity = (parent['table'], parent['id'])
                trusted = restored.get(identity)
                if trusted:
                    row, version, previous = trusted
                    if _same(row, parent['data']) and parent['version'] == previous:
                        parent['version'] = version
                        changed = True
                    else:
                        restored.pop(identity)
            identity = (change['table'], change['id'])
            trusted = restored.pop(identity, None)
            if trusted:
                row, version, previous = trusted
                if _same(row, change[source]) and change['version'] == previous:
                    change['version'] = version
                    changed = True
                # 到真正修改该行的动作即停止；它重放后负责下一段续接。
        if changed:
            next_op.changes = next_changes
    return {'ok': True, 'label': operation.label, 'count': len(changes),
            'message': f"已{'撤销' if direction == 'undo' else '重做'}：{operation.label}（{len(changes)}条）"}
