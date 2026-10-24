"""React theme consumer; palette values remain in the shared page theme owner."""
import re

from .page import (
    DEFAULT_THEME, FONT_CSS, THEME_SEEDS, _mix, _PURE_WHITE,
    _REACT_LIGHT, _REACT_SHADOWS, _REACT_STATES, render_theme,
)


def render_react_theme(name: str) -> str:
    """React appearance over the same account palette; legacy output stays unchanged."""
    key = name if name in THEME_SEEDS else DEFAULT_THEME
    v = dict(re.findall(r"(--[a-z0-9-]+):([^;]+);", render_theme(key)))
    dark = bool(THEME_SEEDS[key].get("dark"))
    if not dark and key != "高对比":
        background = v["--bg"]
        v.update(_REACT_LIGHT)
        if key != DEFAULT_THEME:
            v["--bg"] = _mix(background, _REACT_LIGHT["--bg"], 0.5)
        v.update(_REACT_SHADOWS)
    for role, (accent, text, soft, border) in _REACT_STATES.items():
        v[f"--{role}"] = accent
        v[f"--{role}-d"] = _mix(accent, _PURE_WHITE, 0.40) if dark else text
        v[f"--{role}-l"] = _mix(accent, v["--sf"], 0.84) if dark else soft
        v[f"--{role}-bd"] = _mix(accent, v["--sf"], 0.60) if dark else border
    v.update({
        "--ui-scheme": "dark" if dark else "light",
        "--font-ui-size": "13.5", "--radius-input": "10px", "--radius-card": "16px",
        "--radius-inner": "14px", "--radius-pill": "999px", "--motion-fast": "130ms",
        "--r": "10px", "--r2": "16px",
        "--sb": v["--sf"], "--sb-hd": v["--tx"], "--sb-tx": v["--tx2"],
        "--sb-mut": v["--tx2"], "--sb-bd": v["--bd"], "--sb-hover": v["--sf2"],
        "--sb-on": v["--pri-l"], "--sb-on-hl": v["--pri-d"],
    })
    body = "\n".join(f"  {k}:{value};" for k, value in v.items())
    return ":root{\n" + body + "\n  color-scheme:var(--ui-scheme);\n}\n" + FONT_CSS


