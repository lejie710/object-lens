# Correctness review and regression fixes

Review date: 3 November 2026. Reviewed starting point: merged `main` at `9a60886`, containing the public-preparation implementation `3ac9422`. The review kept the feature scope fixed. Website upload remains parked; no successful public deployment or hosted verification is recorded.

## Scope and method

The maintained application, Python server, all tests, setup/package/evidence helpers and document-generation/navigation helpers were read. Model/runtime binaries, distributed notices and preserved upstream files were checked against their recorded hashes. That integrity check does not constitute a manual audit of every third-party implementation or a general model-accuracy evaluation.

Independent source-reading passes examined application state, packaging/reproducibility, and test/document evidence. Findings were reproduced through controlled local HTTP timing, ordinary temporary directories or isolated mocks/copies. The application's source was not deliberately corrupted to create these defects. This review was assisted by AI tools; it was not an external Opus review.

## Confirmed findings and corrections

| Finding | Before | Correction and observed check |
| --- | --- | --- |
| Configuration loading had no application deadline | A held response before headers or during its JSON body left the app loading after the 20-second regression wait; the model watchdog had not started | A real 15-second configuration deadline aborts the request. Retry fetches configuration again and retains the chosen image. Both held-response cases pass. |
| Background startup could erase an input error | An invalid file's explanation disappeared when delayed configuration completed and started the worker | Worker creation no longer clears user-facing errors as an incidental startup action. The error remains until a deliberate recovery action. |
| Worker readiness could misreport an active file read | The app said Ready to choose an image while a held file read was still pending | Track the current preparation revision separately. Ready and retry paths preserve Reading image or Loading sample until preparation actually finishes. |
| Package provenance depended on the test's parent directory | The privacy test failed outside a Git checkout because a deliberately incomplete `.git` marker caused Git to exit 128 | Missing/unusable optional Git metadata produces absent provenance; a source copy never inherits its parent's repository metadata. Byte-integrity and public-file checks are unchanged. |
| Failure-evidence writing could bypass browser cleanup | Injected evidence-directory denial skipped `driver.quit()`; observed mock call count was zero | An outer `finally` always attempts browser cleanup after creation. Evidence-write failures remain secondary. Three mocked failure paths require exactly one cleanup call. |
| Navigation checking did not require return links | Prior rules accepted a disposable PDF with one Back to contents link removed | Require one return link per top-level section. The delivered document passes with ten; the damaged copy fails with nine. Its page content was unchanged. |

The initial five startup regressions failed against the previous app in 73.44 seconds. After the first correction they passed in 64.17 seconds. A further regression covers worker retry during an unfinished file read. The original packaging privacy case failed outside the checkout in 1.89 seconds; after the provenance fix, eight browser-free cases passed there in 4.83 seconds. A separate case also covers a missing Git executable.

A controlled duplicate-label case was added because actual model observations include two spoon predictions. It verifies selection, coordinates, colors and filtering by prediction identity rather than merely comparing labels. No current duplicate-selection defect was found; this strengthens the regression oracle for an existing requirement.

## Final combined result

The complete suite passed **72 cases**, with zero failures, errors or skips, in **531.53 seconds**. It used a temporary directory outside any Git repository, addressing the condition hidden by the earlier in-checkout test runs. There are 68 non-inference cases and four actual-model cases. The static-package real-model workflow remains included.

The delivered Word/PDF files are unchanged. The stricter navigation check passed the 19-page document, 31 heading targets, 62 contents links and ten return links. Removing one return annotation from a disposable copy failed the new check; reconstructed prior rules incorrectly passed that same copy. This is a corrected verification gap, not a claim that the delivered document was missing its links.

The selected records and source hashes are in `docs/evidence/source-review-verification.json`. Earlier 26-, 48- and 59-case records retain their original source/version scope; their counts are not added together or relabelled as current execution.

## Remaining limits and review handoff

No blocking finding remains from this bounded review of the agreed local workflow. This does not prove every possible input, browser, operating-system behavior or third-party dependency correct. Chrome on the recorded Windows environment remains the verified target; wider browser/device support, general recognition accuracy and hosted behavior remain unqualified.

The optional transfer-rate checker still respects the app's 120-second model-load deadline. A sufficiently low requested rate is therefore a negative loading scenario, not an expectation that every positive rate must complete successfully. The recorded 10 Mbps model-only simulation remains limited to that scenario.

The corrected deployment package supersedes the earlier prepared ZIP, but upload remains paused. An independent reviewer should inspect this branch and the retained evidence before making additional release claims. Any next changes should address a demonstrated defect or a necessary clarification within the frozen scope.
