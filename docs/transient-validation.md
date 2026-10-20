# Bassman attack regression, 20 October 2026

The original raw Standard model SHA256 is
`c0028731afa974afd8ec3df58cb98b8fc33280a9a85f4483f29ae0bb9e0bafbc`.
It fits ordinary notes but extrapolates badly on short broadband attacks.
Previously, a 64-sample attack at playback peak 0.95 caused 3871 clipped samples
(80.65 ms); the corresponding original teacher peak was 0.377942. The baked
playback pad was already 12 dB. Bounding the output did not correct its shape.

For this change, all 144 original teacher settings were rendered into fresh WAVs:
120 training streams, 24 epoch-validation streams and 144 separate final-check
streams. The project retains the original recordings. Input mapping is recorded
from the actual preparation gain, rather than guessed from peaks. The included
starting model is the raw Standard model, not its calibrated playback version.

The new reserved-stream check rejects the old calibrated model at Gain 5 in all
eight Modes. ESR spans 8.92–11.71 and excess ceiling plateaus span 1423–3303 samples.
Each capture is scored against its own teacher response, including the recovery
tail. These are offline synthetic attack tests; they do not prove a match to a
particular guitar's pickup or to the physical amp.

A four-batch CPU fine-tuning integration check on the actual Standard model
completed training and re-export in about ten seconds. This checks code integration
only. It does not establish that the model is repaired. That short model is not
included in the training package. Full GPU fine-tuning, qualification, listening,
and target pedal deadline checks remain necessary before a new playback model
can be recommended.

The desktop was inspected at 1140×840 and 800×800 with the real project. The Train
page displays the recorded 12 dB mapping, prevents conflicting manual changes,
and shows the raw fine-tuning source. The input-reference dialog supports known
digital gains or measured analog full-scale references.

Run the package's benchmark, resume its checkpoint, and collect only if the current
qualification passes. A legacy version-2 report cannot enable desktop Save.
