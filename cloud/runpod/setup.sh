#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
python3 -c 'import sys; assert (3,11) <= sys.version_info[:2] < (3,14), "Use Python 3.11–3.13"'
python3 train.py verify
# Reuse the template's CUDA-enabled torch; keep other dependencies in /workspace.
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python train.py doctor
.venv/bin/python -m pip freeze > installed-requirements.txt
echo 'Setup complete. Next: .venv/bin/python train.py benchmark --batch 1'
