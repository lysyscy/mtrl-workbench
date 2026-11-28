"""Reject prose comments on added Git lines or in explicitly selected source files."""

from __future__ import annotations

import argparse
import ast
from bisect import bisect_right
from collections.abc import Iterator
from dataclasses import dataclass
from io import BytesIO
import os
from pathlib import Path
import re
import subprocess
import sys
import tokenize

if __package__:
    from .git_index import _git, index_bytes
else:
    from git_index import _git, index_bytes


SUFFIXES = {'.py', '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs'}
HUNK = re.compile(rb'^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@')
ENCODING = re.compile(r'#.*?coding[:=][ \t]*[-\w.]+')
EXTERNAL = re.compile(r'^(?:constraint:|外部约束:|NOTE\(external\):)')
PY_DIRECTIVE = re.compile(r'^(?:noqa\b|type:|ruff:|pragma:|pylint:|fmt:|coupling-ignore\b)')
JS_DIRECTIVE = re.compile(r'^(?:oxlint-disable\b|eslint-disable\b|@vite\b)')
WORD = re.compile(r'[$\w]+')
JSX_GENERIC = re.compile(r'\s*(?:[,=]|extends\b)')
JSX_TAG = re.compile(r'<(?:[A-Za-z_$][\w$.:.-]*|(?=>))')
REGEX_AFTER = {
    'await', 'case', 'delete', 'do', 'else', 'in', 'instanceof', 'new',
    'of', 'return', 'throw', 'typeof', 'void', 'yield',
}
CONTROL = {'if', 'while', 'for', 'with', 'switch', 'catch'}


@dataclass(frozen=True)
class Comment:
    line: int
    text: str


class JsComments:
    def __init__(self, text: str, jsx: bool):
        self.text = text
        self.jsx = jsx
        self.pos = 0
        self.line_starts = [0, *(m.end() for m in re.finditer('\n', text))]
        self.comments: list[Comment] = []

    def add(self, start: int, stop: int) -> None:
        line = bisect_right(self.line_starts, start)
        self.comments.extend(Comment(line + offset, text) for offset, text in
                             enumerate(self.text[start:stop].splitlines()))

    def quoted(self, quote: str, *, escapes: bool = True) -> None:
        self.pos += 1
        while self.pos < len(self.text):
            char = self.text[self.pos]
            self.pos += 1
            if char == quote:
                return
            if escapes and char == '\\':
                self.pos += 1

    def template(self) -> None:
        self.pos += 1
        while self.pos < len(self.text):
            char = self.text[self.pos]
            self.pos += 1
            if char == chr(96):
                return
            if char == '\\':
                self.pos += 1
            elif char == '$' and self.text.startswith('{', self.pos):
                self.pos += 1
                self.code('}')

    def regex_end(self, start: int) -> int | None:
        in_class = False
        pos = start + 1
        while pos < len(self.text):
            char = self.text[pos]
            if char in '\r\n':
                break
            if char == '\\':
                pos += 2
                continue
            if char == '/' and not in_class:
                return pos + 1
            if char in '[]':
                in_class = char == '['
            pos += 1
        return None

    def jsx_element(self, tag_end: int) -> None:
        self.pos = tag_end
        if self.text.startswith('<', self.pos):
            depth = 0
            while self.pos < len(self.text):
                char = self.text[self.pos]
                if char in ('"', "'"):
                    self.quoted(char)
                    continue
                self.pos += 1
                if char == '<':
                    depth += 1
                elif char == '>' and not self.text.startswith('=>', self.pos - 2):
                    depth -= 1
                    if not depth:
                        break
        while self.pos < len(self.text):
            if self.text.startswith('/>', self.pos):
                self.pos += 2
                return
            char = self.text[self.pos]
            if char in ('"', "'"):
                self.quoted(char, escapes=False)
            else:
                self.pos += 1
                if char == '>':
                    break
                if char == '{':
                    self.code('}')
        while self.pos < len(self.text):
            if self.text.startswith('</', self.pos):
                end = self.text.find('>', self.pos + 2)
                self.pos = len(self.text) if end == -1 else end + 1
                return
            if tag := JSX_TAG.match(self.text, self.pos):
                self.jsx_element(tag.end())
                continue
            char = self.text[self.pos]
            self.pos += 1
            if char == '{':
                self.code('}')

    def code(self, stop: str = '') -> None:
        expect_expression = True
        previous = ''
        while self.pos < len(self.text):
            pos = self.pos
            char = self.text[pos]
            if char.isspace():
                self.pos += 1
                continue
            if char == stop:
                self.pos += 1
                return
            if self.text.startswith('//', pos) or pos == 0 and self.text.startswith('#!'):
                end = self.text.find('\n', pos)
                self.pos = len(self.text) if end == -1 else end
                self.add(pos, self.pos)
                continue
            if self.text.startswith('/*', pos):
                end = self.text.find('*/', pos + 2)
                self.pos = len(self.text) if end == -1 else end + 2
                if not self.text.startswith('/**', pos):
                    self.add(pos, self.pos)
                continue
            if word := WORD.match(self.text, pos):
                previous = word.group()
                expect_expression = previous in REGEX_AFTER
                self.pos = word.end()
                continue
            self.pos += 1
            if char in ('"', "'"):
                self.pos = pos
                self.quoted(char)
                expect_expression = False
            elif char == chr(96):
                self.pos = pos
                self.template()
                expect_expression = False
            elif char == '/' and expect_expression and (end := self.regex_end(pos)) is not None:
                self.pos = end
                expect_expression = False
            elif char == '<' and expect_expression and self.jsx and (tag := JSX_TAG.match(self.text, pos)) and \
                    not JSX_GENERIC.match(self.text, tag.end()):
                self.jsx_element(tag.end())
                expect_expression = False
            elif char == '(':
                self.code(')')
                expect_expression = previous in CONTROL
            elif char == '{':
                self.code('}')
                expect_expression = False
            else:
                expect_expression = char in '=+-*/%!~&|^?:;,<>['
            previous = char


def comments(data: bytes, suffix: str) -> Iterator[Comment]:
    if suffix == '.py':
        for token in tokenize.tokenize(BytesIO(data).readline):
            if token.type == tokenize.COMMENT:
                yield Comment(token.start[0], token.string)
    else:
        scanner = JsComments(data.decode('utf-8-sig'), suffix in {'.jsx', '.tsx'})
        scanner.code()
        yield from scanner.comments


def allowed(comment: Comment, suffix: str) -> bool:
    text = comment.text.strip()
    if text.startswith('#!') and comment.line == 1:
        return True
    if suffix == '.py':
        return bool(comment.line <= 2 and ENCODING.match(text) or
                    PY_DIRECTIVE.match(text[1:].lstrip()) or EXTERNAL.match(text[1:].lstrip()))
    if text.startswith('///') and re.match(r'///\s*<reference\b', text):
        return True
    body = text.removeprefix('//').removeprefix('/*').removesuffix('*/').lstrip('* \t')
    return bool(JS_DIRECTIVE.match(body) or EXTERNAL.match(body))


def added_lines_by_file(patch: bytes) -> dict[str, set[int]]:
    added: dict[str, set[int]] = {}
    current: str | None = None
    saw_destination = False
    line: int | None = None
    for row in patch.split(b'\n'):
        if row.startswith(b'diff --git '):
            current = None
            saw_destination = False
            line = None
        elif not saw_destination and row.startswith(b'+++ '):
            saw_destination = True
            raw = row[4:].rstrip(b'\r').removesuffix(b'\t')
            if raw.startswith(b'"'):
                raw = ast.literal_eval('b' + raw.decode('ascii'))
            if raw.startswith(b'b/'):
                current = os.fsdecode(raw[2:])
        elif current is not None and (match := HUNK.match(row)):
            line = int(match[1])
        elif current is not None and line is not None and row.startswith(b'+'):
            added.setdefault(current, set()).add(line)
            line += 1
        elif current is not None and line is not None and row.startswith(b' '):
            line += 1
    return added


def candidates(root: Path, args: argparse.Namespace) -> Iterator[tuple[Path, bytes, set[int] | None]]:
    if args.files is not None:
        for name in args.files:
            path = root / name
            if path.suffix in SUFFIXES:
                yield path, path.read_bytes(), None
        return

    flags = ('--cached',) if args.staged else ('HEAD',)
    patterns = [f':(glob)**/*{suffix}' for suffix in sorted(SUFFIXES)]
    patch = _git(root, '-c', 'core.quotePath=true', 'diff', *flags, '--unified=0', '--no-renames',
                 '--no-color', '--no-ext-diff', '--no-textconv', '--diff-filter=ACMRT',
                 '--src-prefix=a/', '--dst-prefix=b/', '--', *patterns)
    by_file = added_lines_by_file(patch)
    for rel, lines in sorted(by_file.items()):
        path = root / rel
        if path.suffix not in SUFFIXES or (not args.staged and path.is_symlink()):
            continue
        if lines:
            yield path, index_bytes(root, path) if args.staged else path.read_bytes(), lines
    if args.diff:
        names = _git(root, 'ls-files', '--others', '--exclude-standard', '-z', '--', *patterns)
        for name in filter(None, names.split(b'\0')):
            path = root / os.fsdecode(name)
            if path.suffix in SUFFIXES and not path.is_symlink():
                yield path, path.read_bytes(), None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--staged', action='store_true')
    modes.add_argument('--diff', action='store_true')
    modes.add_argument('--files', type=Path, nargs='+')
    args = parser.parse_args()
    try:
        root = Path.cwd() if args.files is not None else Path(
            _git(Path.cwd(), 'rev-parse', '--show-toplevel').decode('utf-8').strip())
        findings = 0
        for path, data, lines in candidates(root, args):
            display = path.relative_to(root) if path.is_relative_to(root) else path
            for comment in comments(data, path.suffix):
                if (lines is None or comment.line in lines) and not allowed(comment, path.suffix):
                    print(f'{display.as_posix()}:{comment.line}: {comment.text.strip()}')
                    findings += 1
        if findings:
            print('Remove prose comments or name the external constraint using constraint: or 外部约束:.')
        return int(bool(findings))
    except (OSError, subprocess.SubprocessError, SyntaxError, UnicodeError, tokenize.TokenError) as exc:
        print(f'Comment check could not finish: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
