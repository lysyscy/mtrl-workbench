"""Update the original ticket with an explicit terminal status and evidence."""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import sys

from tail_common import TICKETS, STATE_RE, read_tickets, write_many, encoded_like


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--id', required=True, type=int)
    parser.add_argument('--status', required=True, choices=['done', 'wontfix'])
    parser.add_argument('--reason', required=True)
    parser.add_argument('--tickets', type=Path, default=TICKETS)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args(argv)
    if not args.reason.strip():
        raise ValueError('real completion evidence or withdrawal reason is required')
    tickets = read_tickets(args.tickets)
    if args.id not in tickets:
        raise ValueError('missing ticket')
    path, text, state = tickets[args.id]
    if state in ('done', 'wontfix'):
        raise ValueError('ticket is already terminal; inspect the original evidence')
    updated = STATE_RE.sub(f'**Status:** {args.status}', text, count=1)
    if '## Comments' not in updated:
        updated += '\n\n## Comments\n'
    updated += f'\n{date.today()} · {args.status}: {args.reason.strip()}\n'
    print(f'TAIL-{args.id}: {state} -> {args.status}; apply={args.apply}')
    if args.apply:
        write_many({path: encoded_like(updated, path.read_bytes())})
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print(f'Cannot close ticket: {exc}', file=sys.stderr)
        raise SystemExit(1)
