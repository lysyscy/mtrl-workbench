"""Read verified run receipts and the current-runs table."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re

from .repo import read_json, safe_path

COMMIT_PATTERN = r'[0-9a-f]{40}'
TABLE_HEADER = '| finished_at | run_id | action | product_commit | pid |'
TABLE_DIVIDER = '| --- | --- | --- | --- | ---: |'
TABLE_ROW = re.compile(
    rf'\| ([^|]+) \| `([\w.-]+)` \| `([\w-]+)` \| `({COMMIT_PATTERN})` \| ([1-9]\d*) \|',
)


def timestamp(value: str) -> datetime:
    stamp = datetime.fromisoformat(value)
    if stamp.utcoffset() is None:
        raise ValueError(f'timestamp requires a time zone: {value}')
    return stamp


@dataclass(frozen=True)
class ReleaseRun:
    run_id: str
    action: str
    product_commit: str
    pid: int
    finished_at: str


def section_bounds(text: str, heading: str) -> tuple[int, int]:
    matches = list(re.finditer(rf'(?m)^{re.escape(heading)}[ \t]*$', text))
    if len(matches) != 1:
        raise ValueError(f'expected one section: {heading}')
    start = matches[0].end()
    next_section = re.search(r'(?m)^#{1,2}[ \t]+', text[start:])
    return start, start + next_section.start() if next_section else len(text)


def parse_table(section: str) -> list[ReleaseRun] | None:
    """Return None for a legacy section without a current-runs table."""
    lines = section.splitlines()
    headers = [index for index, line in enumerate(lines) if line == TABLE_HEADER]
    if not headers:
        return None
    if len(headers) != 1 or lines[headers[0] + 1:headers[0] + 2] != [TABLE_DIVIDER]:
        raise ValueError('invalid current-runs table header')
    runs = []
    for line in lines[headers[0] + 2:]:
        if not line.startswith('|'):
            break
        row = TABLE_ROW.fullmatch(line)
        if not row:
            raise ValueError('invalid current-runs table row')
        at, run_id, action, commit, pid = row.groups()
        timestamp(at)
        runs.append(ReleaseRun(run_id, action, commit, int(pid), at))
    if not runs or len({run.run_id for run in runs}) != len(runs):
        raise ValueError('missing or duplicate run id')
    if runs != sorted(runs, key=lambda run: timestamp(run.finished_at), reverse=True):
        raise ValueError('current-runs table must be newest first')
    return runs


def value_at(value, accessor: str):
    for key in accessor.split('.'):
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def receipts(root: Path, entry: dict) -> list[ReleaseRun]:
    runs = {}
    for source in entry['release_sources']:
        for path in sorted(root.glob(source['glob'])):
            record = read_json(safe_path(path, root))
            try:
                verified = all(type(actual := value_at(record, key)) is type(expected) and actual == expected
                               for key, expected in entry['release_verified'].items())
            except (KeyError, IndexError, TypeError):
                verified = False
            if not verified:
                continue
            run = ReleaseRun(run_id=path.parents[source['run_id_parent']].name,
                             **{key: value_at(record, field) for key, field in entry['release_fields'].items()})
            if run.action not in entry['release_actions']:
                continue
            if (not re.fullmatch(r'[\w.-]+', run.run_id) or not re.fullmatch(COMMIT_PATTERN, run.product_commit)
                    or type(run.pid) is not int or run.pid < 1):
                raise ValueError(f'invalid release identity in {path}')
            timestamp(run.finished_at)
            if run.run_id in runs and runs[run.run_id] != run:
                raise ValueError(f'conflicting release receipts for {run.run_id}')
            runs[run.run_id] = run
    return sorted(runs.values(), key=lambda run: (timestamp(run.finished_at), run.run_id), reverse=True)


def render_table(runs: list[ReleaseRun], entry: dict) -> str:
    zone = timezone(timedelta(minutes=entry['utc_offset_minutes']))
    rows = ['', '', TABLE_HEADER, TABLE_DIVIDER]
    for run in runs:
        stamp = timestamp(run.finished_at).astimezone(zone).isoformat()
        rows.append(f'| {stamp} | `{run.run_id}` | `{run.action}` | `{run.product_commit}` | {run.pid} |')
    rows += ['', entry['release_history_note'], '', '']
    return '\n'.join(rows)
