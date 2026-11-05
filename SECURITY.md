# Security

Object Lens is a finished portfolio project (version 1.0). Only the `main` branch is maintained.

## What runs where

- `serve.py` is a local development server. It listens on `127.0.0.1` only and is not meant to face a network.
- The hosted demo is static files: the browser app, the pinned model and runtime, one sample photo and licence notices. Photos you choose are processed in your browser and are not uploaded.
- Python dependencies are pinned in `requirements-lock.txt` and audited with `tools/security_scan.py`. Browser runtime and model files are pinned by SHA-256 in `asset-lock.json`, and setup refuses files that do not match.

## Reporting a problem

Please use GitHub's **Report a vulnerability** button on the Security tab of this repository, which sends a private report. Do not open a public issue for a security problem.
