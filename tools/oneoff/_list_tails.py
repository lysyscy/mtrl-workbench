"""List the tickets in this worktree and resolve their prerequisites."""
import argparse
from pathlib import Path
import sys

from tail_common import TICKETS, TERMINAL, read_tickets, dependencies, dependency_state


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tickets', type=Path, default=TICKETS)
    parser.add_argument('--all', action='store_true')
    args = parser.parse_args(argv)
    tickets = read_tickets(args.tickets)
    errors = []
    for number, (path, text, state) in tickets.items():
        if state in TERMINAL and not args.all:
            continue
        try:
            pending = dependency_state(dependencies(text), tickets)
            detail = ', '.join(pending) if pending else 'prerequisites done/none; check external conditions'
        except ValueError as exc:
            detail = str(exc)
            errors.append(detail)
        print(f'TAIL-{number}: {state} | {detail} | {path.name}')
    return 1 if errors else 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print(f'Cannot list tickets: {exc}', file=sys.stderr)
        raise SystemExit(1)
