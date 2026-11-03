// CONTROLLED TEST DATA. This worker never runs an AI model.
// Available only from serve.py --test-mode, with an explicit UI indicator.
const samplePredictions = {
  normal: [
    { label: 'laptop', score: 0.97, box: { xmin: 0.1, ymin: 0.2, xmax: 0.7, ymax: 0.85 } },
    { label: 'cup', score: 0.91, box: { xmin: 0.75, ymin: 0.5, xmax: 0.9, ymax: 0.8 } },
  ],
  dog: [{ label: 'dog', score: 0.93, box: { xmin: 0.15, ymin: 0.2, xmax: 0.75, ymax: 0.9 } }],
  car: [{ label: 'car', score: 0.95, box: { xmin: 0.05, ymin: 0.3, xmax: 0.95, ymax: 0.8 } }],
  // Deliberate values around the display-filter boundary. The first score rounds
  // to 0.80 in the UI but is below 0.80 and must not pass that minimum.
  boundary: [
    { label: 'spoon', score: 0.7999, box: { xmin: 0.05, ymin: 0.15, xmax: 0.2, ymax: 0.8 } },
    { label: 'cup', score: 0.8, box: { xmin: 0.3, ymin: 0.3, xmax: 0.55, ymax: 0.7 } },
    { label: 'bottle', score: 0.95, box: { xmin: 0.7, ymin: 0.1, xmax: 0.9, ymax: 0.9 } },
  ],
  // Equal class labels still identify different predictions and image locations.
  duplicateSpoons: [
    { label: 'spoon', score: 0.7, box: { xmin: 0.1, ymin: 0.2, xmax: 0.25, ymax: 0.8 } },
    { label: 'spoon', score: 0.95, box: { xmin: 0.65, ymin: 0.15, xmax: 0.8, ymax: 0.9 } },
  ],
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
    if (filename.includes('score-boundary')) predictions = samplePredictions.boundary;
    if (filename.includes('duplicate-spoons')) predictions = samplePredictions.duplicateSpoons;
    if (filename.startsWith('empty')) predictions = [];
    self.postMessage({ type: 'result', id: data.id, predictions, durationMs: delay });
  }, delay);
};
