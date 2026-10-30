"""Project artifact entry; no enrollment or cleanup happens on import."""
import subprocess
import sys

if __name__ == '__main__':
    if len(sys.argv) < 2: raise SystemExit('action required')
    own_args = sys.argv[2:sys.argv.index('--')] if '--' in sys.argv else sys.argv[2:]
    if any(x.split('=', 1)[0] in {'--r', '--ro', '--roo', '--root'} for x in own_args): raise SystemExit('Project output root is fixed')
    raise SystemExit(subprocess.run([sys.executable, 'C:\\Users\\Administrator\\.skills-manager\\skills\\setup-solo-workflow\\scripts\\artifact_lifecycle.py', sys.argv[1], '--root', 'C:\\Users\\Administrator\\AppData\\Local\\AgentArtifacts\\projects\\mtrl-workbench', *sys.argv[2:]], check=False).returncode)
