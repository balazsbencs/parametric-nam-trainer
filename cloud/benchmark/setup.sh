#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
python3 -c 'import sys; assert (3,11)<=sys.version_info[:2]<(3,14), "Use Python 3.11–3.13"'
python3 benchmark.py verify
# Keep the CUDA-enabled PyTorch supplied by the pod template.
if [[ ! -e .venv ]]; then python3 -m venv --system-site-packages .venv; fi
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python benchmark.py doctor
.venv/bin/python -m pip freeze > installed-requirements.txt
echo 'Installed. Run: .venv/bin/python benchmark.py'
