# Design reference

`approved-concept.png` is the visual concept approved during planning. It was generated with the built-in image-generation tool. The photograph, labels and scores in that image are illustrative; they are not model execution evidence.

The implemented application follows its practical layout: a white header, essential controls, a large image area, a compact results list and restrained blue selection. The original concept said "Objects"; actual model results showed duplicate predictions, so the implementation uses "Detections" and "predictions" instead.

Actual browser screenshots are in `../screenshots`. Verification records distinguish real inference from controlled UI fixtures.

The generation prompt is retained in `generation-prompt.txt`. It is provenance for the planning image, not an application dependency or instruction to add more features.
