# Operations

Setting up, running, testing and troubleshooting Object Lens on Windows. Commands are for Windows PowerShell. After the clone step, run them from the `object-lens` folder.

## 1. First setup

Needs Python 3.12 and Google Chrome. The first setup needs internet access to download the Python packages, the Chrome driver, the browser runtime and the model files. No paid API is needed.

```powershell
git clone https://github.com/lejie710/object-lens.git
cd object-lens
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe tools/prepare_assets.py
.\.venv\Scripts\python.exe tools/download_samples.py
.\.venv\Scripts\python.exe tools/browser_check.py
```

| Step | What it does |
| --- | --- |
| `pip install -r requirements-lock.txt` | `requirements.txt` lists the direct dependencies, and `requirements-lock.txt` records the full tested environment |
| `tools/prepare_assets.py` | Downloads the pinned browser runtime and model files into `dist/assets`, which is kept out of Git. Their sources and SHA-256 hashes are in `asset-lock.json`, and later runs verify the saved checksums |
| `tools/download_samples.py` | The public sample photos are already in `dist/samples`. The script checks them against their pinned upstream SHA-256 hashes, fetches only a photo that is missing, and stops with an error if any photo does not match |
| `tools/browser_check.py` | Starts a headless Chrome session to confirm the browser and driver work, without touching the desktop |

To check the prepared files without downloading anything:

```powershell
.\.venv\Scripts\python.exe tools/prepare_assets.py --verify-only
.\.venv\Scripts\python.exe tools/download_samples.py --verify
```

## 2. Run the app

```powershell
.\.venv\Scripts\python.exe serve.py
```

Open `http://127.0.0.1:8765` in Chrome. The server is reachable only from this computer, and Ctrl+C stops it. If port 8765 is already in use, run `.\.venv\Scripts\python.exe serve.py --port 8766` and open port 8766 instead.

To try it: click **Try sample**, select the cup, move **Minimum model score** from 0.50 to 0.80, and click **Save result**. Then lower the filter again to bring the hidden predictions back. Predictions can include mistakes or duplicates, and a score does not guarantee the prediction is right.

## 3. Run the tests

The tests start and stop their own local servers and use headless Chrome, so `serve.py` does not need to be running.

```powershell
# Full suite
.\.venv\Scripts\python.exe -m pytest

# Controlled app, server, package and harness checks; not evidence about the model
.\.venv\Scripts\python.exe -m pytest -m "not inference"

# Real model: three photo regression checks plus the static-package workflow
.\.venv\Scripts\python.exe -m pytest -m inference
```

Temporary test files go under `.local/pytest` (set in `pytest.ini`), because some managed Windows machines block pytest's default folder.

The static-package test serves the prepared site under the subpath `/object-lens/` from an ordinary local static server. The worker resolves the model and runtime files relative to its own location, so the package works at a site root or under a subpath such as a GitHub Pages project site. The showcase is published by the manually started [pages.yml](../.github/workflows/pages.yml) workflow, which builds the same allowlisted package with `tools/build_public_demo.py`; the tests do not check the hosted copy. [PUBLIC_DEMO.md](PUBLIC_DEMO.md) describes the package.

CI ([ci.yml](../.github/workflows/ci.yml)) runs the controlled tests on every push to `main` and every pull request, and audits the locked Python dependencies with pip-audit. The real-model tests run locally only; their recorded references hold only on the machine that recorded them.

## 4. Record evidence

The commands that reproduce the recorded results (fault sensitivity, recovery comparison, screen captures, the verification record, the package build and the dependency audit) are listed in [VERIFICATION.md](VERIFICATION.md#reproduce-the-evidence), together with the rules for choosing new output names. The dependency audit on its own:

```powershell
.\.venv\Scripts\python.exe -m pip install pip-audit==2.10.1
.\.venv\Scripts\python.exe tools/security_scan.py
```

`security_scan.py` needs an internet connection and rewrites `docs/evidence/security/pip-audit.json`. It exits non-zero if pip-audit produced no report or any dependency has a known vulnerability. The browser runtime and model are pinned by hash in `asset-lock.json` and are not covered by this audit. The [evidence index](evidence/README.md) describes each recorded file.

## 5. Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| The app reports a missing file | The model or runtime files in `dist/assets` are missing or incomplete | Run `tools/prepare_assets.py` again, then click **Try again** in the app |
| `serve.py` cannot start on port 8765 | Another program uses the port | `.\.venv\Scripts\python.exe serve.py --port 8766`, then open port 8766 |
| `download_samples.py` stops with a hash error | A photo in `dist/samples` does not match its pinned upstream hash | Delete that photo and run the script again; it fetches only missing photos |
| An evidence tool refuses to run | Its output location or record prefix already holds results | Choose a new output folder or prefix; earlier evidence is never overwritten |
| pytest prints an ignored `PermissionError` after the summary line | Exit-time cleanup of pytest's default temporary folder met a stale link from an earlier run | Nothing to fix: the exit code and the results are unaffected |

## 6. Repository layout

| Folder | Purpose |
| --- | --- |
| `dist` | The app and its prepared local assets |
| `tests` | The pytest and Selenium suite, plus the controlled worker fixture |
| `tools` | Helpers for setup, packaging, collecting evidence and checking fault sensitivity |
| `docs` | Design, verification evidence, screenshots and diagrams |
| `baseline` | The original upstream example, kept for attribution and comparison |
| `.github/workflows` | CI for the controlled suite and dependency audit, and the manual showcase deployment |
| `.venv`, `.local`, `artifacts` | Generated locally and ignored by Git: the Python environment, the driver cache and local verification copies, and raw test outputs; not part of the app |
