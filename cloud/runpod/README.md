# Bassman transient fine-tuning on Runpod

Use a persistent `/workspace` volume and a CUDA PyTorch template with Python
3.11–3.13. Upload/unzip `Bassman-Runpod-v3.zip` and enter `Bassman-Runpod-v3`.
The package includes the original Standard raw NAM, original recordings, fresh
teacher attack recordings, and a frozen trainer. It does not include a repaired
playable model: fine-tuning and qualification must finish first.

```sh
bash setup.sh
.venv/bin/python train.py benchmark --batch 4 --epochs 3
# Read the printed run folder and its timing.json for an estimate on your GPU.
.venv/bin/python train.py resume project/outputs/RUN_FOLDER --epochs 20
.venv/bin/python train.py collect project/outputs/RUN_FOLDER
```

`benchmark` really trains the model and saves checkpoints, so resume that run.
Twenty epochs is an initial fine-tuning target, not a promised quality threshold.
If collection fails, inspect `playback/qualification.json`, retain the checkpoint,
and train longer or revise the examples. Do not load a raw checkpoint NAM on the
pedal. There is no qualification bypass. Only a passing run creates
`playback/model_playback.nam` and its download ZIP. Listening and pedal deadline
checks are still needed on the final model.

The default is **A2 Standard**, matching the provided raw model. Batch 4 is a
starting point; reduce to 1–2 if GPU memory is insufficient. `--warm-start` can
select another matching raw NAM. `project/fine_tune.json` selects the included
model automatically. No cloud credentials are embedded; this package does not
create or pay for a pod. Stop the pod after downloading outputs/checkpoints.

The capture/playback mapping is recorded in `input_reference.json`: digital
capture gain −12 dB and playback gain 0 dB, giving a fixed 12 dB playback pad. WAV
hashes bind that mapping to the actual inputs. This preserves the original amp
drive; no continuous gain adjustment is performed. The extra 6 dB workaround is
not baked into this package.

There are 120 original training settings and 24 held-out settings. Each receives
an additional attack stream. A third waveform is rendered at all 144 settings
solely for final qualification. It is not used for gradient updates or checkpoint
selection. Original recordings remain as tone anchors. The original raw NAM
already saw the ordinary validation settings during evaluation; the new attack
waveform itself is reserved from the fine-tuning process.

Qualification checks ordinary held-out tone, bounded output across the control
grid, and teacher fidelity/recovery for all 144 reserved attack streams. The
previous calibrated model fails the new attack checks. A limiter bounding its
bad response no longer makes it eligible for export.

Before paying for compute, local preflight is possible (CPU is explicit):

```sh
python3 train.py verify
.venv/bin/python train.py benchmark --device cpu --check --batch 1
```

CUDA is the default and never silently falls back to CPU. Training uses FP32,
no compilation and no mixed precision. `installed-requirements.txt` records
installed packages; `PROVENANCE.json` and `SHA256.json` identify the frozen code,
data, and starting NAM. Resume accepts checkpoints from this exact package only.
Only resume checkpoints you trust.

To build a package from source:

```sh
python3 cloud/runpod/build_package.py --trainer . --upstream .upstream \
  --dataset /path/to/augmented/project --output /path/to/Bassman-Runpod-v3.zip
```

The native teacher renderer is needed only when preparing fresh attack responses,
not on Runpod. See the desktop README for the source manifest format and capture
reference commands.
