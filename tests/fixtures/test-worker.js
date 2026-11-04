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

// Deliberately malformed component responses. These never describe real-model output.
function invalidPredictions(kind) {
  const prediction = { ...samplePredictions.normal[0], box: { ...samplePredictions.normal[0].box } };
  switch (kind) {
    case 'not-array': return { predictions: [prediction] };
    case 'null-item': return [samplePredictions.normal[1], null];
    case 'missing-box': delete prediction.box; break;
    case 'missing-coordinate': delete prediction.box.xmax; break;
    case 'string-coordinate': prediction.box.xmin = '0.1'; break;
    case 'nonfinite-coordinate': prediction.box.ymax = Infinity; break;
    case 'empty-label': prediction.label = ''; break;
    case 'blank-label': prediction.label = '   '; break;
    case 'missing-score': delete prediction.score; break;
    case 'string-score': prediction.score = '0.97'; break;
    case 'nonfinite-score': prediction.score = NaN; break;
    case 'negative-score': prediction.score = -0.1; break;
    case 'excess-score': prediction.score = 1.1; break;
    case 'reversed-box': prediction.box.xmin = 0.8; break;
    case 'zero-area-box': prediction.box.ymax = prediction.box.ymin; break;
    case 'outside-box': prediction.box.xmin = 1.1; prediction.box.xmax = 1.4; break;
    default: throw new Error(`Unknown controlled invalid response: ${kind}`);
  }
  // A valid entry before the malformed one must not leak as a partial result.
  return [samplePredictions.normal[1], prediction];
}

const attemptedFiles = new Set();

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
    const invalidCase = /^invalid-result-(.+)\.png$/.exec(filename);
    if (invalidCase) predictions = invalidPredictions(invalidCase[1]);
    if (filename === 'invalid-once.png' && !attemptedFiles.has(filename)) {
      predictions = [null];
      attemptedFiles.add(filename);
    }
    if (filename === 'clamped-box.png') {
      predictions = [{ label: 'laptop', score: 0.97,
        box: { xmin: -0.1, ymin: -0.2, xmax: 1.2, ymax: 0.85 } }];
    }
    if (filename.includes('dog')) predictions = samplePredictions.dog;
    if (filename.includes('car')) predictions = samplePredictions.car;
    if (filename.includes('score-boundary')) predictions = samplePredictions.boundary;
    if (filename.includes('duplicate-spoons')) predictions = samplePredictions.duplicateSpoons;
    if (filename.startsWith('empty')) predictions = [];
    self.postMessage({ type: 'result', id: data.id, predictions, durationMs: delay });
  }, delay);
};
