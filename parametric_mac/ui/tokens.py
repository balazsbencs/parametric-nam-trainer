"""Console theme tokens. The only module that may hold color literals."""
from dataclasses import dataclass
from typing import Literal

Appearance = Literal["system", "light", "dark"]
Mode = Literal["light", "dark"]
APPEARANCES: tuple[Appearance, ...] = ("system", "light", "dark")


@dataclass(frozen=True)
class Palette:
    bg: str
    panel: str
    raised: str
    line: str
    line_strong: str
    text: str
    muted: str
    accent_fill: str
    on_accent: str
    accent_text: str
    ok: str
    warn: str
    danger: str
    hover: str
    accent_surface: str
    ok_surface: str
    warn_surface: str
    danger_surface: str
    danger_border: str


DARK = Palette(
    bg="#101317", panel="#0c0f12", raised="#161b21", line="#222830", line_strong="#2a313b",
    text="#e3e8ee", muted="#7f8a97", accent_fill="#d4ff4f", on_accent="#101317",
    accent_text="#d4ff4f", ok="#8de07a", warn="#ffb547", danger="#ff4d4d",
    hover="#1d232b", accent_surface="#2a3312", ok_surface="#18251a", warn_surface="#2e2414",
    danger_surface="#1e1414", danger_border="#5a2a2a",
)

# Provisional light tokens (spec §4.0); the user approves them from screenshots.
LIGHT = Palette(
    bg="#f4f5f2", panel="#ebede8", raised="#ffffff", line="#d9dcd5", line_strong="#c9cdc4",
    text="#14171b", muted="#5f6873", accent_fill="#d4ff4f", on_accent="#14171b",
    accent_text="#4d6400", ok="#2f7a24", warn="#9a5b00", danger="#d42c2c",
    hover="#e7eae3", accent_surface="#eef6cf", ok_surface="#ebf5e7", warn_surface="#f8ecd6",
    danger_surface="#fdf1f1", danger_border="#efb4b4",
)

# (foreground, background) field pairs that must meet WCAG AA (4.5:1).
TEXT_PAIRS: tuple[tuple[str, str], ...] = (
    ("text", "bg"), ("text", "panel"), ("text", "raised"),
    ("muted", "bg"), ("muted", "panel"), ("muted", "raised"),
    ("accent_text", "bg"), ("accent_text", "panel"), ("accent_text", "raised"),
    ("on_accent", "accent_fill"),
    ("ok", "bg"), ("ok", "raised"), ("warn", "bg"), ("warn", "raised"),
    ("danger", "bg"), ("danger", "raised"),
    ("text", "hover"), ("accent_text", "accent_surface"), ("ok", "ok_surface"),
    ("warn", "warn_surface"), ("danger", "danger_surface"), ("text", "danger_surface"),
)


def resolve_mode(choice: Appearance, system_is_dark: bool) -> Mode:
    if choice == "system":
        return "dark" if system_is_dark else "light"
    return choice


def palette_for(mode: Mode) -> Palette:
    return DARK if mode == "dark" else LIGHT


def _luminance(color: str) -> float:
    value = color.lstrip("#")
    if len(value) != 6:
        raise ValueError(f"Expected a #rrggbb color, got {color!r}")
    channels = (int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(foreground: str, background: str) -> float:
    lighter, darker = sorted((_luminance(foreground), _luminance(background)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)
