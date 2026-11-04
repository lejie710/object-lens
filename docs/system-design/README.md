# Object Lens system design

Read the [PDF companion](Object_Lens_System_Design.pdf) or the [editable Word edition](Object_Lens_System_Design.docx). Both contain clickable contents titles and page numbers, plus links back to the contents. The companion documents the release source: base commit `be34c5e` plus the implementation and test file hashes in `source.json`, which match [release-verification.json](../evidence/release-verification.json).

Begin with the scope and technology responsibilities, then follow the architecture, image-replacement sequence and testing diagrams. The document explains configuration/loading feedback, a model-loading deadline based on stalls rather than elapsed time, stage-specific timeout and Clear recovery, malformed output validation, visible result assertions, box-position regression and the static-package boundary. The worked size-limit test connects requirements to automation; the failure chapter distinguishes observed defects, including the slow-connection loading defect, from deliberate fault experiments.

The companion's results are those of the release suite in [release-verification.json](../evidence/release-verification.json), assessed in [VERIFICATION.md](../VERIFICATION.md). Other suite records in `docs/evidence` cover other source versions and are not combined with it. Reference boxes are previous outputs of the pinned model, not independent ground truth. Announcement checks inspect page content and configuration, not actual screen-reader behavior. No website deployment or public URL is included.

## Sources and generated files

| File | Role |
| --- | --- |
| `source.json` | Authoritative prose, tables, captions, code excerpts, source commit and evidence hashes |
| `diagrams/*.html` | Authoritative editable diagrams, with self-contained inline SVG |
| `diagrams/*.svg` and `diagrams/*.png` | Generated diagram exports used by the document |
| `../screenshots/review-followup/desktop.png` and `../screenshots/review-followup/export.png` | Shared actual application and PNG-output captures |
| `build_document.py` | Builds the Word document from the JSON and declared image assets |
| `export_document.ps1` | Exports through a hidden, task-owned Word instance and records actual heading pages |
| `verify_document_navigation.py` | Checks Word anchors, PDF link destinations, printed contents pages and heading locations |
| `verify_document_content.py` | Checks source/evidence/figure hashes and exact code excerpts; renders PDF page PNGs with bundled pypdfium2 |
| `page-map.json` | Verified one-based page numbers for the stable heading bookmarks |
| `navigation-manifest.json` and `navigation-audit.json` | Heading/asset manifest and results for the delivered document pair |
| `document-validation.json` | Final document hashes, source/evidence checks and the record of all-page visual inspection |

Edit the JSON and relevant diagram HTML when the content changes, then regenerate their outputs. Manual changes to a generated Word or PDF copy are not automatically imported into `source.json`. Diagram exports must retain the full canvas and its explanatory notes. `diagrams/SOURCE_CHECKS.md` records their scope and source correspondence.

Save authoring text as UTF-8 with LF line endings, matching the repository's Git attributes. The builder checks the source JSON's line endings so byte hashes remain stable after checkout. Selected evidence text also uses LF; its original raw-run hashes continue to refer to the untouched files under `artifacts`.

## Rebuilding in the existing authoring environment

Reading these documents and running Object Lens require no document-authoring package installation. The application `.venv` is for the app's Python tests. Document production needs a Python with `python-docx`, `lxml`, `pypdf` and `pypdfium2`, plus the installed Word application on the recorded Windows environment. The document was built with Python 3.12.10 (python-docx 1.2.0, lxml 6.1.1, pypdf 6.13.2, pypdfium2 5.12.1). Use whichever such Python is available as `$documentPython` below.

From the repository root, rebuild the Word file with the existing verified page map:

```powershell
& $documentPython docs/system-design/build_document.py --source docs/system-design/source.json --output docs/system-design/Object_Lens_System_Design.docx --page-map docs/system-design/page-map.json --navigation-manifest docs/system-design/navigation-manifest.json
```

Use an ignored QA directory for intermediate conversion records. The tested Windows route uses static contents and direct PDF export, without a native TOC field-refresh dependency:

```powershell
New-Item -ItemType Directory -Force .local/document-planning | Out-Null
& docs/system-design/export_document.ps1 -InputDocx docs/system-design/Object_Lens_System_Design.docx -OutputPdf docs/system-design/Object_Lens_System_Design.pdf -NavigationManifest docs/system-design/navigation-manifest.json -ResultJson .local/document-planning/word-pages.json -ExportWithoutFieldRefresh
& $documentPython docs/system-design/verify_document_navigation.py --docx docs/system-design/Object_Lens_System_Design.docx --pdf docs/system-design/Object_Lens_System_Design.pdf --manifest docs/system-design/navigation-manifest.json --word-result .local/document-planning/word-pages.json --output docs/system-design/navigation-audit.json --page-map-output .local/document-planning/page-map.next.json
```

If headings or layout changed, first create an explicitly labelled preview with `--allow-draft`. The conversion records the actual heading pages. Inspect the PDF heading targets and adopt the newly verified page map, then rebuild without `--allow-draft`. Repeat the export and audit until the printed page numbers and targets agree. Do not retain preview labels or provisional page numbers in the delivered files.

The export helper requires an empty newly created Word instance, keeps it hidden and closes only its own document and instance. It does not change system security or network settings. Its recorded direct-export route performs the layout needed for the PDF; the static contents entries are generated from the verified page map.

After any content or layout change, render and inspect every final PDF page at readable scale. Check text, tables, figures, captions, page numbering and the link audit. Keep page PNGs and intermediate conversion records under ignored QA directories. Update the source/evidence hashes only after verifying the final bytes and actual results. The book records the starting commit plus final content hashes to avoid a circular claim about the commit that will contain the generated book.

LibreOffice `soffice.exe` is not installed on this Windows host, so the hidden Word export supplies the PDF. The export script passes Word's by-reference `Close` and `Quit` arguments with `[ref]`, which Windows PowerShell 5.1 requires, and still quits the task-owned instance if closing fails. This fallback changes no Office security or execution-policy setting. Render and check the artifacts with the document Python:

```powershell
& $documentPython docs/system-design/verify_document_content.py --bundle-version system-python-3.12.10 --word-state .local/document-planning/word-pages.json.state.json --render-dir artifacts/document-qa/pages
```

Open every resulting page image and inspect text, tables, figures, captions and page edges. Only after completing that visual review, run the checker with `--visual-reviewed-all` to record it. That flag records the reviewer's completed inspection; the program cannot establish visual quality by itself.

Pass an identifier for the document runtime actually used, such as `system-python-3.12.10`. The checker records the running Python and package versions, and the export state supplies the actual Word and PowerShell versions.
