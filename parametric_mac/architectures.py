"""A2 topology and conditioning profiles for the companion trainer."""
import copy

FILM_FACTORY = "parametric_mac.film.init_film"

A2_KERNEL_SIZES = (6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 15, 15, 6, 6, 6, 6, 6, 6, 6)
A2_DILATIONS = (1, 3, 7, 17, 41, 101, 239, 1, 3, 7, 17, 41, 101, 239, 1, 13, 1, 3, 7, 17, 41, 101, 239)
ARCHITECTURES = {
    "a2-dual": "NAM A2 · Standard + Nano (one file)",
    "auto": "Current recipe · automatic width",
    "a2-standard": "NAM A2 Standard · 8 channels",
    "a2-nano": "NAM A2 Nano · 3 channels",
    "film-dual": "NAM A2 FiLM · Standard + Nano (one file)",
    "film-standard": "NAM A2 FiLM Standard · 8 channels",
    "film-nano": "NAM A2 FiLM Nano · 3 channels",
}


def is_film(architecture):
    return architecture.startswith("film-")


def is_dual(architecture):
    return architecture in ("a2-dual", "film-dual")


def apply_architecture(model, architecture="auto"):
    if architecture not in ARCHITECTURES:
        raise ValueError("Choose a supported concat or FiLM model architecture.")
    result = copy.deepcopy(model)
    if result["net"]["name"] not in ("ConcatWaveNet", FILM_FACTORY):
        raise ValueError("This workflow trains concat or FiLM A2 parametric models.")
    if is_film(architecture):
        params = result["net"]["config"]["params"]
        if not 1 <= len(params) <= 16:
            raise ValueError("FiLM supports 1–16 continuous controls. Choose a concat profile for more controls.")
        if any(p.get("type", "continuous") != "continuous" for p in params):
            raise ValueError("FiLM supports continuous controls only. Choose a concat profile for projects with switches.")
        result["net"]["name"] = FILM_FACTORY
    else:
        result["net"]["name"] = "ConcatWaveNet"
    if architecture != "auto":
        result["net"]["config"]["layers"] = [{
            "channels": 3 if architecture.endswith("nano") else 8,
            "kernel_sizes": list(A2_KERNEL_SIZES), "dilations": list(A2_DILATIONS),
            "activation": "LeakyReLU", "gated": False,
            "head": {"out_channels": 1, "kernel_size": 16, "bias": True},
        }]
    return result
