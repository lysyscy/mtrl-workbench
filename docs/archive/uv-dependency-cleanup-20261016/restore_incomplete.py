"""Restore only missing original wheel files after Windows blocked an uninstall."""
from pathlib import Path
import shutil

cache = Path('C:/Users/Administrator/AppData/Local/uv/cache/archive-v0')
target = Path('backend/.venv/Lib/site-packages').resolve()
assert target == Path('D:/dev/mtrl-workbench/backend/.venv/Lib/site-packages')
count = 0
for archive in ('oADGCAI_8YEKoojX', 'DozfZrUFnmGwUAns', '-z-vqfNMVTUqN0Du'):
    source = cache / archive
    assert source.is_dir()
    for item in source.rglob('*'):
        if item.is_file():
            destination = target / item.relative_to(source)
            assert destination.resolve().is_relative_to(target)
            if not destination.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, destination)
                assert item.read_bytes() == destination.read_bytes()
                count += 1
print(f'Restored {count} missing original wheel files; existing files were preserved')
