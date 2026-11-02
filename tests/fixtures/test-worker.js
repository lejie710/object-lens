// CONTROLLED TEST DATA. This worker never runs an AI model.
// Available only from serve.py --test-mode, with an explicit UI indicator.
const samplePredictions = {
  normal: [
    { label: 'laptop', score: 0.97, box: { xmin: 0.1, ymin: 0.2, xmax: 0.7, ymax: 0.85 } },
    { label: 'cup', score: 0.91, box: { xmin: 0.75, ymin: 0.5, xmax: 0.9, ymax: 0.8 } },
  ],
  dog: [{ label: 'dog', score: 0.93, box: { xmin: 0.15, ymin: 0.2, xmax: 0.75, ymax: 0.9 } }],
  car: [{ label: 'car', score: 0.95, box: { xmin: 0.05, ymin: 0.3, xmax: 0.95, ymax: 0.8 } }],
};

self.onmessage = ({ data }) => {
  if (data.type === 'load') {
    self.postMessage({ type: 'ready' });
    return;
  }
  if (data.type !== 'infer') return;
  const filename = data.filename || '';
  // Deliberately simulate a worker that stays alive but never returns a result.
  if (filename.startsWith('silent')) return;
  const delay = filename.startsWith('slow-') ? 900 : 40;
  setTimeout(() => {
    if (filename.startsWith('fail')) {
      self.postMessage({ type: 'error', stage: 'infer', id: data.id,
        message: 'Deliberately simulated inference failure.' });
      return;
    }
    let predictions = samplePredictions.normal;
    if (filename.includes('dog')) predictions = samplePredictions.dog;
    if (filename.includes('car')) predictions = samplePredictions.car;
    if (filename.startsWith('empty')) predictions = [];
    self.postMessage({ type: 'result', id: data.id, predictions, durationMs: delay });
  }, delay);
};
