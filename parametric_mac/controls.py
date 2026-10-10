"""Typed controls that preserve switch metadata through capture, reload and export."""
from dataclasses import dataclass
import itertools
import hashlib
import re
import json
from pathlib import Path
from typing import Literal
from nam.capture.params import KnobSpec, validate_knobs
from nam.capture.project import CaptureProject, KnobModel, CaptureEntryModel, new_project, add_corner_captures
from nam.models.parametric import ParamSpec, abbreviate_param_names, make_capture_y_path


@dataclass(frozen=True)
class SwitchSpec(KnobSpec):
    enum_names: tuple[str, ...] = ('Off', 'On')

    def to_param_spec(self):
        if self.min != 0 or self.max != len(self.enum_names)-1 or self.is_gain or self.avoid_zero:
            raise ValueError('Switch bounds must match its named positions; switches cannot be gain knobs.')
        return ParamSpec(self.name, 0, len(self.enum_names)-1, self.default,
                         type='switch', enum_names=self.enum_names)


class ControlModel(KnobModel):
    type: Literal['continuous', 'switch'] = 'continuous'
    enum_names: tuple[str, ...] | None = None

    def to_knob_spec(self):
        if self.type == 'switch':
            if self.is_gain or self.avoid_zero:
                raise ValueError('Switches cannot use gain or avoid-zero roles.')
            spec = SwitchSpec(self.name, self.min, self.max, step=1, default=self.default,
                              enum_names=self.enum_names or ())
            spec.to_param_spec()  # Validate label count, uniqueness and index bounds.
            return spec
        return super().to_knob_spec()

    @classmethod
    def from_spec(cls, spec):
        return cls(**spec.to_dict(), type='switch' if isinstance(spec, SwitchSpec) else 'continuous',
                   enum_names=spec.enum_names if isinstance(spec, SwitchSpec) else None)


class ControlProject(CaptureProject):
    knobs: list[ControlModel]


def load_project(directory):
    from nam.capture.project import load_project as legacy_load
    legacy_load(directory)  # Preserve version validation and legacy behavior.
    payload = json.loads((Path(directory)/'capture_project.json').read_text())
    project = ControlProject.model_validate(payload)
    project.knob_specs()
    return project


def model_config(project):
    from nam.capture.export import build_concat_model_config
    model = build_concat_model_config(project)
    params = []
    for control in project.knob_specs():
        spec = control.to_param_spec().to_dict()
        spec.pop('avoid_zero', None)
        if spec['type'] == 'continuous':
            spec.pop('enum_names', None)
        params.append(spec)
    model['net']['config']['params'] = params
    return model


def switch_combinations(controls):
    count = 1
    for control in controls:
        if isinstance(control, SwitchSpec):
            control.to_param_spec()
            count *= len(control.enum_names)
    if count > 32:
        raise ValueError(f'These switches create {count} combinations. Model at most 32 in one project; keep some switches fixed or use separate projects.')
    return count


def plan_controls(controls, train, tests, seed, corners, **kwargs):
    validate_knobs(controls)
    continuous = tuple(c for c in controls if not isinstance(c, SwitchSpec))
    switches = tuple(c for c in controls if isinstance(c, SwitchSpec))
    if not continuous:
        raise ValueError('Include at least one knob so unseen knob settings can test the model.')
    combinations = switch_combinations(controls)
    if train % combinations or tests % combinations:
        raise ValueError(f'Use recording counts divisible by {combinations} so every switch combination gets equal coverage.')
    if tests < combinations:
        raise ValueError('Reserve at least one unseen test setting per switch combination.')
    indices = {'train': 0, 'validation': 0}
    entries = []
    abbreviations = abbreviate_param_names([c.name for c in controls])
    for group, values in enumerate(itertools.product(*(range(len(c.enum_names)) for c in switches))):
        part = continuous_plan(continuous, train//combinations, tests//combinations, seed+group, corners)
        for entry in part.entries:
            params = {**entry.params, **dict(zip((s.name for s in switches), values))}
            params = {c.name: params[c.name] for c in controls}
            index = indices[entry.split]
            indices[entry.split] += 1
            prefix = 'lhs_' if entry.split == 'train' else 'val_lhs_'
            filename = make_capture_y_path(f'{prefix}{index:04d}_', params, abbreviations)
            entries.append(CaptureEntryModel(index=index, split=entry.split, params=params,
                                             y_path='captures/'+filename))
    return ControlProject(knobs=[ControlModel.from_spec(c) for c in controls], entries=entries,
                          seed=seed, n_train_lhs=train, include_initial_corners=corners, **kwargs)


def format_controls(params, controls):
    values = []
    for control in controls:
        value = params[control.name]
        text = control.enum_names[int(value)] if isinstance(control, SwitchSpec) else f'{value:g}'
        values.append(f'{control.name}: {text}')
    return ' · '.join(values)


def boundary_settings(controls):
    """For larger rigs, sample each axis at its extremes plus both global extremes.

    This stays linear in knob count rather than requesting exponentially many corners.
    All values use the same quantization and avoid-zero rules as the upstream planner.
    """
    from nam.models.parametric import quantize_to_capture_grid, decode_named_params
    specs = tuple(c.to_param_spec() for c in controls)
    center = [(c.min+c.max)/2 for c in controls]
    raw = [[c.min for c in controls], [c.max for c in controls]]
    for i, control in enumerate(controls):
        for value in (control.min, control.max):
            point = center.copy()
            point[i] = value
            raw.append(point)
    result = {}
    for point in raw:
        params = decode_named_params(quantize_to_capture_grid(point, specs, default_step=.5), specs)
        result[tuple(params[c.name] for c in controls)] = params
    return list(result.values())


def continuous_plan(controls, train, tests, seed, corners):
    if len(controls) <= 8:
        part = new_project(controls, n_train=train, n_validation=tests, seed=seed)
        if corners:
            add_corner_captures(part)
        return part
    from nam.capture.planner import plan_unique_splits
    specs = tuple(c.to_param_spec() for c in controls)
    boundaries = boundary_settings(controls) if corners else []
    reserve = {tuple(p[c.name] for c in controls) for p in boundaries}
    training, validation = plan_unique_splits(specs, n_train=train, n_validation=tests,
        seed=seed, default_step=.5, validation_exclude=reserve)
    existing = {tuple(p[c.name] for c in controls) for p in training}
    training.extend(p for p in boundaries if tuple(p[c.name] for c in controls) not in existing)
    entries = []
    abbreviations = abbreviate_param_names([c.name for c in controls])
    for split, points in [('train', training), ('validation', validation)]:
        for i, params in enumerate(points):
            prefix = 'lhs_' if split == 'train' else 'val_lhs_'
            entries.append(CaptureEntryModel(index=i, split=split, params=params,
                y_path='captures/'+make_capture_y_path(f'{prefix}{i:04d}_', params, abbreviations)))
    return CaptureProject(knobs=[KnobModel.from_knob_spec(c) for c in controls], entries=entries,
        seed=seed, n_train_lhs=train, include_initial_corners=corners)


def safe_capture_paths(project):
    """New plans accept physical names without making them filesystem paths.

    Existing saved paths are never rewritten. Prefix/index and a hash preserve unique
    recovery targets if long or non-ASCII display names need a shorter filename.
    """
    for entry in project.entries:
        original = entry.y_path.removeprefix('captures/')
        filename = re.sub(r'[^A-Za-z0-9._-]', '_', original)
        if len(filename) > 220:
            digest = hashlib.sha256(original.encode()).hexdigest()[:16]
            filename = filename[:195].rstrip('._') + '_' + digest + '.wav'
        entry.y_path = 'captures/' + filename
    return project
