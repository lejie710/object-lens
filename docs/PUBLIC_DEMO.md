# Public demo package

Status: the static package can be built and inspected locally, and `.github/workflows/pages.yml` is set up to publish it to GitHub Pages at [lejie710.github.io/object-lens](https://lejie710.github.io/object-lens/). The deployed showcase, built before the link preview was added, was opened in a fresh headless Chrome profile and passed the README try-it steps ([showcase-check.json](evidence/showcase-check.json)). [The verification record](evidence/v1-0-2-verification.json) identifies the tested source and [the package record](evidence/v1-0-2-package.json) identifies the archive. [Defects and corrections](DEFECTS.md) lists the startup, recovery and slow-connection loading defects and the tests that prevent them.

## What the public package exposes

The published demo is a static website, separate from the source repository. Visitors necessarily receive the browser application's HTML, CSS, JavaScript, model and runtime files; those delivered files can be inspected. Design documents, tests, repository history, environments and raw evidence are not part of the package.

The application processes selected photos in the visitor's browser. Its requests obtain the website, model/runtime files and optional public coffee sample; it does not upload the selected photo for inference. The hosting provider still handles ordinary website requests. The browser may cache downloaded runtime/model assets. Selected photo data and predictions are held by the active page/worker; the app has no saved-photo history or persistent photo-storage feature. Clearing the page removes its current image state, not browser-cached model files. The public credits page explains that the selected photo stays in the browser while the website's files are still requested, and states that labels, boxes and scores are predictions that can be wrong.

## Prepared website

The package has 29 allowlisted files: eight application/configuration files (including the link preview image), six pinned model/runtime files, one public sample and fourteen licence/provenance texts. Each build's manifest records its exact byte counts, content identity, ZIP size and ZIP hash. The archive contains `index.html` at its root. Page and worker requests use relative URLs, and the worker resolves model and runtime files relative to its own location, so the package works at a site root or under a URL subpath such as a GitHub Pages project site (`https://lejie710.github.io/object-lens/`). It excludes `docs`, `tests`, `.git`, `.venv`, `.local`, `artifacts` and the comparison baseline.

Normal static hosting reads `runtime-config.json` from the package with `testMode` set to the JSON boolean `false`. The local Python server generates this response itself, allowing explicitly controlled tests to use their separate mode. The uploaded site needs no Python service, database or paid inference API.

The loading notice distinguishes model transfer from runtime initialization. A model progress value of 100 does not claim that the detector is ready. When a host omits Content-Length, Transformers.js 2.17.2 reports the bytes received so far as the total; the page then shows megabytes received with an indeterminate bar rather than a false percentage. Errors remain separate, and an old worker cannot update a newer worker's loading state. Loading and inference timeout messages identify the failed stage. Clear after a stopped worker preserves an unavailable/retry state rather than claiming readiness. Model transfer is bounded by a 45-second stall window rather than total elapsed time, so a slow but steady connection can complete the download. Once every byte of a known-size transfer has arrived, runtime initialization, including the library's local Cache Storage write, keeps a fixed 120-second deadline, and inference keeps 90 seconds. Retry starts the model download again from the beginning; a connection that repeatedly stalls for 45 seconds still cannot load the detector.

Configuration has its own 15-second request/body deadline before worker startup. Retry fetches it again without losing the selected image. Background readiness preserves existing input errors and unfinished file preparation.

`credits-lock.json` records the source, byte count and SHA-256 of each distributed licence/model-card file. Their original bytes are preserved. The package also verifies all six runtime/model files against `asset-lock.json` and the coffee image against its independently pinned hash.

## Link preview

Social sites such as LinkedIn build a link's preview card from tags in the page, not from the repository. `index.html` carries Open Graph and Twitter card tags (`og:title`, `og:description`, `og:url`, `og:image` and its type, size and alternative text, and `twitter:card` set to `summary_large_image`). Social sites fetch the image from its absolute URL on the showcase, `https://lejie710.github.io/object-lens/social-preview.png`, so the image is one of the allowlisted package files. A browser opening the page does not request it.

`dist/social-preview.png` (1200 x 630 PNG, 623,292 bytes, SHA-256 `6a0e8abf86fb495cfaa4ca33760c2df8b7b311023b10113097efb7d622ef2962`) is derived from the recorded real-model capture `docs/screenshots/app/desktop.png` (SHA-256 `4d86d92f4dcd5f84c5ee1c7f36256f4f5995bf2dae852d77d16717e85bc1ec5e`): cropped to the box from (17, 0) to (1407, 730), which ends above the status line, resized with Lanczos resampling to 1200 x 630 and saved as an optimized PNG with Pillow 12.2.0. Pillow is not a project dependency; the image is a one-time derived file, not regenerated by the build. The coffee photo in it is the CC0 sample listed in [IMAGE_SOURCES.md](IMAGE_SOURCES.md).

`tests/test_public_package.py::test_link_preview_tags_point_to_the_packaged_image` checks, without a browser, that `og:url` is the showcase address, that `og:image` is an absolute URL on it naming a file in the package allowlist, that the Twitter tags repeat the Open Graph values, and that the image is a PNG with the declared 1200 x 630 size and under 5 MB, inside [LinkedIn's sharing guidance](https://www.linkedin.com/help/linkedin/answer/a521928) (at least 1200 x 627, about 1.91:1, at most 5 MB). It does not show how any social site renders the card. That has not been checked yet: after deployment it is checked with LinkedIn Post Inspector and recorded separately (see [Still required after publication](#still-required-after-publication)).

## Rebuild and inspect locally

After preparing the normal project environment and assets:

```powershell
.\.venv\Scripts\python.exe tools/build_public_demo.py
```

The command creates a new directory under `artifacts/public-demo` (or under `--output`) and prints three paths: `site`, `Object_Lens_Public_Demo.zip` and `package-manifest.json`. Only the ZIP or the `site` folder is published. The manifest stays outside the public payload and records file hashes, content identity, source commit and whether the checkout was dirty. The builder does not download or publish anything.

The public package is selected explicitly rather than copied from the entire repository or `dist`. Copying a GitHub source archive alone is insufficient because model/runtime binaries are excluded from Git. A changed, missing or unapproved dependency prevents packaging.

For an isolated static-server review, pass the actual generated `site` path:

```powershell
.\.venv\Scripts\python.exe tools/check_public_demo.py --site '<generated site directory>' --model-mbps 10
```

This helper uses a fresh headless Chrome profile. It paces only the model response on loopback, then checks real inference, filtering, PNG download, usable viewport widths, local credit links and keyboard focus. The simulated transfer is not Internet performance or proof of a deployed website.

## Verification

Package identity and archive integrity are in [the package record](evidence/v1-0-2-package.json). The ordinary static-server run (real sample detection, filtering and PNG export without the custom Python routes, with the package served under `/object-lens/`) is `tests/test_public_package.py::test_packaged_site_runs_real_sample_filter_and_export_on_an_ordinary_static_server`, part of the suite recorded in [the verification assessment](VERIFICATION.md). The isolated static-server observations from `tools/check_public_demo.py` (viewports, credits links, keyboard focus, paced transfer) are in [public-prep-review.json](evidence/history/public-prep-review.json), with captures in [screenshots/history/public-prep](screenshots/history/public-prep), and cover an earlier package version that was served at the site root. These are local results from Chrome on one Windows laptop. Other browsers and devices, public connectivity, hosting access configuration, provider quotas and real Internet performance have not been qualified. No general model-accuracy claim is made. Older package and static-server records are listed in the [evidence index](evidence/README.md).

## Publishing route

The showcase is published by `.github/workflows/pages.yml`. It runs only when started manually (`workflow_dispatch`). It downloads the pinned runtime and model files, verifies them against `asset-lock.json`, builds the allowlisted package with `tools/build_public_demo.py` and deploys the generated `site` folder to GitHub Pages. It runs no tests and publishes no documents or test worker.

The workflow does nothing useful until two repository settings are in place: GitHub Pages must be available for the repository (a public repository, or a plan that allows Pages for private ones), and Settings, Pages, Source must be set to GitHub Actions. Merging or pushing does not update the website by itself; start the workflow again to publish a new build.

Any other static host can serve the same package: upload `Object_Lens_Public_Demo.zip` or the contents of its `site` folder, with `index.html` as the root page. No paid plan, domain, Python service or inference API is needed.

## Still required after publication

Verify the actual HTTPS production address from a fresh signed-out browser. Confirm that it opens the app rather than an authentication page; observe a fresh model load; run Try sample and a selected public photo; exercise filtering, PNG download and recovery; check the visible layout and console; and verify that design documents, tests and test routes are absent. Record the actual URL, date, build identity, observations and remaining limits in a separate evidence record from the local results above. After a deployment that changes the link-preview tags or image, also confirm that the page serves the tags and the image, and paste the showcase address into [LinkedIn Post Inspector](https://www.linkedin.com/post-inspector/) to see the card LinkedIn will show; an existing LinkedIn post or project link keeps its old preview until LinkedIn fetches the page again.

The README links the showcase address; that link is not hosted evidence until these checks are recorded.
