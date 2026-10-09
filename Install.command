#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
if [[ "$(uname -s)" != Darwin || "$(uname -m)" != arm64 ]]; then
  echo "Run this installer on Apple Silicon macOS in a native Terminal (Rosetta disabled)."
  exit 1
fi
parametric_python="${PARAMETRIC_PYTHON:-python3}"
if ! command -v "$parametric_python" >/dev/null; then
  echo "Install native Python 3.12 from python.org, then run this again."
  exit 1
fi
"$parametric_python" -c 'import sys, platform; assert (3,11) <= sys.version_info[:2] < (3,14) and platform.machine() == "arm64", "Use native arm64 Python 3.11–3.13 (3.12 recommended). Set PARAMETRIC_PYTHON to its path if needed."; import tkinter'
command -v git >/dev/null || { echo "Install Xcode Command Line Tools: xcode-select --install"; exit 1; }
if [[ ! -d .venv ]]; then "$parametric_python" -m venv .venv; fi
.venv/bin/python -c 'import platform; assert platform.machine() == "arm64", "Existing .venv is not arm64; rename it and rerun the installer."'
.venv/bin/python -m pip install --upgrade pip
parametric_revision=a3684411076be69dab53505df14922487697f2cf
if [[ ! -d .upstream ]]; then
  git clone https://github.com/phillipmself/neural-amp-modeler-parametric.git .upstream
  git -C .upstream checkout --detach "$parametric_revision"
fi
if [[ "$(git -C .upstream rev-parse HEAD)" != "$parametric_revision" ]]; then
  echo "Existing .upstream is a different revision. Rename it and rerun; it has not been changed."
  exit 1
fi
if [[ -n "$(git -C .upstream status --porcelain)" ]]; then
  echo "Existing .upstream has local edits. Rename it and rerun; your edits have not been changed."
  exit 1
fi
# Editable is intentional: upstream's explicit wheel package list omits nam.capture.
.venv/bin/python -m pip install -e '.upstream[capture-app]' -e .
.venv/bin/python -m parametric_mac inputs inputs
.venv/bin/python -m parametric_mac doctor
printf '\nInstalled. Open Capture.command to begin.\n'
