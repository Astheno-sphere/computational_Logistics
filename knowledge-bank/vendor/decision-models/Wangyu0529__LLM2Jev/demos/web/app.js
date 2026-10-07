"use strict";

const questionsElement = document.querySelector("#questions");
const template = document.querySelector("#question-template");
const submitButton = document.querySelector("#submit-button");
const validationMessage = document.querySelector("#validation-message");
const connectionStatus = document.querySelector("#connection-status");
let nextQuestionNumber = 1;

const defaults = {
  choice: {
    id: "department",
    instructions: "这个请求应该交给哪个部门处理？",
    criteria: [["billing", "付款、账单或退款问题"], ["shipping", "物流、配送或包裹丢失问题"], ["technical", "产品故障或技术支持问题"]],
  },
  score: {
    id: "urgency",
    instructions: "评估这个客户请求的紧急程度。",
    criteria: [["", "不紧急"], ["", "比较紧急"], ["", "非常紧急"]],
  },
  noul: {
    id: "is_delivery_issue",
    instructions: "这是否是一个物流配送问题？",
    criteria: [],
  },
};

function input(value, className, placeholder) {
  const element = document.createElement("input");
  element.className = className;
  element.value = value;
  element.placeholder = placeholder;
  return element;
}

function removeButton(label, onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "remove-row";
  button.textContent = "×";
  button.title = label;
  button.setAttribute("aria-label", label);
  button.addEventListener("click", onClick);
  return button;
}

function addCriteriaRow(container, type, key = "", description = "") {
  const row = document.createElement("div");
  row.className = `criteria-row${type === "score" ? " level-row" : ""}`;
  if (type === "choice") {
    row.append(input(key, "criterion-key", "选项名"));
  } else {
    const number = document.createElement("span");
    number.className = "level-number";
    row.append(number);
  }
  row.append(input(description, "criterion-description", type === "score" ? "等级说明" : "选项说明"));
  row.append(removeButton("删除条件", () => {
    row.remove();
    renumberLevels(container);
  }));
  container.append(row);
  renumberLevels(container);
}

function renumberLevels(container) {
  container.querySelectorAll(".level-number").forEach((element, index) => {
    element.textContent = String(index);
  });
}

function renderCriteria(card, type, values) {
  const block = card.querySelector(".criteria-block");
  if (type === "noul") {
    const label = document.createElement("label");
    label.className = "noul-toggle";
    const toggle = document.createElement("input");
    toggle.type = "checkbox";
    label.append(toggle, document.createTextNode("定义 true / false 条件"));
    const rows = document.createElement("div");
    rows.className = "criteria-rows noul-criteria";
    rows.hidden = true;
    [["true", "符合条件"], ["false", "不符合条件"]].forEach(([key, placeholder]) => {
      const row = document.createElement("div");
      row.className = "criteria-row";
      const keyInput = input(key, "criterion-key", "");
      keyInput.readOnly = true;
      row.append(keyInput, input("", "criterion-description", placeholder), document.createElement("span"));
      rows.append(row);
    });
    toggle.addEventListener("change", () => { rows.hidden = !toggle.checked; });
    block.append(label, rows);
    return;
  }

  const heading = document.createElement("div");
  heading.className = "criteria-label";
  heading.textContent = type === "choice" ? "选项" : "等级（从低到高）";
  const rows = document.createElement("div");
  rows.className = "criteria-rows";
  values.forEach(([key, description]) => addCriteriaRow(rows, type, key, description));
  const add = document.createElement("button");
  add.type = "button";
  add.className = "add-row";
  add.textContent = type === "choice" ? "+ 添加选项" : "+ 添加等级";
  add.addEventListener("click", () => addCriteriaRow(rows, type));
  block.append(heading, rows, add);
}

function addQuestion(type, values = defaults[type]) {
  const card = template.content.firstElementChild.cloneNode(true);
  card.dataset.type = type;
  card.querySelector(".question-number").textContent = String(nextQuestionNumber).padStart(2, "0");
  card.querySelector(".type-badge").textContent = type;
  card.querySelector(".question-id").value = values.id;
  card.querySelector(".question-instructions").value = values.instructions;
  card.querySelector(".remove-question").addEventListener("click", () => {
    card.remove();
    renumberQuestions();
  });
  renderCriteria(card, type, values.criteria);
  questionsElement.append(card);
  nextQuestionNumber += 1;
}

function renumberQuestions() {
  questionsElement.querySelectorAll(".question-card").forEach((card, index) => {
    card.querySelector(".question-number").textContent = String(index + 1).padStart(2, "0");
  });
  nextQuestionNumber = questionsElement.children.length + 1;
}

function parseState(value) {
  const trimmed = value.trim();
  if (!trimmed) throw new Error("State 不能为空");
  if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
    try { return JSON.parse(trimmed); } catch { throw new Error("State 看起来是 JSON，但格式无效"); }
  }
  return value;
}

function collectRequest() {
  const model = document.querySelector("#model").value.trim();
  if (!model) throw new Error("模型不能为空");
  const cards = [...questionsElement.querySelectorAll(".question-card")];
  if (!cards.length) throw new Error("请至少添加一个问题");
  const questions = {};

  cards.forEach((card) => {
    const type = card.dataset.type;
    const id = card.querySelector(".question-id").value.trim();
    const instructions = card.querySelector(".question-instructions").value.trim();
    if (!id) throw new Error("问题 ID 不能为空");
    if (Object.hasOwn(questions, id)) throw new Error(`问题 ID “${id}” 重复`);
    if (!instructions) throw new Error(`问题 “${id}” 的 instructions 不能为空`);
    const question = {type, instructions};

    if (type === "choice") {
      question.criteria = {};
      card.querySelectorAll(".criteria-row").forEach((row) => {
        const key = row.querySelector(".criterion-key").value.trim();
        const description = row.querySelector(".criterion-description").value.trim();
        if (!key) throw new Error(`Choice “${id}” 存在空选项名`);
        if (Object.hasOwn(question.criteria, key)) throw new Error(`Choice “${id}” 的选项 “${key}” 重复`);
        question.criteria[key] = description || null;
      });
      if (Object.keys(question.criteria).length < 2) throw new Error(`Choice “${id}” 至少需要两个选项`);
    } else if (type === "score") {
      question.criteria = [...card.querySelectorAll(".criterion-description")].map((element) => element.value.trim());
      if (question.criteria.length < 2) throw new Error(`Score “${id}” 至少需要两个等级`);
      if (question.criteria.some((value) => !value)) throw new Error(`Score “${id}” 的等级说明不能为空`);
    } else {
      const toggle = card.querySelector(".noul-toggle input");
      if (toggle.checked) {
        question.criteria = {};
        card.querySelectorAll(".criteria-row").forEach((row) => {
          const key = row.querySelector(".criterion-key").value;
          const description = row.querySelector(".criterion-description").value.trim();
          question.criteria[key] = description || null;
        });
      }
    }
    questions[id] = question;
  });
  return {state: parseState(document.querySelector("#state").value), model, questions};
}

function probabilityRows(probabilities, selected) {
  const container = document.createElement("div");
  container.className = "probabilities";
  Object.entries(probabilities).forEach(([label, probability]) => {
    const row = document.createElement("div");
    row.className = `probability-row${String(label) === String(selected) ? " is-selected" : ""}`;
    const text = document.createElement("div");
    text.className = "probability-label";
    const name = document.createElement("span");
    name.textContent = label;
    const value = document.createElement("span");
    value.textContent = `${(probability * 100).toFixed(1)}%`;
    text.append(name, value);
    const track = document.createElement("div");
    track.className = "probability-track";
    const fill = document.createElement("div");
    fill.className = "probability-fill";
    fill.style.width = `${Math.max(0, Math.min(100, probability * 100))}%`;
    track.append(fill);
    row.append(text, track);
    container.append(row);
  });
  return container;
}

function renderResults(response, elapsed) {
  const list = document.querySelector("#answer-list");
  list.replaceChildren();
  Object.entries(response.answers || {}).forEach(([id, answer]) => {
    const card = document.createElement("article");
    card.className = "answer-card";
    const title = document.createElement("div");
    title.className = "answer-title";
    const titleText = document.createElement("div");
    const name = document.createElement("h3");
    name.textContent = id;
    const type = document.createElement("span");
    type.className = "answer-type";
    type.textContent = answer.type;
    titleText.append(name, type);
    const value = document.createElement("span");
    value.className = "answer-value";
    const selected = answer.type === "choice" ? answer.choice : answer.type === "score" ? answer.score.toFixed(2) : answer.noul;
    value.textContent = answer.type === "noul" ? `${(answer.noul * 100).toFixed(1)}%` : selected;
    title.append(titleText, value);
    card.append(title);
    if (answer.confidence !== undefined) {
      const meta = document.createElement("div");
      meta.className = "answer-meta";
      meta.textContent = `Confidence ${(answer.confidence * 100).toFixed(1)}%`;
      card.append(meta);
    }
    if (answer.probabilities) {
      card.append(probabilityRows(answer.probabilities, answer.type === "choice" ? answer.choice : Math.round(answer.score)));
    } else if (answer.type === "noul") {
      card.append(probabilityRows({true: answer.noul, false: 1 - answer.noul}, answer.noul >= .5 ? "true" : "false"));
    }
    list.append(card);
  });
  document.querySelector("#result-empty").hidden = true;
  list.hidden = false;
  document.querySelector("#raw-panel").hidden = false;
  document.querySelector("#raw-json").textContent = JSON.stringify(response, null, 2);
  const usage = response.usage || {};
  const tokens = usage.input_tokens == null ? "" : ` · ${usage.input_tokens} tokens`;
  document.querySelector("#latency").textContent = `${elapsed} ms${tokens}`;
}

async function submit() {
  validationMessage.textContent = "";
  let payload;
  try { payload = collectRequest(); } catch (error) {
    validationMessage.textContent = error.message;
    return;
  }
  submitButton.disabled = true;
  submitButton.classList.add("is-loading");
  const started = performance.now();
  try {
    const response = await fetch("/api/systemone", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({detail: `HTTP ${response.status}`}));
    if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail));
    renderResults(data, Math.round(performance.now() - started));
  } catch (error) {
    validationMessage.textContent = error.message;
  } finally {
    submitButton.disabled = false;
    submitButton.classList.remove("is-loading");
  }
}

async function loadModels() {
  try {
    const response = await fetch("/api/models");
    if (!response.ok) throw new Error();
    const payload = await response.json();
    const models = Array.isArray(payload.data) ? payload.data.map((item) => item.id).filter(Boolean) : [];
    const datalist = document.querySelector("#model-options");
    models.forEach((model) => {
      const option = document.createElement("option");
      option.value = model;
      datalist.append(option);
    });
    if (models.length) document.querySelector("#model").value = models[0];
    connectionStatus.textContent = "服务已连接";
    connectionStatus.dataset.tone = "ok";
  } catch {
    connectionStatus.textContent = "服务未连接";
    connectionStatus.dataset.tone = "error";
  }
}

function reset() {
  questionsElement.replaceChildren();
  nextQuestionNumber = 1;
  ["noul", "choice", "score"].forEach((type) => addQuestion(type));
  validationMessage.textContent = "";
}

document.querySelectorAll("[data-add-type]").forEach((button) => {
  button.addEventListener("click", () => addQuestion(button.dataset.addType));
});
document.querySelector("#reset-button").addEventListener("click", reset);
submitButton.addEventListener("click", submit);
reset();
loadModels();
