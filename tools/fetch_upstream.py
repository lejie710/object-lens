"""Record the licensed original tutorial as a read-only comparison snapshot."""
import argparse
import hashlib
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
destination = ROOT / "baseline" / "upstream"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--verify-only", action="store_true")
verify_only = parser.parse_args().verify_only
lock = ROOT / "baseline" / "source.json"
if lock.exists():
    manifest = json.loads(lock.read_text(encoding="utf-8"))
    revision = manifest["revision"]
elif verify_only:
    raise SystemExit("The upstream source snapshot has not been prepared.")
else:
    request = urllib.request.Request(
        "https://api.github.com/repos/huggingface/transformers.js-examples/commits/main",
        headers={"User-Agent": "Object-Lens-source-record"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        revision = json.load(response)["sha"]
    manifest = {"repository": "https://github.com/huggingface/transformers.js-examples", "revision": revision, "files": []}
if not re.fullmatch(r"[a-f0-9]{40}", revision):
    raise ValueError("Unexpected upstream revision")
destination.mkdir(parents=True, exist_ok=True)
if not verify_only:
    lock.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
for name in ["index.html", "index.js", "style.css", "README.md", "LICENSE"]:
    record = next((item for item in manifest["files"] if item["path"] == name), None)
    target = destination / name
    if target.exists() and record:
        if hashlib.sha256(target.read_bytes()).hexdigest() != record["sha256"]:
            raise SystemExit(f"Original snapshot changed: {name}. Preserve and review it before proceeding.")
        print(f"Verified original {name}", flush=True)
        continue
    if verify_only:
        raise SystemExit(f"Missing original source: {name}")
    location = name if name == "LICENSE" else "vanilla-js/" + name
    url = f"https://raw.githubusercontent.com/huggingface/transformers.js-examples/{revision}/{location}"
    with urllib.request.urlopen(url, timeout=60) as response:
        content = response.read()
    checksum = hashlib.sha256(content).hexdigest()
    if record and checksum != record["sha256"]:
        raise SystemExit(f"Upstream checksum changed for {name}")
    target.write_bytes(content)
    if not record:
        manifest["files"].append({"path": name, "url": url, "sha256": checksum})
    lock.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Saved upstream {name}: {len(content)} bytes", flush=True)
