"""Capture coverage presets, using the pinned planner's real quantized grid."""
from dataclasses import dataclass, replace
from pathlib import Path
import json
import math
from nam.capture.planner import _grid_capacity, corner_capture_count
from .controls import SwitchSpec, ControlProject, ControlModel, plan_controls, switch_combinations, continuous_plan, boundary_settings, safe_capture_paths


@dataclass(frozen=True)
class Quality:
    name: str
    description: str
    per_knob: int
    tests_per_knob: float
    fraction: float


QUALITIES = (
    Quality("Quick test", "Check your setup. Too sparse for a finished model.", 4, 1.5, .2),
    Quality("Decent", "A starting point. Fine changes between settings may be missed.", 9, 2, .1),
    Quality("Good", "Recommended starting point: balanced coverage and recording effort.", 15, 3, .05),
    Quality("Thorough", "More coverage to explore subtle changes. Allow a longer session.", 27, 5, .05),
    Quality("Overkill", "Much more recording. Improvements may be small; listen before spending the time.", 48, 8, .05),
)


RECOMMENDED_LEVEL = 2  # "Good"
# The three levels on the Record page: (card title, index into QUALITIES). Decent (1) and Overkill (4) are Expert.
MAIN_LEVELS: tuple[tuple[str, int], ...] = (("Fast", 0), ("Good", 2), ("Max", 3))
_MAIN_NAMES = {index: name for name, index in MAIN_LEVELS}


def level_label(index: int) -> str:
    """The name the Record page shows for a stored quality index."""
    return _MAIN_NAMES.get(index, QUALITIES[index].name)


def quality_settings(knobs, level):
    quality = QUALITIES[level]
    all_controls = knobs
    combinations = switch_combinations(all_controls)
    knobs = tuple(k for k in knobs if not isinstance(k, SwitchSpec))
    if not knobs:
        raise ValueError("Add at least one knob to model alongside your switches.")
    knobs = tuple(replace(k, step=round((k.max - k.min) * quality.fraction, 6), default=None)
                  for k in knobs)
    specs = tuple(k.to_param_spec() for k in knobs)
    capacity = _grid_capacity(specs, .5)
    corners = corner_capture_count(knobs) if len(knobs) <= 8 else len(boundary_settings(knobs))
    # A small one-knob grid can saturate. Keep test allocation bounded so moving
    # toward Thorough/Overkill doesn't consume progressively more training points.
    test_budget = max(3, capacity // 10)
    tests = min(math.ceil(quality.tests_per_knob * len(knobs)), capacity - corners, test_budget)
    train = min(quality.per_knob * len(knobs), capacity - tests)
    if train < 1 or tests < 1:
        raise ValueError("These knob ranges leave no unseen test settings. Use wider ranges or a finer step in Advanced.")
    replaced = {k.name: k for k in knobs}
    controls = tuple(replaced.get(c.name, c) for c in all_controls)
    return controls, train * combinations, tests * combinations


def make_plan(knobs, train, tests, seed=0, corners=True, **kwargs):
    if not 1 <= len(knobs) <= 24:
        raise ValueError("Model 1–24 controls in one project.")
    if train + tests > 5000:
        raise ValueError("Use fewer than 5,001 settings in one plan; split larger experiments into separate projects.")
    if any((k.max - k.min) / k.step > 2000 for k in knobs):
        raise ValueError("The knob step is too fine for hand-set controls. Use at most 2,001 positions per knob.")
    if any(isinstance(c, SwitchSpec) for c in knobs):
        project = plan_controls(knobs, train, tests, seed, corners, **kwargs)
        if len(project.entries) > 5000:
            raise ValueError("This plan exceeds 5,000 recordings. Lower quality or keep some controls fixed.")
        return safe_capture_paths(project)
    project = continuous_plan(knobs, train, tests, seed, corners)
    for key, value in kwargs.items():
        setattr(project, key, value)
    project.include_initial_corners = corners
    if len(project.entries) > 5000:
        raise ValueError("This plan exceeds 5,000 recordings. Lower quality or keep some controls fixed.")
    return safe_capture_paths(ControlProject(**{**project.model_dump(), "knobs": [ControlModel.from_spec(c) for c in knobs]}))


def recording_minutes(project, train_seconds=38, test_seconds=7):
    # Estimate includes ten seconds to set physical knobs, not ML training time.
    return math.ceil(sum((train_seconds if e.split == "train" else test_seconds) + 10
                         for e in project.entries) / 60)


def read_state(directory):
    try:
        value = json.loads((Path(directory) / "workflow.json").read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def write_state(directory, value):
    from nam.capture.project import atomic_write_json
    atomic_write_json(Path(directory) / "workflow.json", value)
