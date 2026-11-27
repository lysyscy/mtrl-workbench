"""Check local Markdown destinations against the Git index."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
import posixpath
import re
from urllib.parse import unquote

from .repo import git, relative_path, tracked_paths


DESTINATION = r'(<[^<>\n]+>|(?:\\[()]|\([^()\n]*\)|[^\s()])+)'
INLINE = re.compile(r'(?<!\\)\]\(\s*' + DESTINATION + r'''(?:[ \t]+(?:"[^"]*"|'[^']*'))?[ \t]*\)''')
REFERENCE = re.compile(r'^ {0,3}\[[^\]]+\]:[ \t]*' + DESTINATION)
FENCE = re.compile(r'^ {0,3}(`{3,}|~{3,})(.*)$')
INLINE_CODE = re.compile(r'(?<!`)(`+)(?!`).*?(?<!`)\1(?!`)')
COMMENT = re.compile(r'<!--.*?(?:-->|$)', re.DOTALL)
SCHEME = re.compile(r'^[A-Za-z][A-Za-z0-9+.-]*:')
DRIVE = re.compile(r'^[A-Za-z]:[\\/]')


@dataclass(frozen=True)
class Link:
    source: str
    line: int
    target: str
    raw: str


def destinations(source: str, text: str):
    """Yield repository paths from inline links, images and reference definitions."""
    fence = ''
    text = COMMENT.sub(lambda match: '\n' * match[0].count('\n'), text)
    for number, original in enumerate(text.splitlines(), 1):
        line = re.sub(r'^(?: {0,3}>[ \t]?)+', '', original)
        marker = FENCE.match(line)
        if fence:
            if marker and marker[1].startswith(fence) and not marker[2].strip():
                fence = ''
            continue
        if marker:
            fence = marker[1]
            continue
        if line.startswith(('    ', '\t')):
            continue
        line = INLINE_CODE.sub('', line)
        matches = list(INLINE.finditer(line))
        if definition := REFERENCE.match(line):
            matches.append(definition)
        for match in matches:
            raw = match[1].removeprefix('<').removesuffix('>')
            if raw.startswith(('#', '//')) or (SCHEME.match(raw) and not DRIVE.match(raw)):
                continue
            path = unquote(re.split('[?#]', raw, maxsplit=1)[0])
            path = re.sub(r'\\([()])', r'\1', path).replace('\\', '/')
            path = re.sub(r':\d+$', '', path)
            if not path:
                continue
            target = path if DRIVE.match(path) else posixpath.normpath(
                posixpath.join(posixpath.dirname(source), path),
            )
            yield Link(source, number, target, raw)


def scan(root: Path, *, exclude_sources: dict[str, str] | None = None) -> dict:
    tracked = tracked_paths(root)
    directories = {parent.as_posix() for name in tracked for parent in PurePosixPath(name).parents}
    exclusions = {name: reason for name, reason in (exclude_sources or {}).items() if name in tracked}
    sources = sorted(name for name in tracked - exclusions.keys() if name.lower().endswith('.md'))
    errors, examined = [], 0
    for name in sources:
        try:
            text = relative_path(root, name).read_text(encoding='utf-8-sig')
        except (OSError, ValueError) as error:
            errors.append({'code': 'LINK_SOURCE_UNREADABLE', 'source': name, 'detail': str(error)})
            continue
        for link in destinations(name, text):
            examined += 1
            code = link_problem(root, link.target, tracked, directories)
            if code:
                errors.append({'code': code, **asdict(link)})
    return {'ok': not errors, 'source_documents': len(sources),
            'local_links_examined': examined, 'excluded_sources': exclusions, 'diagnostics': errors}


def link_problem(root: Path, target: str, tracked: set[str], directories: set[str]) -> str | None:
    if target == '..' or target.startswith(('../', '/')) or DRIVE.match(target):
        return 'LINK_OUTSIDE_REPO'
    if target == '.':
        return None
    try:
        path = relative_path(root, target)
    except ValueError:
        return 'LINK_UNSAFE_TARGET'
    if not path.exists():
        return 'LINK_MISSING_TARGET'
    if target not in tracked and target not in directories:
        return 'LINK_UNTRACKED_TARGET'
    return None


def referrers(root: Path, target: str) -> list[dict]:
    """Check both versioned and local Markdown before retiring a local handoff."""
    paths = git(root, 'ls-files', '--cached', '--others', '--exclude-standard', '-z').stdout.split('\0')
    matches = []
    for name in sorted(set(paths)):
        if not name.lower().endswith('.md') or name == target:
            continue
        path = relative_path(root, name)
        if not path.is_file():
            raise ValueError(f'cannot check handoff references in {name}')
        text = path.read_text(encoding='utf-8-sig')
        matches.extend(asdict(link) for link in destinations(name, text) if link.target == target)
        # Local handoffs can also be referenced by a literal command or inline path.
        if target in text.replace('\\', '/') and not any(match['source'] == name for match in matches):
            matches.append({'source': name, 'target': target})
    return matches
