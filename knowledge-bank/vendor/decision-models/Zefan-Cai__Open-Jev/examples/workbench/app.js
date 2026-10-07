import {MAX_ROWS, presets, parseCategories, parseCSV, makeRequest, readAnswer, resultsCSV} from './logic.mjs';

const $ = id => document.getElementById(id);
let mode = 'text', preset = 'support', csv = null, rows = [], running = false, stop = false;
let service = null, illustrative = false, fileVersion = 0, exportHeaders = [];
const labels = {pending: 'Pending', complete: 'Complete', error: 'Error', stopped: 'Not processed', illustrative: 'Illustrative example'};

function node(tag, text, className) {
  const element = document.createElement(tag);
  element.textContent = text;
  if (className) element.className = className;
  return element;
}

function setError(message) {
  $('error').textContent = message;
  $('error').hidden = !message;
}

function inputRows() {
  if (mode === 'csv') {
    if (!csv) throw new Error('Choose a UTF-8 CSV file first.');
    return csv.rows.map((row, index) => ({index: index + 1, text: row[Number($('text-column').value)] ?? '', original: [...row]}));
  }
  const values = $('input-text').value.split(/\r?\n/).filter(text => text.trim());
  if (!values.length) throw new Error('Add the text to classify, one message per line.');
  if (values.length > MAX_ROWS) throw new Error(`Process up to ${MAX_ROWS} rows at a time. Split larger inputs into batches.`);
  return values.map((text, index) => ({index: index + 1, text}));
}

function renderRows() {
  $('result-rows').replaceChildren();
  for (const row of rows) {
    const tr = document.createElement('tr');
    tr.append(node('td', row.index), node('td', row.text), node('td', row.label || '—'),
      node('td', row.probability == null ? '—' : `${(row.probability * 100).toFixed(1)}%`),
      node('td', row.error ? `${labels[row.status]}: ${row.error}` : labels[row.status]));
    $('result-rows').append(tr);
  }
  $('empty-state').hidden = rows.length > 0;
  $('results').hidden = rows.length === 0;
  $('download').disabled = !rows.length || running;
  $('result-summary').textContent = illustrative ? 'Illustrative example · Categories are preset. No model was called and no model probabilities are shown.' :
    rows.length ? `${rows.filter(r => r.status === 'complete').length} complete · ${rows.filter(r => r.status === 'error').length} errors · ${rows.filter(r => ['pending', 'stopped'].includes(r.status)).length} not processed` : 'Your results will appear here.';
}

function note() {
  $('mode-note').textContent = illustrative ? 'This illustration uses preset text and categories. Your edited inputs are unchanged. To classify your own text, connect a model and select “Start classification”.' :
    service ? 'A real model is connected. Starting classification sends your text to this Open-Jev service. Candidate probability is not measured accuracy.' :
    'You can edit a task, import and preview a CSV, or export task settings. Select “Show an example” to explore the workflow. A connected model is required to classify your own text.';
  $('setup-note').hidden = !!service;
}

function refreshPreview() {
  $('input-preview').replaceChildren();
  try {
    const inputs = inputRows();
    $('input-preview').append(node('p', `${inputs.length} rows · Previewing the first ${Math.min(inputs.length, 3)}`));
    inputs.slice(0, 3).forEach(row => $('input-preview').append(node('p', `${row.index}. ${row.text || '(empty; will be marked as an error)'}`)));
    $('request-preview').textContent = JSON.stringify(makeRequest(inputs[0].text, $('instructions').value, parseCategories($('categories').value)), null, 2);
  } catch (error) {
    $('request-preview').textContent = error.message;
  }
}

function invalidate() {
  if (running) return;
  rows = []; illustrative = false; exportHeaders = []; setError(''); $('progress').textContent = '';
  renderRows(); refreshPreview(); note();
}

function chooseMode(value) {
  mode = value; fileVersion++;
  $('text-panel').hidden = value !== 'text'; $('csv-panel').hidden = value !== 'csv';
  document.querySelectorAll('[data-mode]').forEach(button => {
    button.classList.toggle('active', button.dataset.mode === value);
    button.setAttribute('aria-pressed', String(button.dataset.mode === value));
  });
  invalidate();
}

function choosePreset(value) {
  preset = value;
  $('instructions').value = presets[value].instructions;
  $('categories').value = presets[value].categories;
  document.querySelectorAll('[data-preset]').forEach(button => {
    button.classList.toggle('active', button.dataset.preset === value);
    button.setAttribute('aria-pressed', String(button.dataset.preset === value));
  });
  invalidate();
}

function freeze(value) {
  running = value;
  document.querySelectorAll('input, select, textarea, button').forEach(element => {
    if (element.id !== 'stop') element.disabled = value;
  });
  $('stop').hidden = !value; $('stop').disabled = false;
  $('run').disabled = value || !service;
  $('download').disabled = value || !rows.length;
  $('text-column').disabled = value || !csv;
}

async function checkHealth() {
  try {
    const response = await fetch('/health', {signal: AbortSignal.timeout(10000)});
    const data = await response.json();
    if (data.status === 'ready' && typeof data.model === 'string') {
      service = data;
      $('health').textContent = `Model connected · ${data.checkpoint || data.model}${data.device ? ' · ' + data.device.toUpperCase() : ''}`;
      $('health').dataset.state = 'connected';
    } else if (data.status === 'loading') {
      $('health').textContent = 'Model loading. You can edit your task while you wait…';
      $('health').dataset.state = 'checking';
      setTimeout(checkHealth, 10000);
    } else throw new Error('not ready');
  } catch (_) {
    service = null; $('health').textContent = 'Interface preview · No model connected'; $('health').dataset.state = 'disconnected';
  }
  $('run').disabled = running || !service; note();
}

$('run').addEventListener('click', async () => {
  if (running || !service) return;
  setError('');
  let categories, instructions, inputs;
  try {
    inputs = inputRows(); categories = parseCategories($('categories').value); instructions = $('instructions').value;
    if (!instructions.trim()) throw new Error('Enter classification instructions.');
    const limit = service.limits?.max_candidates;
    if (limit && Object.keys(categories).length > limit) throw new Error(`This service supports up to ${limit} categories per request.`);
  } catch (error) { setError(error.message); return; }
  rows = inputs.map(row => ({...row, status: 'pending'})); illustrative = false; stop = false;
  exportHeaders = mode === 'csv' ? [...csv.headers] : [];
  freeze(true); renderRows(); note();
  for (const [index, row] of rows.entries()) {
    if (stop) break;
    $('progress').textContent = `Processing ${index + 1} / ${rows.length}…`;
    try {
      if (service.limits?.max_text_chars && row.text.length > service.limits.max_text_chars) throw new Error(`Text exceeds this service limit of ${service.limits.max_text_chars} characters.`);
      const request = makeRequest(row.text, instructions, categories);
      let response;
      try {
        response = await fetch('/v1/systemone', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(request), signal: AbortSignal.timeout(300000)});
      } catch (_) { stop = true; throw new Error('The connection was interrupted or timed out. The server may still be processing this row. Later rows were not submitted; check the service before continuing.'); }
      let data;
      try { data = await response.json(); }
      catch (_) { stop = true; throw new Error('The service response could not be read. Later rows were not submitted.'); }
      if (!response.ok) {
        if (response.status !== 422) stop = true;
        throw new Error(response.status === 429 ? 'The service is busy. Later rows were not submitted. Try again when it is available.' : (data.error || `The service returned HTTP ${response.status}`));
      }
      try { Object.assign(row, readAnswer(data, categories)); }
      catch (error) { stop = true; throw error; }
      row.status = 'complete';
    } catch (error) { row.status = 'error'; row.error = error.message; }
    renderRows();
  }
  rows.filter(row => row.status === 'pending').forEach(row => { row.status = 'stopped'; });
  freeze(false); renderRows();
  $('progress').textContent = stop ? 'Later rows were not submitted. Completed results are available to download; a timed-out request may still be running.' : 'Batch finished. Review the results before using them.';
});

$('stop').addEventListener('click', () => {
  stop = true; $('stop').disabled = true;
  $('progress').textContent = 'Stopping after the current request finishes. No later rows will be submitted.';
});

function download(filename, text, type) {
  const url = URL.createObjectURL(new Blob([text], {type}));
  const link = document.createElement('a'); link.href = url; link.download = filename; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
$('download').addEventListener('click', () => download(illustrative ? 'open-jev-illustrative-example.csv' : 'open-jev-results.csv', resultsCSV(rows, exportHeaders), 'text/csv;charset=utf-8'));
$('download-config').addEventListener('click', () => {
  try {
    const categories = parseCategories($('categories').value);
    if (!$('instructions').value.trim()) throw new Error('Enter classification instructions.');
    download('open-jev-task.json', JSON.stringify({instructions: $('instructions').value, categories}, null, 2), 'application/json');
  } catch (error) { setError(error.message); }
});
$('show-demo').addEventListener('click', () => {
  rows = presets[preset].text.split('\n').map((text, index) => ({index: index + 1, text, label: presets[preset].illustrative[index], status: 'illustrative'}));
  illustrative = true; exportHeaders = []; setError(''); refreshPreview(); renderRows(); note();
});
$('csv-file').addEventListener('change', async event => {
  invalidate(); csv = null; $('text-column').disabled = true;
  const file = event.target.files[0]; const version = ++fileVersion;
  if (!file) { refreshPreview(); return; }
  try {
    if (file.size > 2 * 1024 * 1024) throw new Error('Choose a UTF-8 CSV file no larger than 2 MB.');
    const text = new TextDecoder('utf-8', {fatal: true}).decode(await file.arrayBuffer());
    if (version !== fileVersion) return;
    csv = parseCSV(text); $('text-column').replaceChildren(); $('text-column').disabled = false;
    csv.headers.forEach((header, index) => { const option = node('option', header); option.value = index; $('text-column').append(option); });
    refreshPreview();
  } catch (error) { if (version === fileVersion) { csv = null; setError(error.message); refreshPreview(); } }
});
document.querySelectorAll('[data-preset]').forEach(button => button.addEventListener('click', () => choosePreset(button.dataset.preset)));
document.querySelectorAll('[data-mode]').forEach(button => button.addEventListener('click', () => chooseMode(button.dataset.mode)));
['input-text', 'instructions', 'categories'].forEach(id => $(id).addEventListener('input', invalidate));
$('text-column').addEventListener('change', invalidate);
$('input-text').value = presets.support.text;
choosePreset('support'); chooseMode('text');
$('run').disabled = true;
checkHealth();
