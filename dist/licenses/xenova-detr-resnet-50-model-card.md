---
base_model: facebook/detr-resnet-50
library_name: transformers.js
---

https://huggingface.co/facebook/detr-resnet-50 with ONNX weights to be compatible with Transformers.js.


## Usage (Transformers.js)

If you haven't already, you can install the [Transformers.js](https://huggingface.co/docs/transformers.js) JavaScript library from [NPM](https://www.npmjs.com/package/@huggingface/transformers) using:
```bash
npm i @huggingface/transformers
```

**Example:** Perform object-detection with `Xenova/detr-resnet-50`.

```js
import { pipeline } from '@huggingface/transformers';

const detector = await pipeline('object-detection', 'Xenova/detr-resnet-50');

const img = 'https://huggingface.co/datasets/Xenova/transformers.js-docs/resolve/main/cats.jpg';
const output = await detector(img, { threshold: 0.9 });
// [{
//   "score": 0.9976370930671692,
//   "label": "remote",
//   "box": { "xmin": 31, "ymin": 68, "xmax": 190, "ymax": 118 }
// },
// ...
// {
//   "score": 0.9984092116355896,
//   "label": "cat",
//   "box": { "xmin": 331, "ymin": 19, "xmax": 649, "ymax": 371 }
// }]
```

## Demo

Test it out [here](https://huggingface.co/spaces/static-templates/transformers.js), or [create](https://huggingface.co/new-space?template=static-templates%2Ftransformers.js) your own object-detection demo with 1 click! 

![image/png](https://cdn-uploads.huggingface.co/production/uploads/61b253b7ac5ecaae3d1efe0c/Tum2wSnygrcAJUIDk_bCg.png)

---


Note: Having a separate repo for ONNX weights is intended to be a temporary solution until WebML gains more traction. If you would like to make your models web-ready, we recommend converting to ONNX using [🤗 Optimum](https://huggingface.co/docs/optimum/index) and structuring your repo like this one (with ONNX weights located in a subfolder named `onnx`).