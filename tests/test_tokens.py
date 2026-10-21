from parametric_mac.ui.tokens import DARK, LIGHT, TEXT_PAIRS, contrast_ratio, resolve_mode, palette_for


def test_dark_tokens_match_spec():
    assert (DARK.bg, DARK.panel, DARK.raised, DARK.accent_fill, DARK.danger) == ("#101317", "#0c0f12", "#161b21", "#d4ff4f", "#ff4d4d")


def test_light_accent_text_differs_from_fill():
    assert LIGHT.accent_fill == "#d4ff4f" and LIGHT.accent_text == "#4d6400" and LIGHT.on_accent == "#14171b"


def test_contrast_ratio_known_values():
    assert round(contrast_ratio("#000000", "#ffffff"), 1) == 21.0
    assert round(contrast_ratio("#777777", "#ffffff"), 2) == 4.48


def test_all_text_pairs_pass_wcag_aa_in_both_modes():
    for palette in (DARK, LIGHT):
        for fg, bg in TEXT_PAIRS:
            assert contrast_ratio(getattr(palette, fg), getattr(palette, bg)) >= 4.5, (palette, fg, bg)


def test_resolve_mode():
    assert resolve_mode("system", True) == "dark"
    assert resolve_mode("system", False) == "light"
    assert resolve_mode("light", True) == "light"
    assert resolve_mode("dark", False) == "dark"
    assert palette_for("dark") is DARK
    assert palette_for("light") is LIGHT
