// Real CPU inference in a dedicated worker. No hosted inference API is used.
import { pipeline, env } from './assets/runtime/transformers.min.js';

env.allowLocalModels = true;
env.allowRemoteModels = false;
env.localModelPath = '/assets/models/';
env.backends.onnx.wasm.wasmPaths = '/assets/runtime/';
env.backends.onnx.wasm.numThreads = 1;

let detector;
let loading;
let queue = Promise.resolve();

async function load() {
  if (!loading) {
    loading = pipeline('object-detection', 'Xenova/detr-resnet-50', {
      quantized: true,
      progress_callback: (event) => {
        if (event.status === 'progress') {
          self.postMessage({ type: 'progress', progress: event.progress });
        }
      },
    }).then((value) => { detector = value; return value; }).catch((error) => {
      loading = undefined;
      throw error;
    });
  }
  return loading;
}

self.onmessage = ({ data }) => {
  if (data.type === 'load') {
    load().then(() => self.postMessage({ type: 'ready' })).catch((error) => {
      self.postMessage({ type: 'error', stage: 'load', message: String(error.message || error) });
    });
  }
  if (data.type === 'infer') {
    queue = queue.then(async () => {
      try {
        await load();
        const start = performance.now();
        const predictions = await detector(data.image, { threshold: 0.5, percentage: true });
        self.postMessage({ type: 'result', id: data.id, predictions, durationMs: performance.now() - start });
      } catch (error) {
        self.postMessage({ type: 'error', stage: 'infer', id: data.id, message: String(error.message || error) });
      }
    });
  }
};
