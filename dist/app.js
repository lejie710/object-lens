// Object Lens: one image, one active inference, and at most one latest pending image.
import { createAnnotatedPng, resultFilename } from './png-export.js';

const MAX_BYTES = 10 * 1024 * 1024;
const MAX_PIXELS = 16_000_000;
const CONFIG_TIMEOUT_MS = 15_000;
const LOAD_TIMEOUT_MS = 120_000;
const INFERENCE_TIMEOUT_MS = 90_000;
const SAMPLE_TIMEOUT_MS = 15_000;
const CONTROLLED_TIMEOUT_MS = 4_000;
const DEFAULT_MINIMUM_SCORE = 0.5;
const COLORS = ['#285bd4', '#008078', '#a36b00', '#9251a5', '#bb503b', '#547832'];
const byId = (id) => document.getElementById(id);
const elements = {
  fileInput: byId('file-input'), choose: byId('choose-image'), clear: byId('clear-image'),
  trySample: byId('try-sample'),
  saveResult: byId('save-result'), exportMessage: byId('export-message'),
  filename: byId('filename'), dimensions: byId('image-dimensions'),
  empty: byId('empty-state'), stage: byId('image-stage'), preview: byId('image-preview'),
  boxes: byId('box-layer'), results: byId('results-list'), count: byId('result-count'),
  resultsEmpty: byId('results-empty'), selectionHelp: byId('selection-help'),
  minimumScore: byId('minimum-score'), minimumScoreValue: byId('minimum-score-value'),
  filterSummary: byId('filter-summary'),
  status: byId('status'), indicator: byId('status-indicator'),
  modelLoading: byId('model-loading'), modelLoadingStage: byId('model-loading-stage'),
  modelLoadingProgress: byId('model-loading-progress'), modelLoadingDetail: byId('model-loading-detail'),
  errorNotice: byId('error-notice'), error: byId('error-message'), retry: byId('retry-detection'),
};

let revision = 0;
let currentImage = null;
let pendingImage = null;
let activeRequest = null;
let worker = null;
let modelReady = false;
let modelFailed = false;
let testMode = false;
let configReady = false;
let configRequest = null;
let preparingImageId = null;
let loadTimer = null;
let inferenceTimer = null;
let currentPredictions = null;
let selectedPredictionId = null;
let sampleRequest = null;
let exportRevision = 0;
let exportBusy = false;
let modelFileStarted = false;
let modelFileLoaded = false;

function showModelLoading() {
  modelFileStarted = false;
  modelFileLoaded = false;
  elements.modelLoading.hidden = false;
  elements.modelLoading.dataset.phase = 'preparing';
  elements.modelLoadingStage.textContent = 'Loading detection files…';
  elements.modelLoadingProgress.removeAttribute('value');
  elements.modelLoadingDetail.textContent = 'You can choose an image while this loads.';
}

function updateModelLoading(data) {
  if (modelReady || modelFailed || elements.modelLoading.hidden) return;
  if (!['initiate', 'download', 'progress', 'done'].includes(data.status)) return;
  const isModel = typeof data.file === 'string' && /\.onnx$/i.test(data.file);
  if (!isModel) {
    // Small settings files may finish after the model starts. Do not let their
    // individual progress replace the model's progress or initialization stage.
    if (modelFileStarted || modelFileLoaded) return;
    elements.modelLoadingStage.textContent = 'Loading detection settings…';
    elements.modelLoadingProgress.removeAttribute('value');
    elements.modelLoadingDetail.textContent = 'Preparing the files needed for object detection.';
    return;
  }
  if (data.status === 'done') {
    modelFileLoaded = true;
    elements.modelLoading.dataset.phase = 'initializing';
    elements.modelLoadingStage.textContent = 'Starting the detector…';
    elements.modelLoadingProgress.removeAttribute('value');
    elements.modelLoadingDetail.textContent = 'Model received. Loading and initializing the browser runtime.';
    return;
  }
  if (modelFileLoaded) return;
  modelFileStarted = true;
  elements.modelLoading.dataset.phase = 'downloading';
  elements.modelLoadingStage.textContent = 'Loading detection model…';
  if (Number.isFinite(data.loaded) && Number.isFinite(data.total) && data.total > 0) {
    const received = Math.max(0, Math.min(data.loaded, data.total));
    const percentage = received / data.total * 100;
    elements.modelLoadingProgress.value = percentage;
    elements.modelLoadingDetail.textContent = `${(received / 1_000_000).toFixed(1)} of ${(data.total / 1_000_000).toFixed(1)} MB received (${Math.floor(percentage)}%).`;
  } else {
    elements.modelLoadingProgress.removeAttribute('value');
    elements.modelLoadingDetail.textContent = 'Receiving the model. Download size is not available yet.';
  }
}

function visiblePredictions() {
  const minimum = Number(elements.minimumScore.value);
  return (currentPredictions || []).filter(({ score }) => score >= minimum);
}

function updateExportButton() {
  elements.saveResult.disabled = exportBusy || !currentImage || visiblePredictions().length === 0;
  elements.saveResult.textContent = exportBusy ? 'Preparing PNG…' : 'Save result';
}

function invalidateExport() {
  exportRevision += 1;
  exportBusy = false;
  elements.exportMessage.textContent = '';
  elements.exportMessage.dataset.kind = '';
  updateExportButton();
}

async function saveResult() {
  const predictions = visiblePredictions();
  if (exportBusy || !currentImage || !predictions.length) return;
  const snapshot = currentImage;
  const minimum = Number(elements.minimumScore.value);
  const token = ++exportRevision;
  exportBusy = true;
  elements.exportMessage.textContent = '';
  elements.exportMessage.dataset.kind = '';
  updateExportButton();
  try {
    const blob = await createAnnotatedPng(snapshot, predictions);
    // Clear, image replacement and filter changes all retire an older export.
    if (token !== exportRevision || snapshot.id !== revision) return;
    const url = URL.createObjectURL(blob);
    try {
      const link = document.createElement('a');
      link.href = url;
      link.download = resultFilename(snapshot.filename, minimum);
      document.body.append(link);
      link.click();
      link.remove();
    } finally {
      // Give the browser time to consume the download before releasing its URL.
      setTimeout(() => URL.revokeObjectURL(url), 30_000);
    }
    elements.exportMessage.textContent = 'PNG download started.';
  } catch (error) {
    if (token !== exportRevision || snapshot.id !== revision) return;
    console.error('Object Lens PNG export:', error);
    elements.exportMessage.dataset.kind = 'error';
    elements.exportMessage.textContent = error.name === 'TimeoutError'
      ? 'Preparing the PNG took too long. Try Save result again.'
      : 'The PNG could not be prepared. Try Save result again.';
  } finally {
    if (token === exportRevision) {
      exportBusy = false;
      updateExportButton();
    }
  }
}

function setState(state, text) {
  document.documentElement.dataset.state = state;
  elements.status.textContent = text;
  elements.indicator.dataset.kind = state;
  elements.stage.setAttribute('aria-busy', String(state === 'processing' || state === 'loading'));
}

function clearError() {
  elements.errorNotice.hidden = true;
  elements.error.textContent = '';
  elements.retry.hidden = true;
}

function showError(message, { retry = false } = {}) {
  elements.error.textContent = message;
  elements.errorNotice.hidden = false;
  elements.retry.hidden = !retry;
  elements.clear.disabled = false;
  elements.resultsEmpty.textContent = 'No results to display.';
  setState('error', 'Action needed');
}

function clearRenderedResults() {
  elements.results.replaceChildren();
  elements.boxes.replaceChildren();
  elements.count.textContent = '0';
  elements.resultsEmpty.hidden = false;
  elements.selectionHelp.hidden = true;
}

function clearResults() {
  currentPredictions = null;
  selectedPredictionId = null;
  clearRenderedResults();
  elements.minimumScore.disabled = true;
  elements.minimumScore.value = String(DEFAULT_MINIMUM_SCORE);
  elements.minimumScoreValue.value = DEFAULT_MINIMUM_SCORE.toFixed(2);
  elements.minimumScore.setAttribute('aria-valuetext', DEFAULT_MINIMUM_SCORE.toFixed(2));
  elements.filterSummary.textContent = '';
  elements.filterSummary.hidden = true;
  invalidateExport();
}

function stopWorker() {
  clearTimeout(loadTimer);
  clearTimeout(inferenceTimer);
  loadTimer = null;
  inferenceTimer = null;
  const previous = worker;
  worker = null;
  previous?.terminate();
  activeRequest = null;
  modelReady = false;
}

function failWorker(message) {
  stopWorker();
  modelFailed = true;
  elements.modelLoading.hidden = true;
  pendingImage = currentImage;
  clearResults();
  showError(message, { retry: true });
}

function workerTimedOut(instance, stage) {
  if (instance !== worker) return;
  console.error(`Object Lens ${stage} timed out.`);
  failWorker(stage === 'load'
    ? 'The detection model took too long to load. Try again or reload the page.'
    : 'Image analysis took too long. Try again or choose another image.');
}

function removeImage() {
  preparingImageId = null;
  currentImage = null;
  pendingImage = null;
  elements.stage.hidden = true;
  elements.preview.removeAttribute('src');
  elements.preview.alt = 'Selected image for object detection';
  elements.empty.hidden = false;
  elements.filename.textContent = 'No image selected';
  elements.filename.removeAttribute('title');
  elements.dimensions.textContent = '';
  elements.dimensions.hidden = true;
  clearResults();
}

function clearWorkspace() {
  revision += 1;
  cancelSampleLoad();
  removeImage();
  clearError();
  elements.fileInput.value = '';
  elements.clear.disabled = true;
  elements.resultsEmpty.textContent = 'Detections will appear here.';
  if (modelFailed) {
    showError('Object detection is unavailable. Try again to restart the detector.', { retry: true });
  } else {
    setState(modelReady ? 'ready' : 'loading', modelReady ? 'Ready to choose an image' : 'Preparing object detection…');
  }
}

function readDataURL(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error('The image file could not be read. Choose another JPEG or PNG.'));
    reader.readAsDataURL(file);
  });
}

// Inspect encoded dimensions before decoding, so an oversized compressed image
// can be rejected without asking the browser to allocate its entire pixel buffer.
function encodedDimensions(bytes) {
  const png = [137, 80, 78, 71, 13, 10, 26, 10].every((value, index) => bytes[index] === value);
  if (png) {
    if (bytes.length < 24) throw new Error('This PNG could not be read. Choose a different image.');
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    return { width: view.getUint32(16), height: view.getUint32(20) };
  }
  if (bytes[0] !== 255 || bytes[1] !== 216) {
    throw new Error('Choose a JPEG or PNG image. Other file formats are not supported.');
  }
  let offset = 2;
  while (offset + 3 < bytes.length) {
    if (bytes[offset] !== 255) break;
    while (bytes[offset] === 255) offset += 1;
    const marker = bytes[offset++];
    if (marker === 217 || marker === 218) break;
    if (marker === 1 || (marker >= 208 && marker <= 215)) continue;
    if (offset + 1 >= bytes.length) break;
    const length = (bytes[offset] << 8) + bytes[offset + 1];
    if (length < 2 || offset + length > bytes.length) break;
    const isFrame = marker >= 192 && marker <= 207 && ![196, 200, 204].includes(marker);
    if (isFrame && length >= 7) {
      return {
        width: (bytes[offset + 5] << 8) + bytes[offset + 6],
        height: (bytes[offset + 3] << 8) + bytes[offset + 4],
      };
    }
    offset += length;
  }
  throw new Error('This JPEG could not be read. Choose a different image.');
}

function checkDimensions({ width, height }) {
  if (!width || !height) throw new Error('This image has invalid dimensions. Choose a different image.');
  if (width * height > MAX_PIXELS) throw new Error('This image exceeds 16 megapixels. Resize it and try again.');
}

function finishSampleLoad(request) {
  clearTimeout(request.timer);
  if (sampleRequest !== request) return;
  sampleRequest = null;
  elements.trySample.disabled = false;
  elements.trySample.textContent = 'Try sample';
}

function cancelSampleLoad() {
  if (!sampleRequest) return;
  const request = sampleRequest;
  finishSampleLoad(request);
  request.controller.abort();
}

function beginImageSelection() {
  const id = ++revision;
  cancelSampleLoad();
  clearError();
  removeImage();
  preparingImageId = id;
  elements.clear.disabled = false;
  elements.resultsEmpty.textContent = 'Your image is being prepared.';
  setState('loading', 'Reading image…');
  return id;
}

async function trySample() {
  if (sampleRequest) return;
  // Reserve the image revision before fetch, so a late sample cannot replace a newer choice.
  const id = beginImageSelection();
  const request = { id, controller: new AbortController(), timer: null, timedOut: false };
  sampleRequest = request;
  elements.trySample.disabled = true;
  elements.trySample.textContent = 'Loading sample…';
  elements.resultsEmpty.textContent = 'The sample image is being prepared.';
  setState('loading', 'Loading sample…');
  request.timer = setTimeout(() => {
    if (sampleRequest !== request) return;
    request.timedOut = true;
    request.controller.abort();
  }, SAMPLE_TIMEOUT_MS);
  try {
    const response = await fetch('./samples/coffee.png', { signal: request.controller.signal, cache: 'no-store' });
    if (!response.ok) throw new Error(`Sample request returned ${response.status}.`);
    const blob = await response.blob();
    if (id !== revision || sampleRequest !== request) return;
    finishSampleLoad(request);
    // The sample uses the same validation, decoding and inference path as a selected file.
    await selectFile(new File([blob], 'coffee.png', { type: blob.type || 'image/png' }), id);
  } catch (error) {
    if (id !== revision || sampleRequest !== request) return;
    console.error('Object Lens sample loading:', error);
    showError(request.timedOut
      ? 'The sample took too long to load. Try sample again or choose an image.'
      : 'The sample image could not be loaded. Try sample again or choose an image.');
  } finally {
    finishSampleLoad(request);
    if (preparingImageId === id) preparingImageId = null;
  }
}

async function selectFile(file, reservedId) {
  if (!file) return;
  const id = reservedId ?? beginImageSelection();
  if (id !== revision) return;
  setState('loading', 'Reading image…');
  try {
    if (file.size > MAX_BYTES) throw new Error('This image exceeds 10 MiB. Choose a smaller JPEG or PNG.');
    const bytes = new Uint8Array(await file.arrayBuffer());
    if (id !== revision) return;
    checkDimensions(encodedDimensions(bytes));
    const image = await readDataURL(file);
    if (id !== revision) return;
    const decoded = new Image();
    decoded.src = image;
    try {
      await decoded.decode();
    } catch {
      throw new Error('This image could not be read. Choose a different JPEG or PNG.');
    }
    if (id !== revision) return;
    checkDimensions({ width: decoded.naturalWidth, height: decoded.naturalHeight });
    currentImage = { id, image, filename: file.name, width: decoded.naturalWidth, height: decoded.naturalHeight };
    if (preparingImageId === id) preparingImageId = null;
    elements.preview.width = currentImage.width;
    elements.preview.height = currentImage.height;
    elements.preview.src = image;
    elements.preview.alt = `Selected image: ${file.name}`;
    elements.stage.style.setProperty('--image-ratio', String(currentImage.width / currentImage.height));
    elements.stage.hidden = false;
    elements.empty.hidden = true;
    elements.filename.textContent = file.name;
    elements.filename.title = file.name;
    elements.dimensions.textContent = `${currentImage.width} × ${currentImage.height}`;
    elements.dimensions.hidden = false;
    pendingImage = currentImage;
    if (!configReady) {
      // A valid selection waits for configuration or retries a failed bootstrap.
      clearError();
      setState('loading', 'Preparing object detection…');
      elements.resultsEmpty.textContent = 'Detections will appear when processing finishes.';
      initialize();
    } else if (modelFailed) {
      // A new valid image is also a recovery action after a failed worker.
      clearError();
      createWorker();
    } else {
      const message = !modelReady ? 'Preparing object detection…'
        : activeRequest !== null ? 'Waiting for previous analysis…' : 'Analyzing image…';
      setState(modelReady ? 'processing' : 'loading', message);
      elements.resultsEmpty.textContent = 'Detections will appear when processing finishes.';
      startPendingInference();
    }
  } catch (error) {
    if (id !== revision) return;
    showError(error.message);
  } finally {
    if (preparingImageId === id) preparingImageId = null;
  }
}

function startPendingInference() {
  if (!worker || !modelReady || activeRequest !== null || !pendingImage) return;
  const image = pendingImage;
  pendingImage = null;
  if (image.id !== revision) return;
  activeRequest = image.id;
  setState('processing', 'Analyzing image…');
  const instance = worker;
  clearTimeout(inferenceTimer);
  inferenceTimer = setTimeout(() => {
    if (activeRequest === image.id) workerTimedOut(instance, 'infer');
  }, testMode ? CONTROLLED_TIMEOUT_MS : INFERENCE_TIMEOUT_MS);
  try {
    instance.postMessage({ type: 'infer', id: image.id, image: image.image, filename: image.filename });
  } catch (error) {
    console.error('Object Lens inference could not start:', error);
    failWorker('Object detection stopped unexpectedly. Try again or choose another image.');
  }
}

function selectResult(id) {
  selectedPredictionId = id;
  const rows = elements.results.querySelectorAll('.result-row');
  const boxes = elements.boxes.querySelectorAll('.detection-box');
  rows.forEach((row) => {
    const selected = row.dataset.predictionId === String(id);
    row.classList.toggle('is-selected', selected);
    row.setAttribute('aria-pressed', String(selected));
  });
  boxes.forEach((box) => box.classList.toggle('is-selected', box.dataset.predictionId === String(id)));
}

function renderResults(predictions) {
  if (!Array.isArray(predictions)) throw new Error('The detector returned an unreadable result.');
  const clean = predictions.map((prediction, index) => {
    if (!prediction || typeof prediction !== 'object' || Array.isArray(prediction)) {
      throw new Error('The detector returned an unreadable result.');
    }
    const { label, score, box } = prediction;
    if (typeof label !== 'string' || !label.trim() || !Number.isFinite(score) || score < 0 || score > 1 ||
        !box || typeof box !== 'object' || Array.isArray(box) ||
        !['xmin', 'ymin', 'xmax', 'ymax'].every((key) => Number.isFinite(box[key]))) {
      throw new Error('The detector returned an unreadable result.');
    }
    const bounds = Object.fromEntries(['xmin', 'ymin', 'xmax', 'ymax']
      .map((key) => [key, Math.max(0, Math.min(1, box[key]))]));
    if (bounds.xmax <= bounds.xmin || bounds.ymax <= bounds.ymin) throw new Error('The detector returned an invalid box.');
    return { id: index, label, score, box: bounds, color: COLORS[index % COLORS.length] };
  });
  currentPredictions = clean;
  selectedPredictionId = null;
  elements.minimumScore.disabled = clean.length === 0;
  renderFilteredResults();
}

function renderFilteredResults() {
  if (currentPredictions === null) return;
  invalidateExport();
  const minimum = Number(elements.minimumScore.value);
  elements.minimumScoreValue.value = minimum.toFixed(2);
  elements.minimumScore.setAttribute('aria-valuetext', minimum.toFixed(2));
  // Keep original scores and identities. Display rounding must not change filtering.
  const visible = visiblePredictions();
  clearRenderedResults();
  visible.forEach(({ id, label, score, box, color }) => {
    const rectangle = document.createElement('div');
    rectangle.className = 'detection-box';
    rectangle.dataset.predictionId = String(id);
    rectangle.dataset.label = label;
    for (const [key, value] of Object.entries(box)) rectangle.dataset[key] = String(value);
    rectangle.style.setProperty('--object-color', color);
    Object.assign(rectangle.style, {
      left: `${box.xmin * 100}%`, top: `${box.ymin * 100}%`,
      width: `${(box.xmax - box.xmin) * 100}%`, height: `${(box.ymax - box.ymin) * 100}%`,
    });
    rectangle.classList.toggle('label-inside', box.ymin < 0.065);
    rectangle.classList.toggle('label-right', box.xmin > 0.65);
    const tag = document.createElement('span');
    tag.className = 'box-label';
    tag.textContent = label;
    rectangle.append(tag);
    elements.boxes.append(rectangle);

    const item = document.createElement('li');
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'result-row';
    button.dataset.predictionId = String(id);
    button.dataset.label = label;
    button.dataset.score = String(score);
    button.setAttribute('aria-pressed', 'false');
    button.setAttribute('aria-label', `Select ${label}, model score ${score.toFixed(2)}`);
    button.style.setProperty('--object-color', color);
    const dot = document.createElement('span');
    dot.className = 'object-dot';
    dot.setAttribute('aria-hidden', 'true');
    const name = document.createElement('span');
    name.className = 'object-name';
    name.textContent = label;
    const modelScore = document.createElement('span');
    modelScore.className = 'object-score';
    modelScore.textContent = score.toFixed(2);
    button.append(dot, name, modelScore);
    button.addEventListener('click', () => selectResult(id));
    item.append(button);
    elements.results.append(item);
  });
  elements.count.textContent = String(visible.length);
  elements.resultsEmpty.hidden = visible.length > 0;
  elements.selectionHelp.hidden = visible.length === 0;
  const summary = `Showing ${visible.length} of ${currentPredictions.length} predictions.`;
  elements.filterSummary.textContent = summary;
  elements.filterSummary.hidden = false;
  if (visible.length) {
    const selection = visible.find(({ id }) => id === selectedPredictionId) || visible[0];
    selectResult(selection.id);
    setState('complete', `Detection complete. ${summary}`);
  } else if (currentPredictions.length) {
    selectedPredictionId = null;
    elements.resultsEmpty.textContent = 'No predictions meet this minimum score.';
    setState('filtered-empty', `Detection complete. ${summary} Lower the minimum score to see predictions.`);
  } else {
    selectedPredictionId = null;
    elements.resultsEmpty.textContent = 'No supported objects were detected in this image.';
    setState('empty', 'Detection complete. No predictions.');
  }
}

function onWorkerMessage({ data }) {
  if (data.type === 'progress') {
    updateModelLoading(data);
    return;
  }
  if (data.type === 'ready') {
    clearTimeout(loadTimer);
    loadTimer = null;
    modelReady = true;
    modelFailed = false;
    elements.modelLoading.hidden = true;
    if (pendingImage) startPendingInference();
    else if (!currentImage && !sampleRequest && preparingImageId === null && elements.errorNotice.hidden) {
      setState('ready', 'Ready to choose an image');
    }
    return;
  }
  if (data.type === 'result' || (data.type === 'error' && data.stage === 'infer')) {
    if (data.id !== activeRequest) return;
    clearTimeout(inferenceTimer);
    inferenceTimer = null;
    activeRequest = null;
    if (data.id === revision && currentImage?.id === revision) {
      if (data.type === 'result') {
        try {
          renderResults(data.predictions);
        } catch (error) {
          console.error('Object Lens result validation:', error);
          clearResults();
          showError('The detector returned an invalid result. Try again or choose another image.', { retry: true });
        }
      } else {
        console.error('Object Lens inference:', data.message);
        showError('This image could not be analyzed. Try again or choose another image.', { retry: true });
      }
    }
    startPendingInference();
    return;
  }
  if (data.type === 'error' && data.stage === 'load') {
    console.error('Object Lens model loading:', data.message);
    failWorker('Object detection could not start. Try again or reload the page.');
  }
}

function createWorker() {
  stopWorker();
  modelFailed = false;
  showModelLoading();
  try {
    const instance = new Worker(testMode ? './test-worker.js' : './worker.js', { type: 'module' });
    worker = instance;
    instance.onmessage = (event) => { if (instance === worker) onWorkerMessage(event); };
    instance.onerror = (error) => {
      if (instance !== worker) return;
      console.error('Object Lens worker:', error.message);
      failWorker(modelReady
        ? 'Object detection stopped unexpectedly. Try again or choose another image.'
        : 'Object detection could not start. Try again or reload the page.');
    };
    // Background startup must not dismiss an input error or an active file read.
    if (elements.errorNotice.hidden && preparingImageId === null) {
      setState('loading', 'Preparing object detection…');
    }
    // Controlled startup progress tests use the same deadline as the real model.
    loadTimer = setTimeout(() => workerTimedOut(instance, 'load'), LOAD_TIMEOUT_MS);
    instance.postMessage({ type: 'load' });
  } catch (error) {
    console.error('Object Lens worker creation:', error);
    failWorker('Object detection could not start. Try again or reload the page.');
  }
}

elements.choose.addEventListener('click', () => elements.fileInput.click());
elements.trySample.addEventListener('click', trySample);
elements.saveResult.addEventListener('click', saveResult);
elements.fileInput.addEventListener('change', () => {
  const file = elements.fileInput.files[0];
  elements.fileInput.value = '';
  selectFile(file);
});
elements.clear.addEventListener('click', clearWorkspace);
elements.minimumScore.addEventListener('input', renderFilteredResults);
elements.retry.addEventListener('click', () => {
  clearError();
  if (preparingImageId !== null) {
    setState('loading', sampleRequest ? 'Loading sample…' : 'Reading image…');
  }
  if (currentImage) {
    currentImage = { ...currentImage, id: ++revision };
    pendingImage = currentImage;
    clearResults();
    elements.resultsEmpty.textContent = 'Detections will appear when processing finishes.';
  }
  if (!configReady) {
    if (preparingImageId === null) setState('loading', 'Preparing object detection…');
    initialize();
  } else if (modelFailed || !worker) createWorker();
  else startPendingInference();
});

async function initialize() {
  if (configReady || configRequest) return;
  const request = { controller: new AbortController(), timer: null, timedOut: false };
  configRequest = request;
  modelFailed = false;
  showModelLoading();
  if (elements.errorNotice.hidden && preparingImageId === null) {
    setState('loading', 'Preparing object detection…');
  }
  request.timer = setTimeout(() => {
    request.timedOut = true;
    request.controller.abort();
  }, CONFIG_TIMEOUT_MS);
  try {
    const response = await fetch('./runtime-config.json', {
      cache: 'no-store', signal: request.controller.signal,
    });
    if (!response.ok) throw new Error('Local application configuration is unavailable.');
    const config = await response.json();
    if (!config || typeof config.testMode !== 'boolean') {
      throw new Error('Application configuration must specify a boolean testMode.');
    }
    configReady = true;
    testMode = config.testMode;
    byId('test-mode-notice').hidden = !testMode;
    createWorker();
  } catch (error) {
    modelFailed = true;
    elements.modelLoading.hidden = true;
    console.error('Object Lens initialization:', error);
    showError(request.timedOut
      ? 'The app settings took too long to load. Try again or reload the page.'
      : 'Object detection could not start. Check your connection and try again.', { retry: true });
  } finally {
    clearTimeout(request.timer);
    if (configRequest === request) configRequest = null;
  }
}

initialize();
