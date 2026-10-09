# Parametric pedal capture for Mac

A local companion for capturing a pedal at multiple knob settings and training one controllable NAM model. Built around the public [parametric NAM fork](https://github.com/phillipmself/neural-amp-modeler-parametric), pinned to a reviewed revision. Includes a native capture app with a **Train on Mac** tab, preflight checks, and instructions for your **UMC22**.

## Start on Apple Silicon

Move the source ZIP to your Mac and unzip it first. It excludes this development workspace's Linux environment; the installer creates a fresh Mac environment.

Install native Python **3.12** from [python.org](https://www.python.org/downloads/macos/) (includes Tk) and Xcode Command Line Tools (`xcode-select --install`) if Git is unavailable. Use Python 3.11–3.13, with Rosetta disabled.

1. Double-click **Install.command**. It creates an isolated `.venv`, installs the pinned trainer from source, and downloads checksum-verified training signals. Network access is needed; the ML dependencies are a substantial download.
2. Read [the UMC22 pedal wiring guide](docs/hardware-umc22.md) and connect your reamp box and pedal.
3. Double-click **Capture.command**. Create a project, choose the two files in `inputs/`, define continuous knobs and generate a capture plan. Set up Audio I/O and run Route test. Record the prompted positions.
4. In **Train on Mac**, check captures and try one epoch. Then run a longer training job. **Train.command** opens the same app on that tab; open your project in Project first.
5. **Open outputs** reveals separate run folders. Load `model_parametric.nam` in the matching [NamParametricPlugin](https://github.com/phillipmself/NamParametricPlugin), then listen and evaluate unseen settings. The stock NAM plugin cannot play this parametric architecture.

The first workflow supports continuous knobs. Keep switches fixed per project. Start with an overdrive/distortion/EQ pedal; modulation and delay are outside the initial capture protocol.

## Terminal controls

```sh
.venv/bin/parametric doctor
.venv/bin/parametric inputs ./inputs
.venv/bin/parametric capture
.venv/bin/parametric check "/path/to/pedal project"
.venv/bin/parametric train "/path/to/pedal project" --epochs 1 --batch 4
.venv/bin/parametric train "/path/to/pedal project" --device mps --epochs 200 --batch 4
.venv/bin/parametric train "/path/to/pedal project" --device cpu --epochs 200 --batch 1
```

`--dry-run` runs preflight and saves run configs without training. Automatic device selection chooses MPS when available, otherwise CPU. GPU errors stay visible; retry on CPU or lower batch size. The execution profile uses float32, no `torch.compile`, and no worker processes. Training rebuilds configs from the current saved capture project so an old export cannot omit newer captures.

Preflight checks missing/mono/mismatched audio, digital full-scale peaks, silence, non-finite values, control labels, windows, capture QA and overlap between train/validation settings. It does not independently measure converter calibration, prove that timing is correct, or detect every analog clipping/dropout artifact. Use the native route/capture QA and listen too.

Each run saves data/model/learning configs, an environment manifest, trainer outputs and status. Failed runs retain their folders. WAVs and the capture project are not rewritten by training. Stop allows a graceful interrupt and export if possible, with a 15-second forced-stop limit; inspect outputs rather than assuming a stopped run is complete. Resuming checkpoints is not exposed in this version.

## Research and hardware

- [How parametric modeling works, source notes and limitations](docs/research.md)
- [UMC22 wiring, equipment and capture instructions](docs/hardware-umc22.md)
- [Validation performed and Mac hardware checks still needed](docs/validation.md)
- [UI audit and prioritized UX findings](docs/ui-audit/report.md)
- [Full workflow mockup overview](docs/mockups/overview.html) and [clickable prototype](docs/mockups/index.html)

The mockups open locally in a browser and use example data. They demonstrate the proposed Connect → Plan → Capture → Train → Review journey; physical audio and training still run through the native application.
The proposed Plan screen uses one quality slider with **Good** selected by default; detailed knob and sampling controls stay under Advanced. These presets are illustrative capture coverage, not measured sound-quality guarantees.

This is a source-based first version, not a signed standalone Mac installer or a new plugin runtime. The original ParametricOD article does not publish its full recipe. We use the public fork's actual capture and training machinery, with a Mac companion layer.

## Development

On Linux, native GUI imports also need system Tk and PortAudio libraries. For CPU-only validation install a CPU PyTorch wheel before the trainer to avoid unnecessary CUDA dependencies:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
git clone https://github.com/phillipmself/neural-amp-modeler-parametric.git .upstream
git -C .upstream checkout a3684411076be69dab53505df14922487697f2cf
.venv/bin/python -m pip install -e '.upstream[capture-app]' -e . pytest
.venv/bin/python -m pytest
```

Editable installation is deliberate because the fork's inspected wheel package list omits its capture package. The trainer revision is pinned; transitive dependencies are constrained by their packages but not fully locked. Re-run validation before updating dependencies or upstream code. Synthetic tests prove integration, not pedal accuracy.
