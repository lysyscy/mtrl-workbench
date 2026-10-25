# /// script
# requires-python = ">=3.12"
# dependencies = ["fonttools[woff]==4.67.0"]
# ///
"""Localize Xiaomi's unmodified web subsets; retain original glyph coverage as fallback.

Run with `uv run --no-project tools/dev/sync_misans_web.py` after an authorized asset update.
The application has no FontTools or network dependency.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
from urllib.request import urlopen
from fontTools.ttLib import TTFont

FONTS = Path(__file__).resolve().parents[2] / 'backend/app/web/fonts'
SOURCE = 'https://cdn-font.hyperos.mi.com/font/css?family=MiSans:400,500,600:Chinese_Simplify,Latin&display=swap'

def ranges(codes):
    spans = []
    for value in sorted(codes):
        if spans and value == spans[-1][1] + 1:
            spans[-1][1] = value
        else:
            spans.append([value, value])
    return ','.join(f'U+{a:X}' if a == b else f'U+{a:X}-{b:X}' for a, b in spans)

def fetch(url):
    with urlopen(url, timeout=60) as response:
        return response.read()

def main():
    css = fetch(SOURCE).decode('utf-8')
    faces = []
    for block in re.findall(r'@font-face\s*\{([^}]+)\}', css):
        weight = int(re.search(r'font-weight:\s*(\d+);', block)[1])
        url = re.search(r'url\("([^"]+\.woff2)"\)', block)[1]
        if not re.fullmatch(r'https://cdn-file\.hyperos\.mi\.com/mi-font-service/misans/(400|500|600)/[a-z0-9.]+\.woff2', url):
            raise ValueError('Unexpected official asset URL')
        codepoints = set()
        for value in re.search(r'unicode-range:\s*([^;]+);', block)[1].split(','):
            bounds = value.strip().removeprefix('U+').split('-')
            codepoints.update(range(int(bounds[0], 16), int(bounds[-1], 16) + 1))
        faces.append((weight, url, codepoints))
    assert faces and {weight for weight, _, _ in faces} == {400, 500, 600}
    folder = FONTS / 'misans-web'
    folder.mkdir(exist_ok=True)
    with ThreadPoolExecutor(max_workers=8) as pool:
        bodies = list(pool.map(fetch, [url for _, url, _ in faces]))
    originals = {weight: TTFont(FONTS / f'MiSans-{name}.woff2') for weight, name in [(400, 'Regular'), (500, 'Medium'), (600, 'Semibold')]}
    coverage = {weight: set() for weight in originals}
    manifest = {'source': SOURCE, 'unmodified_official_subsets': [], 'coverage': {}, 'metric_differences': []}
    rules = []
    for (weight, url, codes), body in zip(faces, bodies, strict=True):
        name = f'{weight}-{url.rsplit("/", 1)[1]}'
        target = folder / name
        target.write_bytes(body)
        font = TTFont(target); actual = font.getBestCmap(); original = originals[weight]
        assert codes <= actual.keys()
        for field in ['ascent', 'descent', 'lineGap']:
            assert getattr(font['hhea'], field) == getattr(original['hhea'], field)
        for code in codes & original.getBestCmap().keys():
            before = original['hmtx'][original.getBestCmap()[code]][0]
            after = font['hmtx'][actual[code]][0]
            if before != after:
                manifest['metric_differences'].append({'weight': weight, 'code': hex(code), 'before': before, 'after': after})
                assert not 0x3400 <= code <= 0x9FFF, 'Chinese text geometry changed'
        coverage[weight].update(codes)
        rules.append(f"@font-face{{font-family:MiSans;font-style:normal;font-weight:{weight};font-display:swap;src:url('/static/fonts/misans-web/{name}') format('woff2');unicode-range:{ranges(codes)}}}")
        manifest['unmodified_official_subsets'].append({'file': name, 'source': url, 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()})
    for weight, original in originals.items():
        missing = set(original.getBestCmap()) - coverage[weight]
        name = original['name'].getDebugName(6) + '.woff2'
        # shortcut: official subsets omit rare glyphs; original files cover those ranges until Xiaomi supplies them.
        rules.append(f"@font-face{{font-family:MiSans;font-style:normal;font-weight:{weight};font-display:swap;src:url('/static/fonts/{name}') format('woff2');unicode-range:{ranges(missing)}}}")
        manifest['coverage'][weight] = {'original': len(original.getBestCmap()), 'official': len(coverage[weight]), 'original_fallback': len(missing)}
        assert set(original.getBestCmap()) <= coverage[weight] | missing
    (FONTS / 'misans-web.css').write_text('\n'.join(rules) + '\n', encoding='utf-8')
    (folder / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(f'Verified {len(faces)} unmodified official subsets; complete original coverage/line metrics verified; horizontal differences recorded')

if __name__ == '__main__':
    main()
