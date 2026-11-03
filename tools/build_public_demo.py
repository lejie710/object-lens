"""Build an allowlisted, checksum-verified static website and upload ZIP.

This command uses prepared local assets. It does not download, publish, or
change repository visibility. Build records stay outside the public website.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
APP_FILES = (
    "index.html", "style.css", "app.js", "worker.js", "png-export.js",
    "credits.html", "runtime-config.json",
)
ASSET_FILES = frozenset({
    "assets/runtime/transformers.min.js",
    "assets/runtime/ort-wasm-simd.wasm",
    "assets/runtime/ort-wasm.wasm",
    "assets/models/Xenova/detr-resnet-50/config.json",
    "assets/models/Xenova/detr-resnet-50/preprocessor_config.json",
    "assets/models/Xenova/detr-resnet-50/onnx/model_quantized.onnx",
})
COFFEE = {
    "path": "samples/coffee.png", "bytes": 466706,
    "sha256": "cc02f8ca188b167c775a7101b5d767d1e71792cf762c33d6fa15a4599b5a8de7",
}


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def source_file(dist: Path, name: str) -> Path:
    """Accept portable relative file names, never a path escaping the app."""
    relative = PurePosixPath(name)
    if (not name or "\\" in name or ":" in name or relative.is_absolute()
            or ".." in relative.parts or relative.as_posix() != name):
        raise ValueError(f"Unsafe public file path: {name!r}")
    path = (dist / name).resolve()
    if not path.is_relative_to(dist) or not path.is_file():
        raise ValueError(f"Missing or unsafe public file: {name}")
    return path


def checked_record(dist: Path, name: str, expected: dict | None = None) -> dict:
    path = source_file(dist, name)
    record = {"path": name, "bytes": path.stat().st_size, "sha256": sha256(path)}
    if expected is not None:
        if record["bytes"] != expected.get("bytes") or record["sha256"] != expected.get("sha256"):
            raise ValueError(f"Checksum or size mismatch: {name}")
    if record["bytes"] > 100_000_000:
        raise ValueError(f"Public file exceeds the selected 100 MB upload bound: {name}")
    return record


def git_provenance(project_root: Path) -> tuple[str | None, bool | None]:
    if not (project_root / ".git").exists():
        return None, None
    top = subprocess.check_output(
        ["git", "-C", str(project_root), "rev-parse", "--show-toplevel"], text=True
    ).strip()
    if Path(top).resolve() != project_root:
        return None, None
    commit = subprocess.check_output(
        ["git", "-C", str(project_root), "rev-parse", "HEAD"], text=True
    ).strip()
    changed = subprocess.check_output(
        ["git", "-C", str(project_root), "status", "--porcelain"], text=True
    ).strip()
    return commit, bool(changed)


def build(output_root: Path, project_root: Path = ROOT) -> dict:
    project_root = Path(project_root).resolve()
    dist = (project_root / "dist").resolve()
    output_root = Path(output_root).resolve()
    if output_root == project_root or output_root.is_relative_to(dist):
        raise ValueError("Build output must be separate from the application source directory.")

    config = json.loads(source_file(dist, "runtime-config.json").read_text(encoding="utf-8"))
    if not isinstance(config, dict) or set(config) != {"testMode"} or config["testMode"] is not False:
        raise ValueError("The public runtime configuration must contain only testMode: false.")
    records = [checked_record(dist, name) for name in APP_FILES]
    asset_lock = json.loads((project_root / "asset-lock.json").read_text(encoding="utf-8"))
    assets = asset_lock["files"]
    if len(assets) != len(ASSET_FILES) or {item["path"] for item in assets} != ASSET_FILES:
        raise ValueError("Asset lock must describe the six approved runtime/model files.")
    records.extend(checked_record(dist, item["path"], item) for item in assets)
    records.append(checked_record(dist, COFFEE["path"], COFFEE))

    credit_lock = json.loads((project_root / "credits-lock.json").read_text(encoding="utf-8"))
    licences = credit_lock["files"]
    if not licences:
        raise ValueError("Public distribution requires the recorded licence notices.")
    for item in licences:
        name = item["path"]
        if not name.startswith("licenses/") or PurePosixPath(name).suffix not in {".txt", ".md"}:
            raise ValueError(f"Licence must be a text file under licenses/: {name}")
        records.append(checked_record(dist, name, item))
    records.sort(key=lambda item: item["path"])
    if len({item["path"] for item in records}) != len(records):
        raise ValueError("Duplicate public file in the package specification.")
    content_id = hashlib.sha256(json.dumps(records, sort_keys=True).encode("utf-8")).hexdigest()
    commit, dirty = git_provenance(project_root)

    # Each build gets a new owned directory: no recursive removal or overwriting.
    output_root.mkdir(parents=True, exist_ok=True)
    build_root = Path(tempfile.mkdtemp(prefix=f"object-lens-{content_id[:10]}-", dir=output_root))
    site = build_root / "site"
    site.mkdir()
    for item in records:
        target = site / item["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_file(dist, item["path"]), target)
        if sha256(target) != item["sha256"]:
            raise ValueError(f"Source changed during packaging: {item['path']}")

    archive_path = build_root / "Object_Lens_Public_Demo.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for item in records:
            info = zipfile.ZipInfo(item["path"], date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            with (site / item["path"]).open("rb") as source, archive.open(info, "w") as target:
                shutil.copyfileobj(source, target)
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None or set(archive.namelist()) != {item["path"] for item in records}:
            raise ValueError("The upload archive failed its integrity check.")

    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_commit": commit, "source_dirty": dirty, "content_id": content_id,
        "files": records, "file_count": len(records),
        "uncompressed_bytes": sum(item["bytes"] for item in records),
        "archive_bytes": archive_path.stat().st_size, "archive_sha256": sha256(archive_path),
        "runtime_configuration": config,
        "privacy_boundary": "Only allowlisted browser app files, public sample, model/runtime assets and credits are included. Repository history, tests, documents and environments are excluded.",
        "verification_boundary": "A prepared local package is not evidence of a successful public deployment.",
    }
    manifest_path = build_root / "package-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    return {"site_directory": str(site), "archive": str(archive_path),
            "manifest": str(manifest_path), "content_id": content_id}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "public-demo")
    args = parser.parse_args()
    print(json.dumps(build(args.output), indent=2))
