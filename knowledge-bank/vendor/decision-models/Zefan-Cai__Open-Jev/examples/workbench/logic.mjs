export const MAX_ROWS = 200;

export const presets = {
  support: {
    instructions: 'Choose the category that best matches the main customer request. Choose Human review if there is not enough information.',
    categories: 'Refunds: refunds, returns, or duplicate charges\nShipping: deliveries, tracking, or shipping addresses\nProduct issues: faulty, damaged, or difficult-to-use products\nHuman review: not enough information or no category applies',
    text: 'I was charged twice for this order. Please refund the duplicate charge.\nMy package has not moved in three days. Can you check it?\nThe left side of my new headphones has no sound.',
    illustrative: ['Refunds', 'Shipping', 'Product issues'],
  },
  feedback: {
    instructions: 'Choose the category that best matches the feedback. Choose Human review if there is not enough information.',
    categories: 'Feature requests: requests to add or improve a feature\nBug reports: an existing feature does not work\nHow-to questions: questions about using existing features\nHuman review: unclear feedback or no category applies',
    text: 'Please add an option to export reports as PDF.\nThe page keeps spinning after I select Save, and my changes are lost.\nWhere can I change my notification settings?',
    illustrative: ['Feature requests', 'Bug reports', 'How-to questions'],
  },
  custom: {
    instructions: 'Choose the category that best matches each message, using the definitions below.',
    categories: 'Action needed: a clear request or task to complete\nFor information: an update that requires no action\nHuman review: not enough information to decide',
    text: 'Please confirm the meeting time by Friday.\nThe product update notes for this month are available.\nAbout that thing we discussed…',
    illustrative: ['Action needed', 'For information', 'Human review'],
  },
};

export function parseCategories(text) {
  const pairs = text.split(/\r?\n/).map(line => line.trim()).filter(Boolean).map(line => {
    const separator = line.search(/[:：]/);
    const label = (separator < 0 ? line : line.slice(0, separator)).trim();
    const description = separator < 0 ? null : line.slice(separator + 1).trim() || null;
    if (!label) throw new Error('Every category needs a name.');
    return [label, description];
  });
  if (pairs.length < 2 || pairs.length > 20) throw new Error('Enter 2–20 categories, one per line.');
  if (new Set(pairs.map(([label]) => label)).size !== pairs.length) throw new Error('Category names must be unique.');
  return Object.fromEntries(pairs);
}

// RFC 4180-style comma-separated CSV, including quoted newlines and UTF-8 BOM.
export function parseCSV(source) {
  source = source.replace(/^\uFEFF/, '');
  const records = [];
  let record = [], field = '', quoted = false, closed = false, started = false;
  function finishField() { record.push(field); field = ''; closed = false; started = false; }
  function finishRecord() {
    finishField(); records.push(record); record = [];
    if (records.length > MAX_ROWS + 1) throw new Error(`Process up to ${MAX_ROWS} rows at a time. Split larger files into batches.`);
  }
  for (let i = 0; i < source.length; i++) {
    const char = source[i];
    if (quoted) {
      if (char === '"') {
        if (source[i + 1] === '"') { field += '"'; i++; }
        else { quoted = false; closed = true; }
      } else field += char;
    } else if (char === ',') finishField();
    else if (char === '\n' || char === '\r') {
      if (char === '\r' && source[i + 1] === '\n') i++;
      finishRecord();
    } else if (closed) throw new Error('Unexpected characters after a closing CSV quote. Check the file format.');
    else if (char === '"') {
      if (started) throw new Error('The CSV contains an unescaped quote.');
      quoted = true; started = true;
    } else { field += char; started = true; }
  }
  if (quoted) throw new Error('The CSV contains an unclosed quote.');
  if (record.length || started || closed || field) finishRecord();
  if (records.length < 2) throw new Error('The CSV needs a header row and at least one data row.');
  const headers = records.shift().map(header => header.trim());
  if (headers.some(header => !header) || new Set(headers).size !== headers.length) {
    throw new Error('CSV column names must be nonempty and unique.');
  }
  for (const [index, row] of records.entries()) {
    if (row.length !== headers.length) throw new Error(`CSV row ${index + 2} has a different number of columns from the header.`);
  }
  return {headers, rows: records};
}

export function makeRequest(text, instructions, categories) {
  if (!text.trim()) throw new Error('This row has no text to classify.');
  if (!instructions.trim()) throw new Error('Enter classification instructions.');
  return {state: text, questions: {category: {type: 'choice', instructions: instructions.trim(), criteria: categories}}};
}

export function readAnswer(data, categories) {
  if (!data || typeof data !== 'object' || !data.answers || Object.keys(data.answers).join() !== 'category') {
    throw new Error('The service returned a response for a different question.');
  }
  const answer = data.answers.category;
  const labels = Object.keys(categories);
  const probabilities = answer?.probabilities;
  if (answer?.type !== 'choice' || !probabilities || Array.isArray(probabilities) ||
      Object.keys(probabilities).length !== labels.length ||
      labels.some(label => !Object.hasOwn(probabilities, label)) || !labels.includes(answer.choice)) {
    throw new Error('The returned categories do not match this task.');
  }
  const values = labels.map(label => probabilities[label]);
  if (values.some(p => typeof p !== 'number' || !Number.isFinite(p) || p < 0 || p > 1) ||
      Math.abs(values.reduce((a, b) => a + b, 0) - 1) > 1e-6 ||
      probabilities[answer.choice] < Math.max(...values) - 1e-12) {
    throw new Error('The service returned invalid probabilities. This result was not accepted.');
  }
  return {label: answer.choice, probability: probabilities[answer.choice], probabilities,
    model: typeof data.model === 'string' ? data.model : ''};
}

function csvCell(value) {
  let text = String(value ?? '');
  // Treat spreadsheet formula prefixes as text, including after whitespace.
  if (/^[\s\uFEFF]*[=+\-@]/.test(text) || /^[\t\r]/.test(text)) text = "'" + text;
  return '"' + text.replaceAll('"', '""') + '"';
}

export function resultsCSV(rows, sourceHeaders = []) {
  if (sourceHeaders.length) {
    const used = new Set(sourceHeaders);
    const columns = ['row', 'category', 'category_probability', 'status', 'error', 'all_probabilities', 'model'].map(key => {
      let name = `open_jev_${key}`;
      while (used.has(name)) name += '_result';
      used.add(name); return name;
    });
    const table = [[...sourceHeaders, ...columns], ...rows.map(row => [...row.original,
      row.index, row.label, row.probability, row.status, row.error,
      row.probabilities ? JSON.stringify(row.probabilities) : '', row.model])];
    return '\uFEFF' + table.map(row => row.map(csvCell).join(',')).join('\r\n') + '\r\n';
  }
  const table = [['row', 'text', 'category', 'category_probability', 'status', 'error', 'all_probabilities', 'model']];
  rows.forEach(row => table.push([row.index, row.text, row.label, row.probability, row.status,
    row.error, row.probabilities ? JSON.stringify(row.probabilities) : '', row.model]));
  return '\uFEFF' + table.map(row => row.map(csvCell).join(',')).join('\r\n') + '\r\n';
}
