# Plan with one quality slider

The user wants ordinary pedal owners to choose a useful capture plan quickly, without understanding sampling or training parameters. The Plan mockup stays in the existing desktop utility design and asks for one decision: capture quality. Good is selected by default, with one Start capturing action. Advanced controls remain collapsed.

| Level | Meaning in the proposal | Training positions | Extremes | Sound checks | Total recordings | Both knob increments | Estimated recording effort |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Quick test | Try the setup; expect rough spots | 8 | 4 | 3 | 15 | 2.0 | 11 min |
| Decent | A starting point to explore | 18 | 4 | 4 | 26 | 1.0 | 19 min |
| Good | Recommended starting point | 30 | 4 | 6 | 40 | 0.5 | 29 min |
| Thorough | Extra coverage, more effort | 54 | 4 | 10 | 68 | 0.5 | 50 min |
| Overkill | Diminishing returns | 96 | 4 | 16 | 116 | 0.5 | 85 min |

These are illustrative presets for the two-knob example, not experimentally established quality thresholds. No measured sound score is inferred from recording count. Effort assumes the example 38-second training/7-second test signals and 10 seconds per knob change; training time and retries are additional. A production preset must account for actual knob count, valid physical ranges, reachable positions and available reference audio, then be validated on real hardware. Avoid promising that any preset always sounds good or that additional captures cannot improve a difficult pedal.

The slider updates recording density, sound-check count and increments for every modeled knob together. Physical minimum/maximum positions and fixed pedal controls do not change with quality. At Thorough and Overkill the physical increments remain practical; additional samples increase coverage rather than demanding ever smaller hand adjustments. Manual Advanced edits are labeled Custom settings. Moving the slider restores the complete automatic preset.

Use a native range input with five stops, a visible label, descriptive value text and keyboard support. Preserve the input element during pointer movement. The quality description, counts and estimated effort update immediately. Labels and descriptions explain the scale as well as color.

Once a take is accepted, freeze the plan and its controls. Starting a separate plan lists earlier example take metadata separately and starts the new session at zero. Busy recording/training blocks that transition. This browser prototype stores only in-memory examples; production must preserve immutable plan/calibration identities and real source files before offering equivalent actions.

Verification covers all five levels, both knob increments, fixed physical ranges, preset persistence, custom overrides, pointer dragging, keyboard focus/value text, capture handoff and plan locking. The production Qt planning screen remains unchanged by this mockup refinement.
