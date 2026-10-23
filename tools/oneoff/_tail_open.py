"""Create one ticket and advance the unique highwater; dry-run by default."""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import re
import sys

from tail_common import (TRACKER, TICKETS, STATES, TERMINAL, WATER_RE, read_tickets,
                         highwater, dependencies, dependency_state, write_many, encoded_like)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--what', required=True)
    parser.add_argument('--pre', default='None')
    parser.add_argument('--acceptance', required=True, action='append')
    parser.add_argument('--id', type=int, help='optional unused number above highwater')
    parser.add_argument('--state', choices=sorted(STATES - TERMINAL))
    parser.add_argument('--short', default='')
    parser.add_argument('--tracker', type=Path, default=TRACKER)
    parser.add_argument('--tickets', type=Path, default=TICKETS)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args(argv)
    tickets = read_tickets(args.tickets)
    original = args.tracker.read_bytes()
    tracker = original.decode('utf-8')
    last = highwater(tracker, tickets)
    number = args.id if args.id is not None else last + 1
    if number <= last or number in tickets:
        raise ValueError('ticket number must be unused and above highwater')
    if any('\n' in value or '\r' in value or not value.strip()
           for value in [args.what, args.pre, *args.acceptance]):
        raise ValueError('ticket fields must be nonempty single lines')
    pending = dependency_state(dependencies(f'**Blocked by:** {args.pre}'), tickets)
    state = args.state or ('blocked' if pending else 'ready-for-agent')
    if pending and state == 'ready-for-agent':
        raise ValueError('ready-for-agent cannot have unsatisfied prerequisites')
    slug = re.sub(r'[^\w-]+', '', args.short or args.what)[:32] or 'ticket'
    path = args.tickets / f'TAIL-{number}-{slug}.md'
    text = (f'# TAIL-{number}: {args.what}\n\n**What to build:** {args.what}\n\n'
            f'**Blocked by:** {args.pre}\n\n**Status:** {state}\n\n'
            + '\n'.join(f'- [ ] {value}' for value in args.acceptance)
            + f'\n\n## Comments\n\n{date.today()} · Created.\n')
    print(f'TAIL-{number} {state}; prerequisites: {pending or "done/none"}; apply={args.apply}')
    if args.apply:
        updated = WATER_RE.sub(f'TAIL_LAST_ISSUED: {number}', tracker)
        write_many({path: text.encode('utf-8'), args.tracker: encoded_like(updated, original)})
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print(f'Cannot open ticket: {exc}', file=sys.stderr)
        raise SystemExit(1)
