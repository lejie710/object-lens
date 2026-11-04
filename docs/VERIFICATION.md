# Verification and release assessment

Status on 4 November 2026: the branch review keeps Object Lens suitable for its bounded local learning and demonstration workflow. The current combined result is **102 passed, 0 failures/errors/skips; 780.398 seconds of JUnit suite time (98 non-model and 4 real-model cases)**. Website upload remains parked; no successful public deployment or verified public URL is recorded.

## Current branch review

Two further AI-assisted reviews examined the branch after the loading follow-up: a separate single-agent review session and a multi-agent review in which every finding had to survive three independent attempts to refute it. They found no new defect in the slow-connection fix itself. They did find documentation miscounts and overstatements, two remaining loading edge cases, a misleading message after Clear, weak or self-referential assertions, and local paths in retained evidence. [SOURCE_REVIEW.md](SOURCE_REVIEW.md) lists every confirmed finding and its correction.

Environment: Python 3.12.10, pytest 9.0.3, Selenium 4.40.0, Chrome 156.0.8078.80 and ChromeDriver 156.0.8078.80 on Windows 11. The integrated runner recorded 782.747 seconds of wall time; the JUnit duration above is the separate test-suite measurement. The run used one browser at a time.

The current execution record is [branch-review-verification.json](evidence/branch-review-verification.json), with the combined JUnit result in [branch-review-full-suite.xml](evidence/branch-review-full-suite.xml). It records the exact commands, environment and source hashes. The run started from commit `f1a19a9` with uncommitted changes; the recorded hashes identify the tested files, which are the files committed with this review.

| Change | What is checked | What the evidence does not establish |
| --- | --- | --- |
| Transfer completion starts initialization | When every model byte has arrived, the 120-second initialization deadline replaces the 45-second stall window, so the library's silent Cache Storage write is not reported as a stalled connection | Cache Storage timing on every device |
| Honest progress without a known size | Transformers.js 2.17.2 reports total = bytes received when a host omits Content-Length; the page shows received megabytes and an indeterminate bar instead of a false 100%, replaying that real event shape | Every hosting provider's headers |
| Clear during a hung analysis | If Clear removed the image before its analysis timed out, the detector restarts quietly instead of showing an analysis failure on an empty workspace | That a real model hang occurred |
| Recorded-reference comparison | Every visible real-model row, including the 0.67 coffee spoon, matches the earlier recorded output of the same pinned model within 0.01; the expected values come from the recorded file, not the page's own attributes | Model accuracy; the reference is an earlier output, not ground truth |
| Startup and provenance checks | Startup tests count real-worker requests as well as controlled-worker requests; package provenance also tolerates a repository with no commits | Every possible Git state |

The rebuilt package is identified in [branch-review-package.json](evidence/branch-review-package.json). The paced 2.5 Mbps probe was repeated against it: [branch-review-slow-transfer.json](evidence/branch-review-slow-transfer.json) records the previous fixed-deadline failure and the current package reaching ready at 140.6 seconds. [branch-review-rendered-review.json](evidence/branch-review-rendered-review.json) records the current captures. They were byte-identical to the earlier set, so the repository keeps one copy in `docs/screenshots/review-followup`; the record lists the matching hashes.

The audit that started the loading follow-up retained two records here: [audit-17f2b9a-full-suite.xml](evidence/audit-17f2b9a-full-suite.xml), its 93-case reproduction of `17f2b9a` in a disposable copy, and [audit-17f2b9a-blank-label-fault.xml](evidence/audit-17f2b9a-blank-label-fault.xml), where 44 recovery and UI tests still passed with the blank-label check deleted.

## Loading follow-up

Commit `f1a19a9` replaced the fixed 120-second model-loading deadline with a 45-second stall window and a separate 120-second initialization deadline, after an audit throttled the model to 2.5 Mbps and observed a failure at 86% received. Its records are [loading-followup-verification.json](evidence/loading-followup-verification.json) (98 passed, 783.414 s JUnit) and [loading-followup-slow-transfer.json](evidence/loading-followup-slow-transfer.json). That verification record's `evidence_type` text still names the earlier review follow-up: the label was a hard-coded string in `tools/record_verification.py`, now made neutral. Its sensitivity record contains eight faults and 14 intended failures; the documentation at that commit overstated this as nine and 15.

## Preceding review follow-up

The agreed review improvements below were verified on 3 November with 93 passed, 0 failures/errors/skips, 648.509 seconds of JUnit suite time (89 non-model and 4 real-model cases), in [followup-verification.json](evidence/followup-verification.json) and [followup-full-suite.xml](evidence/followup-full-suite.xml). Those records describe that earlier source and are retained as history. Every check they list remains in the current suite.

| Agreed improvement | What is checked | What the evidence does not establish |
| --- | --- | --- |
| Visible labels and scores | Result rows and box labels show the expected name; result rows show two-decimal model scores; blank text in disposable copies is detected | Correct recognition of arbitrary images |
| Real-model box positions | Person, cup and cat coordinates stay within a stated tolerance of earlier pinned-model outputs; actual box geometry agrees with the displayed image | Localization accuracy against independent human annotations |
| Truthful timeout and Clear feedback | Model-loading and inference deadlines have distinct explanations; Clear leaves a stopped detector unavailable; Retry restores operation | That a real model outage occurred |
| Malformed model responses | Representative invalid scores, missing/non-finite coordinates, impossible boxes and mixed valid/invalid batches are rejected without misleading detections; recovery and clamping are checked | Exhaustive validation of every possible object shape or dependency fault |
| Useful feedback and announcements | Important input errors contain the format/limit/recovery information; status and error elements retain intended roles/live settings | Actual screen-reader speech, accessibility certification or every assistive technology |
| Current documentation and package | Current claims reconcile with the new evidence; Word/PDF contents, page references, return links and page layout are verified; package allowlist and hashes pass | Deployment or correctness on an untested hosting provider |

That pass's browser review and images are recorded in [followup-rendered-review.json](evidence/followup-rendered-review.json) and `docs/screenshots/review-followup`. Real coffee inference and export captures are distinguished from the deliberately controlled timeout/Clear state. Its public package record is [followup-package.json](evidence/followup-package.json). Browser console and request observations describe the captured sessions, not all operating-system activity.

## Reproduce the evidence

From the prepared repository environment:

```powershell
.\.venv\Scripts\python.exe tools/prepare_assets.py --verify-only
.\.venv\Scripts\python.exe tools/download_samples.py --verify
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe tools/check_review_sensitivity.py --output artifacts/sensitivity-new
.\.venv\Scripts\python.exe tools/check_recovery_comparison.py --output artifacts/recovery-comparison-new
.\.venv\Scripts\python.exe tools/capture_review.py --screenshots artifacts/captures-new --report artifacts/captures-new.json
.\.venv\Scripts\python.exe tools/record_verification.py --retain-prefix verification-new
.\.venv\Scripts\python.exe tools/build_public_demo.py
```

The manifest records the exact invocation used for the retained run, including its temporary directory outside any Git checkout. The helpers retain reusable procedures for the new sensitivity, capture and evidence-export work. They do not reconstruct every historical experiment whose original helper remained under ignored `artifacts`. JUnit evidence copies remove hostnames; the manifest records redaction and hashes of the raw and selected records.

Production deadlines are 15 seconds for configuration, a 45-second model-transfer stall window that each loading event restarts, 120 seconds for runtime initialization once the model's bytes have all arrived, and 90 seconds for inference. Normal controlled loading keeps the production deadlines. Dedicated loading tests accelerate only the 45000 ms stall timer to 1500 ms and the 120000 ms initialization timer to 2500 ms; controlled inference uses four seconds. Those durations exercise failure paths and are not measured model performance. Test processes run headlessly with local assets and a cached driver. They do not change system security settings.

## Deliberate fault sensitivity

[branch-review-recovery-comparison.json](evidence/branch-review-recovery-comparison.json) records three controlled wording checks failing against `74d108f` in 26.952 seconds and all three passing against the current source in 26.040 seconds; earlier passes are retained in [loading-followup-recovery-comparison.json](evidence/loading-followup-recovery-comparison.json) and [followup-recovery-comparison.json](evidence/followup-recovery-comparison.json). The old checks fail before Clear, so they do not independently reproduce the old Clear message. The passing current checks continue through Clear, truthful detector unavailability, Retry and a successful new image. The substituted runtime crash is a component simulation; no production trigger is claimed.

[branch-review-sensitivity.json](evidence/branch-review-sensitivity.json) records fresh disposable-copy experiments and their intended failing assertions. A 13-case clean control passes, then 11 deliberate faults each fail their intended assertions, 17 expected failures in total. Four faults come from the review follow-up: blank visible names or scores, displaced rendered boxes and removed announcement settings. The other seven test this branch's changes: a fixed load deadline that ignores progress, settings events extending initialization, accepted blank labels, every score scaled by 0.95, every score forced to 1.0, a completed transfer left under the stall window, and a cleared hang reported as an analysis failure. Within the real-model checks, only the recorded-reference comparison catches the two score faults, because the page's own attributes change with them; controlled UI tests compare against independently specified fixture values and are a separate oracle. Earlier records are [loading-followup-sensitivity.json](evidence/loading-followup-sensitivity.json) and [followup-sensitivity.json](evidence/followup-sensitivity.json). The clean application is preserved. These results show that the selected checks detect the selected faults; they are not a mutation score, broad test-completeness proof or naturally observed production incidents.

Earlier external review reported that blank labels/scores, displaced boxes and removed announcement settings could pass the previous assertions. That report motivated the new checks. Only the new locally retained runs are claimed as this follow-up's reproduced evidence. The malformed responses are deliberate test-worker outputs, not faults observed from the real pretrained model.

## Acceptance coverage

| Criterion | Representative evidence |
| --- | --- |
| AC1: input limits and useful rejection | Exact 10 MiB and 16,000,000-pixel boundaries, JPEG/EXIF, unsupported content and truncated PNG; meaningful visible format/limit messages |
| AC2: current-image results | Visible labels/scores, row/box identity, controlled geometry and selected-box regression on three real photos |
| AC3: selection and Clear | Selected-box/keyboard checks; Clear removes content and preserves truthful unavailable state after a stopped worker |
| AC4: stale-result protection | In-flight Clear, fast/slow replacement, sample-fetch cancellation and retired-worker checks |
| AC5: recovery | Input errors, empty results, inference failure, malformed responses, model/inference timeout and recovery |
| AC6: usable interface | Keyboard/focus, usable viewport widths, visible status/error content and announcement-configuration assertions |
| AC7: score filter | Raw-score boundary, restore without inference, stable identity/color/selection, filter-empty and keyboard behavior |
| AC8: Try sample | Real local-photo path; missing/unreadable data, actual 15-second fetch timeout and late-response rejection |
| AC9: PNG export | Downloaded PNG bytes/dimensions, retained/excluded annotation pixels, EXIF, encoder failure/timeout and stale-export rejection |
| AC10: bounded startup | Configuration headers/body deadline, invalid configuration with no worker of either kind, preserved input errors/preparation, model progress including the no-Content-Length event shape, stalled transfer, slow steady transfer, completed transfer before 'done', initialization hang, stage-specific worker failure and Retry |
| AC11: static package | Exact file/ZIP/hash checks, private-file exclusions, optional Git provenance outside a checkout and actual model/export through an ordinary static server |

## Historical checkpoints

These executions retain their original source, date and limits. Counts overlap and are never added to the current result.

| Milestone | Recorded result | Retained evidence |
| --- | --- | --- |
| 3 November loading follow-up (`f1a19a9`) | 98 passed, 0 failures/errors/skips; 783.414 s; 94 non-model and four real-model cases | `loading-followup-full-suite.xml`, `loading-followup-verification.json` |
| 3 November audit reproduction of `17f2b9a` | 93 passed, 0 failures/errors/skips; 725.685 s in a disposable copy | `audit-17f2b9a-full-suite.xml` |
| 3 November review follow-up | 93 passed, 0 failures/errors/skips; 648.509 s; 89 non-model and four real-model cases | `followup-full-suite.xml`, `followup-verification.json` |
| 3 November preceding correctness review | 72 passed, 0 failures/errors/skips; 531.363 s JUnit (531.53 s runner); 68 non-inference and four real-model cases | `review-full-suite.xml`, `source-review-verification.json` |
| 3 November public preparation | 59 passed; 441.33 s; focused run 11 passed in 52.46 s | `public-prep-full-suite.xml`, `public-prep-focused-suite.xml`, `public-prep-verification.json` |
| 2 November combined extension | 48 passed; 418.62 s; 45 non-inference and three real-model cases | `extension-full-suite.xml`, `extension-verification.json` |
| Filter checkpoint | 29 controlled cases passed; 199.37 s | `score-filter-suite.xml`, `score-filter-record.json` |
| Sample checkpoint | Seven controlled plus three real cases passed; 137.27 s | `sample-image-suite.xml`, `sample-image-record.json` |
| PNG checkpoint | Eight controlled export cases passed; 89.03 s | `export-png-suite.xml` |
| Base final suite | 26 passed; 215.13 s | `final-full-suite.xml` |
| Base fresh setup on the same laptop | 26 passed; 205.13 s | `fresh-setup-summary.json`, `fresh-setup-suite.xml` |
| Base repeated use | 320 cycles, 320 clears and 32 rapid replacements; 3615.927 s; no observed failure | `stability-summary.json` |

The historical public-preparation review paced only the model response at 10 Mbps on loopback: 43,102,531 bytes arrived in 34.493 seconds, and readiness occurred at 36.776 seconds. This controlled transfer observation is not Internet performance. The historical environment was Python 3.12.10, pytest 9.0.3, Selenium 4.40.0, Chrome 156.0.8078.74 and ChromeDriver 156.0.8078.80; the new manifest independently records the current run's versions.

## Findings and their interpretation

The preceding review reproduced missing configuration deadlines, startup erasing an input error, readiness misreporting an unfinished file read, optional package provenance failing outside Git, failure-evidence writing bypassing browser cleanup, and an incomplete document-navigation check. [SOURCE_REVIEW.md](SOURCE_REVIEW.md) preserves the before/after evidence and describes this follow-up separately.

The extension's 320-pixel viewport defect was observed rather than injected. Its vertical scrollbar left 305 pixels of usable width, but the body's minimum was 320 pixels. Comparing against `window.innerWidth` hid the overflow; the corrected check uses `documentElement.clientWidth`. [viewport-before-fix.xml](evidence/viewport-before-fix.xml) retains the real failing assertion, and the historical extension capture measured 305-pixel content inside that 305-pixel space after correction.

The first extension suite had 47 passes and one failed download-folder assertion. The extra file was `downloads.htm.crdownload`, with a CRX container header, not an application PNG; its producing request was not captured. The assertion was retained and external hostname resolution was disabled only inside isolated test browsers. The rerun passed 48 cases. [extension-first-full-suite.xml](evidence/extension-first-full-suite.xml) preserves that failed run without inventing its origin.

Earlier setup/test issues included a worker-failure injection that initially returned HTTP 200, an authenticated Git request unsuitable for public asset retrieval, proxy handling for numeric loopback, CRLF manifest output and insufficient failure diagnostics. Their original records remain in the evidence index. The base watchdog work addressed a possible silent worker; no real-model hang was observed.

## Real-model observations and limits

The five-photo historical observations are in [model-observations.json](evidence/model-observations.json). Astronaut produced person; coffee produced spoon, dining table, cup and another spoon; chelsea produced cat; camera included person with incorrect/duplicate other predictions; rocket produced no predictions. These convenience samples are not an exhaustive annotated dataset.

The three geometry checks compare against earlier coordinates from that same pinned model, with tolerance documented in `tests/test_inference.py`. This detects a position regression or rendering displacement. It cannot establish whether the reference boxes are objectively correct. Expected-label notes came from upstream descriptions and separate AI-assisted visual inspection; they are partial expectations, not full human annotations.

## Release decision and remaining limits

The current combined suite and targeted fault/recovery evidence support the agreed local exploration workflow: **102 passed, 0 failures/errors/skips; 780.398 seconds of JUnit suite time (98 non-model and 4 real-model cases)**. The current package also completed a paced 2.5 Mbps model transfer that the fixed-deadline source could not complete. The refreshed documents and rebuilt static ZIP are local deliverables. Source publication remains owner-operated, and website upload remains parked.

Only the recorded Windows/Chrome environment was checked. No other browser, iOS/Safari, hosted CI, deployed URL, general accuracy benchmark, GPU/NPU execution, semiconductor inspection or production-scale behavior was qualified. The historical one-hour session does not requalify this revision, establish a flake rate or certify memory-leak freedom. Timing varies with workstation load. Live-region configuration checks are not actual screen-reader testing. Retry still restarts the model download from the beginning, so a connection that repeatedly stalls for 45 seconds cannot load the detector. After Clear in the unavailable state the Clear button stays enabled on an empty workspace; pressing it again is harmless.

Raw outputs and retained recovery-comparison copies remain under ignored working directories. The sensitivity runner removes its own temporary source copies after each run while preserving logs and results. The maintained application is the repository's root `dist` directory. Preserve those evidence boundaries when explaining the project or using screenshots in a learning update.
