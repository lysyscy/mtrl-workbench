"""React theme consumer; approved colors remain in the shared page theme owner."""
import re

from .page import (
    DEFAULT_THEME, REACT_GEOMETRY, REACT_THEME_SPEC, REACT_THEME_OVERRIDES,
    _REACT_LIGHT, _REACT_SHADOWS, _REACT_STATES, render_theme,
)


def theme_name(name: str) -> str:
    """Removed or unknown preferences display the React default without rewriting storage."""
    return name if name in REACT_THEME_SPEC else DEFAULT_THEME


def _variables(name: str) -> dict[str, str]:
    key = theme_name(name)
    v = dict(re.findall(r"(--[a-z0-9-]+):([^;]+);", render_theme('松绿' if key == '松绿' else DEFAULT_THEME)))
    if key != '松绿':
        v.update(_REACT_LIGHT)
        v.update(_REACT_SHADOWS)
        for role, (accent, text, soft, border) in _REACT_STATES.items():
            v.update({f'--{role}': accent, f'--{role}-d': text,
                      f'--{role}-l': soft, f'--{role}-bd': border})
        v.update({'--sb': v['--sf'], '--sb-hd': v['--tx'], '--sb-tx': v['--tx2'],
                  '--sb-mut': v['--tx2'], '--sb-bd': v['--bd'], '--sb-hover': v['--sf2'],
                  '--sb-on': v['--pri-l'], '--sb-on-hl': v['--pri-d']})
    v.update(REACT_GEOMETRY)
    v.update(REACT_THEME_OVERRIDES[key])
    return v


def theme_choices() -> list[dict]:
    """Card previews and the served page share the exact same resolved roles."""
    return [{'name': name, **spec, 'style': spec['description'], 'vars': _variables(name)}
            for name, spec in REACT_THEME_SPEC.items()]


def render_react_theme(name: str) -> str:
    body = "\n".join(f"  {key}:{value};" for key, value in _variables(name).items())
    return "@import url('/static/fonts/misans-web.css');\n:root{\n" + body + "\n  color-scheme:var(--ui-scheme);\n}\n"
