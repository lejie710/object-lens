r"""Audit the locked Python dependencies and save the report under docs/evidence/security.

    .venv\Scripts\python.exe -m pip install pip-audit==2.10.1
    .venv\Scripts\python.exe tools\security_scan.py

pip-audit checks every pinned version in requirements-lock.txt against the
public Python vulnerability database, so it needs an internet connection.
The report is written first; the exit code is then non-zero if pip-audit did
not produce a report or any dependency has a known vulnerability, so the CI
step can fail. The browser runtime and model are pinned by hash in
asset-lock.json and are not covered by this audit.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "evidence" / "security"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    # The lock pins every package, so pip-audit can read it without resolving an environment.
    audit = subprocess.run(
        [sys.executable, "-m", "pip_audit", "-r", "requirements-lock.txt", "--no-deps", "--disable-pip",
         "--format", "json", "--progress-spinner", "off"],
        cwd=ROOT, capture_output=True, text=True)
    report = OUT / "pip-audit.json"
    try:
        data = json.loads(audit.stdout)
    except ValueError:
        report.write_text(audit.stderr, encoding="utf-8", newline="\n")
        print(f"pip-audit produced no report: {audit.stderr.strip()[:300]}")
        return 1
    report.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")
    packages = data.get("dependencies", [])
    vulnerable = [item for item in packages if item.get("vulns")]
    print(f"pip-audit: {len(packages)} packages checked, {len(vulnerable)} with known vulnerabilities")
    for item in vulnerable:
        print(f"  {item['name']} {item['version']}: {', '.join(v['id'] for v in item['vulns'])}")
    return 1 if vulnerable else 0


if __name__ == "__main__":
    raise SystemExit(main())
