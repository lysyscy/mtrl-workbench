"""Validate task frontmatter and render the activity view."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import posixpath
import re
from urllib.parse import quote

from .links import scan
from .releases import receipts, render_table, section_bounds, timestamp
from .repo import atomic_write, relative_path, safe_path, tracked_paths


WORKTREE_STATES = {'in-use', 'blocked', 'retiring', 'retired'}
REQUIRED = {'id', 'kind', 'status', 'parent', 'children', 'blocked_by', 'worktree',
            'worktree_state', 'managed_runs', 'remaining_acceptance', 'next_step', 'updated_at'}
NAME = re.compile(r'[\w.-]+')


@dataclass(frozen=True)
class Task:
    id: str
    kind: str
    status: str
    parent: str | None
    children: list[str]
    blocked_by: list[str]
    worktree: str | None
    worktree_state: str | None
    managed_runs: list[str]
    remaining_acceptance: list[str]
    next_step: str
    updated_at: str
    title: str
    source: str
    branch: str | None = None


def task_scalar(value: str):
    """Read the scalar and flow-array subset used by the task schema."""
    value = value.strip()
    if value.startswith(('"', '[', '{')) or value in ('null', 'true', 'false'):
        return json.loads(value)
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1].replace("''", "'")
    if not value or value[0] in '*&!|>@#%`' or ': ' in value or ' #' in value:
        raise ValueError(f'unsupported frontmatter value: {value!r}')
    return value


def frontmatter(text: str) -> tuple[dict, str]:
    lines = text.splitlines()
    if not lines or lines[0] != '---' or '---' not in lines[1:]:
        raise ValueError('expected frontmatter delimited by ---')
    end = lines.index('---', 1)
    fields = {}
    index = 1
    while index < end:
        line = lines[index]
        index += 1
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        key, sep, value = line.partition(':')
        if not sep or not re.fullmatch('[a-z_]+', key) or key in fields:
            raise ValueError(f'invalid or duplicate frontmatter field: {key!r}')
        if value.strip():
            fields[key] = task_scalar(value)
        else:
            items = []
            while index < end and (item := re.fullmatch(r' +-[ \t]+(.+)', lines[index])):
                items.append(task_scalar(item[1]))
                index += 1
            if not items:
                raise ValueError(f'expected a value or sequence for {key}')
            fields[key] = items
    title = next((line.strip() for line in lines[end + 1:] if line.strip()), '')
    if not title.startswith('# ') or not title[2:].strip():
        raise ValueError('expected a task title after frontmatter')
    return fields, title[2:]


def nonblank(value) -> bool:
    return isinstance(value, str) and bool(value.strip()) and '\n' not in value and '\r' not in value


def identifier(value) -> bool:
    return isinstance(value, str) and NAME.fullmatch(value) is not None and value not in {'.', '..'}


def parse_task(text: str, source: str, schema: dict) -> Task:
    fields, title = frontmatter(text)
    missing = REQUIRED - fields.keys()
    extra = fields.keys() - (REQUIRED | {'branch'})
    if missing or extra:
        raise ValueError(f'fields missing={sorted(missing)} unexpected={sorted(extra)}')

    def task_id(value):
        return nonblank(value) and re.fullmatch(schema['id_pattern'], value)

    def list_of(value, predicate):
        return isinstance(value, list) and all(predicate(item) for item in value) and len(set(value)) == len(value)

    rules = {
        'id': task_id,
        'kind': lambda value: value in schema['kinds'],
        'status': lambda value: value in schema['statuses'],
        'parent': lambda value: value is None or task_id(value),
        'children': lambda value: list_of(value, task_id),
        'blocked_by': lambda value: list_of(value, task_id),
        'worktree': lambda value: value is None or identifier(value),
        'worktree_state': lambda value: value is None or (isinstance(value, str) and value in WORKTREE_STATES),
        'branch': lambda value: value is None or nonblank(value),
        'managed_runs': lambda value: list_of(value, identifier),
        'remaining_acceptance': lambda value: list_of(value, nonblank),
        'next_step': nonblank,
        'updated_at': nonblank,
    }
    for field, value in fields.items():
        if not rules[field](value):
            raise ValueError(f'invalid value for {field}')
    timestamp(fields['updated_at'])
    return Task(**fields, title=title, source=source)


def tree_specs(settings: dict) -> dict[str, dict]:
    specs = {}
    for tree in settings.get('worktrees', []):
        tree_id = tree['id']
        if not identifier(tree_id) or tree_id in specs or tree['state'] not in WORKTREE_STATES:
            raise ValueError(f'invalid or duplicate worktree: {tree_id}')
        specs[tree_id] = tree
    return specs


def validate_tasks(tasks: dict[str, Task], trees: dict[str, dict]) -> list[dict]:
    errors = []
    for task in tasks.values():
        def report(code, related, task_id=task.id):
            errors.append({'code': code, 'task': task_id, 'related': related})

        parent = tasks.get(task.parent)
        if task.parent is not None and (parent is None or task.id not in parent.children):
            report('TASK_PARENT_BACKLINK', task.parent)
        for child in task.children:
            if child not in tasks or tasks[child].parent != task.id:
                report('TASK_CHILD_BACKLINK', child)
        for dependency in task.blocked_by:
            if dependency == task.id or dependency not in tasks:
                report('TASK_DEPENDENCY_INVALID', dependency)
        seen = {task.id}
        while parent and parent.id not in seen:
            seen.add(parent.id)
            parent = tasks.get(parent.parent)
        if parent:
            report('TASK_PARENT_CYCLE', parent.id)
        tree = trees.get(task.worktree)
        if task.worktree is not None and (task.worktree_state == 'retired' or (tree and tree['state'] == 'retired')):
            report('TASK_RETIRED_WORKTREE', task.worktree)
        elif task.worktree is not None:
            if tree is None or task.branch != tree.get('branch') or task.worktree_state != tree['state']:
                report('TASK_WORKTREE_INVALID', task.worktree)
        elif task.branch is not None or task.worktree_state not in (None, 'retired'):
            report('TASK_WORKTREE_INVALID', task.branch or task.worktree_state)
    for tree in trees.values():
        if tree.get('task') not in (None, *tasks):
            errors.append({'code': 'WORKTREE_TASK_MISSING', 'worktree': tree['id'], 'related': tree['task']})
    return errors


def load_tasks(root: Path, schema: dict, trees: dict[str, dict]) -> tuple[dict[str, Task], list[dict]]:
    tasks, errors = {}, []
    tracked = tracked_paths(root)
    for path in sorted(root.glob(schema['glob'])):
        source = path.relative_to(root).as_posix()
        if source not in tracked:
            errors.append({'code': 'TASK_UNTRACKED', 'source': source})
            continue
        try:
            task = parse_task(safe_path(path, root).read_text(encoding='utf-8-sig'), source, schema)
            if task.id in tasks:
                raise ValueError(f'duplicate task id {task.id}')
            tasks[task.id] = task
        except (OSError, ValueError) as error:
            errors.append({'code': 'TASK_SCHEMA_INVALID', 'source': source, 'detail': str(error)})
    errors.extend(validate_tasks(tasks, trees))
    return tasks, errors


def render_view(tasks: dict[str, Task], trees: dict[str, dict], config: dict) -> str:
    entry = config['entry']
    labels = entry['labels']

    def task_link(task):
        path = posixpath.relpath(task.source, posixpath.dirname(entry['status_path']))
        label = task.title.replace('[', r'\[').replace(']', r'\]')
        return f'[{label}]({quote(path, safe="/")})'

    rows = ['', '', entry['active_heading'], '']
    active = [task for task in tasks.values() if task.status not in config['tasks']['finished_states']]
    for task in sorted(active, key=lambda task: (task.parent or task.id, task.parent is not None, task.id)):
        pending = ' / '.join(task.remaining_acceptance) or labels['none']
        rows.append(f'- {task_link(task)} · {labels["status"]} {task.status} · '
                    f'{labels["acceptance"]} {pending} · {labels["next"]} {task.next_step}')
    if not active:
        rows.append(labels['none'])
    rows.extend(['', entry['worktree_heading'], ''])
    for tree in sorted(trees.values(), key=lambda tree: (tree['state'] == 'retired', tree['id'])):
        owner = tasks.get(tree.get('task'))
        detail = task_link(owner) if owner else tree['label']
        rows.append(f'- `{tree["id"]}` · {tree["state"]} · {detail} · {tree["reason"]}')
    if not trees:
        rows.append(labels['none'])
    return '\n'.join([*rows, '', ''])


def inspect_entry(root: Path, config: dict, *, refresh: bool = False) -> dict:
    entry = config['entry']
    path = relative_path(root, entry['status_path'])
    previous = path.read_bytes()
    text = previous.decode('utf-8-sig').replace('\r\n', '\n')
    begin, end = entry['view_start'], entry['view_end']
    if text.splitlines().count(begin) != 1 or text.splitlines().count(end) != 1:
        raise ValueError('expected one matched pair of view markers')
    marker = text.index(begin)
    view_start, view_end = marker + len(begin), text.index(end)
    start, finish = section_bounds(text, entry['release_heading'])
    finish = min(finish, marker)
    if not (start < finish <= marker < view_start < view_end):
        raise ValueError('release section and activity view must appear in order')
    latest = receipts(root, entry)[:entry['release_limit']]
    if not latest or not 1 <= entry['release_limit'] <= 2:
        raise ValueError('expected one or two verified current runs')
    trees = tree_specs(config.get('closeout', {}))
    tasks, errors = load_tasks(root, config['tasks'], trees)
    changed = False
    if not errors:
        view, table = render_view(tasks, trees, config), render_table(latest, entry)
        if refresh:
            updated = text[:start] + table + text[finish:view_start] + view + text[view_end:]
            if changed := updated != text:
                crlf = b'\r\n' in previous
                encoding = 'utf-8-sig' if previous.startswith(b'\xef\xbb\xbf') else 'utf-8'
                atomic_write(path, (updated.replace('\n', '\r\n') if crlf else updated).encode(encoding),
                             previous=previous)
        else:
            if text[start:finish] != table:
                errors.append({'code': 'RELEASE_SECTION_DRIFT'})
            if text[view_start:view_end] != view:
                errors.append({'code': 'ACTIVE_VIEW_DRIFT'})
    link_report = scan(root, **config.get('links', {}))
    errors.extend(link_report['diagnostics'])
    return {'ok': not errors, 'changed': changed, 'task_count': len(tasks),
            'release_count': len(latest), 'source_documents': link_report['source_documents'],
            'local_links_examined': link_report['local_links_examined'], 'diagnostics': errors}
