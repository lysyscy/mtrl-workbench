"""Project artifact entry; no enrollment or cleanup happens on import."""
import subprocess
import sys

if __name__ == '__main__':
    if len(sys.argv) < 2: raise SystemExit('action required')
    raise SystemExit(subprocess.run([sys.executable, 'C:\\Users\\Administrator\\.skills-manager\\skills\\setup-solo-workflow\\scripts\\artifact_lifecycle.py', sys.argv[1], '--root', 'C:\\Users\\Administrator\\AppData\\Local\\AgentArtifacts\\projects\\mtrl-workbench', *sys.argv[2:]], check=False).returncode)
