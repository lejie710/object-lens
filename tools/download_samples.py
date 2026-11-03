"""Fetch the five public scikit-image samples, checking pinned upstream hashes.

No scikit-image installation is needed. Run with --verify to check existing
files without contacting the network. Attribution is in docs/IMAGE_SOURCES.md.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "dist" / "samples"
SOURCE = "https://raw.githubusercontent.com/scikit-image/scikit-image/v0.25.2/skimage/data/"

# Hashes copied from scikit-image v0.25.2's data/_registry.py, not calculated
# from an untrusted first download.
SAMPLES = {
    "astronaut.png": "88431cd9653ccd539741b555fb0a46b61558b301d4110412b5bc28b5e3ea6cb5",
    "coffee.png": "cc02f8ca188b167c775a7101b5d767d1e71792cf762c33d6fa15a4599b5a8de7",
    "chelsea.png": "596aa1e7cb875eb79f437e310381d26b338a81c2da23439704a73c4651e8c4bb",
    "camera.png": "b0793d2adda0fa6ae899c03989482bff9a42d3d5690fc7e3648f2795d730c23a",
    "rocket.jpg": "c2dd0de7c538df8d111e479619b129464d0269d0ae5fd18ca91d33a7fdfea95c",
}


def verify(path: Path, expected: str) -> int:
    contents = path.read_bytes()
    actual = hashlib.sha256(contents).hexdigest()
    if actual != expected:
        raise ValueError(f"Hash mismatch for {path.name}: {actual}")
    return len(contents)


def prepare(verify_only: bool) -> None:
    if not verify_only:
        DESTINATION.mkdir(parents=True, exist_ok=True)
    total = 0
    for name, expected in SAMPLES.items():
        path = DESTINATION / name
        if not path.exists():
            if verify_only:
                raise FileNotFoundError(f"Missing sample: {path}")
            request = Request(SOURCE + name, headers={"User-Agent": "Object-Lens-sample-setup"})
            with urlopen(request, timeout=45) as response:
                contents = response.read(5 * 1024 * 1024 + 1)
            if hashlib.sha256(contents).hexdigest() != expected:
                raise ValueError(f"Downloaded sample failed its upstream hash: {name}")
            path.write_bytes(contents)
        size = verify(path, expected)
        total += size
        print(f"Verified {name}: {size:,} bytes; SHA-256 {expected}", flush=True)
    print(f"Verified {len(SAMPLES)} images, {total:,} bytes total.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="Check local hashes without downloading")
    prepare(parser.parse_args().verify)
