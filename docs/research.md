# How parametric NAM works

Research date: 9 October 2026. The implementation is pinned to trainer revision `a3684411076be69dab53505df14922487697f2cf`; later changes need rechecking.

## What the linked demonstration establishes

ParametricOD demonstrates a neural pedal model whose behavior depends on physical controls. Its author describes two knobs and two switches, experimental design to reduce recording time, and a specialized architecture with custom playback code. The post does not publish the exact capture design or training recipe. We therefore cannot claim to reproduce it exactly. [Original article](https://www.neuralampmodeler.com/post/the-first-publicly-available-parametric-neural-amp-model).

## The learning problem

Our working formulation is `y[t] = f(audio history, control settings)`. For every recorded setting, the trainer needs the dry excitation, wet return, settings, sample rate and timing. The model receives the setting alongside the audio; at playback, changing that setting changes the learned response. This is a conditioned network, rather than crossfading a bank of fixed models.

Record each example with stationary knobs. Changing a knob halfway through a take would require time-varying labels that this capture workflow does not create. Physical knob position is the label, even for logarithmic potentiometers; do not substitute an estimated electrical resistance. Validate the interpolated behavior empirically.

Conditioned audio networks and ensemble-based capture selection are described in the PANAMA research. The paper reports a successful 75-setting experiment, not a universal minimum for every pedal. Its approach uses an ensemble to find settings with disagreement, followed by another round of recordings. [PANAMA paper](https://arxiv.org/html/2509.26564v1).

## The practical public foundation

The public community fork supplies a Qt capture app, dataset format, ConcatWaveNet and HyperWaveNet trainers, and exports for a corresponding player. Its capture plan combines Latin hypercube sampling with boundary settings. Active learning is experimental. This project adds Mac installation, checks and training controls to that foundation. This is a community fork, not an official ParametricOD training kit. [Trainer repository](https://github.com/phillipmself/neural-amp-modeler-parametric).

ConcatWaveNet encodes controls, repeats them over time and concatenates them with audio. These control channels also reach the convolutional conditioning paths. The model config preserves control names, ranges and defaults. We use this architecture first. [Inspected implementation](https://github.com/phillipmself/neural-amp-modeler-parametric/blob/a3684411076be69dab53505df14922487697f2cf/nam/models/parametric/_concat_wavenet.py).

The pinned capture recipe already uses A2's 23-layer kernel/dilation pattern with LeakyReLU and a 16-sample head. Its automatic width grows with control count. The companion offers fixed-width A2 Standard (8 channels) and A2 Nano (3 channels), preserving concat conditioning and learning settings. Individual models remain ConcatWaveNet 1.0.0 exports. Combined mode trains both independently and packages them in an Ardor-compatible SlimmableContainer 1.0.0, with common controls and separate weights/loudness. This is a container extension, rather than shared-weight slimmable training. Ardor's compatibility tests compare the actual exports and both container children with Python inference. [Pinned capture recipe](https://github.com/phillipmself/neural-amp-modeler-parametric/blob/a3684411076be69dab53505df14922487697f2cf/nam/capture/export.py), [NAM's A2 configuration](https://github.com/sdatkinson/neural-amp-modeler/blob/main/nam/train/_resources/config_model_packed.json).

HyperWaveNet generates audio-network weights from the controls. Its runtime and training tradeoffs differ. The fork documents audible artifacts when moving its controls; it is outside this companion's initial training path. [Trainer architecture notes](https://github.com/phillipmself/neural-amp-modeler-parametric#which-architecture).

## FiLM A2 extension

The companion also trains FiLM A2 using a local PyTorch implementation and the same pinned upstream dataset, optimizer, losses, checkpoints and training workflow. Its export contract is pinned to Gene Ko's core revision `419bb5712e651fb7fb548f8aa54431207727aa59`: `ParametricWaveNet` 0.7.0, FiLM schema 1, `head_mode: skip`. Audio enters a mono rechannel and per-layer audio mixin; controls produce separate per-layer scale and shift before LeakyReLU. The head reads the sum of the 23 layers' activations. Playback includes a first-order 20 Hz DC blocker, which the differentiable Python training model includes as well. [Public FiLM contract and weight layout](https://github.com/mrgeneko/NeuralAmpModelerCore/blob/419bb5712e651fb7fb548f8aa54431207727aa59/NAM/wavenet/parametric_wavenet.h).

Training normalizes continuous ranges to [0,1] for optimization, then folds that affine transformation into the exported FiLM matrices so the runtime consumes raw physical values. The supported training profiles use 8-channel Standard and 3-channel Nano, with at most 16 continuous controls. Switch projects keep using concat. This adds a trainable network; it does not convert existing concat weights, modify the upstream checkout, or reproduce Gene Ko's undisclosed training recipe.

Combined FiLM mode trains both sizes independently and emits a 0.7.0 container. Copies of the child output heads are normalized to −18 dB to match each standalone model's normalized playback under the FiLM container's parent-level gain convention. Original per-tier files retain their calibration. The actual trained exports are checked against Ardor's C++ runtime; same-format playback in Gene Ko's player and MPS training still need separate qualification.

## Capture design we recommend

For a first drive pedal, choose Drive and Tone, keeping the pedal's output Level and switches fixed. Begin with the planner's suggested interior points and include boundaries. Make repeatable settings: a half-unit step is often more realistic than two decimal places. Reduce the modeled range if a knob's zero position mutes the pedal; don't teach a near-silent region inadvertently.

Keep validation settings disjoint from training settings. Prefer a different validation DI signal too. This tests both interpolation and response to unseen audio. Listening at several unseen combinations is essential: a low average error can hide a poor corner. Increase capture density where a real pedal and the model disagree. These are our practical recommendations, not the original article's undisclosed experimental design.

The inherited planner exposes continuous knobs only, although the lower-level parametric representation has switch encoding. The companion extends its schema, planner and UI for named switches: each switch combination receives continuous-control captures and unseen validation settings, and exported configs preserve one-hot switch definitions. Keep unmodeled switches fixed. [Knob capture implementation](https://github.com/phillipmself/neural-amp-modeler-parametric/blob/a3684411076be69dab53505df14922487697f2cf/nam/capture/params.py), [companion control implementation](../parametric_mac/controls.py).

## Mac training

PyTorch's MPS backend provides GPU execution on supported Macs. Availability must be checked at runtime. MPS support alone does not establish that a particular model trains correctly or faster than CPU. We run float32, disable `torch.compile`, use one device and zero DataLoader workers, and start with batch size four. CPU is a visible fallback choice; unsupported GPU operations are not silently hidden. [PyTorch MPS documentation](https://docs.pytorch.org/docs/stable/notes/mps.html).

The companion preserves the trainer's model and losses while overriding execution settings. It rebuilds configs from the latest saved capture project and saves resolved paths in a new run directory. Full validation windows are inherited from the capture project; if validation runs out of memory, reduce its window size in the upstream project/config and record that change when comparing metrics. Batch size one is another useful memory reduction. MPS performance, memory use and training duration must be measured on the user's Mac.

The native capture dependency is installed from its pinned source checkout in editable mode: its inspected packaging list does not include `nam.capture`, so depending solely on the built wheel is insufficient. The upstream import chain also requires Tk even though capture uses Qt. Use python.org Python with Tk, or install the matching Tk package for a Homebrew Python.

## Evaluate and play

ESR is error energy divided by target energy: `sum((prediction-target)^2) / sum(target^2)`, subject to the trainer's masking and aggregation. Smaller is better; quiet targets can make the denominator problematic. Read capture-level and worst-case validation results, not only the average. There is no universal ESR cutoff that guarantees a good pedal model.

After training, compare loudness-matched hardware and rendered model on unseen DI, at unseen settings. Test silence, transients, sustained notes, high input levels and knob movement. Preserve input calibration so the model's clipping threshold corresponds to your intended guitar level. Stationary-knob training does not by itself prove artifact-free parameter automation.

`model_parametric.nam` requires the corresponding parametric player; the stock NAM plugin is not a compatible host for this architecture. The public player supports macOS standalone and plugin builds. Its README lists dynamic model controls as UI-only rather than DAW-automatable parameters in v1. Download/build compatibility must be checked before relying on automation. [Player repository](https://github.com/phillipmself/NamParametricPlugin).

## First-version boundaries

This tool orchestrates the real fork; it does not include a new DSP runtime, robot knob-turning hardware, cloud trainer, or signed `.app` installer. Capture/playback level calibration and MPS execution still require real hardware verification. Delay, reverb, modulation and pickup-sensitive fuzz need a separately designed capture protocol before we promise a useful model. Continue with a conventional drive pedal first.
