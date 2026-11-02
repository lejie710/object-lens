"""Create a local runtime-normalized copy of the original tutorial for comparison.

Original files remain unchanged in baseline/upstream. The browser library,
model source and WASM settings are normalized to Object Lens to isolate UI
behavior. This is not a claim about the stock upstream runtime or release.
"""
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / "baseline" / "upstream"
destination = ROOT / "dist" / "baseline"
destination.mkdir(parents=True, exist_ok=True)
script = (source / "index.js").read_text(encoding="utf-8")
script, replacements = re.subn(
    r'import \{ pipeline \} from "https://cdn\.jsdelivr\.net/[^"\n]+";',
    """import { pipeline, env } from '/assets/runtime/transformers.min.js';
env.allowLocalModels = true;
env.allowRemoteModels = false;
env.localModelPath = '/assets/models/';
env.backends.onnx.wasm.wasmPaths = '/assets/runtime/';
env.backends.onnx.wasm.numThreads = 1;""",
    script,
    count=1,
)
if replacements != 1:
    raise SystemExit("Upstream import changed; inspect source before adapting it.")
html = (source / "index.html").read_text(encoding="utf-8")
html = re.sub(r'<img\s+class="upload-icon"[\s\S]*?/>', '', html, count=1)
html = html.replace('<body>', '<body>\n<p style="text-align:center">Original tutorial UI · Local runtime adaptation</p>')
html = "\n".join(line.rstrip() for line in html.splitlines()) + "\n"
(destination / "index.js").write_text(script, encoding="utf-8", newline="\n")
(destination / "index.html").write_text(html, encoding="utf-8", newline="\n")
shutil.copyfile(source / "style.css", destination / "style.css")
shutil.copyfile(source / "LICENSE", ROOT / "LICENSE")
print("Prepared baseline UI with local pinned runtime; original source retained unchanged.")
