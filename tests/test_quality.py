"""Presets must produce realizable, distinct training and unseen test settings."""
import pytest
from nam.capture.params import KnobSpec
from parametric_mac.workflow import quality_settings, make_plan, recording_minutes


@pytest.mark.parametrize('level', range(5))
@pytest.mark.parametrize('count', [1, 2, 4])
def test_quality_plans_are_realizable_and_hold_out_settings(level, count):
    source = tuple(KnobSpec(f'Knob{i}', 0, 10, is_gain=i == 0, avoid_zero=i == 0)
                   for i in range(count))
    knobs, train, tests = quality_settings(source, level)
    plan = make_plan(knobs, train, tests)
    seen = [tuple(e.params.values()) for e in plan.entries]
    assert len(seen) == len(set(seen))
    assert len(plan.entries_for_split('validation')) == tests > 0
    assert all(e.params['Knob0'] > 0 for e in plan.entries)
    assert [(k.min, k.max, k.is_gain, k.avoid_zero) for k in knobs] == [
        (k.min, k.max, k.is_gain, k.avoid_zero) for k in source]
    assert recording_minutes(plan) > 0


def test_good_two_knob_plan_matches_approved_effort():
    knobs, train, tests = quality_settings((KnobSpec('Drive', 0, 10, avoid_zero=True, is_gain=True),
                                          KnobSpec('Tone', 0, 10)), 2)
    plan = make_plan(knobs, train, tests)
    assert len(plan.entries) == 40
    assert recording_minutes(plan) == 29
    assert [k.step for k in knobs] == [.5, .5]


def test_quality_scales_to_physical_dial_ranges():
    knobs, train, tests = quality_settings((KnobSpec('Drive', 1, 11), KnobSpec('Tone', -1, 1)), 0)
    assert [k.step for k in knobs] == [2, .4]
    plan = make_plan(knobs, train, tests)
    assert all(-1 <= e.params['Tone'] <= 1 for e in plan.entries)


def test_rejects_unusable_fine_grid_without_enumerating_it():
    with pytest.raises(ValueError, match='too fine'):
        make_plan((KnobSpec('Drive', 0, 10, step=1e-12),), 4, 3)


def test_one_knob_more_coverage_never_reduces_training_settings():
    source = (KnobSpec('Drive', 0, 10, avoid_zero=True, is_gain=True),)
    counts = []
    for level in range(5):
        knobs, train, tests = quality_settings(source, level)
        counts.append(len(make_plan(knobs, train, tests).entries_for_split('train')))
    assert counts == sorted(counts)
