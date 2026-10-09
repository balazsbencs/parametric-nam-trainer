"""Download upstream excitation signals with release-published SHA-256 checksums."""
import hashlib
import os
from pathlib import Path
import tempfile
from urllib.request import urlopen

RELEASE = "https://github.com/phillipmself/neural-amp-modeler-parametric/releases/download/training-inputs-v1/"
FILES = {
    "inputTrunc.wav": "1e0959e8ffe2f26585994dd87e06e5109d237cee65321ad8450908f0c156491e",
    "validation.wav": "24c00c6351caa09df3e45c3d6b67cc2275994ef93c74ba7002019ac94c01adf4",
}


def download_inputs(directory):
    directory = Path(directory).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    for name, digest in FILES.items():
        target = directory / name
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise ValueError(f"{target} already exists with different contents. Choose another folder.")
            print(f"Verified: {target}")
            continue
        fd, temporary = tempfile.mkstemp(dir=directory, suffix=".download")
        try:
            checksum = hashlib.sha256()
            with os.fdopen(fd, "wb") as dest, urlopen(RELEASE + name, timeout=60) as source:
                while chunk := source.read(65536):
                    dest.write(chunk)
                    checksum.update(chunk)
            if checksum.hexdigest() != digest:
                raise ValueError(f"Checksum mismatch for {name}; download rejected.")
            # Don't overwrite a file that appeared during download.
            os.link(temporary, target)
            print(f"Downloaded and verified: {target}")
        finally:
            Path(temporary).unlink(missing_ok=True)
    return directory
