#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
if [[ "$(uname -s)" != Darwin || "$(uname -m)" != arm64 ]]; then
  echo "Run this installer on Apple Silicon macOS in a native Terminal (Rosetta disabled)."
  exit 1
fi
command -v git >/dev/null || { echo "Install Xcode Command Line Tools: xcode-select --install"; exit 1; }

check_python() {
  "$1" - <<'PY'
import platform
import sys

if not ((3, 11) <= sys.version_info[:2] < (3, 14) and platform.machine() == "arm64"):
    sys.exit("The trainer needs native arm64 Python 3.11–3.13; Python 3.15 has no compatible PyTorch wheel.")
try:
    import tkinter
except ImportError:
    sys.exit("This Python is missing Tk. Use the default uv-managed Python or a Python.org installation.")
print(f"Trainer Python: {sys.version.split()[0]} ({platform.machine()}); Tk available")
PY
}

# Preserve existing environments, including broken symlinks and unsupported Python.
if [[ -e .venv || -L .venv ]]; then
  if [[ ! -x .venv/bin/python ]] || ! check_python .venv/bin/python; then
    echo "Existing .venv is incompatible or missing Tk; it has not been changed."
    echo "Rename .venv to keep a backup, then rerun Install.command."
    exit 1
  fi
elif [[ -n "${PARAMETRIC_PYTHON:-}" ]]; then
  if ! command -v "$PARAMETRIC_PYTHON" >/dev/null || ! check_python "$PARAMETRIC_PYTHON"; then
    echo "PARAMETRIC_PYTHON must point to native Python 3.11–3.13 with Tk."
    echo "Unset PARAMETRIC_PYTHON to let uv download the project's Python automatically."
    exit 1
  fi
fi

# Finder-launched Terminal sessions may not include user/Homebrew bins in PATH.
parametric_uv="$(command -v uv || true)"
if [[ -z "$parametric_uv" ]]; then
  for parametric_candidate in "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv" /opt/homebrew/bin/uv /usr/local/bin/uv; do
    if [[ -x "$parametric_candidate" ]]; then
      parametric_uv="$parametric_candidate"
      break
    fi
  done
fi
if [[ -z "$parametric_uv" ]]; then
  echo "Installing uv from astral.sh into $HOME/.local/bin…"
  parametric_uv_installer="$(mktemp -t parametric-uv)"
  trap 'rm -f -- "$parametric_uv_installer"' EXIT
  curl --proto '=https' --tlsv1.2 -LsSf https://astral.sh/uv/install.sh -o "$parametric_uv_installer"
  UV_INSTALL_DIR="$HOME/.local/bin" UV_NO_MODIFY_PATH=1 sh "$parametric_uv_installer"
  parametric_uv="$HOME/.local/bin/uv"
fi

if [[ ! -e .venv ]]; then
  if [[ -n "${PARAMETRIC_PYTHON:-}" ]]; then
    "$parametric_uv" venv --python "$PARAMETRIC_PYTHON" .venv
  else
    # Use a bundled-Tk managed runtime, independent of the system's python3.
    "$parametric_uv" venv --managed-python --python "$(cat .python-version)" .venv
  fi
  check_python .venv/bin/python
fi

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
"$parametric_uv" pip install --python .venv/bin/python -e '.upstream[capture-app]' -e .
.venv/bin/python -m parametric_mac inputs inputs
.venv/bin/python -m parametric_mac doctor
printf '\nInstalled. Open Capture.command to begin.\n'
