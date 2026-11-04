# Sample image sources and expected content

These five real photographs are used for a small local inference check and manual exploration. They are not generated images, private workplace material or a representative accuracy benchmark. Each file is an unchanged copy from scikit-image v0.25.2. Their total size is 1,750,810 bytes (about 1.67 MiB).

The setup helper, `tools/download_samples.py`, checks each file against the SHA-256 value published in scikit-image's [versioned data registry](https://github.com/scikit-image/scikit-image/blob/v0.25.2/skimage/data/_registry.py). Run `python tools/download_samples.py --verify` for a network-free integrity check. An unexpected existing file is rejected rather than overwritten.

## Sources and attribution

The licence statements below are documented by the upstream project. Original creator credit is retained even where the image is dedicated to the public domain. The scikit-image project licence does not replace each photograph's stated terms.

| Local file | Dimensions | Bytes | Creator and stated terms | Original file and licence evidence |
| --- | --- | ---: | --- | --- |
| `dist/samples/astronaut.png` | 512 x 512 | 791,555 | NASA photograph of Eileen Collins; public domain | [Pinned file](https://raw.githubusercontent.com/scikit-image/scikit-image/v0.25.2/skimage/data/astronaut.png); [upstream provenance and terms](https://scikit-image.org/docs/0.25.x/api/skimage.data.html#skimage.data.astronaut) |
| `dist/samples/coffee.png` | 600 x 400 | 466,706 | Rachel Michetti, courtesy of Pikolo Espresso Bar; CC0 | [Pinned file](https://raw.githubusercontent.com/scikit-image/scikit-image/v0.25.2/skimage/data/coffee.png); [upstream provenance and terms](https://scikit-image.org/docs/0.25.x/api/skimage.data.html#skimage.data.coffee) |
| `dist/samples/chelsea.png` | 451 x 300 | 240,512 | Stefan van der Walt; CC0 | [Pinned file](https://raw.githubusercontent.com/scikit-image/scikit-image/v0.25.2/skimage/data/chelsea.png); [upstream provenance and terms](https://scikit-image.org/docs/0.25.x/api/skimage.data.html#skimage.data.chelsea) |
| `dist/samples/camera.png` | 512 x 512 | 139,512 | Lav Varshney; CC0 | [Pinned file](https://raw.githubusercontent.com/scikit-image/scikit-image/v0.25.2/skimage/data/camera.png); [upstream provenance and terms](https://scikit-image.org/docs/0.25.x/api/skimage.data.html#skimage.data.camera) |
| `dist/samples/rocket.jpg` | 640 x 427 | 112,525 | SpaceX launch photograph; public domain | [Pinned file](https://raw.githubusercontent.com/scikit-image/scikit-image/v0.25.2/skimage/data/rocket.jpg); [upstream provenance and terms](https://scikit-image.org/docs/0.25.x/api/skimage.data.html#skimage.data.rocket) |

The `camera.png` here is deliberately version-pinned: the upstream documentation says its old image was replaced in version 0.18 because of copyright restrictions. The file here matches the v0.25.2 registry.

## Expected visible content

The expectations below come from the upstream image descriptions and an AI-assisted visual inspection of the downloaded photographs made **before running the object detector**; the set has not been independently annotated by a person. They describe selected visible content rather than the detector's own answers. They are not exhaustive labels or bounding-box ground truth.

| Image | Core positive probe | Additional observations and limits |
| --- | --- | --- |
| `astronaut.png` | One `person` | Portrait in an orange suit. A helmet and a small space-shuttle model are visible; those are not additional required detection targets. The body extends to the bottom image edge. |
| `coffee.png` | One `cup` | One metal spoon, a saucer and a wooden surface are also visible. The spoon can be recorded as a secondary model-quality observation. A saucer is not labelled as a second cup. |
| `chelsea.png` | One `cat` | Close-up of one cat's head and upper body; much of the animal is outside the frame. |
| `camera.png` | One `person` | Grayscale photograph of a person leaning toward a camera on a tripod. The person extends beyond the left and bottom edges. |
| `rocket.jpg` | No required positive class | Rocket and launch towers at dusk. This illustrates limited model vocabulary. It is **not** a guaranteed empty-result fixture: unexpected detections must be recorded rather than suppressed. |

There are four positive probes. The automated photo-regression group uses three of them: astronaut/person, coffee/cup and chelsea/cat. A fourth actual-model test exercises coffee through the generated static package. A miss is a model-quality observation to investigate; it does not automatically prove an application defect. Conversely, a label drawn on the wrong image or retained after clearing is an application-state defect even if that label was plausible for an earlier image.

Use controlled worker fixtures, clearly marked as simulated, to exercise exact empty/error/delay states. Do not describe those controlled results as model inference. Do not calculate general accuracy, precision or recall from this small, partially annotated set.

## Box-position regression references

The photo tests use the selected person, cup and cat coordinates in `docs/evidence/model-observations.json` as regression references. Those coordinates are recorded outputs of the same pinned model, not independent human-drawn annotations. A comparison can detect that the output or rendering moved; it cannot establish localization accuracy.

Each normalized edge allows a difference of 0.005, equivalent to 0.5 percent of that image extent, or about 1.5 to 3 source pixels in these photographs. Rendered positions allow the scaled edge tolerance plus 2 CSS pixels for rounding/borders. Widths and heights depend on two edges, so they allow two scaled edge tolerances plus 2 CSS pixels. `tests/test_inference.py` measures the actual image and box rectangles; the separate disposable-copy experiment verifies that deliberately displacing boxes fails the checks.

## Integrity record

| File | SHA-256 |
| --- | --- |
| `astronaut.png` | `88431cd9653ccd539741b555fb0a46b61558b301d4110412b5bc28b5e3ea6cb5` |
| `coffee.png` | `cc02f8ca188b167c775a7101b5d767d1e71792cf762c33d6fa15a4599b5a8de7` |
| `chelsea.png` | `596aa1e7cb875eb79f437e310381d26b338a81c2da23439704a73c4651e8c4bb` |
| `camera.png` | `b0793d2adda0fa6ae899c03989482bff9a42d3d5690fc7e3648f2795d730c23a` |
| `rocket.jpg` | `c2dd0de7c538df8d111e479619b129464d0269d0ae5fd18ca91d33a7fdfea95c` |
