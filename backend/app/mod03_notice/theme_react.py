"""React styles and appearance cards read the shared theme roles."""

from .page import FONT_CSS, REACT_GEOMETRY, REACT_THEME_SPEC, theme_variables
from .page import theme_name as theme_name


def _variables(name: str | None) -> dict[str, str]:
    return {**theme_variables(name), **REACT_GEOMETRY}


def theme_choices() -> list[dict]:
    return [
        {"name": name, **spec, "style": spec["description"], "vars": _variables(name)}
        for name, spec in REACT_THEME_SPEC.items()
    ]


def render_react_theme(name: str | None) -> str:
    body = "\n".join(f"  {key}:{value};" for key, value in _variables(name).items())
    return FONT_CSS + ":root{\n" + body + "\n  color-scheme:var(--ui-scheme);\n}\n"
