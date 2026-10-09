"""Capture coverage presets, using the pinned planner's real quantized grid."""
from dataclasses import dataclass, replace
from pathlib import Path
import json
import math
from nam.capture.planner import _grid_capacity, corner_capture_count
from nam.capture.project import new_project, add_corner_captures


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


def quality_settings(knobs, level):
    quality = QUALITIES[level]
    knobs = tuple(replace(k, step=round((k.max - k.min) * quality.fraction, 6), default=None)
                  for k in knobs)
    specs = tuple(k.to_param_spec() for k in knobs)
    capacity = _grid_capacity(specs, .5)
    corners = corner_capture_count(knobs)
    # A small one-knob grid can saturate. Keep test allocation bounded so moving
    # toward Thorough/Overkill doesn't consume progressively more training points.
    test_budget = max(3, capacity // 10)
    tests = min(math.ceil(quality.tests_per_knob * len(knobs)), capacity - corners, test_budget)
    train = min(quality.per_knob * len(knobs), capacity - tests)
    if train < 1 or tests < 1:
        raise ValueError("These knob ranges leave no unseen test settings. Use wider ranges or a finer step in Advanced.")
    return knobs, train, tests


def make_plan(knobs, train, tests, seed=0, corners=True, **kwargs):
    if not 1 <= len(knobs) <= 8:
        raise ValueError("Model 1–8 continuous knobs. Keep other knobs and switches fixed.")
    if train + tests > 5000:
        raise ValueError("Use fewer than 5,001 settings in one plan; split larger experiments into separate projects.")
    if any((k.max - k.min) / k.step > 2000 for k in knobs):
        raise ValueError("The knob step is too fine for hand-set controls. Use at most 2,001 positions per knob.")
    project = new_project(knobs, n_train=train, n_validation=tests, seed=seed, **kwargs)
    project.include_initial_corners = corners
    if corners:
        add_corner_captures(project)
    return project


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
