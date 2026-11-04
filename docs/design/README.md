# Design reference

`approved-concept.png` is the AI-generated visual concept the layout follows. Its photograph, labels and scores are illustrative; they are not model output.

The implemented application follows its practical layout: a white header, essential controls, a large image area, a compact results list and restrained blue selection. The list says "Detections" and "predictions" rather than the concept's "Objects" because the model can return duplicate predictions for one object.

Captures of the current app are in `../screenshots/review-followup`; the other files under `../screenshots/` show earlier versions and are kept as evidence. Verification records distinguish real inference from controlled UI fixtures. The concept image is not updated to match the implementation.

The generation prompt is retained in `generation-prompt.txt`. It is provenance for the concept image, not an application dependency or instruction to add more features.
