#!/usr/bin/env python3
"""Bundle local trainer sources and the portable Mac capture archive for Runpod."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
from zipfile import ZipFile, ZIP_DEFLATED


def git(directory, *args):
    return subprocess.check_output(["git", "-C", str(directory), *args], text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trainer", required=True, type=Path)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument('--upstream', type=Path, help='Pinned upstream checkout if the trainer is a linked worktree')
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    trainer = args.trainer.resolve()
    upstream = (args.upstream or trainer / ".upstream").resolve()
    script_dir = Path(__file__).resolve().parent
    checksums = {}
    # The executable snapshot is frozen in the archive, including local companion fixes.
    provenance = {
        "companion_commit": git(trainer, "rev-parse", "HEAD"),
        "companion_local_changes": git(trainer, "status", "--short"),
        "upstream_commit": git(upstream, "rev-parse", "HEAD"),
        "upstream_local_changes": git(upstream, "status", "--short"),
        "headless_adjustment": "Defer tkinter import in nam/train/core.py until _nasty_checks_modal is called.",
        "playback_policy_version": 3,
        "dataset_archive_sha256": None if args.dataset.is_dir() else hashlib.file_digest(args.dataset.open("rb"), "sha256").hexdigest(),
    }
    if provenance["upstream_local_changes"]:
        raise SystemExit("Upstream must be clean for a reproducible training snapshot.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(args.output, "x", ZIP_DEFLATED, compresslevel=1) as archive:
        def write(name, data):
            checksums[name] = hashlib.sha256(data).hexdigest()
            archive.writestr("Bassman-Runpod-v4/" + name, data)

        for name in ("train.py", "playback.py", "setup.sh", "requirements.txt", "README.md"):
            write(name, (script_dir / name).read_bytes())
        for source, target in ((trainer / "parametric_mac", "vendor/parametric_mac"),
                               (upstream / "nam", "vendor/nam")):
            for path in sorted(source.rglob("*")):
                if (path.is_file() and "__pycache__" not in path.parts
                        and (path.suffix in (".py", ".json", ".wav")
                             or path.name.upper() in ("LICENSE", "NOTICE", "COPYING"))):
                    content = path.read_bytes()
                    if target == "vendor/nam" and path.relative_to(source).as_posix() == "train/core.py":
                        text = content.decode()
                        assert text.count("import tkinter as _tk\n") == 1
                        assert text.count("def _nasty_checks_modal():\n") == 1
                        text = text.replace("import tkinter as _tk\n", "")
                        text = text.replace("def _nasty_checks_modal():\n",
                                            "def _nasty_checks_modal():\n    import tkinter as _tk\n")
                        content = text.encode()
                    write(str(PurePosixPath(target) / path.relative_to(source)), content)
        write("vendor/NAM-LICENSE", (upstream / "LICENSE").read_bytes())
        if args.dataset.is_dir():
            for path in sorted(args.dataset.rglob('*')):
                if path.is_file() and path.suffix != '.f32' and not {'outputs', 'performance'} & set(path.relative_to(args.dataset).parts):
                    write('project/' + path.relative_to(args.dataset).as_posix(), path.read_bytes())
        else:
            with ZipFile(args.dataset) as dataset:
                for info in dataset.infolist():
                    path = PurePosixPath(info.filename)
                    if path.is_absolute() or ".." in path.parts:
                        raise ValueError("Unsafe dataset archive member")
                    relative = PurePosixPath(*path.parts[1:])
                    if info.is_dir() or not relative.parts:
                        continue
                    write("project/" + str(relative), dataset.read(info))
        write("PROVENANCE.json", (json.dumps(provenance, indent=2) + "\n").encode())
        archive.writestr("Bassman-Runpod-v4/SHA256.json", json.dumps(checksums, indent=2) + "\n")
    with args.output.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    args.output.with_suffix(".zip.sha256").write_text(f"{digest}  {args.output.name}\n")
    print(f"Created {args.output} ({args.output.stat().st_size:,} bytes), SHA256 {digest}")


if __name__ == "__main__":
    main()
