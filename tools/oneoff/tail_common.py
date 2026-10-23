"""Small file-based TAIL protocol shared by the three ticket commands."""
from __future__ import annotations

import os
from pathlib import Path
import re
import tempfile

ROOT = Path(__file__).resolve().parents[2]
TRACKER = ROOT / 'docs/agents/issue-tracker.md'
TICKETS = ROOT / '.scratch/tails/issues'
STATES = frozenset({'ready-for-agent', 'ready-for-human', 'needs-info', 'needs-triage',
                    'blocked', 'in-progress', 'claimed', 'needs-human', 'done', 'wontfix'})
TERMINAL = frozenset({'done', 'wontfix'})
STATE_RE = re.compile(r'^\*\*Status:\*\*\s*([a-z-]+)', re.M)
WATER_RE = re.compile(r'^TAIL_LAST_ISSUED: ([0-9]+)\r?$', re.M)


def read_tickets(directory: Path) -> dict[int, tuple[Path, str, str]]:
    if not directory.is_dir():
        raise ValueError(f'ticket directory is missing: {directory}')
    result = {}
    for path in sorted(directory.glob('TAIL-*.md')):
        match = re.fullmatch(r'TAIL-([1-9][0-9]*)-.+\.md', path.name)
        if not match:
            raise ValueError(f'invalid ticket filename: {path.name}')
        number = int(match[1])
        text = path.read_text(encoding='utf-8')
        states = STATE_RE.findall(text)
        if number in result or len(states) != 1 or states[0] not in STATES:
            raise ValueError(f'duplicate number or invalid status: {path.name}')
        result[number] = (path, text, states[0])
    return result


def highwater(text: str, tickets: dict) -> int:
    lines = [line for line in text.splitlines() if line.startswith('TAIL_LAST_ISSUED')]
    if len(lines) != 1 or not WATER_RE.fullmatch(lines[0]):
        raise ValueError('exactly one valid TAIL_LAST_ISSUED line is required')
    value = int(WATER_RE.fullmatch(lines[0])[1])
    if value < max(tickets, default=0):
        raise ValueError('highwater is lower than an existing ticket')
    return value


def dependencies(text: str) -> list[int]:
    match = re.search(r'^\*\*Blocked by:\*\*\s*(.*?)(?:\n\s*\n|\Z)', text, re.M | re.S)
    if not match:
        raise ValueError('Blocked by field is required')
    return sorted(set(map(int, re.findall(r'\bTAIL-([1-9][0-9]*)\b', match[1]))))


def dependency_state(numbers: list[int], tickets: dict) -> list[str]:
    pending = []
    for number in numbers:
        if number not in tickets:
            raise ValueError(f'missing prerequisite TAIL-{number}; absence is not done')
        if tickets[number][2] != 'done':
            pending.append(f'TAIL-{number}={tickets[number][2]}')
    return pending


def write_many(updates: dict[Path, bytes]) -> None:
    """Prepare all bytes before publishing; restore original bytes on a write failure.

    The designated integrator serializes issue allocation across worktrees.
    This is local failure protection, not a distributed transaction.
    """
    originals = {path: path.read_bytes() if path.exists() else None for path in updates}
    temps = {}
    written = []
    try:
        for path, content in updates.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, name = tempfile.mkstemp(prefix='.tail-', dir=path.parent)
            temp = Path(name)
            temps[path] = temp
            with os.fdopen(fd, 'wb') as stream:
                stream.write(content)
        for path, temp in temps.items():
            # Refuse intervening edits; do not overwrite a newly created ticket.
            current = path.read_bytes() if path.exists() else None
            if current != originals[path]:
                raise ValueError(f'file changed during preparation: {path}')
            temp.replace(path)
            written.append(path)
    except BaseException:
        for path in reversed(written):
            content = originals[path]
            if content is None:
                path.unlink()
            else:
                fd, name = tempfile.mkstemp(prefix='.tail-restore-', dir=path.parent)
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(content)
                os.replace(name, path)
        raise
    finally:
        for temp in temps.values():
            temp.unlink(missing_ok=True)


def encoded_like(text: str, original: bytes) -> bytes:
    newline = '\r\n' if b'\r\n' in original else '\n'
    return text.replace('\r\n', '\n').replace('\n', newline).encode('utf-8')
