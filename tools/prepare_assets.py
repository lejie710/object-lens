"""Prepare pinned browser runtime/model files; later runs verify the saved checksums.

Sources are the jsDelivr npm mirror and the Hugging Face model repository.
This downloads data and JavaScript; it does not run the downloaded application.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "asset-lock.json"


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def metadata(url):
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.load(response)


def initial_manifest():
    model = metadata("https://huggingface.co/api/models/Xenova/detr-resnet-50")
    revision = model["sha"]
    if not re.fullmatch(r"[a-f0-9]{40,64}", revision):
        raise ValueError("Unexpected model revision")
    urls = {
        "assets/runtime/transformers.min.js": "https://cdn.jsdelivr.net/npm/@xenova/transformers@2.17.2/dist/transformers.min.js",
        "assets/runtime/ort-wasm-simd.wasm": "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.14.0/dist/ort-wasm-simd.wasm",
        "assets/runtime/ort-wasm.wasm": "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.14.0/dist/ort-wasm.wasm",
    }
    for filename in ["config.json", "preprocessor_config.json", "onnx/model_quantized.onnx"]:
        urls[f"assets/models/Xenova/detr-resnet-50/{filename}"] = (
            f"https://huggingface.co/Xenova/detr-resnet-50/resolve/{revision}/{filename}"
        )
    return {
        "transformers_js": "2.17.2",
        "onnxruntime_web": "1.14.0",
        "model": "Xenova/detr-resnet-50",
        "model_revision": revision,
        "files": [{"path": path, "url": url} for path, url in urls.items()],
    }


def prepare(verify_only=False):
    if LOCK.exists():
        manifest = json.loads(LOCK.read_text(encoding="utf-8"))
    elif verify_only:
        raise SystemExit("No asset-lock.json exists. Run the initial asset setup first.")
    else:
        manifest = initial_manifest()
        LOCK.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    for item in manifest["files"]:
        target = (ROOT / "dist" / item["path"]).resolve()
        if not target.is_relative_to((ROOT / "dist").resolve()):
            raise ValueError("Asset path outside the application directory")
        expected = item.get("sha256")
        if target.exists() and expected and digest(target) == expected:
            print(f"Verified {item['path']}", flush=True)
            continue
        if verify_only:
            raise SystemExit(f"Missing or changed asset: {item['path']}")
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".part")
        print(f"Downloading {item['path']}", flush=True)
        with urllib.request.urlopen(item["url"], timeout=120) as response, temporary.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        actual = digest(temporary)
        if expected and actual != expected:
            raise ValueError(f"Checksum mismatch for {item['path']}; file not activated")
        temporary.replace(target)
        item["sha256"] = actual
        item["bytes"] = target.stat().st_size
        LOCK.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(f"Saved {item['bytes']:,} bytes; SHA256 {actual}", flush=True)
    print("All browser and model assets verified.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    prepare(parser.parse_args().verify_only)
