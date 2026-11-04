# Public demo package

Status: no public deployment or verified live URL exists. The static package can be built and inspected locally. [The verification record](evidence/release-verification.json) identifies the tested source and [the package record](evidence/release-package.json) identifies the archive. [Defects and corrections](SOURCE_REVIEW.md) lists the startup, recovery and slow-connection loading defects and the tests that prevent them.

## What the public package exposes

Once published, the demo can be visited without repository access. The GitHub repository is private. Visitors necessarily receive the browser application's HTML, CSS, JavaScript, model and runtime files; those delivered files can be inspected. Private design documents, tests, repository history, environments and raw evidence are not part of the public package.

The application processes selected photos in the visitor's browser. Its requests obtain the website, model/runtime files and optional public coffee sample; it does not upload the selected photo for inference. The hosting provider still handles ordinary website requests. The browser may cache downloaded runtime/model assets. Selected photo data and predictions are held by the active page/worker; the app has no saved-photo history or persistent photo-storage feature. Clearing the page removes its current image state, not browser-cached model files. The public credits page explains that the selected photo stays in the browser while the website's files are still requested, and states that labels, boxes and scores are predictions that can be wrong.

## Prepared website

The package has 23 allowlisted files: seven application/configuration files, six pinned model/runtime files, one public sample and nine licence/provenance texts. Each build's manifest records its exact byte counts, content identity and ZIP hash; the ZIP is approximately 34.6 MB. The archive contains `index.html` at its root. Host it at the site root: worker asset URLs begin with `/assets`, so deployment under a URL subdirectory is not supported by this version. It excludes `docs`, `tests`, `.git`, `.venv`, `.local`, `artifacts` and the comparison baseline.

Normal static hosting reads `runtime-config.json` from the package with `testMode` set to the JSON boolean `false`. The local Python server generates this response itself, allowing explicitly controlled tests to use their separate mode. The uploaded site needs no Python service, database or paid inference API.

The loading notice distinguishes model transfer from runtime initialization. A model progress value of 100 does not claim that the detector is ready. When a host omits Content-Length, Transformers.js 2.17.2 reports the bytes received so far as the total; the page then shows megabytes received with an indeterminate bar rather than a false percentage. Errors remain separate, and an old worker cannot update a newer worker's loading state. Loading and inference timeout messages identify the failed stage. Clear after a stopped worker preserves an unavailable/retry state rather than claiming readiness. Model transfer is bounded by a 45-second stall window rather than total elapsed time, so a slow but steady connection can complete the download. Once every byte of a known-size transfer has arrived, runtime initialization, including the library's local Cache Storage write, keeps a fixed 120-second deadline, and inference keeps 90 seconds. Retry starts the model download again from the beginning; a connection that repeatedly stalls for 45 seconds still cannot load the detector.

Configuration has its own 15-second request/body deadline before worker startup. Retry fetches it again without losing the selected image. Background readiness preserves existing input errors and unfinished file preparation.

`credits-lock.json` records the source, byte count and SHA-256 of each distributed licence/model-card file. Their original bytes are preserved. The package also verifies all six runtime/model files against `asset-lock.json` and the coffee image against its independently pinned hash.

## Rebuild and inspect locally

After preparing the normal project environment and assets:

```powershell
.\.venv\Scripts\python.exe tools/build_public_demo.py
```

The command creates a new directory under `artifacts/public-demo` and prints three paths: `site`, `Object_Lens_Public_Demo.zip` and `package-manifest.json`. Upload only the ZIP or the `site` folder. The manifest stays outside the public payload and records file hashes, content identity, source commit and whether the checkout was dirty. The builder does not download or publish anything.

The public package is selected explicitly rather than copied from the entire repository or `dist`. Copying a GitHub source archive alone is insufficient because model/runtime binaries are excluded from Git. A changed, missing or unapproved dependency prevents packaging.

For an isolated static-server review, pass the actual generated `site` path:

```powershell
.\.venv\Scripts\python.exe tools/check_public_demo.py --site '<generated site directory>' --model-mbps 10
```

This helper uses a fresh headless Chrome profile. It paces only the model response on loopback, then checks real inference, filtering, PNG download, usable viewport widths, local credit links and keyboard focus. The simulated transfer is not Internet performance or proof of a deployed website.

## Verification

Package identity and archive integrity are in [the package record](evidence/release-package.json). The ordinary static-server run (real sample detection, filtering and PNG export without the custom Python routes) is `tests/test_public_package.py::test_packaged_site_runs_real_sample_filter_and_export_on_an_ordinary_static_server`, part of the suite recorded in [the verification assessment](VERIFICATION.md). The isolated static-server observations from `tools/check_public_demo.py` (viewports, credits links, keyboard focus, paced transfer) are in [public-prep-review.json](evidence/public-prep-review.json) and cover an earlier package version. These are local results from Chrome on one Windows laptop. Other browsers and devices, public connectivity, hosting access configuration, provider quotas and real Internet performance have not been qualified. No general model-accuracy claim is made. Older package and static-server records are listed in the [evidence index](evidence/README.md).

## Publishing procedure (on hold)

Publication is on hold until the owner decides to publish; no deployment has been made. These steps use Vercel Drop on the free Hobby plan. Check the provider's current terms, account eligibility and limits before publishing. No paid plan or domain is needed.

1. Sign in to Vercel and open [Vercel Drop](https://vercel.com/drop).
2. Upload the prepared `Object_Lens_Public_Demo.zip`, or the contents of its `site` directory. Select the personal Hobby account/team and a project name.
3. Confirm `index.html` as the root page if prompted, then deploy.
4. Retain the actual production URL Vercel returns. Test access while signed out and provide that URL for the hosted checks below.

A dropped project is not automatically connected to Git. Merging or pushing a later branch does not update this website by itself. To update it, rebuild the package and upload it to the existing project. Git-connected automatic deployments are a separate optional change.

Provider documentation: [Vercel Drop](https://vercel.com/docs/drop), [Hobby plan and usage limits](https://vercel.com/docs/plans/hobby). Account eligibility, availability of a particular project name and remaining usage allowance depend on the owner's account.

## Still required after publication

Verify the actual HTTPS production address from a fresh signed-out browser. Confirm that it opens the app rather than an authentication page; observe a fresh model load; run Try sample and a selected public photo; exercise filtering, PNG download and recovery; check the visible layout and console; and verify that private documents and test routes are absent. Record the actual URL, date, build identity, observations and remaining limits in a separate evidence record from the local results above.

A hosted URL is added to the README only after these checks pass. The [system design companion](system-design/README.md) covers the local implementation and the static-package boundary; it is not hosted evidence.
