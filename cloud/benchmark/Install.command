#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
if [[ "$(uname -s)" != Darwin || "$(uname -m)" != arm64 ]]; then
  echo "Use this installer on Apple Silicon macOS in a native Terminal (Rosetta disabled)."
  exit 1
fi
benchmark_uv="$(command -v uv || true)"
if [[ -z "$benchmark_uv" ]]; then
  for benchmark_candidate in "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv" /opt/homebrew/bin/uv /usr/local/bin/uv; do
    if [[ -x "$benchmark_candidate" ]]; then benchmark_uv="$benchmark_candidate"; break; fi
  done
fi
if [[ -z "$benchmark_uv" ]]; then
  benchmark_installer="$(mktemp -t nam-benchmark-uv)"
  trap 'rm -f -- "$benchmark_installer"' EXIT
  curl --proto '=https' --tlsv1.2 -LsSf https://astral.sh/uv/install.sh -o "$benchmark_installer"
  UV_INSTALL_DIR="$HOME/.local/bin" UV_NO_MODIFY_PATH=1 sh "$benchmark_installer"
  benchmark_uv="$HOME/.local/bin/uv"
fi
if [[ -e .venv || -L .venv ]]; then
  .venv/bin/python -c 'import platform,sys; assert platform.machine()=="arm64" and (3,11)<=sys.version_info[:2]<(3,14), "Existing environment is incompatible; rename it before reinstalling."'
else
  "$benchmark_uv" venv --managed-python --python 3.12 .venv
fi
.venv/bin/python benchmark.py verify
"$benchmark_uv" pip install --python .venv/bin/python 'torch>=2.6,<3' -r requirements.txt
.venv/bin/python benchmark.py doctor
"$benchmark_uv" pip freeze --python .venv/bin/python > installed-requirements.txt
echo 'Installed. Double-click Benchmark Both.command, or use Benchmark Standard.command / Benchmark Nano.command.'
