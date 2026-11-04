# Attribution and scope

Object Lens adapts the interaction demonstrated by Hugging Face's Transformers.js vanilla JavaScript object-detection tutorial. The original example is retained in `baseline/upstream`, under its Apache License 2.0. Its repository, exact revision and file checksums are recorded in `baseline/source.json`.

The Object Lens interface, file validation, background-worker integration, stale-result handling and Python test suite are project modifications developed with AI assistance. They are not represented as upstream features or independently written work by Le Jie.

## Runtime and model

- Transformers.js 2.17.2: https://github.com/huggingface/transformers.js (Apache-2.0).
- ONNX Runtime Web 1.14.0: https://github.com/microsoft/onnxruntime (MIT).
- Hugging Face Jinja 0.2.2, embedded in the browser bundle: https://www.npmjs.com/package/@huggingface/jinja (MIT).
- DETR model: https://huggingface.co/facebook/detr-resnet-50 (Apache-2.0 model card).
- Browser-compatible model conversion: https://huggingface.co/Xenova/detr-resnet-50, with its exact revision in `asset-lock.json`.
- Sample photographs and their separate licences: `docs/IMAGE_SOURCES.md`.

Prepared model/runtime assets are excluded from Git but included in the deliberate public static package. The public credits page and `dist/licenses` retain the applicable original licence texts, upstream notices and model-card provenance; their source URLs and exact bytes are recorded in `credits-lock.json`. The existing project licence is preserved unchanged. Public deployment status and verification are recorded in `docs/PUBLIC_DEMO.md`.

## Baseline interpretation

The preserved upstream source imports Transformers.js 3.2.1. The runnable comparison at `/baseline/` uses the same pinned Transformers.js 2.17.2, WASM runtime and model files as Object Lens. It removes a remote upload icon and adds a visible adaptation caption. Those changes are produced by `tools/build_baseline.py`.

This controlled comparison isolates application behavior with common inference settings. It is not testing the unmodified upstream release or establishing a regression across runtime versions. The new result list and selection behavior have their own requirements; they are not compared as if they existed upstream.

The UI concept in `docs/design/approved-concept.png` is AI-generated design imagery. Its objects, boxes and scores are illustrative, not inference evidence.
