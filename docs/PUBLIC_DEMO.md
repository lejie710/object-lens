# Public demo preparation

Status on 3 November 2026: the owner parked upload after the computer could not complete it. No successful public deployment or verified live URL is recorded. The corrected static package is prepared for later use; [the correctness review](SOURCE_REVIEW.md) describes the subsequent startup and verification fixes.

## Approved sharing boundary

The public demo may be visited without repository access. The GitHub repository remains private. Visitors necessarily receive the browser application's HTML, CSS, JavaScript, model and runtime files; those delivered files can be inspected. Private design documents, tests, repository history, environments and raw evidence are not part of the public package.

The application processes selected photos in the visitor's browser. Its requests obtain the website, model/runtime files and optional public coffee sample; it does not upload the selected photo for inference. The hosting provider still handles ordinary website requests. The public credits page explains this distinction and the model's limits.

## Prepared website

The package has 23 allowlisted files: seven application/configuration files, six pinned model/runtime files, one public sample and nine licence/provenance texts. Each build's manifest records its exact byte counts, content identity and ZIP hash; the corrected ZIP is approximately 34.6 MB. The archive contains `index.html` at its root. It excludes `docs`, `tests`, `.git`, `.venv`, `.local`, `artifacts` and the comparison baseline.

Normal static hosting reads `runtime-config.json` from the package with `testMode` set to the JSON boolean `false`. The local Python server still generates this response itself, allowing explicitly controlled tests to use their separate mode. The uploaded site needs no Python service, database or paid inference API.

The loading notice distinguishes model transfer from runtime initialization. A model progress value of 100 does not claim that the detector is ready. Unknown transfer sizes remain indeterminate, errors remain separate, and an old worker cannot update a newer worker's loading state. The existing 120-second model-load deadline and 90-second inference deadline remain in place; very slow connections can require retry.

Configuration now has its own 15-second request/body deadline before worker startup. Retry fetches it again without losing the selected image. Background readiness preserves existing input errors and unfinished file preparation.

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

## Preparation verification before the correctness review

- Full local suite: **59 passed**, zero failures/errors/skips, in **441.33 seconds**. This consists of 55 non-inference application/server/package checks and four actual-model cases.
- Focused loading/package suite: 11 passed in 52.46 seconds.
- Ordinary static-server integration: real coffee detection, score filtering and a downloaded 600 by 400 PNG passed without the custom Python routes. Private and controlled-test routes returned 404.
- Simulated model transfer: all 43,102,531 bytes arrived in 34.493 seconds, approximately 9.997 Mbps against the selected 10 Mbps pacing. Initial readiness was observed at 36.776 seconds in that local run; other assets were not paced.
- Rendered app review: 320, 390, 768 and 1440 CSS-pixel layouts fit the usable document width. Credits were inspected at desktop and 320 pixels; their local links returned HTTP 200 and keyboard focus remained visible.

These are local preparation results. Chrome on one Windows laptop was exercised. Other browsers/devices, public connectivity, hosting access configuration, provider quotas and real Internet performance have not been qualified. No general model-accuracy claim is made. Earlier 48-case and one-hour records retain their original source/version scope.

The later combined correctness-review suite passed 72 cases in 531.53 seconds, including four actual-model cases and the static-package workflow, with its temporary files outside any Git repository. Use [the source-review record](SOURCE_REVIEW.md) for this newer version. The earlier loading screenshots and paced-transfer figures above remain observations of the preceding preparation version.

The [preparation verification record](evidence/public-prep-verification.json) binds source files and retained evidence. See the actual [model-loading capture](screenshots/public-prep/model-loading.png), [current app](screenshots/public-prep/app-1440.png) and [credits page](screenshots/public-prep/credits-1440.png).

## Owner publication steps

Use a personal Vercel account on the free Hobby plan for this personal, non-commercial demo. A paid plan and a purchased domain are not required for this workflow. Use an owned account rather than leaving an anonymous deployment unclaimed, because anonymous deployments expire.

1. Sign in to Vercel and open [Vercel Drop](https://vercel.com/drop).
2. Upload the prepared `Object_Lens_Public_Demo.zip`, or the contents of its `site` directory. Select the personal Hobby account/team and a project name.
3. Confirm `index.html` as the root page if prompted, then deploy.
4. Retain the actual production URL Vercel returns. Test access while signed out and provide that URL for the hosted checks below.

A dropped project is not automatically connected to Git. Merging or pushing a later branch does not update this website by itself. To update it, rebuild the package and upload it to the existing project. Git-connected automatic deployments are a separate optional change.

Sources checked on 3 November 2026: [Vercel Drop](https://vercel.com/docs/drop), [Hobby plan and usage limits](https://vercel.com/docs/plans/hobby). Account eligibility, availability of a particular project name and remaining usage allowance depend on the owner's account.

## Still required after publication

Verify the actual HTTPS production address from a fresh signed-out browser. Confirm that it opens the app rather than an authentication page; observe a fresh model load; run Try sample and a selected public photo; exercise filtering, PNG download and recovery; check the visible layout and console; and verify that private documents and test routes are absent. Record the actual URL, date, build identity, observations and remaining limits separately from the local results above.

After those checks, update the README's live-demo link and the design's hosting record. The Word/PDF companion remains the versioned explanation of the prior local application; this addendum records the release-preparation changes until hosted evidence is available.
