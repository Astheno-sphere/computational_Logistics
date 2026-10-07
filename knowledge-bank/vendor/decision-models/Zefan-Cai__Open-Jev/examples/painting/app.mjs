const $ = (id) => document.getElementById(id);
let fixture, controller;
$("endpoint").value = `${location.origin}/v1/systemone`;

function probability(value) {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0 || value > 1) throw Error("Invalid model probability");
  return value;
}
function distribution(answer, keys, type) {
  if (answer?.type !== type || !answer.probabilities || Object.keys(answer.probabilities).length !== keys.length) throw Error("Incomplete distribution");
  const p = keys.map((key) => probability(answer.probabilities[key]));
  if (Math.abs(p.reduce((a, b) => a + b) - 1) > 1e-6) throw Error("Probabilities do not sum to one");
  return p;
}
function hsl(h, s, l) {
  const a = s * Math.min(l, 1-l);
  return [0, 8, 4].map((n) => { const k = (n + h * 12) % 12; return 255 * (l - a * Math.max(-1, Math.min(k-3, 9-k, 1))); });
}
function render(answers, mode, size) {
  const canvas = $("canvas"); canvas.width = canvas.height = size;
  const ctx = canvas.getContext("2d"), data = ctx.createImageData(size, size);
  for (let y=0; y<size; y++) for (let x=0; x<size; x++) {
    const key = `x${x}_y${y}`; let rgb;
    if (mode === "palette") {
      const p = distribution(answers[key], Object.keys(fixture.palette), "choice");
      rgb = [0,1,2].map((c) => Object.values(fixture.palette).reduce((sum, color, i) => sum + p[i] * color[c], 0));
    } else if (mode === "silhouette" || mode === "rgb") {
      const names = mode === "silhouette" ? [key] : ["red", "green", "blue"].map((c) => `${key}_${c}`);
      const p = names.map((name) => { if (answers[name]?.type !== "noul") throw Error("Missing Noul answer"); return probability(answers[name].noul); });
      rgb = mode === "silhouette" ? Array(3).fill(255 * (1-p[0])) : p.map((v) => 255*v);
    } else {
      const hp = distribution(answers[`${key}_hue`], Object.keys(fixture.hues), "choice");
      const sp = distribution(answers[`${key}_saturation`], ["0", "1", "2"], "score");
      const lp = distribution(answers[`${key}_lightness`], ["0", "1", "2", "3", "4"], "score");
      rgb = [0,0,0];
      Object.entries(fixture.hues).forEach(([name, hue], i) => sp.forEach((s, j) => lp.forEach((l, k) => {
        const color = hsl(hue, name === "neutral" ? 0 : j/2, k/4);
        for (let c=0;c<3;c++) rgb[c] += hp[i] * s * l * color[c];
      })));
    }
    data.data.set([...rgb.map(Math.round), 255], (y*size+x)*4);
  }
  ctx.putImageData(data, 0, 0);
}

function requests(prompt, mode, size) {
  // Use the Python-created question templates and replace coordinates only.
  const templates = fixture.templates[mode], questions = {};
  for (let y=0;y<size;y++) for (let x=0;x<size;x++) for (const [key, template] of Object.entries(templates)) {
    questions[key.replace("x0_y0", `x${x}_y${y}`)] = {...template, instructions: template.instructions.replace("pixel x=0, y=0", `pixel x=${x}, y=${y}`)};
  }
  const state = {...fixture.states[mode], image_description: prompt, width: size, height: size};
  const entries = Object.entries(questions), batches = [];
  for (let i=0;i<entries.length;i+=64) batches.push({model: $("model").value.trim(), state, questions: Object.fromEntries(entries.slice(i,i+64))});
  return batches;
}

function busy(value) {
  for (const id of ["run", "reference", "mode", "size"]) $(id).disabled = value;
  $("stop").disabled = !value;
}
$("reference").onclick = () => {
  const mode = $("mode").value;
  $("size").value = String(fixture.size);
  $("prompt").value = fixture.prompt;
  render(fixture.answers[mode], mode, fixture.size);
  $("source").textContent = "PROCEDURAL REFERENCE · NO MODEL";
  $("caption").textContent = fixture.prompt;
  $("status").textContent = "Exact geometry targets loaded. No inference request was made.";
};
$("stop").onclick = () => controller?.abort();
$("run").onclick = async () => {
  busy(true); controller = new AbortController();
  $("source").textContent = "AWAITING MODEL";
  const mode = $("mode").value, size = Number($("size").value), prompt = $("prompt").value.trim();
  const endpoint = $("endpoint").value.trim();
  const start = performance.now();
  try {
    if (!prompt || prompt.length > 8000) throw Error("Enter a description of 1–8,000 characters.");
    const batches = requests(prompt, mode, size), answers = {}, models = new Set();
    for (let i=0;i<batches.length;i++) {
      $("status").textContent = `Model batch ${i+1}/${batches.length}. Waiting for typed probabilities…`;
      const response = await fetch(endpoint, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(batches[i]), signal: controller.signal});
      if (!response.ok) throw Error(`Inference returned HTTP ${response.status}: ${(await response.text()).slice(0,250)}`);
      const body = await response.json();
      if (!body.answers || Object.keys(body.answers).length !== Object.keys(batches[i].questions).length) throw Error("Incomplete model response");
      Object.assign(answers, body.answers); models.add(body.model || "unspecified");
    }
    render(answers, mode, size);
    $("source").textContent = "MODEL PREDICTION";
    $("caption").textContent = prompt;
    $("status").textContent = `${size}×${size} ${mode} · ${((performance.now()-start)/1000).toFixed(1)} s end to end\nModel: ${[...models].join(", ")}`;
  } catch (error) {
    $("source").textContent = "NO NEW MODEL RESULT";
    $("status").textContent = error.name === "AbortError" ? "Request stopped. The server may finish an already-started batch." : error.message;
  } finally { busy(false); controller = null; }
};
busy(true);
try {
  const response = await fetch("reference.json");
  if (!response.ok) throw Error("Unable to load example definitions");
  fixture = await response.json();
  busy(false);
} catch (error) { $("status").textContent = `${error.message}. Serve this page over HTTP.`; busy(true); }
