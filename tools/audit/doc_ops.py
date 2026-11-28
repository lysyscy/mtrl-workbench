"""Check repository documentation and plan or apply an explicit phase closeout."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

def main(argv=None) -> int:
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.audit.doc_ops import links
    from tools.audit.doc_ops.repo import checkout, json_text, read_json
    from tools.audit.doc_ops.tasks import inspect_entry

    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    commands = parser.add_subparsers(dest='command', required=True)
    for name, help_text in (
        ('links', 'check local links in tracked Markdown'),
        ('refresh', 'rebuild the current-runs table and active-work view'),
        ('check', 'check task schema, view drift and links'),
        ('closeout-plan', 'inspect resources and produce a read-only plan'),
        ('closeout-apply', 'revalidate and apply a reviewed plan'),
    ):
        command = commands.add_parser(name, help=help_text, allow_abbrev=False)
        command.add_argument('--config', type=Path, required=True)
        command.add_argument('--root', type=Path, default=Path.cwd(), help='Git checkout root')
        if name == 'closeout-plan':
            command.add_argument('--out', type=Path, help='write the plan to a new JSON file')
        if name == 'closeout-apply':
            command.add_argument('--plan', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        root = checkout(args.root)
        config = read_json(args.config)
        if config.get('schema_version') != 1:
            raise ValueError('unsupported configuration schema version')
        if args.command == 'links':
            result = links.scan(root, **config.get('links', {}))
        elif args.command in ('refresh', 'check'):
            result = inspect_entry(root, config, refresh=args.command == 'refresh')
        else:
            from tools.audit.doc_ops.closeout import apply, plan
            if args.command == 'closeout-plan':
                result = plan(root, config)
                if args.out:
                    with args.out.open('x', encoding='utf-8', newline='\n') as output:
                        output.write(json_text(result))
            else:
                result = apply(root, config, read_json(args.plan))
        print(json_text(result), end='')
        return 0 if result['ok'] else 1
    except (KeyError, IndexError, OSError, ValueError, TypeError, RuntimeError, subprocess.SubprocessError) as error:
        print(json_text({'ok': False, 'diagnostics': [{'code': 'INPUT_OR_EXECUTION_ERROR', 'detail': str(error)}]}),
              end='')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
